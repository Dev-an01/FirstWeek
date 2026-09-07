"""
Profile ID Validation Helper

Provides utilities for validating and normalizing profile IDs
across the RAG system.

Supports both static profile IDs (filesystem) and dynamic profile IDs (database).

Author: AI Officer Team
Date: 2025-11-10
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict, Set

logger = logging.getLogger(__name__)


# Cache for dynamically loaded profile IDs from ProfileManager
_dynamic_profile_ids: Set[str] = set()


def register_dynamic_profile_ids(profile_ids: Set[str]):
    """
    Register profile IDs loaded from database or other dynamic sources.

    Called by ProfileManager after loading database profiles.

    Args:
        profile_ids: Set of profile IDs to register
    """
    global _dynamic_profile_ids
    _dynamic_profile_ids = profile_ids
    logger.info(f"Registered {len(profile_ids)} dynamic profile IDs: {profile_ids}")


def get_all_valid_profile_ids() -> Set[str]:
    """
    Get all valid profile IDs (static + dynamic).

    Returns:
        Set of all valid profile IDs
    """
    return ProfileIDValidator.VALID_PROFILE_IDS | _dynamic_profile_ids


class ProfileIDValidator:
    """Validates and normalizes profile IDs"""

    # Official profile IDs (filesystem-based)
    VALID_PROFILE_IDS = {
        'exec_001_test',  # Akiko Tanaka (CEO)
        'exec_002_test',  # Raj Patel (CFO)
        'exec_003_test',  # Yuki Nakamura (CTO)
        'exec_004_test',  # Sarah Kim (CMO)
        'sample_profile',  # Sample Executive (FIRSTWEEK CEO)
    }

    # Legacy ID mapping for backwards compatibility
    LEGACY_ID_MAPPING = {
        'akiko_tanaka': 'exec_001_test',
        'tanaka': 'exec_001_test',
        'raj_patel': 'exec_002_test',
        'yuki_nakamura': 'exec_003_test',
        'sarah_kim': 'exec_004_test',
        'sample': 'sample_profile',
        'sample': 'sample_profile',
    }

    @classmethod
    def validate(cls, profile_id: str) -> bool:
        """
        Check if profile ID is valid (current, legacy, or database)

        Args:
            profile_id: Profile ID to validate

        Returns:
            True if valid (current, legacy, or database), False otherwise
        """
        if not profile_id:
            return False

        # Check if current ID (static)
        if profile_id in cls.VALID_PROFILE_IDS:
            return True

        # Check if legacy ID
        if profile_id in cls.LEGACY_ID_MAPPING:
            logger.warning(
                f"Legacy profile ID used: {profile_id} "
                f"(maps to {cls.LEGACY_ID_MAPPING[profile_id]})"
            )
            return True

        # Check if dynamic (database) profile ID
        if profile_id in _dynamic_profile_ids:
            return True

        return False
    
    @classmethod
    def normalize(cls, profile_id: str) -> Optional[str]:
        """
        Normalize profile ID (convert legacy to current)

        Args:
            profile_id: Profile ID to normalize

        Returns:
            Normalized profile ID or None if invalid
        """
        if not profile_id:
            return None

        # Already current ID (static)
        if profile_id in cls.VALID_PROFILE_IDS:
            return profile_id

        # Convert legacy ID
        if profile_id in cls.LEGACY_ID_MAPPING:
            normalized = cls.LEGACY_ID_MAPPING[profile_id]
            logger.info(f"Normalized {profile_id} → {normalized}")
            return normalized

        # Dynamic (database) profile ID - return as-is
        if profile_id in _dynamic_profile_ids:
            return profile_id

        # Unknown ID - still return it (might be a new database profile not yet registered)
        # The ProfileManager will validate it exists
        logger.debug(f"Profile ID '{profile_id}' not in static list, passing through")
        return profile_id
    
    @classmethod
    def get_profile_name(cls, profile_id: str) -> Optional[str]:
        """
        Get executive name from profile ID
        
        Args:
            profile_id: Profile ID
            
        Returns:
            Executive name or None
        """
        name_mapping = {
            'exec_001_test': 'Akiko Tanaka (田中明子)',
            'exec_002_test': 'Raj Patel',
            'exec_003_test': 'Yuki Nakamura (中村ユキ)',
            'exec_004_test': 'Sarah Kim',
        }
        
        normalized_id = cls.normalize(profile_id)
        return name_mapping.get(normalized_id)
    
    @classmethod
    def get_all_profile_ids(cls) -> Dict[str, str]:
        """
        Get all valid profile IDs with names
        
        Returns:
            Dict mapping profile IDs to names
        """
        return {
            'exec_001_test': 'Akiko Tanaka (田中明子)',
            'exec_002_test': 'Raj Patel',
            'exec_003_test': 'Yuki Nakamura (中村ユキ)',
            'exec_004_test': 'Sarah Kim',
        }


# Convenience functions
def validate_profile_id(profile_id: str) -> bool:
    """Validate profile ID (current or legacy)"""
    return ProfileIDValidator.validate(profile_id)


def normalize_profile_id(profile_id: str) -> Optional[str]:
    """Normalize profile ID (convert legacy to current)"""
    return ProfileIDValidator.normalize(profile_id)


def get_profile_name(profile_id: str) -> Optional[str]:
    """Get executive name from profile ID"""
    return ProfileIDValidator.get_profile_name(profile_id)


__all__ = [
    'ProfileIDValidator',
    'validate_profile_id',
    'normalize_profile_id',
    'get_profile_name'
]
