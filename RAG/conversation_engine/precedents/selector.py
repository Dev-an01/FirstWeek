"""
Precedent Selector - Stage 4 of the Conversation Engine.

Selects the most relevant decision precedent for decision-type queries.
Skipped for non-decision queries (factual, informational).

Selection strategy:
- Category matching (30%)
- Semantic similarity (50%)
- Recency weighting (20%)

Target latency: ~5ms (reuses query embedding from Stage 3).
"""

import logging
import time
import re
from datetime import datetime
from typing import Optional, List, Tuple, TYPE_CHECKING

import numpy as np

from .models import SelectedPrecedent, PrecedentEmbedding, PrecedentCategory, PRECEDENT_CATEGORIES

if TYPE_CHECKING:
    from ..analysis.models import AnalyzedContext
    from ..examples.embedding_cache import EmbeddingCache

logger = logging.getLogger(__name__)


class PrecedentSelector:
    """
    Precedent Selector (Stage 4).

    Selection strategy:
    - 40% category matching (query keywords match precedent category)
    - 40% semantic similarity (embedding distance)
    - 20% recency weighting (newer decisions more relevant)

    IMPORTANT: Category matching now uses semantic intent detection.
    A "pivot" question should match "strategy" cases, NOT "risk_management".

    Skips selection for non-decision queries to save processing time.

    Thread-safe: Uses cached embeddings and stateless scoring.
    """

    # Signal weights - INCREASED category weight for better intent matching
    CATEGORY_WEIGHT = 0.40
    SEMANTIC_WEIGHT = 0.40
    RECENCY_WEIGHT = 0.20

    # Decision query indicators
    DECISION_THEMES = {"budget", "strategy", "security", "people", "vendor", "product",
                       "leadership", "risk_management", "communication", "culture", "meta"}
    DECISION_KEYWORDS = {
        "should", "decide", "decision", "recommend", "advice", "approve",
        "choice", "option", "approach", "strategy", "action", "proceed",
        "go ahead", "move forward", "priority", "prioritize", "choose",
        # Added: Past tense for "tell me about a time" questions
        "time", "when", "example", "experience", "story", "learned",
        "pivoted", "changed", "failed", "succeeded", "handled", "overcome",
    }

    # Semantic intent mappings: query intent -> expected category
    # These help distinguish between similar-sounding queries with different intents
    INTENT_TO_CATEGORY = {
        # Pivot/change queries -> strategy
        "pivot": "strategy",
        "pivoted": "strategy",
        "pivoting": "strategy",
        "change direction": "strategy",
        "changed direction": "strategy",
        "business model change": "strategy",
        "transform": "strategy",
        "focus": "strategy",
        "refocus": "strategy",
        # Delegation queries -> leadership
        "delegate": "leadership",
        "delegated": "leadership",
        "delegation": "leadership",
        "empower": "leadership",
        "let go": "leadership",
        "hand off": "leadership",
        # Risk/compliance queries -> risk_management
        "reject": "risk_management",
        "rejected": "risk_management",
        "turned down": "risk_management",
        "compliance": "risk_management",
        "ethical": "risk_management",
        "gray area": "risk_management",
        # Crisis/turnaround -> budget
        "crisis": "budget",
        "turnaround": "budget",
        "cost cut": "budget",
        "budget cut": "budget",
        "budget cuts": "budget",
        "bankruptcy": "budget",
        # Transparency -> communication
        "transparency": "communication",
        "transparent": "communication",
        "bad news": "communication",
        "report to stakeholder": "communication",
        # M&A -> meta
        "m&a": "meta",
        "acquisition": "meta",
        "merger": "meta",
        "sell company": "meta",
        "exit": "meta",
    }

    # Categories that should NOT match certain intents (negative filtering)
    # Format: intent_keyword -> [excluded_categories]
    INTENT_EXCLUSIONS = {
        "pivot": ["risk_management", "communication", "culture"],
        "pivoted": ["risk_management", "communication", "culture"],
        "change direction": ["risk_management", "communication"],
        "delegate": ["strategy", "budget", "risk_management"],
        "delegation": ["strategy", "budget", "risk_management"],
        "reject": ["strategy", "leadership", "budget"],
        "turned down": ["strategy", "leadership"],
        "crisis": ["strategy", "leadership"],
        "turnaround": ["strategy", "leadership"],
    }

    # Recency configuration
    RECENCY_HALF_LIFE_DAYS = 365  # Score halves after 1 year

    def __init__(
        self,
        embedding_cache: Optional["EmbeddingCache"] = None,
        categories: Optional[List[PrecedentCategory]] = None,
    ):
        """
        Initialize PrecedentSelector.

        Args:
            embedding_cache: EmbeddingCache instance (uses singleton if None)
            categories: Custom categories (uses PRECEDENT_CATEGORIES if None)
        """
        self._embedding_cache = embedding_cache
        self._categories = categories or PRECEDENT_CATEGORIES
        self._category_patterns = self._compile_category_patterns()
        logger.debug(f"PrecedentSelector initialized with {len(self._categories)} categories")

    def _ensure_cache(self) -> None:
        """Lazy load embedding cache."""
        if self._embedding_cache is None:
            from ..examples.embedding_cache import get_embedding_cache
            self._embedding_cache = get_embedding_cache()

    def _compile_category_patterns(self) -> dict:
        """Pre-compile regex patterns for category matching."""
        patterns = {}
        for cat in self._categories:
            # Build pattern from keywords
            keyword_pattern = "|".join(re.escape(kw) for kw in cat.keywords)
            patterns[cat.name] = re.compile(rf"\b({keyword_pattern})\b", re.IGNORECASE)
        return patterns

    def select(
        self,
        query: str,
        query_embedding: np.ndarray,
        profile_id: str,
        analyzed_context: "AnalyzedContext",
    ) -> SelectedPrecedent:
        """
        Select most relevant decision precedent.

        Args:
            query: User's query text
            query_embedding: Pre-computed query embedding (from Stage 3)
            profile_id: Executive profile ID
            analyzed_context: From Phase 3 ContextAnalyzer

        Returns:
            SelectedPrecedent (may be skipped if not decision query)
        """
        start = time.time()

        # Step 1: Check if this is a decision query
        if not self._is_decision_query(query, analyzed_context):
            selection_time = (time.time() - start) * 1000
            logger.debug(f"Skipping precedent selection (not decision query, time={selection_time:.1f}ms)")
            return SelectedPrecedent.create_skipped("not_decision_query")

        self._ensure_cache()

        # Step 2: Get cached precedent embeddings
        precedents = self._embedding_cache.get_precedent_embeddings(profile_id)
        embeddings_array = self._embedding_cache.get_precedent_embeddings_array(profile_id)

        if not precedents or embeddings_array is None or len(embeddings_array) == 0:
            selection_time = (time.time() - start) * 1000
            logger.warning(f"No precedents found for profile: {profile_id}")
            return SelectedPrecedent.create_no_match(f"no_precedents_for_{profile_id}")

        # Step 3: Detect intent and match category
        detected_intent = self._detect_intent(query)
        matched_category, category_confidence = self._match_category(query)
        excluded_categories = self._get_excluded_categories(query)

        logger.debug(
            f"Intent detection: intent={detected_intent}, "
            f"category={matched_category}, confidence={category_confidence:.2f}, "
            f"excluded={excluded_categories}"
        )

        # Step 4: Compute semantic similarities
        semantic_scores = np.dot(embeddings_array, query_embedding)

        # Step 5: Compute multi-signal scores with intent awareness
        scores = []
        for i, precedent in enumerate(precedents):
            # Check if this category is excluded based on query intent
            is_excluded = precedent.category in excluded_categories

            # Category score with intent-aware matching
            # 1.0 = exact match, 0.5 = related, 0.1 = excluded, 0.3 = no match
            if is_excluded:
                # Heavily penalize excluded categories
                category_score = 0.1
                category_match = False
            elif precedent.category == matched_category:
                category_score = 1.0
                category_match = True
            elif detected_intent and precedent.category == detected_intent:
                # Intent match (e.g., query about "pivot" matches "strategy" case)
                category_score = 0.9
                category_match = True
            else:
                category_score = 0.3
                category_match = False

            # Semantic score
            semantic = max(0, semantic_scores[i])

            # Recency score
            recency = self._compute_recency_score(precedent.date)

            # Weighted total
            total = (
                self.CATEGORY_WEIGHT * category_score +
                self.SEMANTIC_WEIGHT * semantic +
                self.RECENCY_WEIGHT * recency
            )

            scores.append({
                "index": i,
                "total": total,
                "category_match": category_match,
                "category_score": category_score,
                "semantic": semantic,
                "recency": recency,
                "is_excluded": is_excluded,
                "precedent_category": precedent.category,
            })

        # Step 6: Select best match (prioritize non-excluded categories)
        scores.sort(key=lambda x: (not x["is_excluded"], x["total"]), reverse=True)
        best = scores[0]
        best_precedent = precedents[best["index"]]

        selection_time = (time.time() - start) * 1000

        # Step 7: Check if match is good enough
        if best["total"] < 0.35:
            logger.debug(f"No relevant precedent found (best score={best['total']:.3f})")
            result = SelectedPrecedent.create_no_match("low_relevance_score")
            result.selection_time_ms = selection_time
            return result

        # Step 8: Build result
        selected = SelectedPrecedent(
            case_id=best_precedent.case_id,
            category=best_precedent.category,
            executive_id=best_precedent.executive_id,
            situation_summary=best_precedent.situation_summary,
            decision_summary=best_precedent.decision_summary,
            rationale_summary=best_precedent.rationale_summary,
            outcome_summary=best_precedent.outcome_summary,
            full_situation=best_precedent.full_situation,
            full_rationale=best_precedent.full_rationale,
            key_factors=best_precedent.key_factors,
            stakeholders=best_precedent.stakeholders,
            relevance_score=best["total"],
            category_match=best["category_match"],
            semantic_similarity=best["semantic"],
            match_reason=self._build_match_reason(best, best_precedent, matched_category),
            connection_to_query=self._build_connection(query, best_precedent),
            skipped=False,
            selection_time_ms=selection_time,
        )

        logger.debug(
            f"Selected precedent {selected.case_id} "
            f"(score={selected.relevance_score:.3f}, category={best_precedent.category}, "
            f"time={selection_time:.1f}ms)"
        )

        return selected

    def _is_decision_query(
        self,
        query: str,
        analyzed_context: "AnalyzedContext",
    ) -> bool:
        """
        Check if query requires decision guidance.

        Decision query indicators:
        - Theme is decision-related (budget, strategy, etc.)
        - Query contains decision keywords
        - Turn type suggests seeking advice
        """
        query_lower = query.lower()

        # Check theme
        theme = analyzed_context.theme.value if analyzed_context.theme else ""
        if theme in self.DECISION_THEMES:
            return True

        # Check for decision keywords
        for keyword in self.DECISION_KEYWORDS:
            if keyword in query_lower:
                return True

        # Check query type if available
        query_type = getattr(analyzed_context, "query_type", None)
        if query_type and query_type.value in ["decision", "advice", "recommendation"]:
            return True

        return False

    def _detect_intent(self, query: str) -> Optional[str]:
        """
        Detect the semantic intent of the query.

        Maps specific query phrases to expected decision categories.
        E.g., "pivot" -> "strategy", "delegate" -> "leadership"

        Returns:
            Category name if intent detected, None otherwise
        """
        query_lower = query.lower()

        # Check for explicit intent phrases
        for phrase, category in self.INTENT_TO_CATEGORY.items():
            if phrase in query_lower:
                logger.debug(f"Intent detected: '{phrase}' -> {category}")
                return category

        return None

    def _get_excluded_categories(self, query: str) -> set:
        """
        Get categories that should be excluded based on query intent.

        E.g., "pivot" questions should NOT match "risk_management" cases
        even if they have high semantic similarity (both involve crisis situations).

        Returns:
            Set of category names to exclude
        """
        query_lower = query.lower()
        excluded = set()

        for intent_keyword, exclusion_list in self.INTENT_EXCLUSIONS.items():
            if intent_keyword in query_lower:
                excluded.update(exclusion_list)

        return excluded

    def _match_category(self, query: str) -> Tuple[Optional[str], float]:
        """
        Match query to a precedent category.

        Now includes intent-based category detection for better accuracy.
        Returns (category_name, confidence) or (None, 0) if no match.
        """
        # First try intent-based matching (highest confidence)
        detected_intent = self._detect_intent(query)
        if detected_intent:
            return detected_intent, 0.9

        # Fall back to keyword pattern matching
        best_category = None
        best_count = 0

        for cat_name, pattern in self._category_patterns.items():
            matches = pattern.findall(query)
            if len(matches) > best_count:
                best_count = len(matches)
                best_category = cat_name

        if best_category:
            # Confidence based on match count
            confidence = min(1.0, 0.5 + (best_count * 0.2))
            return best_category, confidence

        return None, 0.0

    def _compute_recency_score(self, date_str: str) -> float:
        """
        Compute recency score using exponential decay.

        More recent decisions get higher scores.
        Score halves every RECENCY_HALF_LIFE_DAYS.
        """
        if not date_str:
            return 0.5  # Default for missing dates

        try:
            # Parse date (format: YYYY-MM-DD)
            case_date = datetime.strptime(date_str, "%Y-%m-%d")
            today = datetime.now()

            days_old = (today - case_date).days
            if days_old < 0:
                return 1.0  # Future dates get max score

            # Exponential decay
            decay_factor = 0.5 ** (days_old / self.RECENCY_HALF_LIFE_DAYS)
            return max(0.1, decay_factor)  # Minimum 0.1

        except ValueError:
            logger.warning(f"Invalid date format: {date_str}")
            return 0.5

    def _build_match_reason(
        self,
        best: dict,
        precedent: PrecedentEmbedding,
        matched_category: Optional[str],
    ) -> str:
        """Build human-readable match reason."""
        reasons = []

        if best["category_match"]:
            reasons.append(f"category match ({precedent.category})")

        if best["semantic"] >= 0.6:
            reasons.append(f"high semantic similarity ({best['semantic']:.2f})")
        elif best["semantic"] >= 0.4:
            reasons.append(f"moderate similarity ({best['semantic']:.2f})")

        if best["recency"] >= 0.8:
            reasons.append("recent decision")
        elif best["recency"] >= 0.5:
            reasons.append("relevant timeframe")

        if precedent.outcome_type == "SUCCESS":
            reasons.append("successful outcome")

        return "; ".join(reasons) if reasons else "best available match"

    def _build_connection(self, query: str, precedent: PrecedentEmbedding) -> str:
        """Build explanation of how precedent connects to query."""
        # Simple template-based connection
        if precedent.category == "pricing_strategy":
            return "Similar pricing/discount decision context"
        elif precedent.category == "personnel":
            return "Relevant team/HR decision experience"
        elif precedent.category == "budget":
            return "Related budget/investment decision"
        elif precedent.category == "vendor":
            return "Applicable vendor/partnership situation"
        elif precedent.category == "product":
            return "Relevant product/technical decision"
        elif precedent.category == "security":
            return "Security/compliance precedent"
        elif precedent.category == "customer":
            return "Customer relationship precedent"
        else:
            return f"Past {precedent.category} decision"


# Singleton instance
_default_selector: Optional[PrecedentSelector] = None


def get_precedent_selector() -> PrecedentSelector:
    """Get singleton PrecedentSelector instance."""
    global _default_selector
    if _default_selector is None:
        _default_selector = PrecedentSelector()
    return _default_selector


def create_precedent_selector(
    embedding_cache: Optional["EmbeddingCache"] = None,
    categories: Optional[List[PrecedentCategory]] = None,
) -> PrecedentSelector:
    """Create a new PrecedentSelector instance."""
    return PrecedentSelector(
        embedding_cache=embedding_cache,
        categories=categories,
    )
