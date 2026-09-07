"""
Multi-turn Rules - Conversation flow calibration adjustments.

Applies adjustments based on turn type, emotional trend, and conversation length.
"""

import logging
from typing import Dict, Any, List, Callable, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..models import ResponseCalibration
    from ...analysis.models import AnalyzedContext, TurnType
    from ...context.models import ManagedContext

logger = logging.getLogger(__name__)


@dataclass
class MultiturnRule:
    """A single multi-turn calibration rule."""
    name: str
    condition: Callable[["AnalyzedContext", "ManagedContext"], bool]
    adjustments: Dict[str, Any]
    priority: int = 0


class MultiturnRules:
    """
    Multi-turn conversation adjustments.

    Rules (from architecture doc):
    - followup -> shorter response, reference previous
    - emotional_decline -> significantly increase warmth
    - turn_count > 3 -> offer to meet/escalate
    - topic_shift -> acknowledge transition

    Thread-safe: No mutable state.
    """

    def __init__(self):
        """Initialize multi-turn rules."""
        self._rules = self._build_rules()
        logger.debug(f"MultiturnRules initialized with {len(self._rules)} rules")

    def _build_rules(self) -> List[MultiturnRule]:
        """Build the list of multi-turn rules."""
        from ...analysis.models import TurnType

        return [
            # Followup turn - shorter, reference previous
            MultiturnRule(
                name="followup_turn",
                condition=lambda ctx, mgd: ctx.turn_type == TurnType.FOLLOWUP,
                adjustments={
                    "target_length": "short",
                    "reference_previous_turn": True,
                    "target_word_count": 100,
                },
                priority=3,
            ),

            # Clarification turn - concise, direct
            MultiturnRule(
                name="clarification_turn",
                condition=lambda ctx, mgd: ctx.turn_type == TurnType.CLARIFICATION,
                adjustments={
                    "target_length": "short",
                    "reference_previous_turn": True,
                    "directness_boost": 1,
                    "opener_style": "clarifying",
                },
                priority=3,
            ),

            # Emotional shift - acknowledge the emotion
            MultiturnRule(
                name="emotional_shift_turn",
                condition=lambda ctx, mgd: ctx.turn_type == TurnType.EMOTIONAL_SHIFT,
                adjustments={
                    "warmth_boost": 1,
                    "opener_style": "acknowledging",
                    "reference_previous_turn": True,
                },
                priority=4,
            ),

            # Emotional decline - significant warmth boost
            MultiturnRule(
                name="emotional_decline",
                condition=lambda ctx, mgd: ctx.emotional_trend == "declining",
                adjustments={
                    "warmth_boost": 3,
                    "offer_to_meet": True,
                    "opener_style": "empathetic",
                    "tone": "supportive",
                },
                priority=6,
            ),

            # Emotional improvement - positive reinforcement
            MultiturnRule(
                name="emotional_improvement",
                condition=lambda ctx, mgd: ctx.emotional_trend == "improving",
                adjustments={
                    "warmth_boost": 1,
                    "tone": "encouraging",
                },
                priority=2,
            ),

            # Extended conversation (>3 turns) - offer escalation
            MultiturnRule(
                name="extended_conversation",
                condition=lambda ctx, mgd: mgd.get_turn_number() > 3,
                adjustments={
                    "offer_to_meet": True,
                },
                priority=2,
            ),

            # Very long conversation (>5 turns) - summarize option
            MultiturnRule(
                name="long_conversation",
                condition=lambda ctx, mgd: mgd.get_turn_number() > 5,
                adjustments={
                    "signoff_style": "offer_summary",
                    "offer_to_meet": True,
                },
                priority=3,
            ),

            # Topic shift - acknowledge transition
            MultiturnRule(
                name="topic_shift",
                condition=lambda ctx, mgd: (
                    not ctx.continue_topic and
                    mgd.get_turn_number() > 1 and
                    ctx.turn_type == TurnType.NEW_TOPIC
                ),
                adjustments={
                    "opener_style": "transitioning",
                    "acknowledge_transition": True,
                },
                priority=3,
            ),

            # Continuing topic - maintain context
            MultiturnRule(
                name="continuing_topic",
                condition=lambda ctx, mgd: (
                    ctx.continue_topic and
                    mgd.get_turn_number() > 1
                ),
                adjustments={
                    "reference_previous_turn": True,
                },
                priority=1,
            ),

            # First turn in session - fresh start
            MultiturnRule(
                name="first_turn",
                condition=lambda ctx, mgd: mgd.get_turn_number() == 0,
                adjustments={
                    "opener_style": "welcoming",
                    "target_length": "medium",
                },
                priority=1,
            ),

            # Has episodic memory - personalize
            MultiturnRule(
                name="has_memory",
                condition=lambda ctx, mgd: len(mgd.episodic_memory) > 0,
                adjustments={
                    "warmth_boost": 1,
                    "personalize": True,
                },
                priority=2,
            ),

            # Avoiding repetition - has facts to avoid
            MultiturnRule(
                name="avoiding_repetition",
                condition=lambda ctx, mgd: len(mgd.facts_to_avoid) > 0,
                adjustments={
                    "check_repetition": True,
                },
                priority=4,
            ),
        ]

    def apply(
        self,
        calibration: "ResponseCalibration",
        analyzed_context: "AnalyzedContext",
        managed_context: "ManagedContext",
    ) -> "ResponseCalibration":
        """
        Apply multi-turn rules to calibration.

        Args:
            calibration: Current ResponseCalibration
            analyzed_context: AnalyzedContext from analyzer
            managed_context: ManagedContext from Phase 2

        Returns:
            Modified ResponseCalibration
        """
        adjustments_made = list(calibration.adjustments_made)

        # Sort rules by priority
        sorted_rules = sorted(self._rules, key=lambda r: r.priority)

        for rule in sorted_rules:
            try:
                if rule.condition(analyzed_context, managed_context):
                    self._apply_adjustments(calibration, rule.adjustments)
                    adjustments_made.append(f"multiturn:{rule.name}")
                    logger.debug(f"Applied multi-turn rule: {rule.name}")
            except Exception as e:
                logger.warning(f"Multi-turn rule {rule.name} evaluation failed: {e}")
                continue

        # Copy facts_to_avoid from managed context
        if managed_context.facts_to_avoid:
            calibration.facts_to_avoid = list(managed_context.facts_to_avoid)

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
            elif key in ("opener_style", "signoff_style", "personalize",
                        "check_repetition", "acknowledge_transition"):
                # Store for later use
                if not hasattr(calibration, f'_{key}'):
                    setattr(calibration, f'_{key}', value)
            elif hasattr(calibration, key):
                setattr(calibration, key, value)

    def get_applicable_rules(
        self,
        analyzed_context: "AnalyzedContext",
        managed_context: "ManagedContext",
    ) -> List[str]:
        """Get list of rule names that would apply."""
        applicable = []
        for rule in self._rules:
            try:
                if rule.condition(analyzed_context, managed_context):
                    applicable.append(rule.name)
            except Exception:
                continue
        return applicable


# Singleton instance
_default_rules: MultiturnRules = None


def get_multiturn_rules() -> MultiturnRules:
    """Get singleton MultiturnRules instance."""
    global _default_rules
    if _default_rules is None:
        _default_rules = MultiturnRules()
    return _default_rules
