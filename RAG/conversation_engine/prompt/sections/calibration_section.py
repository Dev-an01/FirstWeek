"""
Calibration Section Builder - Response style guidance.

REFACTORED (2025-01-15): Now imports length descriptions from centralized rules.py
- LENGTH_TARGETS now aligned with WORD_LIMITS (no contradiction)
- Uses get_calibration_length_description from rules.py

Uses ResponseCalibration from Phase 3 to guide response style.
Target: 50-80 tokens
"""

import logging
from typing import TYPE_CHECKING, List

# Import from centralized rules - SINGLE SOURCE OF TRUTH
from ..rules import get_calibration_length_description, CALIBRATION_LENGTH_DESCRIPTIONS

if TYPE_CHECKING:
    from ..calibration.models import ResponseCalibration
    from ..analysis.models import AnalyzedContext

logger = logging.getLogger(__name__)


class CalibrationSection:
    """
    Builds response calibration instructions.

    REFACTORED (2025-01-15):
    - Length descriptions now come from rules.py
    - Aligned with word limits (no more "150-200 words" vs "30 words" conflict)

    Uses ResponseCalibration from Phase 3 to guide response style.

    Output format:
        FOR THIS RESPONSE:
        - Tone: Supportive, acknowledge their stress
        - Start with: "I hear you - this is a tough call..."
        - End with: "I'm here if you want to talk it through."
        - Length: Medium (~35-60 words)
        - Offer to meet/call if helpful

    Provides the LLM with:
    - Specific tone guidance
    - Opening and closing phrases
    - Length constraints (ALIGNED with word limits)
    - Special behaviors (offer meeting, use emojis, etc.)

    Target: 50-80 tokens
    """

    # DEPRECATED: Use CALIBRATION_LENGTH_DESCRIPTIONS from rules.py instead
    # Kept for backward compatibility
    LENGTH_TARGETS = CALIBRATION_LENGTH_DESCRIPTIONS

    def build(
        self,
        calibration: "ResponseCalibration",
        analyzed_context: "AnalyzedContext",
        max_tokens: int = 70,
        path: str = "standard",
        is_followup: bool = False,
    ) -> str:
        """
        Build calibration section from Phase 3 output.

        REFACTORED: Uses centralized length descriptions from rules.py

        Args:
            calibration: From Phase 3 ResponseCalibrator
            analyzed_context: From Phase 3 ContextAnalyzer
            max_tokens: Maximum tokens for section
            path: Processing path (fast/standard/agentic)
            is_followup: Whether this is a follow-up turn in conversation

        Returns:
            Calibration section string
        """
        bullets: List[str] = []

        # Tone with emotion acknowledgment
        tone_desc = calibration.tone
        if analyzed_context.user_emotion and analyzed_context.user_emotion.value in ["stressed", "tense"]:
            tone_desc += f", acknowledge their {analyzed_context.user_emotion.value}"
        bullets.append(f"Tone: {tone_desc.capitalize()}")

        # Opener - skip for fast path or follow-up turns
        # Fast path should be direct; follow-ups don't need openers
        if calibration.opener and path != "fast" and not is_followup:
            bullets.append(f'Start with: "{calibration.opener}"')

        # Signoff - skip for fast path or follow-up turns
        # Fast path should be brief; follow-ups in chat don't need signoffs
        if calibration.signoff and path != "fast" and not is_followup:
            bullets.append(f'End with: "{calibration.signoff}"')

        # Length - NOW ALIGNED with word limits from rules.py
        length_desc = get_calibration_length_description(calibration.target_length)
        bullets.append(f"Length: {calibration.target_length.capitalize()} ({length_desc})")

        # Special behaviors
        if calibration.offer_to_meet:
            bullets.append("Offer to meet/call if helpful")

        if calibration.reference_previous_turn:
            bullets.append("Reference previous conversation")

        if calibration.emoji_usage != "none" and calibration.preferred_emojis:
            emojis = " ".join(calibration.preferred_emojis[:3])
            bullets.append(f"Emojis: {calibration.emoji_usage} ({emojis})")

        if calibration.use_bullets:
            # Natural flow preferred - only structure if multiple distinct points needed
            bullets.append("Natural flow preferred - only structure if truly needed")

        # Format as section
        bullet_text = "\n".join(f"- {b}" for b in bullets)
        section = f"""
FOR THIS RESPONSE:
{bullet_text}
"""

        logger.debug(f"Built calibration section: {len(section)} chars, {len(bullets)} bullets, path={path}, followup={is_followup}")
        return section
