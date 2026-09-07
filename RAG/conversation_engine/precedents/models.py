"""
Precedent Selection Data Models

Defines the output of decision case/precedent selection.
Used by Stage 4 (Precedent Selector) of the Conversation Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


@dataclass
class SelectedPrecedent:
    """
    Output of Precedent Selector (Stage 4).

    Contains the most relevant decision case for decision-type queries.
    Skipped for non-decision queries (factual, emotional).

    The precedent helps the LLM:
    - Reference past decisions in first person
    - Apply consistent decision-making philosophy
    - Show reasoning patterns
    - Connect past experience to current situation

    Selection uses:
    - Category matching (pricing_strategy, personnel, etc.)
    - Semantic similarity to query
    - Recency weighting (recent decisions more relevant)
    """
    # Precedent identification
    case_id: str = ""  # e.g., "DC_AKIKO_001"
    category: str = ""  # pricing_strategy, personnel, budget, etc.
    executive_id: str = ""

    # Condensed content (for prompt)
    situation_summary: str = ""  # Brief situation description
    decision_summary: str = ""  # What was decided
    rationale_summary: str = ""  # Why (condensed)
    outcome_summary: str = ""  # What happened

    # Full content (for context)
    full_situation: str = ""
    full_rationale: str = ""
    key_factors: List[str] = field(default_factory=list)
    stakeholders: List[str] = field(default_factory=list)

    # Relevance scoring
    relevance_score: float = 0.0  # Overall relevance (0-1)
    category_match: bool = False  # Category matches query
    semantic_similarity: float = 0.0  # Embedding similarity

    # Match metadata
    match_reason: str = ""
    connection_to_query: str = ""  # How this precedent connects to current query

    # Skip flag (for non-decision queries)
    skipped: bool = False
    skip_reason: Optional[str] = None

    # Timing
    selection_time_ms: float = 0.0

    def is_relevant(self, threshold: float = 0.5) -> bool:
        """Check if precedent is relevant enough to include."""
        return self.relevance_score >= threshold and not self.skipped

    def get_prompt_summary(self, max_tokens: int = 60) -> str:
        """
        Get condensed precedent for prompt inclusion.

        Format: "In DC_XXX_001, I [decision] because [rationale]. Outcome: [result]"
        """
        if self.skipped:
            return ""

        max_chars = max_tokens * 4  # ~4 chars per token

        summary = f"In {self.case_id}, I {self.decision_summary}"
        if self.rationale_summary:
            summary += f" because {self.rationale_summary}"
        if self.outcome_summary:
            summary += f". Outcome: {self.outcome_summary}"

        if len(summary) > max_chars:
            return summary[:max_chars - 3] + "..."
        return summary

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/debugging."""
        return {
            "case_id": self.case_id,
            "category": self.category,
            "executive_id": self.executive_id,
            "situation_summary": self.situation_summary,
            "decision_summary": self.decision_summary,
            "rationale_summary": self.rationale_summary,
            "outcome_summary": self.outcome_summary,
            "key_factors": self.key_factors,
            "relevance_score": self.relevance_score,
            "category_match": self.category_match,
            "semantic_similarity": self.semantic_similarity,
            "match_reason": self.match_reason,
            "skipped": self.skipped,
            "skip_reason": self.skip_reason,
            "selection_time_ms": self.selection_time_ms,
        }

    @classmethod
    def create_skipped(cls, reason: str = "not_decision_query") -> "SelectedPrecedent":
        """Create a skipped precedent for non-decision queries."""
        return cls(
            case_id="",
            skipped=True,
            skip_reason=reason,
        )

    @classmethod
    def create_no_match(cls, reason: str = "no_relevant_precedent") -> "SelectedPrecedent":
        """Create when no relevant precedent is found."""
        return cls(
            case_id="",
            relevance_score=0.0,
            match_reason=f"No match: {reason}",
        )


@dataclass
class PrecedentCategory:
    """
    Category definition for precedent classification.

    Used to match queries to relevant decision categories.
    """
    name: str  # e.g., "pricing_strategy"
    keywords: List[str] = field(default_factory=list)  # Matching keywords
    description: str = ""

    # Common categories:
    # - pricing_strategy: Discounts, pricing changes, deal negotiations
    # - personnel: Hiring, promotions, team changes, performance
    # - budget: Investments, cost cuts, resource allocation
    # - vendor: Vendor selection, partnerships, contracts
    # - product: Feature decisions, roadmap, tech debt
    # - security: Security investments, incident response
    # - customer: Customer escalations, relationship decisions


# Predefined categories for precedent matching
# NOTE: Categories must match those used in executive profile decision_cases
PRECEDENT_CATEGORIES = [
    # === CORE STRATEGY CATEGORIES ===
    PrecedentCategory(
        name="strategy",
        keywords=[
            "pivot", "pivoted", "pivoting", "change direction", "business model",
            "strategy", "strategic", "focus", "diversify", "expand", "contract",
            "market", "target", "positioning", "transform", "transformation",
            "shift", "transition", "reposition", "restructure", "direction",
            "approach", "business change", "new direction", "course correction"
        ],
        description="Business strategy, pivots, direction changes, market focus"
    ),
    PrecedentCategory(
        name="leadership",
        keywords=[
            "delegate", "delegation", "empower", "leadership", "lead", "manage",
            "authority", "responsibility", "ownership", "autonomy", "trust",
            "hand off", "step back", "let go", "give control", "assign"
        ],
        description="Leadership style, delegation, empowerment decisions"
    ),
    PrecedentCategory(
        name="risk_management",
        keywords=[
            "risk", "compliance", "legal", "reject", "refuse", "decline",
            "cautious", "careful", "danger", "threat", "avoid", "protect",
            "ethics", "ethical", "gray area", "grey area", "risky", "unsafe"
        ],
        description="Risk assessment, compliance, rejecting risky opportunities"
    ),
    # === OPERATIONAL CATEGORIES ===
    PrecedentCategory(
        name="budget",
        keywords=[
            "budget", "invest", "investment", "cost", "spend", "allocate", "ROI",
            "cut", "reduce", "save", "expense", "financial", "funding", "capital",
            "money", "resources", "turnaround", "black", "red", "profit", "loss"
        ],
        description="Budget, investments, cost management, financial decisions"
    ),
    PrecedentCategory(
        name="personnel",
        keywords=[
            "hire", "fire", "promote", "team", "performance", "talent",
            "recruit", "employee", "staff", "people", "HR", "human resources",
            "onboard", "terminate", "compensation", "salary"
        ],
        description="HR and team decisions"
    ),
    # === RELATIONSHIP CATEGORIES ===
    PrecedentCategory(
        name="communication",
        keywords=[
            "communicate", "communication", "report", "share", "inform", "tell",
            "transparency", "transparent", "open", "honest", "disclose",
            "bad news", "update", "announce", "message"
        ],
        description="Communication approach, transparency, stakeholder updates"
    ),
    PrecedentCategory(
        name="culture",
        keywords=[
            "culture", "values", "ethics", "behavior", "conduct", "misconduct",
            "harassment", "discipline", "policy", "principle", "integrity",
            "accountability", "standard"
        ],
        description="Company culture, ethics, behavioral standards"
    ),
    # === BUSINESS OPERATION CATEGORIES ===
    PrecedentCategory(
        name="pricing_strategy",
        keywords=["discount", "pricing", "deal", "negotiate", "contract", "renewal"],
        description="Pricing decisions, discounts, deal negotiations"
    ),
    PrecedentCategory(
        name="vendor",
        keywords=["vendor", "partner", "supplier", "outsource", "build vs buy"],
        description="Vendor and partnership decisions"
    ),
    PrecedentCategory(
        name="product",
        keywords=["feature", "roadmap", "tech debt", "architecture", "deprecate"],
        description="Product and technical decisions"
    ),
    PrecedentCategory(
        name="security",
        keywords=["security", "audit", "incident", "breach", "cyber"],
        description="Security decisions (not compliance - see risk_management)"
    ),
    PrecedentCategory(
        name="customer",
        keywords=["customer", "client", "escalation", "churn", "retention"],
        description="Customer relationship decisions"
    ),
    # === META CATEGORIES ===
    PrecedentCategory(
        name="meta",
        keywords=[
            "M&A", "merger", "acquisition", "sell", "exit", "IPO",
            "funding", "fundraise", "round", "investor", "acquisition",
            "major", "life-changing", "career", "company-level"
        ],
        description="Major company decisions: M&A, funding, exits"
    ),
]


@dataclass
class PrecedentEmbedding:
    """
    Pre-computed embedding for a decision case.

    Embedding combines situation + decision for semantic matching.
    Used by PrecedentSelector for fast similarity lookups.
    """
    case_id: str
    category: str
    executive_id: str

    # Pre-computed embedding (1024-dim for BAAI/bge-m3, MIGRATED from 384-dim)
    embedding: List[float] = field(default_factory=list)

    # Metadata for matching and display
    date: str = ""  # ISO format date for recency scoring
    situation_summary: str = ""  # Brief situation for display
    decision_summary: str = ""  # Brief decision for display
    rationale_summary: str = ""  # Brief rationale
    outcome_summary: str = ""  # Brief outcome
    outcome_type: str = ""  # SUCCESS, MIXED, FAILURE

    # Full content (for SelectedPrecedent population)
    full_situation: str = ""
    full_rationale: str = ""
    key_factors: List[str] = field(default_factory=list)
    stakeholders: List[str] = field(default_factory=list)

    # Cache metadata
    computed_at: Optional[str] = None
    model_name: str = "BAAI/bge-m3"  # MIGRATED: from all-MiniLM-L6-v2

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for caching."""
        return {
            "case_id": self.case_id,
            "category": self.category,
            "executive_id": self.executive_id,
            "embedding": self.embedding,
            "date": self.date,
            "situation_summary": self.situation_summary,
            "decision_summary": self.decision_summary,
            "rationale_summary": self.rationale_summary,
            "outcome_summary": self.outcome_summary,
            "outcome_type": self.outcome_type,
            "full_situation": self.full_situation,
            "full_rationale": self.full_rationale,
            "key_factors": self.key_factors,
            "stakeholders": self.stakeholders,
            "computed_at": self.computed_at,
            "model_name": self.model_name,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PrecedentEmbedding":
        """Deserialize from cache."""
        return cls(
            case_id=data["case_id"],
            category=data["category"],
            executive_id=data["executive_id"],
            embedding=data.get("embedding", []),
            date=data.get("date", ""),
            situation_summary=data.get("situation_summary", ""),
            decision_summary=data.get("decision_summary", ""),
            rationale_summary=data.get("rationale_summary", ""),
            outcome_summary=data.get("outcome_summary", ""),
            outcome_type=data.get("outcome_type", ""),
            full_situation=data.get("full_situation", ""),
            full_rationale=data.get("full_rationale", ""),
            key_factors=data.get("key_factors", []),
            stakeholders=data.get("stakeholders", []),
            computed_at=data.get("computed_at"),
            model_name=data.get("model_name", "BAAI/bge-m3"),  # MIGRATED
        )
