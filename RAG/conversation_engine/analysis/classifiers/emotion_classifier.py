"""
Emotion Classifier - Detects user emotional state from language cues.

Uses keyword/pattern matching plus emotional trend integration.
Target latency: 1-2ms.
"""

import re
import logging
from typing import Tuple, List, Dict, Optional

from ..models import UserEmotion

logger = logging.getLogger(__name__)


class EmotionClassifier:
    """
    Detect user emotional state from language cues.

    States:
    - stressed: High anxiety, overwhelmed
    - tense: Some concern, not relaxed
    - neutral: Normal state, no strong emotion
    - positive: Good mood, optimistic
    - celebratory: Excited, celebrating achievement

    Also considers emotional_trend from session state for continuity.

    Thread-safe: No mutable state, can be shared across requests.
    """

    # Pattern dictionaries for each emotional state
    EMOTION_PATTERNS: Dict[str, List[str]] = {
        "stressed": [
            # Direct stress expressions
            r"\b(overwhelmed|stressed|anxious|worried|panick)\b",
            r"\b(struggling|drowning|swamped|buried)\b",
            r"\b(can't\s*cope|too\s*much|at\s*my\s*limit)\b",

            # Help-seeking language
            r"\b(help|please\s*help|I\s*don't\s*know\s*what\s*to\s*do)\b",
            r"\b(desperate|desperately|at\s*a\s*loss)\b",

            # Pressure language
            r"\b(pressure|pressured|deadline|running\s*out\s*of\s*time)\b",
            r"\b(can't\s*sleep|losing\s*sleep|up\s*all\s*night)\b",

            # Overwhelm signals
            r"\b(everything\s*is|it's\s*all|all\s*of\s*this)\b.*\b(falling\s*apart|too\s*much|overwhelming)\b",
        ],
        "tense": [
            # Frustration
            r"\b(frustrat(ed|ing)|annoy(ed|ing)|irritat(ed|ing))\b",
            r"\b(difficult|tough|hard|challenging)\b",

            # Concern
            r"\b(concerned|concerning|worry|worrying)\b",
            r"\b(issue|problem|trouble|blocker)\b",

            # Disappointment
            r"\b(not\s*happy|disappointed|disappointing)\b",
            r"\b(let\s*down|letdown|missed|failed)\b",

            # Mild negative
            r"\b(unfortunately|sadly|regrettably)\b",
            r"\b(stuck|blocked|stalled)\b",
        ],
        "positive": [
            # Optimism
            r"\b(excited|exciting|optimistic|hopeful)\b",
            r"\b(looking\s*forward|can't\s*wait|eager)\b",
            r"\b(opportunity|opportunities|promising)\b",

            # Progress
            r"\b(progress|progressing|momentum|traction)\b",
            r"\b(improvement|improving|better|getting\s*better)\b",
            r"\b(success|successful|succeeded)\b",

            # Gratitude
            r"\b(thank|thanks|appreciate|grateful)\b",
            r"\b(helpful|great\s*help|really\s*helped)\b",

            # Confidence
            r"\b(confident|confidence|optimistic|bullish)\b",
        ],
        "celebratory": [
            # Strong positive
            r"\b(amazing|fantastic|incredible|awesome|wonderful)\b",
            r"\b(thrilled|ecstatic|overjoyed|delighted)\b",

            # Achievement
            r"\b(won|closed|landed|achieved|hit\s*(the\s*)?target)\b",
            r"\b(breakthrough|milestone|record|best\s*ever)\b",

            # Celebration language
            r"\b(celebrate|celebrating|congratulat|cheers)\b",
            r"\b(huge\s*news|great\s*news|big\s*win)\b",

            # Multiple exclamation marks
            r"[!]{2,}",
            # Party/celebration emojis (Unicode)
            r"[\U0001F389\U0001F38A\U00002728\U0001F44F]",
        ],
        # neutral is the default - no patterns needed
    }

    # Emotional trend influence weights
    TREND_WEIGHTS = {
        "declining": {
            # If trend is declining, boost negative emotion detection
            "stressed": 0.15,
            "tense": 0.10,
        },
        "improving": {
            # If trend is improving, boost positive emotion detection
            "positive": 0.15,
            "celebratory": 0.10,
        },
        "stable": {},  # No adjustments
    }

    def __init__(self):
        """Initialize EmotionClassifier with compiled patterns."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()
        logger.debug("EmotionClassifier initialized with 5 emotional states")

    def _compile_patterns(self) -> None:
        """Compile all patterns for performance."""
        for emotion, patterns in self.EMOTION_PATTERNS.items():
            self._compiled_patterns[emotion] = [
                re.compile(pattern, re.IGNORECASE | re.UNICODE)
                for pattern in patterns
            ]

    def classify(
        self,
        query: str,
        emotional_trend: Optional[str] = None,
    ) -> Tuple[UserEmotion, float]:
        """
        Classify user emotional state.

        Args:
            query: User's query text
            emotional_trend: Optional trend from session ("stable", "improving", "declining")

        Returns:
            Tuple of (UserEmotion, confidence)
            - UserEmotion: Classified emotion enum
            - confidence: 0.0 to 1.0
        """
        emotional_trend = emotional_trend or "stable"

        scores: Dict[str, float] = {}
        matched_patterns: Dict[str, List[str]] = {}

        # Score each emotion based on pattern matches
        for emotion, patterns in self._compiled_patterns.items():
            matches = []
            for pattern in patterns:
                if pattern.search(query):
                    matches.append(pattern.pattern)

            if matches:
                # Base score: proportion of patterns matched
                base_score = len(matches) / len(patterns)

                # Boost for multiple matches
                if len(matches) >= 2:
                    base_score = min(base_score + 0.2, 1.0)
                if len(matches) >= 3:
                    base_score = min(base_score + 0.15, 1.0)

                scores[emotion] = base_score
                matched_patterns[emotion] = matches

        # Apply emotional trend influence
        trend_adjustments = self.TREND_WEIGHTS.get(emotional_trend, {})
        for emotion, boost in trend_adjustments.items():
            if emotion in scores:
                scores[emotion] = min(scores[emotion] + boost, 1.0)
            elif boost >= 0.1:
                # Add slight score even without direct matches if trend is strong
                scores[emotion] = boost * 0.5

        # Select best match
        if scores:
            best_emotion = max(scores, key=scores.get)
            confidence = scores[best_emotion]

            # Validate emotion makes sense
            # Don't classify as celebratory with low confidence
            if best_emotion == "celebratory" and confidence < 0.25:
                # Check for positive instead
                if "positive" in scores and scores["positive"] >= 0.2:
                    best_emotion = "positive"
                    confidence = scores["positive"]
                else:
                    best_emotion = "neutral"
                    confidence = 0.6

            logger.debug(
                f"Emotion classified as '{best_emotion}' "
                f"(confidence: {confidence:.2f}, trend: {emotional_trend})"
            )

            return UserEmotion(best_emotion), confidence

        # No patterns matched - return NEUTRAL
        logger.debug("No emotion patterns matched, returning NEUTRAL")
        return UserEmotion.NEUTRAL, 0.7

    def get_emotional_intensity(self, query: str) -> str:
        """
        Get emotional intensity level (low/medium/high).

        Useful for calibrating response warmth.
        """
        emotion, confidence = self.classify(query)

        if confidence >= 0.6:
            return "high"
        elif confidence >= 0.35:
            return "medium"
        else:
            return "low"

    def needs_empathy(self, query: str, emotional_trend: Optional[str] = None) -> bool:
        """
        Quick check if query indicates user needs empathetic response.

        Returns True if user appears stressed, tense, or emotional trend is declining.
        """
        emotion, confidence = self.classify(query, emotional_trend)

        if emotion in [UserEmotion.STRESSED, UserEmotion.TENSE]:
            return True

        if emotional_trend == "declining":
            return True

        return False


# Singleton instance for stateless use
_default_classifier: EmotionClassifier = None


def get_emotion_classifier() -> EmotionClassifier:
    """Get singleton EmotionClassifier instance."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = EmotionClassifier()
    return _default_classifier
