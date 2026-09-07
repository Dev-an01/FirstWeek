"""
ReAct Tools for Agentic Path

Specialized tools that replace placeholder ANALYZE/COMPARE actions
with real functionality using existing infrastructure.

Tools:
1. Entity Relationship Analyzer - Analyze how entities connect (Neo4j)
2. Temporal Context Search - Time-constrained search (PostgreSQL)
3. Precedent Finder - Find similar past decisions (pgvector)
4. Decision Pattern Analyzer - Executive decision patterns (Profile + DB)
"""

from .schemas import (
    EntityRelationshipInput,
    EntityRelationshipOutput,
    TemporalSearchInput,
    TemporalSearchOutput,
    PrecedentFinderInput,
    PrecedentFinderOutput,
    DecisionPatternInput,
    DecisionPatternOutput,
)

from .relationship_analyzer import analyze_entity_relationship
from .temporal_search import temporal_context_search, parse_time_range_from_query
from .precedent_finder import find_precedents, extract_decision_type_from_query
from .decision_pattern import analyze_decision_pattern, extract_domain_from_query

__all__ = [
    # Schemas
    "EntityRelationshipInput",
    "EntityRelationshipOutput",
    "TemporalSearchInput",
    "TemporalSearchOutput",
    "PrecedentFinderInput",
    "PrecedentFinderOutput",
    "DecisionPatternInput",
    "DecisionPatternOutput",
    # Tools
    "analyze_entity_relationship",
    "temporal_context_search",
    "parse_time_range_from_query",
    "find_precedents",
    "extract_decision_type_from_query",
    "analyze_decision_pattern",
    "extract_domain_from_query",
]
