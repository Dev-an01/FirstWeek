"""
Response Calibration Data Models

Defines the calibration output used to adjust response generation.
Used by Stage 2 (Response Calibrator) of the Conversation Engine.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .attention import AttentionWeights


@dataclass
class ResponseCalibration:
    """
    Output of Response Calibrator (Stage 2).

    Contains tone adjustments, openers/signoffs, and content guidance
    based on executive baseline + situational adjustments.

    Example calibration flow:
    1. Load executive baseline (e.g., Akiko: warmth=8, directness=8)
    2. Apply situation rules (crisis → serious tone, no emojis)
    3. Apply multi-turn rules (followup → shorter, reference previous)
    4. Output calibrated settings for prompt assembly
    """
    # Tone settings
    tone: str = "neutral"  # analytical, supportive, celebratory, serious, casual
    warmth_level: int = 5  # 1-10 scale
    directness_level: int = 5  # 1-10 scale
    formality_level: int = 5  # 1-10 scale

    # Emoji usage
    emoji_usage: str = "none"  # none, minimal, moderate, heavy
    preferred_emojis: List[str] = field(default_factory=list)

    # Opener and signoff
    opener: str = ""  # Suggested opening phrase
    signoff: str = ""  # Suggested closing phrase

    # Response structure
    target_length: str = "medium"  # short, medium, long
    target_word_count: int = 200  # Target words
    use_bullets: bool = False  # Suggest bullet points
    use_headers: bool = False  # Suggest section headers

    # Content guidance
    include_precedent: bool = False  # Include relevant decision case
    include_values: bool = False  # Include executive values
    reference_previous_turn: bool = False  # Reference prior conversation
    offer_to_meet: bool = False  # Offer synchronous meeting

    # Avoid repetition
    facts_to_avoid: List[str] = field(default_factory=list)
    sources_to_avoid: List[str] = field(default_factory=list)

    # Reasoning (for debugging/logging)
    calibration_reason: str = ""
    adjustments_made: List[str] = field(default_factory=list)

    # Timing
    calibration_time_ms: float = 0.0

    # Attention weights for voiceprint categories
    # Enables graduated emphasis instead of binary ON/OFF
    attention_weights: Optional["AttentionWeights"] = None

    def get_token_budget(self, path: str = "standard") -> int:
        """
        Get token budget based on path and target length.

        Budgets:
        - Fast path: ~350 tokens
        - Standard path: ~500 tokens
        - Agentic path: ~650 tokens
        """
        base_budgets = {
            "fast": 350,
            "standard": 500,
            "agentic": 650,
        }
        base = base_budgets.get(path, 500)

        # Adjust for target length
        length_multipliers = {
            "short": 0.7,
            "medium": 1.0,
            "long": 1.3,
        }
        multiplier = length_multipliers.get(self.target_length, 1.0)

        return int(base * multiplier)

    def should_boost_warmth(self) -> bool:
        """Check if warmth should be higher than baseline."""
        return self.warmth_level >= 7

    def is_serious_tone(self) -> bool:
        """Check if response should be serious/formal."""
        return self.tone in ["serious", "analytical"] or self.formality_level >= 8

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for logging/debugging."""
        result = {
            "tone": self.tone,
            "warmth_level": self.warmth_level,
            "directness_level": self.directness_level,
            "formality_level": self.formality_level,
            "emoji_usage": self.emoji_usage,
            "opener": self.opener,
            "signoff": self.signoff,
            "target_length": self.target_length,
            "target_word_count": self.target_word_count,
            "include_precedent": self.include_precedent,
            "include_values": self.include_values,
            "reference_previous_turn": self.reference_previous_turn,
            "offer_to_meet": self.offer_to_meet,
            "calibration_reason": self.calibration_reason,
            "adjustments_made": self.adjustments_made,
            "calibration_time_ms": self.calibration_time_ms,
        }
        # Include attention weights if present
        if self.attention_weights is not None:
            result["attention_weights"] = self.attention_weights.to_dict()
            result["attention_query_type"] = self.attention_weights.query_type
            result["attention_dominant_head"] = self.attention_weights.dominant_head
        return result

    @classmethod
    def for_crisis(
        cls,
        executive_warmth: int = 5,
        preferred_emojis: Optional[List[str]] = None,
    ) -> "ResponseCalibration":
        """
        Create calibration preset for crisis situations.

        Note: opener/signoff are left empty - filled by calibrator from voiceprint.
        """
        return cls(
            tone="serious",
            warmth_level=min(executive_warmth + 2, 10),  # Boost warmth
            directness_level=9,
            formality_level=7,
            emoji_usage="none",
            # opener/signoff left empty - calibrator fills from voiceprint
            opener="",
            signoff="",
            target_length="medium",
            include_precedent=True,
            offer_to_meet=True,
            calibration_reason="crisis_situation",
            adjustments_made=["warmth_boosted", "no_emojis", "offer_meeting"],
        )

    @classmethod
    def for_celebration(
        cls,
        executive_warmth: int = 5,
        preferred_emojis: Optional[List[str]] = None,
    ) -> "ResponseCalibration":
        """
        Create calibration preset for celebratory situations.

        Note: opener/signoff/emojis are left empty - filled by calibrator from voiceprint.
        Args:
            preferred_emojis: From voiceprint.style_markers.preferred_emojis
        """
        return cls(
            tone="celebratory",
            warmth_level=min(executive_warmth + 1, 10),
            directness_level=6,
            formality_level=4,
            emoji_usage="moderate",
            # Use voiceprint emojis if provided, otherwise empty (calibrator fills)
            preferred_emojis=preferred_emojis or [],
            # opener left empty - calibrator fills from voiceprint
            opener="",
            target_length="medium",
            calibration_reason="celebration",
            adjustments_made=["positive_tone", "emojis_ok"],
        )

    @classmethod
    def for_followup(cls, executive_warmth: int = 5) -> "ResponseCalibration":
        """
        Create calibration preset for follow-up turns.

        Note: opener/signoff are left empty - filled by calibrator from voiceprint.
        """
        return cls(
            tone="casual",
            warmth_level=executive_warmth,
            # opener/signoff left empty - calibrator fills from voiceprint
            opener="",
            signoff="",
            target_length="short",
            target_word_count=100,
            reference_previous_turn=True,
            calibration_reason="followup_turn",
            adjustments_made=["shorter_response", "reference_previous"],
        )
