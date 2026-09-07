"""
Deterministic ID generators for onboarding entities.

Ensures PostgreSQL IDs match Neo4j/embedding IDs for consistent cross-system lookups.
"""


def generate_case_id(executive_id: str, case_index: int) -> str:
    """
    Generate a deterministic decision case ID.

    Args:
        executive_id: Executive ID.
        case_index: Zero-based index of the case within the executive's cases.

    Returns:
        Deterministic case ID: "{executive_id}_case_{index:03d}"
    """
    return f"{executive_id}_case_{case_index:03d}"
