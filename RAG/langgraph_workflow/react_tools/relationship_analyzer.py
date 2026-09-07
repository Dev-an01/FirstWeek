"""
Entity Relationship Analyzer

Analyzes relationships between two entities using Neo4j graph.
Finds direct connections, indirect paths, and generates summaries.

Usage:
    result = analyze_entity_relationship(
        params=EntityRelationshipInput(entity_a="Tanaka", entity_b="Acme Corp"),
        graph_driver=neo4j_driver
    )
"""

import logging
import re
from typing import Dict, Any, List, Optional

from .schemas import EntityRelationshipInput, EntityRelationshipOutput

logger = logging.getLogger(__name__)


def analyze_entity_relationship(
    params: EntityRelationshipInput,
    graph_driver: Any
) -> EntityRelationshipOutput:
    """
    Analyze relationships between two entities using Neo4j graph.

    Goes beyond simple graph traversal by:
    - Identifying relationship types and context
    - Finding shared connections (indirect via intermediaries)
    - Calculating relationship strength
    - Providing natural language summary

    Args:
        params: EntityRelationshipInput with entity_a, entity_b, include_indirect
        graph_driver: Neo4j driver instance (from GraphContextProvider.driver)

    Returns:
        EntityRelationshipOutput with relationships and summary

    Example:
        Query: "How are Tanaka and Acme Corp related?"
        Result: "Tanaka and Acme Corp are directly connected via WORKED_ON.
                 They also share connections through Project Alpha."
    """
    try:
        logger.info(f"Analyzing relationship: {params.entity_a} <-> {params.entity_b}")

        # Build regex patterns for fuzzy matching (case-insensitive)
        entity_a_pattern = _build_entity_pattern(params.entity_a)
        entity_b_pattern = _build_entity_pattern(params.entity_b)

        # Find direct relationships
        direct_relationships = _find_direct_relationships(
            graph_driver,
            entity_a_pattern,
            entity_b_pattern
        )

        # Find indirect relationships (2-hop) if requested
        indirect_relationships = []
        if params.include_indirect:
            indirect_relationships = _find_indirect_relationships(
                graph_driver,
                entity_a_pattern,
                entity_b_pattern,
                max_paths=params.max_paths
            )

        # Calculate relationship strength
        strength_score = _calculate_strength(
            direct_relationships,
            indirect_relationships
        )

        # Generate natural language summary
        summary = _generate_summary(
            params.entity_a,
            params.entity_b,
            direct_relationships,
            indirect_relationships
        )

        logger.info(
            f"Found {len(direct_relationships)} direct, "
            f"{len(indirect_relationships)} indirect relationships"
        )

        return EntityRelationshipOutput(
            success=True,
            entity_a=params.entity_a,
            entity_b=params.entity_b,
            direct_relationships=direct_relationships,
            indirect_relationships=indirect_relationships[:params.max_paths],
            summary=summary,
            strength_score=strength_score
        )

    except Exception as e:
        logger.error(f"Entity relationship analysis error: {e}")
        return EntityRelationshipOutput(
            success=False,
            entity_a=params.entity_a,
            entity_b=params.entity_b,
            summary=f"Error analyzing relationship: {str(e)}",
            error=str(e)
        )


def _build_entity_pattern(entity_name: str) -> str:
    """
    Build a regex pattern for fuzzy entity matching.

    Handles:
    - Case insensitivity
    - Partial matches (e.g., "Tanaka" matches "Akiko Tanaka")
    - Common variations
    """
    # Escape regex special characters
    escaped = re.escape(entity_name)
    # Make case-insensitive and allow partial matches
    pattern = f"(?i).*{escaped}.*"
    return pattern


def _find_direct_relationships(
    driver: Any,
    entity_a_pattern: str,
    entity_b_pattern: str
) -> List[Dict[str, Any]]:
    """
    Find direct relationships between two entities.

    Cypher query finds all relationships where both entities match patterns.
    """
    cypher = """
        MATCH (a)-[r]-(b)
        WHERE a.name =~ $entity_a_pattern
          AND b.name =~ $entity_b_pattern
        RETURN
            type(r) AS relationship_type,
            a.name AS from_entity,
            a.type AS from_type,
            b.name AS to_entity,
            b.type AS to_type,
            properties(r) AS properties
        LIMIT 10
    """

    relationships = []

    try:
        with driver.session() as session:
            result = session.run(
                cypher,
                entity_a_pattern=entity_a_pattern,
                entity_b_pattern=entity_b_pattern
            )

            for record in result:
                relationships.append({
                    "type": record["relationship_type"],
                    "from": record["from_entity"],
                    "from_type": record["from_type"],
                    "to": record["to_entity"],
                    "to_type": record["to_type"],
                    "properties": dict(record["properties"]) if record["properties"] else {}
                })

    except Exception as e:
        logger.error(f"Error finding direct relationships: {e}")

    return relationships


def _find_indirect_relationships(
    driver: Any,
    entity_a_pattern: str,
    entity_b_pattern: str,
    max_paths: int = 5
) -> List[Dict[str, Any]]:
    """
    Find indirect relationships via intermediary entities (2-hop).

    Useful for finding shared connections like:
    - Tanaka --[WORKS_ON]--> Project Alpha <--[PARTNERED_WITH]-- Acme Corp
    """
    # Use COALESCE to handle different node types with different property names
    # Some nodes use 'name', some use 'title', some use 'id'
    cypher = """
        MATCH (a)-[r1]-(intermediary)-[r2]-(b)
        WHERE a.name =~ $entity_a_pattern
          AND b.name =~ $entity_b_pattern
          AND intermediary <> a
          AND intermediary <> b
        RETURN DISTINCT
            COALESCE(intermediary.name, intermediary.title, intermediary.id) AS via,
            COALESCE(intermediary.type, labels(intermediary)[0]) AS via_type,
            type(r1) AS rel1_type,
            type(r2) AS rel2_type,
            a.name AS from_entity,
            b.name AS to_entity
        LIMIT $max_paths
    """

    relationships = []

    try:
        with driver.session() as session:
            result = session.run(
                cypher,
                entity_a_pattern=entity_a_pattern,
                entity_b_pattern=entity_b_pattern,
                max_paths=max_paths
            )

            for record in result:
                from_entity = record["from_entity"]
                to_entity = record["to_entity"]
                via = record["via"]
                rel1 = record["rel1_type"]
                rel2 = record["rel2_type"]

                relationships.append({
                    "via": via,
                    "via_type": record["via_type"],
                    "path": f"{from_entity} --[{rel1}]--> {via} --[{rel2}]--> {to_entity}",
                    "rel1_type": rel1,
                    "rel2_type": rel2
                })

    except Exception as e:
        logger.error(f"Error finding indirect relationships: {e}")

    return relationships


def _calculate_strength(
    direct: List[Dict[str, Any]],
    indirect: List[Dict[str, Any]]
) -> float:
    """
    Calculate relationship strength score (0.0 - 1.0).

    Factors:
    - Direct relationships are weighted higher (0.4 each, max 1.0)
    - Indirect relationships add smaller value (0.15 each, max 0.5)
    """
    direct_score = min(len(direct) * 0.4, 1.0)
    indirect_score = min(len(indirect) * 0.15, 0.5)

    # Combine scores, cap at 1.0
    total = min(direct_score + indirect_score, 1.0)

    return round(total, 2)


def _generate_summary(
    entity_a: str,
    entity_b: str,
    direct: List[Dict[str, Any]],
    indirect: List[Dict[str, Any]]
) -> str:
    """
    Generate a natural language summary of the relationships.
    """
    if not direct and not indirect:
        return f"No relationship found between {entity_a} and {entity_b} in the knowledge graph."

    summary_parts = []

    # Describe direct relationships
    if direct:
        rel_types = list(set(r["type"] for r in direct))
        if len(rel_types) == 1:
            summary_parts.append(
                f"{entity_a} and {entity_b} are directly connected via {rel_types[0]}."
            )
        else:
            summary_parts.append(
                f"{entity_a} and {entity_b} are directly connected via: {', '.join(rel_types)}."
            )

    # Describe indirect relationships
    if indirect:
        via_entities = list(set(r["via"] for r in indirect[:3]))  # Top 3
        if len(via_entities) == 1:
            summary_parts.append(
                f"They are also connected through {via_entities[0]}."
            )
        else:
            summary_parts.append(
                f"They also share connections through: {', '.join(via_entities)}."
            )

    return " ".join(summary_parts)


# Convenience function for use in ReAct
def format_for_observation(result: EntityRelationshipOutput) -> str:
    """
    Format the relationship analysis result for ReAct observation.

    Returns a concise string suitable for the ReAct loop.
    """
    if not result.success:
        return f"Relationship analysis failed: {result.error}"

    lines = [result.summary]

    if result.direct_relationships:
        lines.append(f"\nDirect connections ({len(result.direct_relationships)}):")
        for rel in result.direct_relationships[:3]:
            lines.append(f"  - {rel['from']} --[{rel['type']}]--> {rel['to']}")

    if result.indirect_relationships:
        lines.append(f"\nIndirect paths ({len(result.indirect_relationships)}):")
        for rel in result.indirect_relationships[:3]:
            lines.append(f"  - via {rel['via']}: {rel['path']}")

    lines.append(f"\nRelationship strength: {result.strength_score}")

    return "\n".join(lines)
