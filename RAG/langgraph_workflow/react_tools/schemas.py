"""
Pydantic schemas for ReAct Tools

Input/Output schemas for all specialized ReAct tools.
"""

from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


# ============================================================
# TOOL 1: Entity Relationship Analyzer
# ============================================================

class EntityRelationshipInput(BaseModel):
    """Input schema for entity relationship analysis."""

    entity_a: str = Field(
        description="First entity name (e.g., 'Tanaka', 'Acme Corp', 'Project Alpha')"
    )

    entity_b: str = Field(
        description="Second entity name (e.g., 'Project Pegasus', 'Beta Corp')"
    )

    include_indirect: bool = Field(
        default=True,
        description="Include indirect relationships via intermediary entities (2-hop)"
    )

    max_paths: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of relationship paths to return"
    )


class EntityRelationshipOutput(BaseModel):
    """Output schema for entity relationship analysis."""

    success: bool = Field(description="Whether the analysis completed successfully")

    entity_a: str = Field(description="First entity searched")
    entity_b: str = Field(description="Second entity searched")

    direct_relationships: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Direct connections between entities"
    )

    indirect_relationships: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Indirect connections via intermediary entities"
    )

    summary: str = Field(
        description="Natural language summary of the relationship"
    )

    strength_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Relationship strength score (0.0 = no connection, 1.0 = strong connection)"
    )

    error: Optional[str] = Field(
        default=None,
        description="Error message if analysis failed"
    )


# ============================================================
# TOOL 2: Temporal Context Search
# ============================================================

class TemporalSearchInput(BaseModel):
    """Input schema for temporal context search."""

    query: str = Field(
        description="Search query (e.g., 'discount decisions', 'project updates')"
    )

    time_range: str = Field(
        description="Time range: 'last_week', 'last_month', 'last_quarter', 'this_year', 'Q1', 'Q2', 'Q3', 'Q4', or custom 'YYYY-MM-DD:YYYY-MM-DD'"
    )

    executive_id: Optional[str] = Field(
        default=None,
        description="Optional: Filter by specific executive (e.g., 'exec_cto_yuki')"
    )

    top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of results to return"
    )


class TemporalSearchOutput(BaseModel):
    """Output schema for temporal context search."""

    success: bool = Field(description="Whether the search completed successfully")

    results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Matching conversations/decisions within time range"
    )

    time_range_resolved: Dict[str, str] = Field(
        default_factory=dict,
        description="Actual date range used (start, end, days)"
    )

    count: int = Field(
        default=0,
        description="Number of results found"
    )

    error: Optional[str] = Field(
        default=None,
        description="Error message if search failed"
    )


# ============================================================
# TOOL 3: Precedent Finder
# ============================================================

class PrecedentFinderInput(BaseModel):
    """Input schema for precedent finder."""

    scenario: str = Field(
        description="Description of current scenario (e.g., '15% discount for strategic A-tier client')"
    )

    decision_type: Optional[str] = Field(
        default=None,
        description="Optional: Filter by decision type (e.g., 'discount', 'hiring', 'investment')"
    )

    similarity_threshold: float = Field(
        default=0.70,
        ge=0.5,
        le=1.0,
        description="Minimum similarity score for precedents (0.5-1.0)"
    )

    include_outcomes: bool = Field(
        default=True,
        description="Whether to include outcome information"
    )

    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of precedents to return"
    )


class PrecedentFinderOutput(BaseModel):
    """Output schema for precedent finder."""

    success: bool = Field(description="Whether the search completed successfully")

    precedents: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Similar past decisions with details"
    )

    count: int = Field(
        default=0,
        description="Number of precedents found"
    )

    avg_similarity: float = Field(
        default=0.0,
        description="Average similarity score of found precedents"
    )

    error: Optional[str] = Field(
        default=None,
        description="Error message if search failed"
    )


# ============================================================
# TOOL 4: Decision Pattern Analyzer
# ============================================================

class DecisionPatternInput(BaseModel):
    """Input schema for decision pattern analysis."""

    executive_id: str = Field(
        description="Executive ID (e.g., 'exec_cto_yuki', 'exec_001_test')"
    )

    decision_domain: Optional[str] = Field(
        default=None,
        description="Optional: Focus on specific domain (e.g., 'discount', 'hiring', 'technical')"
    )

    include_examples: bool = Field(
        default=True,
        description="Whether to include example decisions"
    )


class DecisionPatternOutput(BaseModel):
    """Output schema for decision pattern analysis."""

    success: bool = Field(description="Whether the analysis completed successfully")

    executive_id: str = Field(description="Executive analyzed")

    patterns: Dict[str, Any] = Field(
        default_factory=dict,
        description="Decision-making patterns (risk tolerance, key values, etc.)"
    )

    decision_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of decisions by type/category"
    )

    outcome_stats: Dict[str, int] = Field(
        default_factory=dict,
        description="Outcome statistics (positive, negative, neutral)"
    )

    examples: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Example decisions if requested"
    )

    total_decisions_analyzed: int = Field(
        default=0,
        description="Total number of decisions analyzed"
    )

    error: Optional[str] = Field(
        default=None,
        description="Error message if analysis failed"
    )
