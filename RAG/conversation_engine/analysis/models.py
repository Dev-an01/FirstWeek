"""
Context Analysis Data Models

Defines enums and dataclasses for query classification.
Used by Stage 1 (Context Analyzer) of the Conversation Engine.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


class Theme(Enum):
    """
    Primary theme/domain of the query.

    Used to select appropriate examples and calibrate response style.
    """
    SECURITY = "security"        # Security incidents, compliance, audits
    BUDGET = "budget"            # Financial decisions, costs, ROI
    PEOPLE = "people"            # HR, team issues, performance, hiring
    STRATEGY = "strategy"        # Business strategy, market positioning
    TECHNICAL = "technical"      # Architecture, technology decisions
    OPERATIONS = "operations"    # Day-to-day operations, processes
    CUSTOMER = "customer"        # Customer issues, feedback, relationships
    OTHER = "other"              # Catch-all for unclassified queries


class Urgency(Enum):
    """
    Urgency level of the query.

    Affects response tone and whether to offer immediate assistance.
    """
    CRISIS = "crisis"            # Immediate action needed, emergency
    URGENT = "urgent"            # Time-sensitive, needs quick response
    ROUTINE = "routine"          # Normal business cadence
    PLANNING = "planning"        # Future-oriented, no immediate pressure


class UserEmotion(Enum):
    """
    Detected emotional state of the user.

    Used to calibrate warmth level and tone of response.
    """
    STRESSED = "stressed"        # High anxiety, overwhelmed
    TENSE = "tense"              # Some concern, not relaxed
    NEUTRAL = "neutral"          # Normal state, no strong emotion
    POSITIVE = "positive"        # Good mood, optimistic
    CELEBRATORY = "celebratory"  # Excited, celebrating achievement


class TurnType(Enum):
    """
    Type of turn in multi-turn conversation.

    Used to adjust response length and content.
    """
    NEW_TOPIC = "new_topic"              # Starting a new topic
    FOLLOWUP = "followup"                # Following up on previous topic
    CLARIFICATION = "clarification"      # Asking for clarification
    EMOTIONAL_SHIFT = "emotional_shift"  # Emotional response to previous turn


class QueryType(Enum):
    """
    Type of information being requested.

    Determines whether to include precedents, examples, etc.
    """
    FACTUAL = "factual"          # Looking for facts, data, information
    DECISION = "decision"        # Seeking decision guidance, advice
    EMOTIONAL = "emotional"      # Seeking support, empathy
    ANALYTICAL = "analytical"    # Seeking analysis, reasoning


@dataclass
class AnalyzedContext:
    """
    Output of Context Analyzer (Stage 1).

    Contains all classification results for use by subsequent stages.
    """
    # Primary classification
    theme: Theme = Theme.OTHER
    urgency: Urgency = Urgency.ROUTINE
    user_emotion: UserEmotion = UserEmotion.NEUTRAL
    query_type: QueryType = QueryType.FACTUAL
    formality: str = "team_wide"  # board, team_wide, 1on1, slack

    # Multi-turn analysis (populated if SESSION or MEMORY_AWARE mode)
    turn_type: TurnType = TurnType.NEW_TOPIC
    emotional_trend: str = "stable"  # stable, improving, declining
    resolved_query: Optional[str] = None  # Query with references resolved
    continue_topic: bool = False  # Should continue on same topic

    # Detected entities and keywords
    entities_detected: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    # Topic continuation
    topic_match_score: float = 0.0  # Similarity to previous topic
    suggested_topic: Optional[str] = None

    # Confidence scores
    classification_confidence: float = 0.8
    theme_confidence: float = 0.8
    urgency_confidence: float = 0.8
    emotion_confidence: float = 0.8

    # Analysis timing
    analysis_time_ms: float = 0.0

    def is_crisis(self) -> bool:
        """Check if this is a crisis situation requiring special handling."""
        return self.urgency == Urgency.CRISIS

    def is_decision_query(self) -> bool:
        """Check if this query is asking for decision guidance."""
        return self.query_type == QueryType.DECISION

    def needs_empathy(self) -> bool:
        """Check if user needs empathetic response."""
        return (
            self.user_emotion in [UserEmotion.STRESSED, UserEmotion.TENSE]
            or self.emotional_trend == "declining"
            or self.query_type == QueryType.EMOTIONAL
        )

    def is_followup(self) -> bool:
        """Check if this is a follow-up turn."""
        return self.turn_type in [TurnType.FOLLOWUP, TurnType.CLARIFICATION]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/debugging."""
        return {
            "theme": self.theme.value,
            "urgency": self.urgency.value,
            "user_emotion": self.user_emotion.value,
            "query_type": self.query_type.value,
            "formality": self.formality,
            "turn_type": self.turn_type.value,
            "emotional_trend": self.emotional_trend,
            "resolved_query": self.resolved_query,
            "continue_topic": self.continue_topic,
            "entities_detected": self.entities_detected,
            "keywords": self.keywords,
            "classification_confidence": self.classification_confidence,
            "analysis_time_ms": self.analysis_time_ms,
        }
