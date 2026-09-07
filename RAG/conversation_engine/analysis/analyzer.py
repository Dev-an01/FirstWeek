"""
Context Analyzer - Orchestrates query classification for the Conversation Engine.

Stage 1 of the 5-stage pipeline.
Consumes ManagedContext from Phase 2, produces AnalyzedContext.

Target latency: 5-8ms total.
"""

import re
import time
import logging
from typing import Optional, List, Dict, Any, Tuple, TYPE_CHECKING

from .models import (
    Theme,
    Urgency,
    UserEmotion,
    TurnType,
    QueryType,
    AnalyzedContext,
)
from .classifiers import (
    ThemeClassifier,
    UrgencyClassifier,
    EmotionClassifier,
    TurnTypeClassifier,
)

if TYPE_CHECKING:
    from ..context.models import ManagedContext
    from llm_integration.prompt_builder import RetrievalContext

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """
    Stage 1: Analyze query for theme, urgency, emotion, and turn type.

    Uses keyword/pattern-based classification for fast, deterministic results.
    No LLM calls - must complete in <10ms.

    Classification outputs:
    - theme: security|budget|people|strategy|technical|operations|customer|other
    - urgency: crisis|urgent|routine|planning
    - user_emotion: stressed|tense|neutral|positive|celebratory
    - query_type: factual|decision|emotional|analytical
    - turn_type: new_topic|followup|clarification|emotional_shift (multi-turn only)
    - formality: board|team_wide|1on1|slack

    Thread-safe: Classifiers are stateless, can be shared across requests.
    """

    # Query type patterns
    QUERY_TYPE_PATTERNS: Dict[str, List[str]] = {
        "factual": [
            r"^what\s+(is|are|was|were)\b",
            r"^who\s+(is|are|was|were)\b",
            r"^when\s+(is|was|did|does)\b",
            r"^where\s+(is|are|was|were)\b",
            r"^how\s+(many|much|long|often)\b",
            r"\b(status|update|summary|overview)\b",
            r"\b(list|show|tell\s*me|give\s*me)\b",
        ],
        "decision": [
            r"^should\s+(we|I|they)\b",
            r"\b(recommend|suggest|advise)\b",
            r"\b(approve|reject|accept|decline)\b",
            r"^what\s+(would|do)\s+you\s+(recommend|suggest|think)\b",
            r"\b(decision|decide|choose|select|pick)\b",
            r"^how\s+(would|should)\s+(we|I|you)\b",
            r"\b(best\s+approach|best\s+way|right\s+move)\b",
        ],
        "emotional": [
            r"\b(feel|feeling|felt)\b",
            r"\b(worried|concerned|anxious|stressed)\b",
            r"\b(frustrated|annoyed|upset|angry)\b",
            r"\b(excited|happy|thrilled|relieved)\b",
            r"\b(help|support|guidance)\b",
            r"\b(struggling|overwhelmed|confused)\b",
        ],
        "analytical": [
            r"\b(analyze|analysis|evaluate|assessment)\b",
            r"\b(compare|comparison|contrast|versus|vs)\b",
            r"\b(pros?\s*and\s*cons?|tradeoffs?|trade-offs?)\b",
            r"\b(impact|implications|consequences)\b",
            r"\b(why|reason|cause|explain)\b",
            r"\b(breakdown|deep\s*dive|drill\s*down)\b",
        ],
    }

    # Formality detection patterns
    FORMALITY_PATTERNS: Dict[str, List[str]] = {
        "board": [
            r"\b(board|directors|shareholders|investors)\b",
            r"\b(quarterly\s*review|annual\s*report|earnings)\b",
            r"\b(fiduciary|governance|compliance\s*report)\b",
        ],
        "slack": [
            r"\b(hey|hi|yo|sup)\b",
            r"\b(quick\s*question|btw|fyi|imo|imho)\b",
            r"\b(lol|haha|:[\)\(]|:\-[\)\(])\b",
            r"^(so|ok|okay|alright)\b",
        ],
        "1on1": [
            r"\b(between\s*us|confidential|private)\b",
            r"\b(personal|personally|my\s*opinion)\b",
            r"\b(off\s*the\s*record|just\s*between)\b",
        ],
        # team_wide is the default
    }

    def __init__(self):
        """Initialize ContextAnalyzer with all classifiers."""
        self._theme_classifier = ThemeClassifier()
        self._urgency_classifier = UrgencyClassifier()
        self._emotion_classifier = EmotionClassifier()
        self._turn_type_classifier = TurnTypeClassifier()

        # Compile query type patterns
        self._compiled_query_patterns: Dict[str, List[re.Pattern]] = {}
        for qtype, patterns in self.QUERY_TYPE_PATTERNS.items():
            self._compiled_query_patterns[qtype] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        # Compile formality patterns
        self._compiled_formality_patterns: Dict[str, List[re.Pattern]] = {}
        for formality, patterns in self.FORMALITY_PATTERNS.items():
            self._compiled_formality_patterns[formality] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        logger.info("ContextAnalyzer initialized with all classifiers")

    def analyze(
        self,
        query: str,
        managed_context: "ManagedContext",
        retrieved_context: Optional["RetrievalContext"] = None,
    ) -> AnalyzedContext:
        """
        Main entry point - returns complete analysis.

        Orchestrates all classifiers and aggregates results.

        Args:
            query: User's query text (use resolved_query from managed_context if available)
            managed_context: ManagedContext from Phase 2
            retrieved_context: Optional retrieval results for entity extraction

        Returns:
            AnalyzedContext with all classification results
        """
        start_time = time.time()

        # Use resolved query if available
        effective_query = managed_context.resolved_query or query

        # Extract entities from retrieved context
        entities = self._extract_entities(retrieved_context)

        # Get emotional trend from session state
        emotional_trend = "stable"
        if managed_context.session_state:
            emotional_trend = managed_context.session_state.get_emotional_trend()

        try:
            # 1. Classify theme
            theme, theme_confidence = self._theme_classifier.classify(
                effective_query, entities
            )

            # 2. Classify urgency
            urgency, urgency_confidence = self._urgency_classifier.classify(
                effective_query
            )

            # 3. Classify emotion
            user_emotion, emotion_confidence = self._emotion_classifier.classify(
                effective_query, emotional_trend
            )

            # 4. Classify query type
            query_type, query_type_confidence = self._classify_query_type(
                effective_query
            )

            # 5. Classify turn type (multi-turn only)
            turn_type, turn_confidence = self._turn_type_classifier.classify(
                effective_query, managed_context
            )

            # 6. Determine formality
            formality = self._determine_formality(effective_query)

            # 7. Extract keywords
            keywords = self._extract_keywords(effective_query)

            # 8. Determine if topic should continue
            continue_topic = self._turn_type_classifier.should_continue_topic(
                effective_query, managed_context
            )

            # 9. Calculate topic match score
            topic_match_score = self._calculate_topic_match(
                effective_query, managed_context
            )

            # 10. Suggest topic if new
            suggested_topic = None
            if turn_type == TurnType.NEW_TOPIC:
                suggested_topic = self._suggest_topic(effective_query, theme)

            # Calculate overall confidence
            classification_confidence = (
                theme_confidence * 0.3 +
                urgency_confidence * 0.2 +
                emotion_confidence * 0.2 +
                query_type_confidence * 0.3
            )

            elapsed_ms = (time.time() - start_time) * 1000

            # Build result
            analyzed = AnalyzedContext(
                theme=theme,
                urgency=urgency,
                user_emotion=user_emotion,
                query_type=query_type,
                formality=formality,
                turn_type=turn_type,
                emotional_trend=emotional_trend,
                resolved_query=effective_query,
                continue_topic=continue_topic,
                entities_detected=entities,
                keywords=keywords,
                topic_match_score=topic_match_score,
                suggested_topic=suggested_topic,
                classification_confidence=classification_confidence,
                theme_confidence=theme_confidence,
                urgency_confidence=urgency_confidence,
                emotion_confidence=emotion_confidence,
                analysis_time_ms=elapsed_ms,
            )

            logger.info(
                f"ContextAnalyzer.analyze completed",
                extra={
                    "theme": theme.value,
                    "urgency": urgency.value,
                    "user_emotion": user_emotion.value,
                    "query_type": query_type.value,
                    "turn_type": turn_type.value,
                    "formality": formality,
                    "confidence": classification_confidence,
                    "latency_ms": elapsed_ms,
                }
            )

            return analyzed

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"ContextAnalyzer.analyze failed: {e}")

            # Return defaults on error
            return AnalyzedContext(
                resolved_query=effective_query,
                analysis_time_ms=elapsed_ms,
            )

    def _classify_query_type(self, query: str) -> Tuple[QueryType, float]:
        """
        Classify query type (factual/decision/emotional/analytical).

        Args:
            query: Query text

        Returns:
            Tuple of (QueryType, confidence)
        """
        scores: Dict[str, float] = {}

        for qtype, patterns in self._compiled_query_patterns.items():
            matches = sum(1 for p in patterns if p.search(query))
            if matches > 0:
                scores[qtype] = matches / len(patterns)
                if matches >= 2:
                    scores[qtype] = min(scores[qtype] + 0.2, 1.0)

        if scores:
            best_type = max(scores, key=scores.get)
            return QueryType(best_type), scores[best_type]

        # Default to factual
        return QueryType.FACTUAL, 0.5

    def _determine_formality(self, query: str) -> str:
        """
        Determine appropriate formality level.

        Returns one of: board, team_wide, 1on1, slack
        """
        for formality, patterns in self._compiled_formality_patterns.items():
            matches = sum(1 for p in patterns if p.search(query))
            if matches >= 1:
                return formality

        # Default to team_wide
        return "team_wide"

    def _extract_entities(
        self,
        retrieved_context: Optional["RetrievalContext"],
    ) -> List[str]:
        """Extract entities from retrieved context."""
        entities = []

        if not retrieved_context:
            return entities

        try:
            # Extract from graph results if available
            if hasattr(retrieved_context, 'graph_results'):
                for result in retrieved_context.graph_results or []:
                    if isinstance(result, dict):
                        entity = result.get('entity') or result.get('name')
                        if entity:
                            entities.append(entity)

            # Extract from vector results if available
            if hasattr(retrieved_context, 'vector_results'):
                for result in retrieved_context.vector_results or []:
                    if isinstance(result, dict):
                        metadata = result.get('metadata', {})
                        if metadata.get('entity_type') == 'company':
                            entities.append(metadata.get('entity_name', ''))

        except Exception as e:
            logger.debug(f"Entity extraction failed: {e}")

        return [e for e in entities if e]  # Filter empty

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query."""
        # Simple keyword extraction
        words = re.findall(r'\b[a-zA-Z]{3,}\b', query.lower())

        # Filter common words
        stop_words = {
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
            'can', 'had', 'her', 'was', 'one', 'our', 'out', 'has',
            'have', 'been', 'were', 'they', 'this', 'what', 'when',
            'where', 'which', 'will', 'with', 'would', 'there', 'their',
            'about', 'could', 'should', 'would', 'from', 'that', 'into',
        }

        keywords = [w for w in words if w not in stop_words]
        return keywords[:10]  # Limit to top 10

    def _calculate_topic_match(
        self,
        query: str,
        managed_context: "ManagedContext",
    ) -> float:
        """Calculate similarity to previous topic."""
        if not managed_context.session_state:
            return 0.0

        current_topic = managed_context.session_state.current_topic
        if not current_topic:
            return 0.0

        # Simple keyword overlap
        query_words = set(self._extract_keywords(query))
        topic_words = set(self._extract_keywords(current_topic))

        if not query_words or not topic_words:
            return 0.0

        intersection = len(query_words & topic_words)
        union = len(query_words | topic_words)

        return intersection / union if union > 0 else 0.0

    def _suggest_topic(self, query: str, theme: Theme) -> str:
        """Suggest topic label for new topic turns."""
        keywords = self._extract_keywords(query)

        # Combine theme with key terms
        if keywords:
            key_term = keywords[0].title()
            return f"{theme.value.title()}: {key_term}"

        return theme.value.title()


# Factory function for dependency injection
def create_context_analyzer() -> ContextAnalyzer:
    """Create a new ContextAnalyzer instance."""
    return ContextAnalyzer()


# Singleton instance for stateless use
_default_analyzer: ContextAnalyzer = None


def get_context_analyzer() -> ContextAnalyzer:
    """Get singleton ContextAnalyzer instance."""
    global _default_analyzer
    if _default_analyzer is None:
        _default_analyzer = ContextAnalyzer()
    return _default_analyzer
