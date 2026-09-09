"""
Profile ID Mapper
Week 2, Day 5: Fix profile ID mapping issues

Maps friendly names to database IDs for backward compatibility.
Supports dynamic registration of new profiles from the database.
"""

import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class ProfileIDMapper:
    """
    Maps friendly profile names to database IDs

    Problem: Tests and legacy code use friendly names like "akiko_tanaka"
    Solution: Database uses formal IDs like "exec_001_test"

    This mapper provides bidirectional translation.
    Supports dynamic profiles registered at runtime via refresh_from_db().
    """

    # Dynamic registry populated at runtime from the database
    _dynamic_registry: Dict[str, str] = {}  # id -> id (identity mapping for dynamic profiles)
    _dynamic_display_names: Dict[str, str] = {}  # id -> display name

    # Only database-registered profiles are available.
    FRIENDLY_TO_DB = {}
    DB_TO_FRIENDLY = {}
    DISPLAY_NAMES = {}

    @classmethod
    async def refresh_from_db(cls, pool, company_id: str = None) -> int:
        """
        Refresh the dynamic registry from the executive_profiles database table.

        Queries all executives with profile_data and registers them so they
        can be resolved by to_database_id() without defaulting to sample.

        Args:
            pool: asyncpg connection pool.
            company_id: Optional company filter for tenant-scoped loading.

        Returns:
            Number of profiles registered.
        """
        try:
            if company_id:
                rows = await pool.fetch(
                    "SELECT id, name, title FROM executive_profiles WHERE profile_data IS NOT NULL AND company_id = $1",
                    company_id,
                )
            else:
                rows = await pool.fetch(
                    "SELECT id, name, title FROM executive_profiles WHERE profile_data IS NOT NULL"
                )
            cls._dynamic_registry.clear()
            cls._dynamic_display_names.clear()
            for row in rows:
                exec_id = row["id"]
                cls._dynamic_registry[exec_id] = exec_id
                display = row.get("name") or exec_id
                if row.get("title"):
                    display = f"{display} ({row['title']})"
                cls._dynamic_display_names[exec_id] = display
                # Also add to DB_TO_FRIENDLY for reverse lookups
                cls.DB_TO_FRIENDLY[exec_id] = exec_id
                cls.DISPLAY_NAMES[exec_id] = display

            logger.info(f"Dynamic profile registry refreshed: {len(rows)} profiles")
            return len(rows)
        except Exception as e:
            logger.error(f"Failed to refresh dynamic profile registry: {e}")
            return 0

    @classmethod
    def to_database_id(cls, profile_id: str) -> str:
        """
        Convert friendly name to database ID

        Args:
            profile_id: Friendly name or database ID

        Returns:
            Database ID (passed through as-is for onboarding executives)

        Examples:
            >>> ProfileIDMapper.to_database_id("workspace_profile")
            'workspace_profile'
        """
        if not profile_id:
            raise ValueError("An explicit profile ID is required")

        # Check dynamic registry first (onboarded executives)
        if profile_id in cls._dynamic_registry:
            return cls._dynamic_registry[profile_id]

        # Already the active database ID
        if profile_id in cls.DB_TO_FRIENDLY:
            return profile_id

        # Check explicitly registered friendly names.
        db_id = cls.FRIENDLY_TO_DB.get(profile_id.lower())
        if db_id:
            if profile_id != db_id:
                logger.debug(f"Mapped '{profile_id}' → database ID '{db_id}'")
            return db_id

        # Unknown ID — pass through as-is (likely an onboarding executive)
        # The downstream ProfileManager will handle DB lookup and validation
        logger.info(f"Profile ID '{profile_id}' not in registry, passing through as-is")
        return profile_id
    
    @classmethod
    def to_friendly_name(cls, db_id: str) -> str:
        """
        Convert database ID to friendly name
        
        Args:
            db_id: Database ID (exec_XXX_test format)
            
        Returns:
            Friendly name
            
        Examples:
            >>> ProfileIDMapper.to_friendly_name("exec_001_test")
            "akiko_tanaka"
        """
        return cls.DB_TO_FRIENDLY.get(db_id, db_id)
    
    @classmethod
    def to_display_name(cls, profile_id: str) -> str:
        """
        Get display name (English full name)
        
        Args:
            profile_id: Database ID or friendly name
            
        Returns:
            Display name (e.g., "Akiko Tanaka")
        """
        db_id = cls.to_database_id(profile_id)
        return cls.DISPLAY_NAMES.get(db_id, profile_id)
    
    @classmethod
    def get_all_profiles(cls) -> Dict[str, Dict[str, str]]:
        """
        Get all profile mappings (static + dynamically registered).

        Returns:
            Dictionary of profile information
        """
        profiles = {}
        # Static profiles
        for db_id in cls.DB_TO_FRIENDLY.keys():
            profiles[db_id] = {
                "database_id": db_id,
                "friendly_name": cls.to_friendly_name(db_id),
                "display_name": cls.to_display_name(db_id),
            }
        # Dynamic profiles (may overlap with static, dynamic wins)
        for db_id in cls._dynamic_registry.keys():
            profiles[db_id] = {
                "database_id": db_id,
                "friendly_name": db_id,
                "display_name": cls._dynamic_display_names.get(db_id, db_id),
            }
        return profiles

    @classmethod
    def is_valid_profile_id(cls, profile_id: str) -> bool:
        """
        Check if a profile ID is valid (database ID, friendly name, or dynamic).

        Args:
            profile_id: Profile ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not profile_id:
            return False

        # Check dynamic registry
        if profile_id in cls._dynamic_registry:
            return True

        # Check if it's a database ID
        if profile_id in cls.DB_TO_FRIENDLY:
            return True

        # Check if it's a friendly name
        if profile_id.lower() in cls.FRIENDLY_TO_DB:
            return True

        return False


def normalize_profile_id(profile_id: Optional[str]) -> str:
    """
    Convenience function to normalize profile ID

    Args:
        profile_id: Profile ID (friendly name or database ID)

    Returns:
        Database ID
    """
    return ProfileIDMapper.to_database_id(profile_id)
