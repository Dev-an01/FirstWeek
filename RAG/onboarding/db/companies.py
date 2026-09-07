"""
Company CRUD operations with hierarchy support.
"""

import logging
import json
from typing import Optional, List, Dict, Any
import asyncpg
from collections import defaultdict

logger = logging.getLogger(__name__)


async def create_company(pool: asyncpg.Pool, data: Dict[str, Any]) -> Dict[str, Any]:
    """Insert a new company."""
    # Pass dict directly - asyncpg's jsonb codec handles serialization
    row = await pool.fetchrow(
        """
        INSERT INTO companies (id, name, industry, description, metadata)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, name, industry, description, metadata, created_at, updated_at
        """,
        data["id"],
        data["name"],
        data.get("industry"),
        data.get("description"),
        data.get("metadata", {}),
    )
    if not row:
        return {}
    return dict(row)


async def get_company(pool: asyncpg.Pool, company_id: str) -> Optional[Dict[str, Any]]:
    """Get a company by ID."""
    row = await pool.fetchrow(
        "SELECT id, name, industry, description, metadata, created_at, updated_at FROM companies WHERE id = $1",
        company_id,
    )
    if not row:
        return None
    result = dict(row)
    # Parse metadata if it's a string
    if isinstance(result.get("metadata"), str):
        result["metadata"] = json.loads(result["metadata"])
    return result


async def get_company_with_executives(
    pool: asyncpg.Pool,
    company_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get a company with all executives including hierarchy information.

    Returns company with executives list containing hierarchy_level,
    reports_to, and direct_reports.
    """
    # Get company
    company = await get_company(pool, company_id)
    if not company:
        return None

    # Get all executives with hierarchy info
    rows = await pool.fetch(
        """
        SELECT id, name, name_english, title, department, company_id, email,
               profile_data IS NOT NULL AS has_profile,
               voiceprint_data IS NOT NULL AS has_voiceprint,
               voice_keys IS NOT NULL AS has_voice_keys,
               reports_to, hierarchy_level, sort_order
        FROM executive_profiles
        WHERE company_id = $1
        ORDER BY hierarchy_level, sort_order, name
        """,
        company_id,
    )

    executives = [dict(r) for r in rows]

    # Build direct_reports mapping
    reports_map = defaultdict(list)
    for exec in executives:
        if exec.get("reports_to"):
            reports_map[exec["reports_to"]].append(exec["id"])

    # Add direct_reports to each executive
    for exec in executives:
        exec["direct_reports"] = reports_map.get(exec["id"], [])

    company["executives_count"] = len(executives)
    company["executives"] = executives

    return company


async def update_company(
    pool: asyncpg.Pool,
    company_id: str,
    updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Update company info.

    Args:
        pool: Database connection pool.
        company_id: Company ID.
        updates: Dict of fields to update.

    Returns:
        Updated company dict or None if not found.
    """
    # Build dynamic SET clause
    set_parts = []
    params = [company_id]
    param_idx = 2

    if "name" in updates and updates["name"]:
        set_parts.append(f"name = ${param_idx}")
        params.append(updates["name"])
        param_idx += 1

    if "industry" in updates:
        set_parts.append(f"industry = ${param_idx}")
        params.append(updates["industry"])
        param_idx += 1

    if "description" in updates:
        set_parts.append(f"description = ${param_idx}")
        params.append(updates["description"])
        param_idx += 1

    if "metadata" in updates and updates["metadata"]:
        set_parts.append(f"metadata = ${param_idx}")
        params.append(updates["metadata"])
        param_idx += 1

    if not set_parts:
        return await get_company(pool, company_id)

    set_clause = ", ".join(set_parts)
    row = await pool.fetchrow(
        f"""
        UPDATE companies
        SET {set_clause}, updated_at = NOW()
        WHERE id = $1
        RETURNING id, name, industry, description, metadata, created_at, updated_at
        """,
        *params,
    )
    if not row:
        return None
    result = dict(row)
    # Parse metadata if it's a string
    if isinstance(result.get("metadata"), str):
        result["metadata"] = json.loads(result["metadata"])
    return result


def _parse_company_metadata(row_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Parse metadata field if it's a string."""
    if isinstance(row_dict.get("metadata"), str):
        row_dict["metadata"] = json.loads(row_dict["metadata"])
    return row_dict


async def list_companies(pool: asyncpg.Pool) -> List[Dict[str, Any]]:
    """List all companies."""
    rows = await pool.fetch(
        "SELECT id, name, industry, description, metadata, created_at, updated_at FROM companies ORDER BY created_at DESC"
    )
    return [_parse_company_metadata(dict(r)) for r in rows]


async def list_company_executives(
    pool: asyncpg.Pool,
    company_id: str,
    hierarchy: bool = False,
    sort: str = "name",
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List executives for a company with optional hierarchy grouping.

    Args:
        pool: Database connection pool.
        company_id: Company ID.
        hierarchy: If True, group executives by hierarchy level.
        sort: Sort order - "hierarchy", "name", or "created".
        email: Optional email to filter by.

    Returns:
        Dict with company_id, total, executives list, and optionally by_level.
    """
    # Determine sort order
    order_clause = "name"
    if sort == "hierarchy":
        order_clause = "hierarchy_level, sort_order, name"
    elif sort == "created":
        order_clause = "created_at DESC"

    # Build query
    query = """
        SELECT id, name, name_english, title, department, company_id, email,
               profile_data IS NOT NULL AS has_profile,
               voiceprint_data IS NOT NULL AS has_voiceprint,
               voice_keys IS NOT NULL AS has_voice_keys,
               reports_to, hierarchy_level, sort_order
        FROM executive_profiles
        WHERE company_id = $1
    """
    params = [company_id]
    
    if email:
        query += f" AND email = ${len(params) + 1}"
        params.append(email)

    query += f" ORDER BY {order_clause}"

    rows = await pool.fetch(query, *params)

    executives = [dict(r) for r in rows]

    # Build direct_reports mapping
    reports_map = defaultdict(list)
    for exec in executives:
        if exec.get("reports_to"):
            reports_map[exec["reports_to"]].append(exec["id"])

    # Add direct_reports to each executive
    for exec in executives:
        exec["direct_reports"] = reports_map.get(exec["id"], [])

    result = {
        "company_id": company_id,
        "total": len(executives),
        "executives": executives,
    }

    # Group by hierarchy level if requested
    if hierarchy:
        by_level = defaultdict(list)
        for exec in executives:
            level = str(exec.get("hierarchy_level", 0))
            by_level[level].append(exec)
        result["by_level"] = dict(by_level)

    return result


async def get_executives_count(pool: asyncpg.Pool, company_id: str) -> int:
    """Get count of executives in a company."""
    count = await pool.fetchval(
        "SELECT COUNT(*) FROM executive_profiles WHERE company_id = $1",
        company_id,
    )
    return count or 0
