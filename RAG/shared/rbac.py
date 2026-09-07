"""
Unified RBAC (Role-Based Access Control) Module

Single source of truth for role-to-scope mapping across the entire RAG system.
Matches config.py (canonical) and PDF spec.
"""

from typing import List

SCOPE_HIERARCHY = ["public", "internal", "executive", "confidential"]

ROLE_SCOPES = {
    "super_admin":   ["public", "internal", "executive", "confidential"],
    "company_admin": ["public", "internal", "executive", "confidential"],
    "admin":         ["public", "internal", "executive", "confidential"],
    "executive":     ["public", "internal", "executive"],
    "employee":      ["public", "internal"],
    "guest":         ["public"],
}

DEFAULT_ROLE = "employee"


def get_allowed_scopes(role: str) -> List[str]:
    """
    Get allowed RBAC scopes for a user role.

    Args:
        role: User role string (case-insensitive).

    Returns:
        List of allowed scope strings. Defaults to ["public"] for unknown roles.
    """
    return ROLE_SCOPES.get(role.lower(), ["public"])
