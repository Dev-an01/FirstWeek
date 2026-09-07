"""
Voiceprint Attention Mechanism - Graduated voiceprint category weighting.

Two-phase attention computation:
1. Pattern-based: Fast query classification -> base weights (~1ms)
2. Semantic: Cosine similarity with pre-embedded categories (~0.1ms)

Combined: final_weights = pattern * 0.4 + semantic * 0.6

Transforms binary emphasis to graduated weights.
"""

import logging
import time
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING
import numpy as np

from .voiceprint_embeddings import (
    VoiceprintEmbeddingCache,
    get_voiceprint_embedding_cache,
    EMBEDDABLE_CATEGORIES,
)

if TYPE_CHECKING:
    from ..analysis.models import AnalyzedContext

logger = logging.getLogger(__name__)


@dataclass
class AttentionWeights:
    """
    Container for voiceprint attention weights.

    Weight interpretation:
    - 0.00-0.05: Minimal (may omit from prompt)
    - 0.05-0.10: Low (include briefly)
    - 0.10-0.20: Medium (standard inclusion)
    - 0.20-0.30: High (emphasize, more examples)
    - 0.30+: Critical (prominent placement, explicit instructions)
    """
    # Content weights
    transparency_phrases: float = 0.10
    challenge_invitation: float = 0.10
    risk_language: float = 0.10
    numbers_cadence: float = 0.10
    decision_cadence: float = 0.10
    accountability_phrases: float = 0.05

    # Style weights
    signature_opener: float = 0.15
    sign_off: float = 0.10
    context_signatures: float = 0.08
    disagreement: float = 0.05

    # Emotional weights
    emotional_expressions: float = 0.10
    mentorship_phrases: float = 0.05
    deference_phrases: float = 0.05
    energy_words: float = 0.05
    humor_markers: float = 0.02

    # Lexicon (special)
    lexicon: float = 0.10

    # Metadata
    computation_time_ms: float = 0.0
    query_type: str = ""
    dominant_head: str = ""  # "content", "style", or "emotional"
    blend_ratio: str = ""  # "pattern_only", "semantic_only", "blended"

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary (weights only, no metadata)."""
        return {
            "transparency_phrases": self.transparency_phrases,
            "challenge_invitation": self.challenge_invitation,
            "risk_language": self.risk_language,
            "numbers_cadence": self.numbers_cadence,
            "decision_cadence": self.decision_cadence,
            "accountability_phrases": self.accountability_phrases,
            "signature_opener": self.signature_opener,
            "sign_off": self.sign_off,
            "context_signatures": self.context_signatures,
            "disagreement": self.disagreement,
            "emotional_expressions": self.emotional_expressions,
            "mentorship_phrases": self.mentorship_phrases,
            "deference_phrases": self.deference_phrases,
            "energy_words": self.energy_words,
            "humor_markers": self.humor_markers,
            "lexicon": self.lexicon,
        }

    def get_top_k(self, k: int = 5) -> List[Tuple[str, float]]:
        """Get top-k weighted categories."""
        weights = self.to_dict()
        sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        return sorted_weights[:k]

    def get_emphasis_level(self, category: str) -> str:
        """Get emphasis level string for a category."""
        weight = getattr(self, category, 0.0)
        if weight >= 0.30:
            return "CRITICAL"
        elif weight >= 0.20:
            return "HIGH"
        elif weight >= 0.10:
            return "MEDIUM"
        elif weight >= 0.05:
            return "LOW"
        else:
            return "MINIMAL"

    def get_emphasized_categories(self, min_weight: float = 0.15) -> List[str]:
        """Get list of categories above weight threshold."""
        weights = self.to_dict()
        return [cat for cat, weight in weights.items() if weight >= min_weight]

    @classmethod
    def from_dict(cls, weights: Dict[str, float], **metadata) -> "AttentionWeights":
        """Create from dictionary of weights."""
        return cls(
            transparency_phrases=weights.get("transparency_phrases", 0.10),
            challenge_invitation=weights.get("challenge_invitation", 0.10),
            risk_language=weights.get("risk_language", 0.10),
            numbers_cadence=weights.get("numbers_cadence", 0.10),
            decision_cadence=weights.get("decision_cadence", 0.10),
            accountability_phrases=weights.get("accountability_phrases", 0.05),
            signature_opener=weights.get("signature_opener", 0.15),
            sign_off=weights.get("sign_off", 0.10),
            context_signatures=weights.get("context_signatures", 0.08),
            disagreement=weights.get("disagreement", 0.05),
            emotional_expressions=weights.get("emotional_expressions", 0.10),
            mentorship_phrases=weights.get("mentorship_phrases", 0.05),
            deference_phrases=weights.get("deference_phrases", 0.05),
            energy_words=weights.get("energy_words", 0.05),
            humor_markers=weights.get("humor_markers", 0.02),
            lexicon=weights.get("lexicon", 0.10),
            **metadata,
        )


class SemanticAttention:
    """
    Two-phase attention computation for voiceprint categories.

    Stage 1 (Pattern): Query classification -> base weights
    Stage 2 (Semantic): Embedding similarity -> refined weights

    Blend: final = pattern * pattern_weight + semantic * semantic_weight
    """

    # Query type patterns for fast classification
    QUERY_TYPE_PATTERNS = {
        "decision": [
            "should we", "should i", "approve", "reject", "decide",
            "recommend", "choose", "budget", "hire", "launch", "proceed",
            "go ahead", "move forward", "green light", "sign off",
        ],
        "crisis": [
            "urgent", "emergency", "critical", "failed", "down", "breach",
            "incident", "outage", "issue", "problem", "broken", "crashed",
            "asap", "immediately", "help", "fire",
        ],
        "celebration": [
            "shipped", "launched", "won", "achieved", "milestone", "success",
            "congratulations", "great news", "amazing", "fantastic", "closed",
            "hit target", "exceeded", "celebration", "proud",
        ],
        "coaching": [
            "feedback", "advice", "help me", "how should i", "improve",
            "develop", "mentor", "guide", "struggling", "stuck", "unsure",
            "concerned", "worried", "nervous", "anxious",
        ],
        "update": [
            "status", "update", "progress", "report", "weekly", "summary",
            "recap", "fyi", "heads up", "sync", "check in",
        ],
        "explanation": [
            "why", "explain", "how does", "what is", "understand",
            "clarify", "confused", "context", "background", "reason",
        ],
    }

    # Base attention profiles per query type
    QUERY_TYPE_PROFILES = {
        "decision": {
            "transparency_phrases": 0.25,
            "challenge_invitation": 0.20,
            "numbers_cadence": 0.15,
            "decision_cadence": 0.20,
            "signature_opener": 0.10,
            "sign_off": 0.10,
            "_dominant_head": "content",
        },
        "crisis": {
            "accountability_phrases": 0.30,
            "risk_language": 0.25,
            "emotional_expressions": 0.20,
            "signature_opener": 0.10,
            "mentorship_phrases": 0.10,
            "sign_off": 0.05,
            "_dominant_head": "emotional",
        },
        "celebration": {
            "energy_words": 0.25,
            "emotional_expressions": 0.25,
            "signature_opener": 0.15,
            "sign_off": 0.15,
            "humor_markers": 0.10,
            "lexicon": 0.10,
            "_dominant_head": "emotional",
        },
        "coaching": {
            "mentorship_phrases": 0.25,
            "transparency_phrases": 0.20,
            "deference_phrases": 0.15,
            "emotional_expressions": 0.15,
            "challenge_invitation": 0.10,
            "signature_opener": 0.10,
            "sign_off": 0.05,
            "_dominant_head": "emotional",
        },
        "update": {
            "numbers_cadence": 0.20,
            "signature_opener": 0.15,
            "sign_off": 0.15,
            "context_signatures": 0.15,
            "lexicon": 0.15,
            "transparency_phrases": 0.10,
            "decision_cadence": 0.10,
            "_dominant_head": "style",
        },
        "explanation": {
            "transparency_phrases": 0.25,
            "numbers_cadence": 0.15,
            "decision_cadence": 0.15,
            "signature_opener": 0.15,
            "challenge_invitation": 0.10,
            "lexicon": 0.10,
            "sign_off": 0.10,
            "_dominant_head": "content",
        },
    }

    # Default sharpening configuration (can be overridden by config)
    DEFAULT_SHARPEN_THRESHOLD: float = 0.08  # Weights above this get sharpened
    DEFAULT_SHARPEN_MULTIPLIER: float = 1.4  # How much to boost high weights
    DEFAULT_SHARPEN_CAP: float = 0.35  # Maximum weight after sharpening

    def __init__(
        self,
        voiceprint_cache: Optional[VoiceprintEmbeddingCache] = None,
        pattern_weight: float = 0.6,  # Increased from 0.4 to preserve pattern differentiation
        semantic_weight: float = 0.4,  # Decreased from 0.6
        temperature: float = 0.5,
        enable_sharpening: bool = True,  # Enable weight sharpening
        sharpen_threshold: float = None,  # Override from config
        sharpen_multiplier: float = None,  # Override from config
        sharpen_cap: float = None,  # Override from config
    ):
        """
        Initialize SemanticAttention.

        Args:
            voiceprint_cache: Pre-computed voiceprint embeddings
            pattern_weight: Weight for pattern-based attention (0-1), default 0.6
            semantic_weight: Weight for semantic attention (0-1), default 0.4
            temperature: Softmax temperature (lower = more peaked)
            enable_sharpening: Whether to sharpen weights to prevent over-smoothing
            sharpen_threshold: Min weight for sharpening (from config)
            sharpen_multiplier: Sharpening boost factor (from config)
            sharpen_cap: Max weight after sharpening (from config)
        """
        self._voiceprint_cache = voiceprint_cache
        self._pattern_weight = pattern_weight
        self._semantic_weight = semantic_weight
        self._temperature = temperature
        self._enable_sharpening = enable_sharpening

        # Sharpening config (use provided or defaults)
        self._sharpen_threshold = sharpen_threshold or self.DEFAULT_SHARPEN_THRESHOLD
        self._sharpen_multiplier = sharpen_multiplier or self.DEFAULT_SHARPEN_MULTIPLIER
        self._sharpen_cap = sharpen_cap or self.DEFAULT_SHARPEN_CAP

        logger.debug(
            f"SemanticAttention initialized: "
            f"pattern={pattern_weight}, semantic={semantic_weight}, "
            f"temp={temperature}, sharpening={enable_sharpening}"
        )

    def _ensure_cache(self):
        """Lazy load voiceprint cache."""
        if self._voiceprint_cache is None:
            self._voiceprint_cache = get_voiceprint_embedding_cache()

    def compute_pattern_attention(
        self,
        query: str,
        context_signals: Optional[Dict[str, Any]] = None,
    ) -> AttentionWeights:
        """
        Stage 1: Pattern-based attention using query classification.

        Fast (~1ms) attention computation using keyword matching.

        Args:
            query: User query text
            context_signals: Optional dict with urgency, theme, user_emotion

        Returns:
            AttentionWeights based on query type patterns
        """
        start = time.time()

        # Classify query type
        query_type = self._classify_query_type(query)

        # Get base profile
        profile = self.QUERY_TYPE_PROFILES.get(
            query_type,
            self.QUERY_TYPE_PROFILES["explanation"],
        ).copy()

        # Extract dominant head
        dominant_head = profile.pop("_dominant_head", "content")

        # Apply context signal adjustments
        if context_signals:
            profile = self._apply_context_adjustments(profile, context_signals)

        # Fill missing categories with defaults
        for category in EMBEDDABLE_CATEGORIES:
            if category not in profile:
                profile[category] = 0.05  # Default low weight

        # Normalize
        profile = self._normalize_weights(profile)

        computation_time = (time.time() - start) * 1000

        return AttentionWeights.from_dict(
            profile,
            computation_time_ms=computation_time,
            query_type=query_type,
            dominant_head=dominant_head,
            blend_ratio="pattern_only",
        )

    def refine_with_embedding(
        self,
        pattern_weights: AttentionWeights,
        query_embedding: np.ndarray,
        executive_id: str,
    ) -> AttentionWeights:
        """
        Stage 2: Refine attention using semantic similarity.

        Uses pre-computed voiceprint category embeddings for
        zero-cost semantic similarity computation (~0.1ms).

        Args:
            pattern_weights: Weights from Stage 1
            query_embedding: Query embedding from ExampleSelector (1024-dim, MIGRATED from 384)
            executive_id: Executive profile ID

        Returns:
            Refined AttentionWeights (blended pattern + semantic)
        """
        start = time.time()
        self._ensure_cache()

        # Get category embeddings for this executive
        categories, embeddings_array = self._voiceprint_cache.get_all_category_embeddings_array(
            executive_id
        )

        if embeddings_array is None or len(categories) == 0:
            logger.debug(f"No embeddings for {executive_id}, using pattern-only")
            return pattern_weights

        # Ensure query_embedding is normalized
        query_norm = np.linalg.norm(query_embedding)
        if query_norm > 0:
            query_embedding = query_embedding / query_norm

        # Compute cosine similarities (vectorized)
        similarities = np.dot(embeddings_array, query_embedding)

        # Convert to weights (shift to positive, then normalize)
        semantic_weights = {}
        for i, category in enumerate(categories):
            # Cosine similarity is in [-1, 1], shift to [0, 1]
            sim = (similarities[i] + 1) / 2
            semantic_weights[category] = float(sim)

        # Fill missing categories
        for category in EMBEDDABLE_CATEGORIES:
            if category not in semantic_weights:
                semantic_weights[category] = 0.05

        # Normalize semantic weights
        semantic_weights = self._normalize_weights(semantic_weights)

        # Blend pattern and semantic weights
        pattern_dict = pattern_weights.to_dict()
        blended = {}

        for category in EMBEDDABLE_CATEGORIES:
            pattern_val = pattern_dict.get(category, 0.05)
            semantic_val = semantic_weights.get(category, 0.05)
            blended[category] = (
                self._pattern_weight * pattern_val +
                self._semantic_weight * semantic_val
            )

        # Normalize blended weights
        blended = self._normalize_weights(blended)

        # Apply sharpening to prevent over-smoothing
        blended = self._sharpen_weights(blended)

        computation_time = (time.time() - start) * 1000
        total_time = pattern_weights.computation_time_ms + computation_time

        # Build blend ratio string with sharpening indicator
        blend_info = f"pattern:{self._pattern_weight}/semantic:{self._semantic_weight}"
        if self._enable_sharpening:
            blend_info += "/sharpened"

        logger.debug(
            f"Attention refined for {executive_id}: "
            f"semantic_time={computation_time:.2f}ms, "
            f"sharpening={self._enable_sharpening}, "
            f"top_3={sorted(blended.items(), key=lambda x: x[1], reverse=True)[:3]}"
        )

        return AttentionWeights.from_dict(
            blended,
            computation_time_ms=total_time,
            query_type=pattern_weights.query_type,
            dominant_head=pattern_weights.dominant_head,
            blend_ratio=blend_info,
        )

    def compute_full_attention(
        self,
        query: str,
        query_embedding: Optional[np.ndarray],
        executive_id: str,
        context_signals: Optional[Dict[str, Any]] = None,
    ) -> AttentionWeights:
        """
        Convenience method: Compute full two-phase attention.

        Args:
            query: User query text
            query_embedding: Query embedding (if available, from ExampleSelector)
            executive_id: Executive profile ID
            context_signals: Optional context dict

        Returns:
            Final AttentionWeights
        """
        # Stage 1: Pattern-based
        pattern_weights = self.compute_pattern_attention(query, context_signals)

        # Stage 2: Semantic refinement (if embedding available)
        if query_embedding is not None:
            return self.refine_with_embedding(
                pattern_weights,
                query_embedding,
                executive_id,
            )

        return pattern_weights

    def _classify_query_type(self, query: str) -> str:
        """Classify query into type using pattern matching."""
        query_lower = query.lower()

        type_scores = {}
        for query_type, patterns in self.QUERY_TYPE_PATTERNS.items():
            score = sum(1 for p in patterns if p in query_lower)
            if score > 0:
                type_scores[query_type] = score

        if not type_scores:
            return "explanation"

        return max(type_scores.items(), key=lambda x: x[1])[0]

    def _apply_context_adjustments(
        self,
        weights: Dict[str, float],
        context_signals: Dict[str, Any],
    ) -> Dict[str, float]:
        """Apply context signal adjustments to weights."""
        adjusted = weights.copy()

        # Urgency adjustments
        urgency = str(context_signals.get("urgency", "")).lower()
        if urgency in ["crisis", "critical", "urgent", "high"]:
            adjusted["accountability_phrases"] = adjusted.get("accountability_phrases", 0.05) + 0.10
            adjusted["risk_language"] = adjusted.get("risk_language", 0.10) + 0.08

        # Emotion adjustments
        emotion = str(context_signals.get("user_emotion", "")).lower()
        if emotion in ["stressed", "frustrated", "concerned", "tense"]:
            adjusted["emotional_expressions"] = adjusted.get("emotional_expressions", 0.10) + 0.08
            adjusted["mentorship_phrases"] = adjusted.get("mentorship_phrases", 0.05) + 0.05
        elif emotion in ["excited", "positive", "celebratory"]:
            adjusted["energy_words"] = adjusted.get("energy_words", 0.05) + 0.10
            adjusted["humor_markers"] = adjusted.get("humor_markers", 0.02) + 0.05

        # Theme adjustments
        theme = str(context_signals.get("theme", "")).lower()
        if theme in ["strategic", "strategy", "decision"]:
            adjusted["decision_cadence"] = adjusted.get("decision_cadence", 0.10) + 0.08
            adjusted["transparency_phrases"] = adjusted.get("transparency_phrases", 0.10) + 0.05
        elif theme in ["personal", "people", "hr"]:
            adjusted["mentorship_phrases"] = adjusted.get("mentorship_phrases", 0.05) + 0.10
            adjusted["emotional_expressions"] = adjusted.get("emotional_expressions", 0.10) + 0.05
        elif theme in ["technical", "budget", "numbers"]:
            adjusted["numbers_cadence"] = adjusted.get("numbers_cadence", 0.10) + 0.10

        return adjusted

    def _normalize_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Normalize weights using softmax with temperature."""
        if not weights:
            return weights

        values = np.array(list(weights.values()))

        # Apply softmax with temperature
        # Shift values to prevent overflow
        values = values - np.max(values)
        exp_values = np.exp(values / self._temperature)
        softmax_values = exp_values / exp_values.sum()

        return {k: float(v) for k, v in zip(weights.keys(), softmax_values)}

    def _sharpen_weights(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        Sharpen weights to prevent over-smoothing from semantic blending.

        Weights above threshold get boosted by multiplier, capped at max.
        Then re-normalized to sum to 1.0.

        This preserves differentiation between high and low priority categories.
        """
        if not self._enable_sharpening:
            return weights

        sharpened = {}
        for category, weight in weights.items():
            if weight >= self._sharpen_threshold:
                # Boost weights above threshold
                boosted = weight * self._sharpen_multiplier
                sharpened[category] = min(boosted, self._sharpen_cap)
            else:
                # Slightly reduce low weights to increase contrast
                sharpened[category] = weight * 0.9

        # Re-normalize to sum to 1.0
        total = sum(sharpened.values())
        if total > 0:
            sharpened = {k: v / total for k, v in sharpened.items()}

        return sharpened

    def get_weighted_voiceprint(
        self,
        voiceprint: Dict[str, Any],
        attention_weights: AttentionWeights,
        top_k: int = 7,
        min_weight: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Create weighted voiceprint subset for prompt assembly.

        High-weight categories get:
        - More examples included
        - Explicit emphasis instructions
        - Earlier placement in prompt

        Args:
            voiceprint: Full voiceprint dictionary
            attention_weights: Computed attention weights
            top_k: Maximum categories to include
            min_weight: Minimum weight to include

        Returns:
            Weighted voiceprint subset with emphasis markers
        """
        weights_dict = attention_weights.to_dict()

        # Sort by weight
        sorted_categories = sorted(
            weights_dict.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:top_k]

        weighted_vp = {}

        for category, weight in sorted_categories:
            if weight < min_weight:
                continue

            if category not in voiceprint and category != "lexicon":
                continue

            emphasis = attention_weights.get_emphasis_level(category)

            # Determine example count based on emphasis
            if emphasis == "CRITICAL":
                n_examples = 5
            elif emphasis == "HIGH":
                n_examples = 3
            elif emphasis == "MEDIUM":
                n_examples = 2
            else:
                n_examples = 1

            # Get category data
            if category == "lexicon":
                # Special handling for lexicon (may be top-level in voiceprint data)
                cat_data = voiceprint.get("lexicon", [])
                if isinstance(cat_data, list):
                    weighted_vp[category] = {
                        "weight": weight,
                        "emphasis": emphasis,
                        "phrases": cat_data[:n_examples * 3],
                        "instruction": self._get_emphasis_instruction(emphasis, category),
                    }
            else:
                cat_data = voiceprint.get(category, {})
                if isinstance(cat_data, dict):
                    examples = cat_data.get("examples", [])
                    if not examples:
                        examples = cat_data.get("phrases", [])
                    if not examples:
                        examples = cat_data.get("alternatives", [])

                    weighted_vp[category] = {
                        "weight": weight,
                        "emphasis": emphasis,
                        "data": {
                            **cat_data,
                            "examples": examples[:n_examples],
                        },
                        "instruction": self._get_emphasis_instruction(emphasis, category),
                    }

        return weighted_vp

    def _get_emphasis_instruction(self, emphasis: str, category: str) -> str:
        """Get prompt instruction based on emphasis level."""
        category_readable = category.replace("_", " ")

        if emphasis == "CRITICAL":
            return f"YOU MUST USE {category_readable} prominently in your response"
        elif emphasis == "HIGH":
            return f"Strongly emphasize {category_readable}"
        elif emphasis == "MEDIUM":
            return f"Include {category_readable} naturally"
        else:
            return f"May use {category_readable} if appropriate"


# Singleton instance
_default_attention: Optional[SemanticAttention] = None


def get_semantic_attention() -> SemanticAttention:
    """Get singleton SemanticAttention instance with config values."""
    global _default_attention
    if _default_attention is None:
        _default_attention = create_semantic_attention_from_config()
    return _default_attention


def create_semantic_attention(
    pattern_weight: float = 0.6,
    semantic_weight: float = 0.4,
    temperature: float = 0.5,
    enable_sharpening: bool = True,
    sharpen_threshold: float = None,
    sharpen_multiplier: float = None,
    sharpen_cap: float = None,
) -> SemanticAttention:
    """Create new SemanticAttention instance with explicit parameters."""
    return SemanticAttention(
        pattern_weight=pattern_weight,
        semantic_weight=semantic_weight,
        temperature=temperature,
        enable_sharpening=enable_sharpening,
        sharpen_threshold=sharpen_threshold,
        sharpen_multiplier=sharpen_multiplier,
        sharpen_cap=sharpen_cap,
    )


def create_semantic_attention_from_config() -> SemanticAttention:
    """
    Create SemanticAttention instance using API config values.

    Reads configuration from api.config.settings for A/B testing support.
    Falls back to defaults if config is not available.
    """
    try:
        from api.config import get_attention_config
        config = get_attention_config()
        logger.debug(f"Creating SemanticAttention from config: {config}")
        return SemanticAttention(
            pattern_weight=config.get("pattern_weight", 0.6),
            semantic_weight=config.get("semantic_weight", 0.4),
            temperature=config.get("temperature", 0.5),
            enable_sharpening=config.get("enable_sharpening", True),
            sharpen_threshold=config.get("sharpen_threshold"),
            sharpen_multiplier=config.get("sharpen_multiplier"),
            sharpen_cap=config.get("sharpen_cap"),
        )
    except ImportError:
        logger.debug("api.config not available, using default attention config")
        return SemanticAttention()


def reset_default_attention():
    """Reset singleton instance (for config changes or testing)."""
    global _default_attention
    _default_attention = None
    logger.debug("Default SemanticAttention instance reset")
