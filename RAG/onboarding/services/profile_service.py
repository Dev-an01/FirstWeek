"""
Profile Service - Business logic for profile and voiceprint editing.

Supports dot notation for nested key updates and JSONB merge operations.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Tuple
import asyncpg

logger = logging.getLogger(__name__)


def _set_nested_value(data: dict, path: str, value: Any) -> None:
    """
    Set a value in a nested dict using dot notation.

    Args:
        data: Dict to modify.
        path: Dot-separated path (e.g., "communication_style.formality_scale").
        value: Value to set.
    """
    keys = path.split(".")
    current = data

    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        elif not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]

    current[keys[-1]] = value


def _get_top_level_keys(sections: Dict[str, Any]) -> List[str]:
    """
    Extract top-level section names from a sections dict.

    For "communication_style.formality_scale", returns "communication_style".
    """
    top_keys = set()
    for key in sections.keys():
        top_key = key.split(".")[0]
        top_keys.add(top_key)
    return list(top_keys)


def merge_updates(existing: dict, updates: Dict[str, Any]) -> Tuple[dict, List[str]]:
    """
    Merge updates into existing data using dot notation support.

    Args:
        existing: Current profile/voiceprint data.
        updates: Dict of section updates (keys can use dot notation).

    Returns:
        Tuple of (merged data, list of updated top-level sections).
    """
    result = existing.copy() if existing else {}
    updated_sections = []

    for path, value in updates.items():
        if "." in path:
            # Dot notation - update nested field
            _set_nested_value(result, path, value)
        else:
            # Direct key - replace entire section
            result[path] = value

        # Track top-level section
        top_key = path.split(".")[0]
        if top_key not in updated_sections:
            updated_sections.append(top_key)

    return result, updated_sections


class ProfileService:
    """Service for managing executive profiles and voiceprints."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def get_profile(
        self,
        company_id: str,
        executive_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get executive profile data.

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            Profile dict or None.
        """
        row = await self.pool.fetchrow(
            """
            SELECT profile_data
            FROM executive_profiles
            WHERE id = $1 AND company_id = $2
            """,
            executive_id,
            company_id,
        )
        if not row or not row["profile_data"]:
            return None

        data = row["profile_data"]
        if isinstance(data, str):
            return json.loads(data)
        return data

    async def get_voiceprint(
        self,
        company_id: str,
        executive_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get executive voiceprint data.

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            Voiceprint dict or None.
        """
        row = await self.pool.fetchrow(
            """
            SELECT voiceprint_data
            FROM executive_profiles
            WHERE id = $1 AND company_id = $2
            """,
            executive_id,
            company_id,
        )
        if not row or not row["voiceprint_data"]:
            return None

        data = row["voiceprint_data"]
        if isinstance(data, str):
            return json.loads(data)
        return data

    async def get_profile_with_voiceprint(
        self,
        company_id: str,
        executive_id: str,
    ) -> Dict[str, Any]:
        """
        Get both profile and voiceprint data.

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            Dict with 'profile' and 'voiceprint' keys.
        """
        row = await self.pool.fetchrow(
            """
            SELECT profile_data, voiceprint_data
            FROM executive_profiles
            WHERE id = $1 AND company_id = $2
            """,
            executive_id,
            company_id,
        )

        result = {"profile": None, "voiceprint": None}

        if row:
            if row["profile_data"]:
                data = row["profile_data"]
                result["profile"] = json.loads(data) if isinstance(data, str) else data

            if row["voiceprint_data"]:
                data = row["voiceprint_data"]
                result["voiceprint"] = json.loads(data) if isinstance(data, str) else data

        return result

    async def update_profile(
        self,
        company_id: str,
        executive_id: str,
        sections: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Update profile sections using JSONB merge.

        Supports dot notation for nested keys:
        - "core_values": [...] replaces entire section
        - "communication_style.formality_scale": 7 updates nested field

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.
            sections: Dict of section updates.

        Returns:
            Tuple of (success, list of updated section names).
        """
        # Get existing profile
        existing = await self.get_profile(company_id, executive_id)
        if existing is None:
            existing = {}

        # Merge updates
        merged, updated_sections = merge_updates(existing, sections)

        # Update in database - pass dict directly, asyncpg's jsonb codec handles serialization
        await self.pool.execute(
            """
            UPDATE executive_profiles
            SET profile_data = $3, updated_at = NOW()
            WHERE id = $1 AND company_id = $2
            """,
            executive_id,
            company_id,
            merged,
        )

        logger.info(
            f"Updated profile for {company_id}/{executive_id}, sections: {updated_sections}"
        )
        return True, updated_sections

    async def update_voiceprint(
        self,
        company_id: str,
        executive_id: str,
        sections: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """
        Update voiceprint sections using JSONB merge.

        Supports dot notation for nested keys:
        - "casual_responses.greetings": ["Hi!", "Hello!"]
        - "style_markers.formality": 8

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.
            sections: Dict of section updates.

        Returns:
            Tuple of (success, list of updated section names).
        """
        # Get existing voiceprint
        existing = await self.get_voiceprint(company_id, executive_id)
        if existing is None:
            existing = {}

        # Merge updates
        merged, updated_sections = merge_updates(existing, sections)

        # Update in database - pass dict directly, asyncpg's jsonb codec handles serialization
        await self.pool.execute(
            """
            UPDATE executive_profiles
            SET voiceprint_data = $3, updated_at = NOW()
            WHERE id = $1 AND company_id = $2
            """,
            executive_id,
            company_id,
            merged,
        )

        logger.info(
            f"Updated voiceprint for {company_id}/{executive_id}, sections: {updated_sections}"
        )
        return True, updated_sections

    async def get_validation_report(
        self,
        company_id: str,
        executive_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent validation report for an executive.

        Args:
            company_id: Company ID for tenant isolation.
            executive_id: Executive ID.

        Returns:
            Validation report dict or None.
        """
        row = await self.pool.fetchrow(
            """
            SELECT validation_report
            FROM onboarding_jobs
            WHERE company_id = $1 AND executive_id = $2
                AND validation_report IS NOT NULL
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            company_id,
            executive_id,
        )

        if not row or not row["validation_report"]:
            return None

        data = row["validation_report"]
        if isinstance(data, str):
            return json.loads(data)
        return data
