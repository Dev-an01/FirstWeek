"""
Urgency Classifier - Detects urgency level from language patterns.

Uses keyword/pattern matching for fast, deterministic classification.
Target latency: 1ms.
"""

import re
import logging
from typing import Tuple, List, Dict

from ..models import Urgency

logger = logging.getLogger(__name__)


class UrgencyClassifier:
    """
    Detect urgency level from language patterns.

    Levels:
    - crisis: Immediate action needed, emergency
    - urgent: Time-sensitive, needs quick response
    - routine: Normal business cadence
    - planning: Future-oriented, no immediate pressure

    Thread-safe: No mutable state, can be shared across requests.
    """

    # Pattern dictionaries for each urgency level
    URGENCY_PATTERNS: Dict[str, List[str]] = {
        "crisis": [
            # Emergency keywords
            r"\b(emergency|critical|crisis)\b",
            r"\b(urgent.*immediately|immediately.*urgent)\b",
            r"\b(right\s*now|this\s*instant|drop\s*everything)\b",

            # System/service issues
            r"\b(outage|down|broken|crashed|failed|failing)\b",
            r"\b(breach|hacked|attack|compromised)\b",
            r"\b(production\s*(is\s*)?(down|broken|failing))\b",

            # Legal/regulatory
            r"\b(lawsuit|legal\s*action|regulatory.*deadline)\b",
            r"\b(compliance.*violation|violation.*compliance)\b",

            # Punctuation signals
            r"!!+",
            r"URGENT|CRITICAL|EMERGENCY|ASAP!",
        ],
        "urgent": [
            # Time-sensitive keywords
            r"\b(urgent|urgently|asap|a\.s\.a\.p)\b",
            r"\b(quickly|quick|fast|immediately)\b",
            r"\b(soon|today|tonight|by\s*EOD|end\s*of\s*day)\b",
            r"\b(this\s*week|tomorrow|by\s*monday|by\s*friday)\b",

            # Deadline language
            r"\b(deadline\s*(is\s*)?(approaching|coming|soon))\b",
            r"\b(time-?\s*sensitive|time\s*critical)\b",
            r"\b(pressing|rush|rushed)\b",
            r"\b(need.*quickly|need.*soon|need.*today)\b",

            # Priority indicators
            r"\b(high\s*priority|top\s*priority|priority\s*one)\b",
            r"\b(can't\s*wait|cannot\s*wait|waiting\s*on\s*this)\b",
        ],
        "planning": [
            # Future-oriented
            r"\b(next\s*quarter|next\s*year|next\s*month)\b",
            r"\b(long-?\s*term|long\s*run|future)\b",
            r"\b(eventually|someday|down\s*the\s*road)\b",
            r"\b(5-?\s*year|three-?\s*year|multi-?\s*year)\b",

            # Planning language
            r"\b(planning|plan\s*for|roadmap)\b",
            r"\b(strategy\s*session|brainstorm|ideation)\b",
            r"\b(thinking\s*about|considering|exploring)\b",

            # Hypothetical language
            r"\b(when\s*should\s*we|how\s*might\s*we|could\s*we\s*consider)\b",
            r"\b(what\s*if\s*we|hypothetically|in\s*theory)\b",
            r"\b(no\s*rush|whenever|at\s*your\s*convenience)\b",
        ],
        # routine is the default - no patterns needed
    }

    # Punctuation analysis weights
    EXCLAMATION_WEIGHT = 0.1  # Per exclamation mark (max 3)
    CAPS_WEIGHT = 0.15  # If significant caps usage

    def __init__(self):
        """Initialize UrgencyClassifier with compiled patterns."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()
        logger.debug("UrgencyClassifier initialized with 4 urgency levels")

    def _compile_patterns(self) -> None:
        """Compile all patterns for performance."""
        for urgency, patterns in self.URGENCY_PATTERNS.items():
            self._compiled_patterns[urgency] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]

    def classify(self, query: str) -> Tuple[Urgency, float]:
        """
        Classify query urgency level.

        Args:
            query: User's query text

        Returns:
            Tuple of (Urgency, confidence)
            - Urgency: Classified urgency enum
            - confidence: 0.0 to 1.0
        """
        query_lower = query.lower()

        scores: Dict[str, float] = {}
        matched_patterns: Dict[str, List[str]] = {}

        # Score each urgency level based on pattern matches
        for urgency, patterns in self._compiled_patterns.items():
            matches = []
            for pattern in patterns:
                if pattern.search(query):  # Use original query for case-sensitive patterns
                    matches.append(pattern.pattern)

            if matches:
                # Base score: proportion of patterns matched
                base_score = len(matches) / len(patterns)

                # Boost for multiple matches
                if len(matches) >= 2:
                    base_score = min(base_score + 0.2, 1.0)
                if len(matches) >= 3:
                    base_score = min(base_score + 0.15, 1.0)

                scores[urgency] = base_score
                matched_patterns[urgency] = matches

        # Apply punctuation analysis
        punctuation_boost = self._analyze_punctuation(query)

        # Boost crisis/urgent scores based on punctuation
        if punctuation_boost > 0:
            if "crisis" in scores:
                scores["crisis"] = min(scores["crisis"] + punctuation_boost, 1.0)
            elif "urgent" in scores:
                scores["urgent"] = min(scores["urgent"] + punctuation_boost, 1.0)
            elif punctuation_boost >= 0.2:
                # Strong punctuation signals with no other matches → urgent
                scores["urgent"] = punctuation_boost

        # Select best match
        if scores:
            best_urgency = max(scores, key=scores.get)
            confidence = scores[best_urgency]

            # Crisis should have high confidence threshold
            if best_urgency == "crisis" and confidence < 0.3:
                # Downgrade to urgent if crisis confidence is low
                if "urgent" in scores and scores["urgent"] >= 0.2:
                    best_urgency = "urgent"
                    confidence = scores["urgent"]

            logger.debug(
                f"Urgency classified as '{best_urgency}' "
                f"(confidence: {confidence:.2f})"
            )

            return Urgency(best_urgency), confidence

        # No patterns matched - return ROUTINE
        logger.debug("No urgency patterns matched, returning ROUTINE")
        return Urgency.ROUTINE, 0.7  # High confidence for default

    def _analyze_punctuation(self, query: str) -> float:
        """
        Analyze punctuation for urgency signals.

        Returns boost value (0.0 to 0.3).
        """
        boost = 0.0

        # Count exclamation marks
        exclamation_count = query.count('!')
        if exclamation_count > 0:
            boost += min(exclamation_count * self.EXCLAMATION_WEIGHT, 0.3)

        # Check for significant caps usage (more than 30% caps and at least 5 chars)
        alpha_chars = [c for c in query if c.isalpha()]
        if len(alpha_chars) >= 5:
            caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
            if caps_ratio > 0.3:
                boost += self.CAPS_WEIGHT

        return min(boost, 0.3)

    def is_time_sensitive(self, query: str) -> bool:
        """
        Quick check if query has any time-sensitive language.

        Useful for fast filtering.
        """
        urgency, confidence = self.classify(query)
        return urgency in [Urgency.CRISIS, Urgency.URGENT] and confidence >= 0.3


# Singleton instance for stateless use
_default_classifier: UrgencyClassifier = None


def get_urgency_classifier() -> UrgencyClassifier:
    """Get singleton UrgencyClassifier instance."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = UrgencyClassifier()
    return _default_classifier
