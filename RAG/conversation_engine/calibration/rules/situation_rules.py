"""
Situation Rules - Situation-based calibration adjustments.

Applies adjustments based on urgency, emotion, and query type.
"""

import logging
from typing import Dict, Any, List, Callable, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..models import ResponseCalibration
    from ...analysis.models import AnalyzedContext, Urgency, UserEmotion, QueryType

logger = logging.getLogger(__name__)


@dataclass
class CalibrationRule:
    """A single calibration rule with condition and adjustments."""
    name: str
    condition: Callable[["AnalyzedContext"], bool]
    adjustments: Dict[str, Any]
    priority: int = 0  # Higher priority rules applied last (override)


class SituationRules:
    """
    Situation-based calibration adjustments.

    Rules (from architecture doc):
    - crisis + any_exec -> serious tone, no emojis, +empathy, offer help
    - celebration + warm_exec -> enthusiastic, emojis OK
    - user_stressed -> increase warmth, supportive opener
    - decision_query -> include relevant precedent

    Thread-safe: No mutable state.
    """

    def __init__(self):
        """Initialize situation rules."""
        self._rules = self._build_rules()
        logger.debug(f"SituationRules initialized with {len(self._rules)} rules")

    def _build_rules(self) -> List[CalibrationRule]:
        """Build the list of situation rules."""
        # Import here to avoid circular imports
        from ...analysis.models import Urgency, UserEmotion, QueryType

        return [
            # Crisis response - highest priority for safety
            CalibrationRule(
                name="crisis_response",
                condition=lambda ctx: ctx.urgency == Urgency.CRISIS,
                adjustments={
                    "tone": "serious",
                    "warmth_boost": 2,
                    "emoji_usage": "none",
                    "offer_to_meet": True,
                    "opener_style": "supportive",
                    "target_length": "medium",
                    "directness_boost": 2,
                },
                priority=10,
            ),

            # Urgent but not crisis
            CalibrationRule(
                name="urgent_response",
                condition=lambda ctx: ctx.urgency == Urgency.URGENT,
                adjustments={
                    "tone": "focused",
                    "directness_boost": 1,
                    "target_length": "medium",
                },
                priority=5,
            ),

            # Celebratory mood
            CalibrationRule(
                name="celebration_response",
                condition=lambda ctx: ctx.user_emotion == UserEmotion.CELEBRATORY,
                adjustments={
                    "tone": "celebratory",
                    "warmth_boost": 1,
                    "emoji_usage": "moderate",
                    "opener_style": "enthusiastic",
                },
                priority=4,
            ),

            # Stressed user - boost empathy
            CalibrationRule(
                name="stressed_user",
                condition=lambda ctx: ctx.user_emotion == UserEmotion.STRESSED,
                adjustments={
                    "warmth_boost": 2,
                    "opener_style": "supportive",
                    "offer_to_meet": True,
                    "tone": "supportive",
                },
                priority=6,
            ),

            # Tense user - mild empathy boost
            CalibrationRule(
                name="tense_user",
                condition=lambda ctx: ctx.user_emotion == UserEmotion.TENSE,
                adjustments={
                    "warmth_boost": 1,
                    "opener_style": "understanding",
                },
                priority=3,
            ),

            # Positive user - match energy
            CalibrationRule(
                name="positive_user",
                condition=lambda ctx: ctx.user_emotion == UserEmotion.POSITIVE,
                adjustments={
                    "tone": "positive",
                    "warmth_boost": 1,
                },
                priority=2,
            ),

            # Decision query - include precedent and values
            CalibrationRule(
                name="decision_query",
                condition=lambda ctx: ctx.query_type == QueryType.DECISION,
                adjustments={
                    "include_precedent": True,
                    "include_values": True,
                    "target_length": "medium",
                },
                priority=3,
            ),

            # Emotional query - boost warmth, supportive tone
            CalibrationRule(
                name="emotional_query",
                condition=lambda ctx: ctx.query_type == QueryType.EMOTIONAL,
                adjustments={
                    "warmth_boost": 2,
                    "tone": "supportive",
                    "opener_style": "empathetic",
                },
                priority=4,
            ),

            # Analytical query - structured response
            CalibrationRule(
                name="analytical_query",
                condition=lambda ctx: ctx.query_type == QueryType.ANALYTICAL,
                adjustments={
                    "tone": "analytical",
                    "target_length": "medium",
                },
                priority=2,
            ),

            # Factual query - concise response
            CalibrationRule(
                name="factual_query",
                condition=lambda ctx: ctx.query_type == QueryType.FACTUAL,
                adjustments={
                    "tone": "neutral",
                    "target_length": "short",
                },
                priority=1,
            ),

            # Planning context - thoughtful, future-oriented
            CalibrationRule(
                name="planning_context",
                condition=lambda ctx: ctx.urgency == Urgency.PLANNING,
                adjustments={
                    "tone": "thoughtful",
                    "target_length": "medium",
                },
                priority=2,
            ),

            # Board-level formality
            CalibrationRule(
                name="board_formality",
                condition=lambda ctx: ctx.formality == "board",
                adjustments={
                    "formality_boost": 2,
                    "emoji_usage": "none",
                    "tone": "formal",
                },
                priority=7,
            ),

            # Slack-level informality
            CalibrationRule(
                name="slack_formality",
                condition=lambda ctx: ctx.formality == "slack",
                adjustments={
                    "formality_boost": -2,
                    "target_length": "short",
                },
                priority=2,
            ),
        ]

    def apply(
        self,
        calibration: "ResponseCalibration",
        analyzed_context: "AnalyzedContext",
    ) -> "ResponseCalibration":
        """
        Apply situation rules to calibration.

        Args:
            calibration: Current ResponseCalibration
            analyzed_context: AnalyzedContext from analyzer

        Returns:
            Modified ResponseCalibration
        """
        adjustments_made = list(calibration.adjustments_made)

        # Sort rules by priority (lower first, so higher priority can override)
        sorted_rules = sorted(self._rules, key=lambda r: r.priority)

        for rule in sorted_rules:
            try:
                if rule.condition(analyzed_context):
                    self._apply_adjustments(calibration, rule.adjustments)
                    adjustments_made.append(f"situation:{rule.name}")
                    logger.debug(f"Applied situation rule: {rule.name}")
            except Exception as e:
                logger.warning(f"Rule {rule.name} evaluation failed: {e}")
                continue

        calibration.adjustments_made = adjustments_made
        return calibration

    def _apply_adjustments(
        self,
        calibration: "ResponseCalibration",
        adjustments: Dict[str, Any],
    ) -> None:
        """Apply adjustments to calibration object."""
        for key, value in adjustments.items():
            if key == "warmth_boost":
                calibration.warmth_level = min(
                    calibration.warmth_level + value, 10
                )
            elif key == "directness_boost":
                calibration.directness_level = min(
                    calibration.directness_level + value, 10
                )
            elif key == "formality_boost":
                new_value = calibration.formality_level + value
                calibration.formality_level = max(1, min(new_value, 10))
            elif key == "opener_style":
                # Store for later use by calibrator
                if not hasattr(calibration, '_opener_style'):
                    calibration._opener_style = value
            elif hasattr(calibration, key):
                setattr(calibration, key, value)

    def get_applicable_rules(
        self,
        analyzed_context: "AnalyzedContext",
    ) -> List[str]:
        """Get list of rule names that would apply."""
        applicable = []
        for rule in self._rules:
            try:
                if rule.condition(analyzed_context):
                    applicable.append(rule.name)
            except Exception:
                continue
        return applicable


# Singleton instance
_default_rules: SituationRules = None


def get_situation_rules() -> SituationRules:
    """Get singleton SituationRules instance."""
    global _default_rules
    if _default_rules is None:
        _default_rules = SituationRules()
    return _default_rules
