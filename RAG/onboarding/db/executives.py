"""
Executive CRUD operations with hierarchy support.
"""

import logging
import json
from typing import Optional, Dict, Any, List
import asyncpg

logger = logging.getLogger(__name__)


async def create_executive(pool: asyncpg.Pool, data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert or update an executive profile stub (no profile_data yet)."""
    row = await pool.fetchrow(
        """
        INSERT INTO executive_profiles (id, name, name_english, title, department, company_id, email, reports_to, hierarchy_level, sort_order)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            name_english = COALESCE(EXCLUDED.name_english, executive_profiles.name_english),
            title = COALESCE(EXCLUDED.title, executive_profiles.title),
            department = COALESCE(EXCLUDED.department, executive_profiles.department),
            company_id = COALESCE(EXCLUDED.company_id, executive_profiles.company_id),
            email = COALESCE(EXCLUDED.email, executive_profiles.email),
            reports_to = COALESCE(EXCLUDED.reports_to, executive_profiles.reports_to),
            hierarchy_level = COALESCE(EXCLUDED.hierarchy_level, executive_profiles.hierarchy_level),
            sort_order = COALESCE(EXCLUDED.sort_order, executive_profiles.sort_order)
        RETURNING id, name, name_english, title, department, company_id, email,
                  profile_data IS NOT NULL AS has_profile,
                  voiceprint_data IS NOT NULL AS has_voiceprint,
                  voice_keys IS NOT NULL AS has_voice_keys,
                  reports_to, hierarchy_level, sort_order
        """,
        data["id"],
        data["name"],
        data.get("name_english"),
        data.get("title"),
        data.get("department"),
        data["company_id"],
        data.get("email"),
        data.get("reports_to"),
        data.get("hierarchy_level", 0),
        data.get("sort_order", 0),
    )
    return dict(row) if row else {}


async def get_executive(pool: asyncpg.Pool, executive_id: str) -> Optional[Dict[str, Any]]:
    """Get an executive by ID."""
    row = await pool.fetchrow(
        """
        SELECT id, name, name_english, title, department, company_id, email,
               profile_data IS NOT NULL AS has_profile,
               voiceprint_data IS NOT NULL AS has_voiceprint,
               voice_keys IS NOT NULL AS has_voice_keys,
               reports_to, hierarchy_level, sort_order
        FROM executive_profiles
        WHERE id = $1
        """,
        executive_id,
    )
    return dict(row) if row else None


async def get_executive_with_data(
    pool: asyncpg.Pool,
    executive_id: str,
    company_id: str,
    include_profile: bool = False,
    include_voiceprint: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Get an executive with optional profile and voiceprint data.

    Args:
        pool: Database connection pool.
        executive_id: Executive ID.
        company_id: Company ID for tenant isolation.
        include_profile: Include profile_data in response.
        include_voiceprint: Include voiceprint_data in response.

    Returns:
        Executive dict or None.
    """
    select_fields = """
        id, name, name_english, title, department, company_id, email,
        profile_data IS NOT NULL AS has_profile,
        voiceprint_data IS NOT NULL AS has_voiceprint,
        voice_keys IS NOT NULL AS has_voice_keys,
        reports_to, hierarchy_level, sort_order,
        (SELECT COUNT(*) FROM embeddings e WHERE e.executive_id = executive_profiles.id AND e.company_id = executive_profiles.company_id) AS embeddings_count
    """

    if include_profile:
        select_fields += ", profile_data"
    if include_voiceprint:
        select_fields += ", voiceprint_data"

    row = await pool.fetchrow(
        f"""
        SELECT {select_fields}
        FROM executive_profiles
        WHERE id = $1 AND company_id = $2
        """,
        executive_id,
        company_id,
    )

    if not row:
        return None

    result = dict(row)

    # Parse JSON fields if present
    if include_profile and result.get("profile_data"):
        data = result["profile_data"]
        result["profile_data"] = json.loads(data) if isinstance(data, str) else data

    if include_voiceprint and result.get("voiceprint_data"):
        data = result["voiceprint_data"]
        result["voiceprint_data"] = json.loads(data) if isinstance(data, str) else data

    return result


async def update_executive(
    pool: asyncpg.Pool,
    executive_id: str,
    company_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Update executive basic info.

    Args:
        pool: Database connection pool.
        executive_id: Executive ID.
        company_id: Company ID for tenant isolation.
        updates: Dict of fields to update.

    Returns:
        Updated executive dict or None if not found.
    """
    # Build dynamic SET clause
    set_parts = []
    params = [executive_id, company_id]
    param_idx = 3

    field_map = {
        "name": "name",
        "name_english": "name_english",
        "title": "title",
        "department": "department",
        "email": "email",
        "reports_to": "reports_to",
        "hierarchy_level": "hierarchy_level",
        "sort_order": "sort_order",
    }

    for key, value in updates.items():
        if key in field_map and value is not None:
            set_parts.append(f"{field_map[key]} = ${param_idx}")
            params.append(value)
            param_idx += 1

    if not set_parts:
        # No valid updates
        return await get_executive(pool, executive_id)

    set_clause = ", ".join(set_parts)
    row = await pool.fetchrow(
        f"""
        UPDATE executive_profiles
        SET {set_clause}, updated_at = NOW()
        WHERE id = $1 AND company_id = $2
        RETURNING id, name, name_english, title, department, company_id, email,
                  profile_data IS NOT NULL AS has_profile,
                  voiceprint_data IS NOT NULL AS has_voiceprint,
                  voice_keys IS NOT NULL AS has_voice_keys,
                  reports_to, hierarchy_level, sort_order
        """,
        *params,
    )
    return dict(row) if row else None


async def get_direct_reports(
    pool: asyncpg.Pool,
    executive_id: str,
    company_id: str,
) -> List[str]:
    """
    Get list of executive IDs that report to this executive.

    Args:
        pool: Database connection pool.
        executive_id: Executive ID.
        company_id: Company ID for tenant isolation.

    Returns:
        List of executive IDs.
    """
    rows = await pool.fetch(
        """
        SELECT id FROM executive_profiles
        WHERE company_id = $1 AND reports_to = $2
        ORDER BY sort_order, name
        """,
        company_id,
        executive_id,
    )
    return [r["id"] for r in rows]


async def soft_delete_executive(
    pool: asyncpg.Pool,
    executive_id: str,
    company_id: str,
) -> bool:
    """
    Soft delete an executive (set profile_data and voiceprint_data to NULL).

    Note: This doesn't actually delete the row, just clears the data.
    For true soft delete, you'd add an is_active column.

    Args:
        pool: Database connection pool.
        executive_id: Executive ID.
        company_id: Company ID for tenant isolation.

    Returns:
        True if executive was found and soft-deleted.
    """
    result = await pool.execute(
        """
        UPDATE executive_profiles
        SET profile_data = NULL, voiceprint_data = NULL, updated_at = NOW()
        WHERE id = $1 AND company_id = $2
        """,
        executive_id,
        company_id,
    )
    return result == "UPDATE 1"


async def get_voice_keys(pool: asyncpg.Pool, executive_id: str, company_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get voice cloning keys for an executive, optionally scoped by company."""
    if company_id:
        row = await pool.fetchrow(
            "SELECT voice_keys FROM executive_profiles WHERE id = $1 AND company_id = $2",
            executive_id,
            company_id,
        )
    else:
        row = await pool.fetchrow(
            "SELECT voice_keys FROM executive_profiles WHERE id = $1",
            executive_id,
        )
    if not row or not row["voice_keys"]:
        return None
    data = row["voice_keys"]
    return json.loads(data) if isinstance(data, str) else data


async def update_voice_keys(
    pool: asyncpg.Pool,
    executive_id: str,
    company_id: str,
    voice_keys: Dict[str, Any],
) -> bool:
    """Update voice cloning keys for an executive (merges with existing)."""
    result = await pool.execute(
        """
        UPDATE executive_profiles
        SET voice_keys = $3::jsonb, updated_at = NOW()
        WHERE id = $1 AND company_id = $2
        """,
        executive_id,
        company_id,
        json.dumps(voice_keys),
    )
    return result == "UPDATE 1"
