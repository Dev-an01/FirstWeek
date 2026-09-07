"""
Semantic Example Selector - Stage 3 of the Conversation Engine.

Selects the best communication example using multi-signal matching:
- 70% semantic similarity (embedding distance)
- 10% type match bonus (email vs slack)
- 10% length appropriateness
- 10% emotional tone match

Target latency: ~30ms (including query embedding).
"""

import logging
import time
from typing import Optional, List, Tuple, TYPE_CHECKING

import numpy as np

from .models import SelectedExample, ExampleEmbedding
from .embedding_service import EmbeddingService, get_embedding_service
from .embedding_cache import EmbeddingCache, get_embedding_cache

if TYPE_CHECKING:
    from ..analysis.models import AnalyzedContext
    from ..calibration.models import ResponseCalibration

logger = logging.getLogger(__name__)


class SemanticExampleSelector:
    """
    Semantic Example Selector (Stage 3).

    Multi-signal matching for communication examples:
    - semantic: 70% - Cosine similarity between query and example embeddings
    - type: 10% - Match between query channel and example type
    - length: 10% - Example length appropriate for calibrated response length
    - tone: 10% - Example tone markers match user emotion

    Thread-safe: Uses cached embeddings and stateless scoring.
    """

    # Signal weights (must sum to 1.0)
    SIGNAL_WEIGHTS = {
        "semantic": 0.70,
        "type": 0.10,
        "length": 0.10,
        "tone": 0.10,
    }

    # Type match scoring
    TYPE_SCORES = {
        # (example_type, channel) -> score
        ("email", "email"): 1.0,
        ("slack", "slack"): 1.0,
        ("slack_dm", "slack_dm"): 1.0,
        ("slack_dm", "slack"): 0.7,  # Partial match
        ("slack", "slack_dm"): 0.7,
        ("email", "slack"): 0.3,
        ("slack", "email"): 0.3,
        ("email", "slack_dm"): 0.2,
        ("slack_dm", "email"): 0.2,
    }

    # Length ranges (word count) for each response length
    LENGTH_RANGES = {
        "concise": (20, 80),
        "moderate": (80, 200),
        "detailed": (200, 500),
    }

    # Tone markers to emotion mapping
    TONE_EMOTION_MAP = {
        "empathetic": ["stressed", "tense"],
        "supportive": ["stressed", "tense", "neutral"],
        "celebratory": ["celebratory", "positive"],
        "direct": ["neutral", "tense"],
        "analytical": ["neutral"],
        "neutral": ["neutral"],
    }

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        embedding_cache: Optional[EmbeddingCache] = None,
    ):
        """
        Initialize SemanticExampleSelector.

        Args:
            embedding_service: EmbeddingService instance (uses singleton if None)
            embedding_cache: EmbeddingCache instance (uses singleton if None)
        """
        self._embedding_service = embedding_service
        self._embedding_cache = embedding_cache
        logger.debug("SemanticExampleSelector initialized")

    def _ensure_services(self) -> None:
        """Lazy load services."""
        if self._embedding_service is None:
            self._embedding_service = get_embedding_service()
        if self._embedding_cache is None:
            self._embedding_cache = get_embedding_cache()

    def select(
        self,
        query: str,
        profile_id: str,
        analyzed_context: "AnalyzedContext",
        calibration: "ResponseCalibration",
        channel: str = "slack",
    ) -> Tuple[SelectedExample, np.ndarray]:
        """
        Select best matching communication example.

        Args:
            query: User's query text
            profile_id: Executive profile ID
            analyzed_context: From Phase 3 ContextAnalyzer
            calibration: From Phase 3 ResponseCalibrator
            channel: Target communication channel (email/slack/slack_dm)

        Returns:
            Tuple of (SelectedExample, query_embedding)
            - SelectedExample: Best matching example with scores
            - query_embedding: Query embedding for reuse by PrecedentSelector
        """
        start = time.time()
        self._ensure_services()

        # Step 1: Generate query embedding with context enrichment
        query_embedding, embed_time = self._embedding_service.embed_query(
            query=query,
            theme=analyzed_context.theme.value if analyzed_context.theme else None,
            emotion=analyzed_context.user_emotion.value if analyzed_context.user_emotion else None,
            turn_type=analyzed_context.turn_type.value if analyzed_context.turn_type else None,
        )

        # Step 2: Get cached example embeddings
        examples = self._embedding_cache.get_example_embeddings(profile_id)
        embeddings_array = self._embedding_cache.get_example_embeddings_array(profile_id)

        if not examples or embeddings_array is None or len(embeddings_array) == 0:
            logger.warning(f"No examples found for profile: {profile_id}")
            return (
                SelectedExample.create_fallback(f"no_examples_for_{profile_id}"),
                query_embedding,
            )

        # Step 3: Compute semantic similarities (vectorized)
        semantic_scores = self._embedding_service.cosine_similarities(
            query_embedding, embeddings_array
        )

        # Step 4: Compute multi-signal scores for each example
        scores = []
        for i, example in enumerate(examples):
            semantic = max(0, semantic_scores[i])  # Ensure non-negative

            type_bonus = self._compute_type_bonus(
                example.example_type, channel
            )

            length_bonus = self._compute_length_bonus(
                example.word_count, calibration
            )

            tone_bonus = self._compute_tone_bonus(
                example.tone_markers, analyzed_context
            )

            # Weighted total score
            total = (
                self.SIGNAL_WEIGHTS["semantic"] * semantic +
                self.SIGNAL_WEIGHTS["type"] * type_bonus +
                self.SIGNAL_WEIGHTS["length"] * length_bonus +
                self.SIGNAL_WEIGHTS["tone"] * tone_bonus
            )

            scores.append({
                "index": i,
                "total": total,
                "semantic": semantic,
                "type_bonus": type_bonus,
                "length_bonus": length_bonus,
                "tone_bonus": tone_bonus,
            })

        # Step 5: Select best match
        scores.sort(key=lambda x: x["total"], reverse=True)
        best = scores[0]
        best_example = examples[best["index"]]

        # Step 6: Identify runner-up if exists
        runner_up_id = None
        runner_up_score = 0.0
        if len(scores) > 1:
            runner_up = scores[1]
            runner_up_id = examples[runner_up["index"]].example_id
            runner_up_score = runner_up["total"]

        selection_time = (time.time() - start) * 1000

        # Step 7: Build result
        selected = SelectedExample(
            example_id=best_example.example_id,
            example_type=best_example.example_type,
            context=best_example.context,
            full_text=self._get_full_text(profile_id, best_example.example_id),
            similarity_score=best["total"],
            semantic_score=best["semantic"],
            type_bonus=best["type_bonus"],
            length_bonus=best["length_bonus"],
            tone_bonus=best["tone_bonus"],
            match_reason=self._build_match_reason(best, channel, analyzed_context),
            match_signals={
                "semantic": best["semantic"],
                "type": best["type_bonus"],
                "length": best["length_bonus"],
                "tone": best["tone_bonus"],
            },
            runner_up_id=runner_up_id,
            runner_up_score=runner_up_score,
            is_fallback=False,
            selection_time_ms=selection_time,
        )

        logger.debug(
            f"Selected example {selected.example_id} "
            f"(score={selected.similarity_score:.3f}, time={selection_time:.1f}ms)"
        )

        return selected, query_embedding

    def _compute_type_bonus(self, example_type: str, channel: str) -> float:
        """
        Compute type match bonus.

        Full match (email-email, slack-slack): 1.0 -> 0.10 weighted
        Partial match (slack-slack_dm): 0.7 -> 0.07 weighted
        Mismatch: 0.2-0.3 -> 0.02-0.03 weighted
        """
        key = (example_type, channel)
        if key in self.TYPE_SCORES:
            return self.TYPE_SCORES[key]

        # Fallback for unknown types
        return 0.3 if example_type != channel else 1.0

    def _compute_length_bonus(
        self,
        example_word_count: int,
        calibration: "ResponseCalibration",
    ) -> float:
        """
        Compute length appropriateness bonus.

        Matches example word count to calibrated target_length.
        """
        # Map target_length to our ranges
        length_map = {
            "short": "concise",
            "medium": "moderate",
            "long": "detailed",
        }
        target_length = length_map.get(calibration.target_length, "moderate")
        if target_length not in self.LENGTH_RANGES:
            target_length = "moderate"

        min_len, max_len = self.LENGTH_RANGES[target_length]

        # Perfect match if within range
        if min_len <= example_word_count <= max_len:
            return 1.0

        # Partial match based on distance
        if example_word_count < min_len:
            distance = (min_len - example_word_count) / min_len
        else:
            distance = (example_word_count - max_len) / max_len

        return max(0.0, 1.0 - distance)

    def _compute_tone_bonus(
        self,
        example_tone_markers: List[str],
        analyzed_context: "AnalyzedContext",
    ) -> float:
        """
        Compute emotional tone match bonus.

        Matches example tone markers to user emotion.
        """
        if not example_tone_markers:
            return 0.5  # Neutral for no markers

        user_emotion = analyzed_context.user_emotion.value if analyzed_context.user_emotion else "neutral"

        # Count matching markers
        matches = 0
        for marker in example_tone_markers:
            marker_emotions = self.TONE_EMOTION_MAP.get(marker, [])
            if user_emotion in marker_emotions:
                matches += 1

        if matches > 0:
            return min(1.0, 0.5 + (matches * 0.25))  # 0.5 base + 0.25 per match

        return 0.3  # Low score for no matches

    def _get_full_text(self, profile_id: str, example_id: str) -> str:
        """Get full text for example from cache."""
        examples = self._embedding_cache.get_example_embeddings(profile_id)
        for ex in examples:
            if ex.example_id == example_id:
                return ex.full_text
        return ""

    def _build_match_reason(
        self,
        best: dict,
        channel: str,
        analyzed_context: "AnalyzedContext",
    ) -> str:
        """Build human-readable match reason."""
        reasons = []

        # Determine dominant signal
        if best["semantic"] >= 0.6:
            reasons.append(f"high semantic similarity ({best['semantic']:.2f})")
        elif best["semantic"] >= 0.4:
            reasons.append(f"moderate semantic similarity ({best['semantic']:.2f})")

        if best["type_bonus"] >= 0.8:
            reasons.append(f"matched {channel} channel")

        if best["tone_bonus"] >= 0.7:
            emotion = analyzed_context.user_emotion.value if analyzed_context.user_emotion else "neutral"
            reasons.append(f"tone matches {emotion} emotion")

        if best["length_bonus"] >= 0.8:
            reasons.append("appropriate length")

        if not reasons:
            reasons.append("best available match")

        return "; ".join(reasons)


# Singleton instance
_default_selector: Optional[SemanticExampleSelector] = None


def get_example_selector() -> SemanticExampleSelector:
    """Get singleton SemanticExampleSelector instance."""
    global _default_selector
    if _default_selector is None:
        _default_selector = SemanticExampleSelector()
    return _default_selector


def create_example_selector(
    embedding_service: Optional[EmbeddingService] = None,
    embedding_cache: Optional[EmbeddingCache] = None,
) -> SemanticExampleSelector:
    """Create a new SemanticExampleSelector instance."""
    return SemanticExampleSelector(
        embedding_service=embedding_service,
        embedding_cache=embedding_cache,
    )
