"""
Turn Type Classifier - Classifies turn type for multi-turn conversations.

Uses pattern matching plus topic similarity analysis.
Target latency: 2-3ms.
"""

import re
import logging
from typing import Tuple, List, Dict, Optional, Set, TYPE_CHECKING

from ..models import TurnType

if TYPE_CHECKING:
    from ...context.models import ManagedContext

logger = logging.getLogger(__name__)


class TurnTypeClassifier:
    """
    Classify turn type for multi-turn conversations.

    Types:
    - new_topic: Starting a new topic
    - followup: Following up on previous topic
    - clarification: Asking for clarification
    - emotional_shift: Emotional response to previous turn

    Uses:
    - Query patterns
    - Topic similarity to previous turns (keyword overlap)
    - Session state (topic_history, current_topic)

    Thread-safe: No mutable state, can be shared across requests.
    """

    # Pattern dictionaries for each turn type
    TURN_TYPE_PATTERNS: Dict[str, List[str]] = {
        "followup": [
            # Continuation signals
            r"^(and|also|additionally|furthermore|moreover)\b",
            r"^(what\s*about|how\s*about|regarding|concerning)\b",
            r"^(speaking\s*of|on\s*that\s*note|related\s*to)\b",

            # Reference to previous
            r"\b(you\s*mentioned|as\s*you\s*said|you\s*said)\b",
            r"\b(following\s*up|to\s*follow\s*up|as\s*a\s*follow-?up)\b",
            r"\b(going\s*back\s*to|returning\s*to)\b",

            # Continuation words
            r"\b(more|further|additional|another)\b",
            r"\b(else|other|beyond\s*that)\b",

            # Article references (the/that/this + topic words)
            r"\b(the|that|this)\s+(issue|topic|question|point|matter)\b",
            r"\b(the|that|this)\s+(decision|discussion|conversation)\b",
        ],
        "clarification": [
            # Direct clarification requests
            r"^(what\s*do\s*you\s*mean|can\s*you\s*explain)\b",
            r"^(I\s*don't\s*understand|not\s*sure\s*I\s*understand)\b",
            r"^(could\s*you\s*clarify|please\s*clarify)\b",

            # Elaboration requests
            r"\b(clarify|elaborate|expand\s*on|explain\s*further)\b",
            r"\b(more\s*detail|more\s*specific|be\s*more\s*specific)\b",
            r"\b(what\s*exactly|specifically|precisely)\b",

            # Rephrasing indicators
            r"^(so|meaning|in\s*other\s*words|you're\s*saying)\b",
            r"\b(rephrase|put\s*it\s*differently)\b",

            # Multiple questions (often seeking clarification)
            r"\?.*\?",
        ],
        "emotional_shift": [
            # Direct emotional expression
            r"\b(I\s*feel|I'm\s*feeling|this\s*makes\s*me)\b",
            r"\b(I'm\s*worried|I'm\s*concerned|I'm\s*frustrated)\b",
            r"\b(I'm\s*excited|I'm\s*thrilled|I'm\s*relieved)\b",

            # Emotional reactions
            r"\b(worried|concerned|anxious|stressed)\s+about\b",
            r"\b(excited|happy|thrilled|pleased)\s+about\b",

            # Gratitude/appreciation (emotional response)
            r"^(thank\s*you|thanks|I\s*appreciate)\b",
            r"\b(that\s*helps|that's\s*helpful|that\s*makes\s*sense)\b",

            # Relief/concern signals
            r"\b(what\s*a\s*relief|that's\s*reassuring|that\s*worries\s*me)\b",
        ],
        # new_topic is determined by low similarity to previous topic
    }

    # Keywords to exclude from topic similarity (stop words)
    STOP_WORDS: Set[str] = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "can", "this", "that", "these", "those",
        "i", "you", "we", "they", "he", "she", "it", "my", "your", "our",
        "their", "what", "which", "who", "whom", "when", "where", "why",
        "how", "all", "each", "every", "both", "few", "more", "most",
        "other", "some", "such", "no", "not", "only", "same", "so", "than",
        "too", "very", "just", "also", "now", "here", "there", "then",
        "about", "after", "before", "between", "into", "through", "during",
        "above", "below", "from", "up", "down", "in", "out", "on", "off",
        "over", "under", "again", "further", "once", "and", "but", "or",
        "yet", "for", "nor", "if", "because", "as", "until", "while",
        "of", "at", "by", "with", "to",
    }

    # Topic similarity thresholds
    TOPIC_SIMILARITY_THRESHOLD = 0.25  # Below this = new topic
    HIGH_SIMILARITY_THRESHOLD = 0.5  # Above this = strong followup signal

    def __init__(self):
        """Initialize TurnTypeClassifier with compiled patterns."""
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()
        logger.debug("TurnTypeClassifier initialized with 4 turn types")

    def _compile_patterns(self) -> None:
        """Compile all patterns for performance."""
        for turn_type, patterns in self.TURN_TYPE_PATTERNS.items():
            self._compiled_patterns[turn_type] = [
                re.compile(pattern, re.IGNORECASE)
                for pattern in patterns
            ]

    def classify(
        self,
        query: str,
        managed_context: Optional["ManagedContext"] = None,
    ) -> Tuple[TurnType, float]:
        """
        Classify turn type.

        Args:
            query: User's query text
            managed_context: Optional context with session state

        Returns:
            Tuple of (TurnType, confidence)
            - TurnType: Classified turn type enum
            - confidence: 0.0 to 1.0
        """
        # In STATELESS mode or first turn, always return NEW_TOPIC
        if managed_context is None or managed_context.get_turn_number() == 0:
            logger.debug("First turn or STATELESS mode, returning NEW_TOPIC")
            return TurnType.NEW_TOPIC, 0.9

        scores: Dict[str, float] = {}
        matched_patterns: Dict[str, List[str]] = {}

        # Score each turn type based on pattern matches
        for turn_type, patterns in self._compiled_patterns.items():
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

                scores[turn_type] = base_score
                matched_patterns[turn_type] = matches

        # Calculate topic similarity
        topic_similarity = self._calculate_topic_similarity(query, managed_context)

        # Adjust scores based on topic similarity
        if topic_similarity >= self.HIGH_SIMILARITY_THRESHOLD:
            # High similarity boosts followup
            if "followup" in scores:
                scores["followup"] = min(scores["followup"] + 0.2, 1.0)
            else:
                scores["followup"] = 0.4 + (topic_similarity * 0.3)
        elif topic_similarity < self.TOPIC_SIMILARITY_THRESHOLD:
            # Low similarity suggests new topic
            if not scores or max(scores.values()) < 0.4:
                scores["new_topic"] = 0.6 + ((1 - topic_similarity) * 0.2)

        # Select best match
        if scores:
            best_type = max(scores, key=scores.get)
            confidence = scores[best_type]

            logger.debug(
                f"Turn type classified as '{best_type}' "
                f"(confidence: {confidence:.2f}, "
                f"topic_similarity: {topic_similarity:.2f})"
            )

            return TurnType(best_type), confidence

        # Default: Check topic similarity for fallback
        if topic_similarity >= self.TOPIC_SIMILARITY_THRESHOLD:
            logger.debug(
                f"No patterns matched but topic similar, returning FOLLOWUP "
                f"(similarity: {topic_similarity:.2f})"
            )
            return TurnType.FOLLOWUP, 0.5
        else:
            logger.debug("No patterns matched and low topic similarity, returning NEW_TOPIC")
            return TurnType.NEW_TOPIC, 0.6

    def _calculate_topic_similarity(
        self,
        query: str,
        managed_context: "ManagedContext",
    ) -> float:
        """
        Calculate keyword overlap between query and previous topic.

        Uses simple keyword overlap (Jaccard-like) for speed.
        No embeddings to stay within latency budget.

        Returns:
            Similarity score 0.0 to 1.0
        """
        try:
            # Extract keywords from query
            query_keywords = self._extract_keywords(query)
            if not query_keywords:
                return 0.0

            # Get previous topic keywords
            previous_keywords: Set[str] = set()

            # From current topic
            if managed_context.session_state and managed_context.session_state.current_topic:
                previous_keywords.update(
                    self._extract_keywords(managed_context.session_state.current_topic)
                )

            # From recent turns
            if managed_context.turn_history:
                for turn in managed_context.turn_history[-2:]:  # Last 2 turns
                    previous_keywords.update(self._extract_keywords(turn.user_query))
                    if turn.topic:
                        previous_keywords.update(self._extract_keywords(turn.topic))

            if not previous_keywords:
                return 0.0

            # Calculate Jaccard-like similarity
            intersection = len(query_keywords & previous_keywords)
            union = len(query_keywords | previous_keywords)

            if union == 0:
                return 0.0

            similarity = intersection / union
            return similarity

        except Exception as e:
            logger.warning(f"Topic similarity calculation failed: {e}")
            return 0.0

    def _extract_keywords(self, text: str) -> Set[str]:
        """
        Extract meaningful keywords from text.

        Removes stop words and short words.
        """
        if not text:
            return set()

        # Simple tokenization
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())

        # Filter stop words and short words
        keywords = {
            word for word in words
            if word not in self.STOP_WORDS and len(word) >= 3
        }

        return keywords

    def should_continue_topic(
        self,
        query: str,
        managed_context: Optional["ManagedContext"] = None,
    ) -> bool:
        """
        Check if query should continue the current topic.

        Returns True if turn type is FOLLOWUP or CLARIFICATION.
        """
        turn_type, confidence = self.classify(query, managed_context)
        return turn_type in [TurnType.FOLLOWUP, TurnType.CLARIFICATION]


# Singleton instance for stateless use
_default_classifier: TurnTypeClassifier = None


def get_turn_type_classifier() -> TurnTypeClassifier:
    """Get singleton TurnTypeClassifier instance."""
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = TurnTypeClassifier()
    return _default_classifier
