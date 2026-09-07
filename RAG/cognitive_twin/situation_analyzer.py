"""
Situation Analyzer - Layer 4 of the Cognitive Twin system.

Understands WHY a question is being asked beyond the literal words.
Detects implicit needs, temporal context, emotional undertones, and urgency.

Key principle: A good executive reads between the lines. When someone asks
"What was Q3 performance?", they might really need help preparing for a
board meeting, or they're worried about their team's results.

This layer adds situational awareness to responses.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional

from .config import is_layer_enabled, get_layer_config

logger = logging.getLogger(__name__)


class EmotionalTone(Enum):
    """Detected emotional tone of query."""
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    CONCERNED = "concerned"
    FRUSTRATED = "frustrated"
    ENTHUSIASTIC = "enthusiastic"
    URGENT = "urgent"
    UNCERTAIN = "uncertain"


class UrgencyLevel(Enum):
    """Urgency level of the query."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ImplicitNeed(Enum):
    """Types of implicit needs detected."""
    DECISION_SUPPORT = "decision_support"
    VALIDATION = "validation"
    INFORMATION = "information"
    GUIDANCE = "guidance"
    REASSURANCE = "reassurance"
    PREPARATION = "preparation"
    COMPARISON = "comparison"
    TROUBLESHOOTING = "troubleshooting"


@dataclass
class TemporalContext:
    """Temporal context detected from query and timestamp."""
    is_board_season: bool = False  # Near board meeting
    is_quarter_end: bool = False   # Q1/Q2/Q3/Q4 end
    is_year_end: bool = False      # December/January
    is_planning_season: bool = False  # Budget planning time
    is_review_season: bool = False  # Performance review time
    time_of_day: str = "normal"    # morning, afternoon, evening, late_night
    day_of_week: str = "weekday"   # weekday, weekend
    days_until_eom: int = 15       # Days until end of month


@dataclass
class SituationContext:
    """Complete situational context for a query."""
    # What they really need
    implicit_needs: List[ImplicitNeed] = field(default_factory=list)
    need_description: str = ""

    # Emotional state
    emotional_tone: EmotionalTone = EmotionalTone.NEUTRAL
    urgency_level: UrgencyLevel = UrgencyLevel.NORMAL

    # Temporal context
    temporal_context: TemporalContext = field(default_factory=TemporalContext)

    # Anticipated follow-ups
    anticipated_followups: List[str] = field(default_factory=list)

    # Response guidance
    recommended_depth: str = "standard"  # brief, standard, comprehensive
    recommended_tone: str = "professional"  # casual, professional, formal

    # Reasoning
    reasoning: str = ""


class SituationAnalyzer:
    """
    Analyzes the situational context of a query.

    Goes beyond the literal question to understand:
    - What the person really needs (implicit needs)
    - How they're feeling (emotional tone)
    - How urgent this is (urgency level)
    - What's happening in time (temporal context)
    - What they'll ask next (anticipated follow-ups)
    """

    # Patterns for emotional tone detection
    CONCERN_PATTERNS = [
        r"worried\s*about", r"concerned\s*about", r"problem\s*with",
        r"issue\s*with", r"not\s*working", r"failed", r"failing",
        r"struggling", r"challenge", r"trouble", r"difficult",
    ]

    FRUSTRATION_PATTERNS = [
        r"again\?", r"still\s*not", r"keeps?\s*(failing|breaking)",
        r"why\s*(isn't|doesn't|won't)", r"frustrat", r"ugh",
        r"seriously\?", r"come\s*on",
    ]

    URGENCY_PATTERNS = [
        r"asap", r"urgent", r"immediately", r"right\s*now",
        r"today", r"by\s*end\s*of\s*day", r"eod", r"critical",
        r"emergency", r"deadline", r"due\s*tomorrow",
    ]

    ENTHUSIASM_PATTERNS = [
        r"excited", r"great\s*news", r"awesome", r"amazing",
        r"love\s*to", r"can't\s*wait", r"looking\s*forward",
    ]

    UNCERTAINTY_PATTERNS = [
        r"not\s*sure", r"confused", r"don't\s*understand",
        r"what\s*do\s*you\s*think", r"should\s*i", r"would\s*you",
        r"is\s*it\s*okay", r"is\s*this\s*right",
    ]

    # Patterns for implicit needs
    VALIDATION_PATTERNS = [
        r"is\s*this\s*(right|correct|okay)", r"does\s*this\s*(look|seem)",
        r"what\s*do\s*you\s*think", r"good\s*approach", r"make\s*sense",
        r"on\s*the\s*right\s*track",
    ]

    DECISION_PATTERNS = [
        r"should\s*(i|we)", r"which\s*(one|option)", r"best\s*(way|approach)",
        r"recommend", r"between\s*\w+\s*and", r"choose", r"decide",
        r"approve", r"go\s*with",
    ]

    PREPARATION_PATTERNS = [
        r"board\s*(meeting|presentation|deck)", r"prepare\s*for",
        r"presenting\s*to", r"meeting\s*with", r"update\s*for",
        r"exec\s*summary", r"stakeholder",
    ]

    def __init__(self):
        """Initialize the SituationAnalyzer."""
        self._config = get_layer_config("enhancement.situation_analyzer")

        # Compile patterns for performance
        self._compile_patterns()

        logger.info("SituationAnalyzer initialized")

    def _compile_patterns(self):
        """Compile regex patterns for performance."""
        self._concern_re = [re.compile(p, re.IGNORECASE) for p in self.CONCERN_PATTERNS]
        self._frustration_re = [re.compile(p, re.IGNORECASE) for p in self.FRUSTRATION_PATTERNS]
        self._urgency_re = [re.compile(p, re.IGNORECASE) for p in self.URGENCY_PATTERNS]
        self._enthusiasm_re = [re.compile(p, re.IGNORECASE) for p in self.ENTHUSIASM_PATTERNS]
        self._uncertainty_re = [re.compile(p, re.IGNORECASE) for p in self.UNCERTAINTY_PATTERNS]
        self._validation_re = [re.compile(p, re.IGNORECASE) for p in self.VALIDATION_PATTERNS]
        self._decision_re = [re.compile(p, re.IGNORECASE) for p in self.DECISION_PATTERNS]
        self._preparation_re = [re.compile(p, re.IGNORECASE) for p in self.PREPARATION_PATTERNS]

    def analyze(
        self,
        query: str,
        timestamp: Optional[datetime] = None,
        conversation_history: Optional[List[dict]] = None,
        user_metadata: Optional[dict] = None,
    ) -> SituationContext:
        """
        Analyze the situational context of a query.

        Args:
            query: User's query
            timestamp: When the query was made
            conversation_history: Previous turns in conversation
            user_metadata: Additional user context (role, department, etc.)

        Returns:
            SituationContext with full situational analysis
        """
        # Check if analyzer is enabled
        if not is_layer_enabled("enhancement.situation_analyzer"):
            return SituationContext(reasoning="Situation analyzer disabled")

        timestamp = timestamp or datetime.now()

        # Detect emotional tone
        emotional_tone = self._detect_emotional_tone(query)

        # Detect urgency
        urgency_level = self._detect_urgency(query)

        # Detect implicit needs
        implicit_needs = self._detect_implicit_needs(query, conversation_history)

        # Analyze temporal context
        temporal_context = self._analyze_temporal_context(timestamp)

        # Anticipate follow-ups
        anticipated_followups = self._anticipate_followups(
            query, implicit_needs, user_metadata
        )

        # Determine recommended response parameters
        recommended_depth = self._recommend_depth(
            implicit_needs, urgency_level, user_metadata
        )
        recommended_tone = self._recommend_tone(
            emotional_tone, urgency_level, user_metadata
        )

        # Build need description
        need_description = self._build_need_description(implicit_needs, emotional_tone)

        context = SituationContext(
            implicit_needs=implicit_needs,
            need_description=need_description,
            emotional_tone=emotional_tone,
            urgency_level=urgency_level,
            temporal_context=temporal_context,
            anticipated_followups=anticipated_followups,
            recommended_depth=recommended_depth,
            recommended_tone=recommended_tone,
            reasoning=f"Detected {emotional_tone.value} tone, {urgency_level.value} urgency",
        )

        logger.info(
            f"SituationAnalyzer: tone={emotional_tone.value}, "
            f"urgency={urgency_level.value}, needs={[n.value for n in implicit_needs]}"
        )

        return context

    def _detect_emotional_tone(self, query: str) -> EmotionalTone:
        """Detect the emotional tone of the query."""
        # Check frustration first (strongest negative)
        for pattern in self._frustration_re:
            if pattern.search(query):
                return EmotionalTone.FRUSTRATED

        # Check concern
        for pattern in self._concern_re:
            if pattern.search(query):
                return EmotionalTone.CONCERNED

        # Check urgency (can overlap with frustrated)
        for pattern in self._urgency_re:
            if pattern.search(query):
                return EmotionalTone.URGENT

        # Check enthusiasm
        for pattern in self._enthusiasm_re:
            if pattern.search(query):
                return EmotionalTone.ENTHUSIASTIC

        # Check uncertainty
        for pattern in self._uncertainty_re:
            if pattern.search(query):
                return EmotionalTone.UNCERTAIN

        # Check if it's a question (curious)
        if "?" in query:
            return EmotionalTone.CURIOUS

        return EmotionalTone.NEUTRAL

    def _detect_urgency(self, query: str) -> UrgencyLevel:
        """Detect the urgency level of the query."""
        query_lower = query.lower()

        # Critical urgency
        critical_words = ["emergency", "critical", "crisis", "immediately"]
        if any(word in query_lower for word in critical_words):
            return UrgencyLevel.CRITICAL

        # High urgency
        for pattern in self._urgency_re:
            if pattern.search(query):
                return UrgencyLevel.HIGH

        # Check for time pressure
        time_pressure = ["today", "tonight", "this morning", "this afternoon",
                         "by end of day", "eod", "before the meeting"]
        if any(phrase in query_lower for phrase in time_pressure):
            return UrgencyLevel.HIGH

        return UrgencyLevel.NORMAL

    def _detect_implicit_needs(
        self,
        query: str,
        conversation_history: Optional[List[dict]] = None,
    ) -> List[ImplicitNeed]:
        """Detect implicit needs behind the query."""
        needs = []

        # Check for validation needs
        for pattern in self._validation_re:
            if pattern.search(query):
                needs.append(ImplicitNeed.VALIDATION)
                break

        # Check for decision support
        for pattern in self._decision_re:
            if pattern.search(query):
                needs.append(ImplicitNeed.DECISION_SUPPORT)
                break

        # Check for preparation needs
        for pattern in self._preparation_re:
            if pattern.search(query):
                needs.append(ImplicitNeed.PREPARATION)
                break

        # Check for troubleshooting
        troubleshooting_words = ["not working", "broken", "failed", "error",
                                  "issue", "problem", "fix", "debug"]
        if any(word in query.lower() for word in troubleshooting_words):
            needs.append(ImplicitNeed.TROUBLESHOOTING)

        # Check for comparison needs
        if any(word in query.lower() for word in ["vs", "versus", "compare", "between"]):
            needs.append(ImplicitNeed.COMPARISON)

        # Default to information if no specific need detected
        if not needs:
            needs.append(ImplicitNeed.INFORMATION)

        return needs

    def _analyze_temporal_context(self, timestamp: datetime) -> TemporalContext:
        """Analyze temporal context from timestamp."""
        month = timestamp.month
        day = timestamp.day
        weekday = timestamp.weekday()
        hour = timestamp.hour

        # Calculate days until end of month
        if month in [1, 3, 5, 7, 8, 10, 12]:
            days_in_month = 31
        elif month in [4, 6, 9, 11]:
            days_in_month = 30
        else:
            days_in_month = 29 if timestamp.year % 4 == 0 else 28
        days_until_eom = days_in_month - day

        # Determine time of day
        if hour < 9:
            time_of_day = "early_morning"
        elif hour < 12:
            time_of_day = "morning"
        elif hour < 17:
            time_of_day = "afternoon"
        elif hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "late_night"

        return TemporalContext(
            is_board_season=(month in [1, 4, 7, 10] and day <= 15),  # First 2 weeks of quarter
            is_quarter_end=(month in [3, 6, 9, 12] and day >= 15),
            is_year_end=(month == 12 or (month == 1 and day <= 15)),
            is_planning_season=(month in [10, 11]),  # Budget planning
            is_review_season=(month in [1, 7] and day <= 20),  # Performance reviews
            time_of_day=time_of_day,
            day_of_week="weekend" if weekday >= 5 else "weekday",
            days_until_eom=days_until_eom,
        )

    def _anticipate_followups(
        self,
        query: str,
        implicit_needs: List[ImplicitNeed],
        user_metadata: Optional[dict] = None,
    ) -> List[str]:
        """Anticipate what the user will ask next."""
        followups = []
        query_lower = query.lower()

        # Based on implicit needs
        if ImplicitNeed.DECISION_SUPPORT in implicit_needs:
            followups.extend([
                "What are the risks?",
                "What would you recommend?",
                "What did we do last time?",
            ])

        if ImplicitNeed.PREPARATION in implicit_needs:
            followups.extend([
                "Can you summarize the key points?",
                "What questions might come up?",
                "What's the backup plan?",
            ])

        if ImplicitNeed.TROUBLESHOOTING in implicit_needs:
            followups.extend([
                "What's the root cause?",
                "How do we prevent this?",
                "Who should be involved?",
            ])

        # Based on user role (if available)
        if user_metadata:
            role = user_metadata.get("role", "").lower()
            if "cfo" in role or "finance" in role:
                followups.append("What's the financial impact?")
            elif "cto" in role or "tech" in role:
                followups.append("What's the technical complexity?")

        # Based on query content
        if "performance" in query_lower or "results" in query_lower:
            followups.append("How does this compare to targets?")

        if "budget" in query_lower:
            followups.append("What's the variance from plan?")

        return followups[:3]  # Limit to top 3

    def _recommend_depth(
        self,
        implicit_needs: List[ImplicitNeed],
        urgency_level: UrgencyLevel,
        user_metadata: Optional[dict] = None,
    ) -> str:
        """Recommend response depth based on context."""
        # High urgency -> brief
        if urgency_level in [UrgencyLevel.CRITICAL, UrgencyLevel.HIGH]:
            return "brief"

        # Preparation needs -> comprehensive
        if ImplicitNeed.PREPARATION in implicit_needs:
            return "comprehensive"

        # Decision support -> standard with options
        if ImplicitNeed.DECISION_SUPPORT in implicit_needs:
            return "standard"

        # Quick validation -> brief
        if ImplicitNeed.VALIDATION in implicit_needs:
            return "brief"

        return "standard"

    def _recommend_tone(
        self,
        emotional_tone: EmotionalTone,
        urgency_level: UrgencyLevel,
        user_metadata: Optional[dict] = None,
    ) -> str:
        """Recommend response tone based on context."""
        # Frustrated -> empathetic, solution-focused
        if emotional_tone == EmotionalTone.FRUSTRATED:
            return "empathetic_direct"

        # Concerned -> reassuring but factual
        if emotional_tone == EmotionalTone.CONCERNED:
            return "reassuring"

        # Urgent -> direct and action-oriented
        if urgency_level in [UrgencyLevel.CRITICAL, UrgencyLevel.HIGH]:
            return "direct"

        # Enthusiastic -> match energy
        if emotional_tone == EmotionalTone.ENTHUSIASTIC:
            return "engaged"

        return "professional"

    def _build_need_description(
        self,
        implicit_needs: List[ImplicitNeed],
        emotional_tone: EmotionalTone,
    ) -> str:
        """Build a human-readable description of what the user needs."""
        descriptions = {
            ImplicitNeed.DECISION_SUPPORT: "help making a decision",
            ImplicitNeed.VALIDATION: "validation of their approach",
            ImplicitNeed.INFORMATION: "information",
            ImplicitNeed.GUIDANCE: "guidance on how to proceed",
            ImplicitNeed.REASSURANCE: "reassurance that things are on track",
            ImplicitNeed.PREPARATION: "help preparing for something important",
            ImplicitNeed.COMPARISON: "comparison of options",
            ImplicitNeed.TROUBLESHOOTING: "help solving a problem",
        }

        need_strs = [descriptions.get(n, "help") for n in implicit_needs]

        if emotional_tone == EmotionalTone.FRUSTRATED:
            return f"They seem frustrated and need {' and '.join(need_strs)}"
        elif emotional_tone == EmotionalTone.CONCERNED:
            return f"They seem concerned and need {' and '.join(need_strs)}"
        elif emotional_tone == EmotionalTone.UNCERTAIN:
            return f"They seem uncertain and need {' and '.join(need_strs)}"
        else:
            return f"They need {' and '.join(need_strs)}"


# Singleton instance
_analyzer: Optional[SituationAnalyzer] = None


def get_situation_analyzer() -> SituationAnalyzer:
    """Get the singleton SituationAnalyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SituationAnalyzer()
    return _analyzer
