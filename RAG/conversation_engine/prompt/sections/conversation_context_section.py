"""
Conversation Context Section Builder - Multi-turn session context.

Builds conversation state awareness for multi-turn sessions.
Target: 50-80 tokens
Skip if: STATELESS mode
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...context.models import ManagedContext, ConversationMode
    from ...analysis.models import AnalyzedContext
    from ...calibration.models import ResponseCalibration

logger = logging.getLogger(__name__)


class ConversationContextSection:
    """
    Builds conversation context for multi-turn sessions.

    Output format:
        ═══════════════════════════════════════════════════════
        CONVERSATION CONTEXT:
        This is turn 3. Topic: MegaCorp discount decision.
        User is feeling stressed (emotional trend: declining).
        DO NOT REPEAT: MegaCorp NPS is 72, 45-day deadline.
        ═══════════════════════════════════════════════════════

    Provides the LLM with:
    - Turn number for response pacing
    - Current topic for continuity
    - User emotional state for tone calibration
    - Facts to avoid repeating

    Target: 50-80 tokens
    Skip if: STATELESS mode
    """

    # Section delimiter
    DELIMITER = "═══════════════════════════════════════════════════════"

    def build(
        self,
        managed_context: "ManagedContext",
        analyzed_context: "AnalyzedContext",
        calibration: "ResponseCalibration",
        max_tokens: int = 60,
    ) -> str:
        """
        Build conversation context section.

        Args:
            managed_context: From Phase 2 ContextManager
            analyzed_context: From Phase 3 ContextAnalyzer
            calibration: From Phase 3 ResponseCalibrator
            max_tokens: Maximum tokens for section

        Returns:
            Conversation context section string, empty if STATELESS
        """
        from ...context.models import ConversationMode

        # Skip for stateless mode
        if managed_context.mode == ConversationMode.STATELESS:
            return ""

        # Get turn number
        turn_number = managed_context.get_turn_number()

        # Get topic
        topic = ""
        if managed_context.session_state:
            topic = managed_context.session_state.current_topic or "general discussion"
        else:
            topic = "general discussion"

        # Get emotion and trend
        emotion = "neutral"
        if analyzed_context.user_emotion:
            emotion = analyzed_context.user_emotion.value

        trend = analyzed_context.emotional_trend or managed_context.get_emotional_trend()

        # Get facts to avoid (top 3)
        facts_to_avoid = calibration.facts_to_avoid[:3] if calibration.facts_to_avoid else []

        # Build section
        lines = [
            self.DELIMITER,
            "CONVERSATION CONTEXT:",
            f"This is turn {turn_number}. Topic: {topic}.",
            f"User is feeling {emotion} (emotional trend: {trend}).",
        ]

        if facts_to_avoid:
            facts_str = ", ".join(facts_to_avoid)
            lines.append(f"DO NOT REPEAT: {facts_str}.")

        # Add reference to previous turn if applicable
        if calibration.reference_previous_turn and turn_number > 1:
            lines.append("Build on your previous response.")

        lines.append(self.DELIMITER)

        section = "\n".join(lines)
        logger.debug(f"Built conversation context section: {len(section)} chars")

        return section
