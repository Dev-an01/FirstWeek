"""
Response Calibrator - Calibrates response tone and style.

Stage 2 of the 5-stage pipeline.
Consumes AnalyzedContext + ManagedContext, produces ResponseCalibration.

Target latency: 2-3ms.
"""

import json
import time
import logging
import random
from pathlib import Path
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from .models import ResponseCalibration
from .rules import (
    SituationRules,
    MultiturnRules,
    ExecutiveRules,
)
from .attention import SemanticAttention, get_semantic_attention

if TYPE_CHECKING:
    from ..analysis.models import AnalyzedContext, TurnType, QueryType
    from ..context.models import ManagedContext
    from profile_management.profile_manager import ProfileManager

logger = logging.getLogger(__name__)


class ResponseCalibrator:
    """
    Stage 2: Calibrate response tone and style.

    Applies executive baseline + situational adjustments + multi-turn adjustments.

    Calibration flow:
    1. Load executive baseline (warmth, directness, formality from voiceprint)
    2. Apply situation rules (crisis -> serious, celebration -> enthusiastic)
    3. Apply multi-turn rules (followup -> shorter, emotional_decline -> boost warmth)
    4. Apply executive rules (per-executive overrides)
    5. Select opener and signoff from voiceprint
    6. Output calibrated ResponseCalibration

    Thread-safe: Rule engines are stateless.
    """

    # Default voiceprint path
    VOICEPRINT_DIR = Path(__file__).parent.parent.parent / "test_data" / "voiceprints"

    # Opener style to voiceprint section mapping (profile-driven, not hardcoded)
    # Each style maps to a voiceprint section that contains relevant examples
    OPENER_STYLE_TO_VOICEPRINT_SECTION: Dict[str, List[str]] = {
        "supportive": ["emotional_expressions.encouragement", "mentorship_phrases.examples"],
        "empathetic": ["mentorship_phrases.examples", "emotional_expressions.encouragement"],
        "enthusiastic": ["emotional_expressions.pride", "emotional_expressions.approval"],
        "clarifying": ["transparency_phrases.examples", "decision_cadence.examples"],
        "transitioning": ["signature_opener.examples"],
        "acknowledging": ["deference_phrases.examples", "signature_opener.examples"],
        "welcoming": ["signature_opener.examples"],
        "understanding": ["signature_opener.examples", "transparency_phrases.examples"],
        "default": ["signature_opener.examples"],
    }

    # Signoff style to voiceprint section mapping
    SIGNOFF_STYLE_TO_VOICEPRINT_SECTION: Dict[str, List[str]] = {
        "offer_meeting": ["sign_off.alternatives"],  # Filter for meeting-related
        "offer_summary": ["sign_off.alternatives"],  # Filter for summary-related
        "supportive": ["sign_off.alternatives", "emotional_expressions.encouragement"],
        "default": ["sign_off.alternatives"],
    }

    def __init__(
        self,
        profile_manager: Optional["ProfileManager"] = None,
        voiceprint_dir: Optional[Path] = None,
    ):
        """
        Initialize ResponseCalibrator.

        Args:
            profile_manager: Optional ProfileManager for loading profiles
            voiceprint_dir: Optional path to voiceprint directory
        """
        self.profile_manager = profile_manager
        self.voiceprint_dir = voiceprint_dir or self.VOICEPRINT_DIR

        # Initialize rule engines
        self._situation_rules = SituationRules()
        self._multiturn_rules = MultiturnRules()
        self._executive_rules = ExecutiveRules()

        # Initialize attention mechanism
        self._semantic_attention = SemanticAttention()

        # Cache for voiceprints
        self._voiceprint_cache: Dict[str, Dict[str, Any]] = {}

        logger.info("ResponseCalibrator initialized (with attention mechanism)")

    def calibrate(
        self,
        profile_id: str,
        analyzed_context: "AnalyzedContext",
        managed_context: "ManagedContext",
    ) -> ResponseCalibration:
        """
        Main entry point - returns complete calibration.

        Args:
            profile_id: Executive profile ID
            analyzed_context: AnalyzedContext from analyzer
            managed_context: ManagedContext from context manager

        Returns:
            ResponseCalibration with all adjustments applied
        """
        start_time = time.time()

        try:
            # 1. Load executive baseline
            voiceprint = self._load_voiceprint(profile_id)
            calibration = self._create_baseline(voiceprint)

            # 2. Apply situation rules
            calibration = self._situation_rules.apply(
                calibration, analyzed_context
            )

            # 3. Apply multi-turn rules
            calibration = self._multiturn_rules.apply(
                calibration, analyzed_context, managed_context
            )

            # 4. Apply executive rules (pass voiceprint for data-agnostic extraction)
            calibration = self._executive_rules.apply(
                calibration,
                profile_id,
                formality_context=analyzed_context.formality,
                voiceprint=voiceprint.get("voiceprint", {}),
            )

            # 5. Select opener
            calibration.opener = self._select_opener(
                analyzed_context, voiceprint, calibration
            )

            # 6. Select signoff
            calibration.signoff = self._select_signoff(
                analyzed_context, voiceprint, calibration
            )

            # 7. Set preferred emojis from voiceprint
            if calibration.emoji_usage != "none":
                calibration.preferred_emojis = voiceprint.get(
                    "voiceprint", {}
                ).get("style_markers", {}).get("preferred_emojis", [])

            # 8. Compute pattern-based attention weights
            # Semantic refinement happens later in ConversationEngine after embedding is computed
            try:
                context_signals = {
                    "urgency": analyzed_context.urgency.value if analyzed_context.urgency else "",
                    "user_emotion": analyzed_context.user_emotion.value if analyzed_context.user_emotion else "",
                    "theme": analyzed_context.theme.value if analyzed_context.theme else "",
                }
                # Get query from resolved_query if available, else use empty (will classify as explanation)
                query = analyzed_context.resolved_query or ""
                calibration.attention_weights = self._semantic_attention.compute_pattern_attention(
                    query=query,
                    context_signals=context_signals,
                )
                calibration.adjustments_made.append("attention:pattern_computed")
                logger.debug(
                    f"Pattern attention computed: type={calibration.attention_weights.query_type}, "
                    f"top_3={calibration.attention_weights.get_top_k(3)}"
                )
            except Exception as e:
                logger.warning(f"Attention computation failed: {e}, continuing without attention")
                calibration.attention_weights = None

            # Calculate timing
            elapsed_ms = (time.time() - start_time) * 1000
            calibration.calibration_time_ms = elapsed_ms

            # Set reason summary
            calibration.calibration_reason = self._summarize_reason(
                analyzed_context, calibration
            )

            logger.info(
                f"ResponseCalibrator.calibrate completed",
                extra={
                    "profile_id": profile_id,
                    "tone": calibration.tone,
                    "warmth": calibration.warmth_level,
                    "adjustments": len(calibration.adjustments_made),
                    "latency_ms": elapsed_ms,
                }
            )

            return calibration

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.error(f"ResponseCalibrator.calibrate failed: {e}")

            # Return defaults on error
            return ResponseCalibration(
                calibration_time_ms=elapsed_ms,
                calibration_reason="error_fallback",
            )

    def _load_voiceprint(self, profile_id: str) -> Dict[str, Any]:
        """
        Load voiceprint for executive.

        Tries:
        1. Cache
        2. ProfileManager
        3. JSON file
        4. Empty default
        """
        # Check cache
        if profile_id in self._voiceprint_cache:
            return self._voiceprint_cache[profile_id]

        voiceprint = {}

        # Try ProfileManager
        if self.profile_manager:
            try:
                profile = self.profile_manager.get_profile(profile_id)
                if profile and hasattr(profile, 'voiceprint'):
                    voiceprint = profile.voiceprint or {}
            except Exception as e:
                logger.debug(f"ProfileManager load failed: {e}")

        # Try JSON file
        if not voiceprint:
            voiceprint = self._load_voiceprint_from_file(profile_id)

        # Cache and return
        self._voiceprint_cache[profile_id] = voiceprint
        return voiceprint

    def _load_voiceprint_from_file(self, profile_id: str) -> Dict[str, Any]:
        """Load voiceprint from JSON file."""
        # Map profile IDs to file names (matches DB: exec_003=Yuki CTO, exec_004=Sarah CMO)
        profile_file_map = {
            "exec_001_test": "akiko_tanaka_voiceprint.json",
            "exec_002_test": "raj_patel_voiceprint.json",
            "exec_003_test": "yuki_nakamura_voiceprint.json",  # CTO
            "exec_004_test": "sarah_kim_voiceprint.json",      # CMO
        }

        filename = profile_file_map.get(profile_id)
        if not filename:
            logger.debug(f"No voiceprint file mapping for {profile_id}")
            return {}

        filepath = self.voiceprint_dir / filename
        if not filepath.exists():
            logger.debug(f"Voiceprint file not found: {filepath}")
            return {}

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load voiceprint: {e}")
            return {}

    def _create_baseline(self, voiceprint: Dict[str, Any]) -> ResponseCalibration:
        """
        Create baseline calibration from voiceprint.

        Extracts warmth, directness, formality from style_markers.
        """
        style_markers = voiceprint.get("voiceprint", {}).get("style_markers", {})

        warmth = style_markers.get("warmth", 5)
        directness = style_markers.get("directness", 5)
        formality = style_markers.get("formality", 5)

        # Determine baseline tone
        if warmth >= 7 and directness >= 7:
            tone = "warm_direct"
        elif warmth >= 7:
            tone = "warm"
        elif directness >= 7:
            tone = "direct"
        else:
            tone = "neutral"

        # Determine emoji usage from voiceprint
        emoji_usage = "none"
        if style_markers.get("emoji_usage"):
            emoji_desc = style_markers.get("emoji_usage", "").lower()
            if "heavy" in emoji_desc or "frequent" in emoji_desc:
                emoji_usage = "moderate"
            elif "occasional" in emoji_desc or "minimal" in emoji_desc:
                emoji_usage = "minimal"

        return ResponseCalibration(
            tone=tone,
            warmth_level=warmth,
            directness_level=directness,
            formality_level=formality,
            emoji_usage=emoji_usage,
            adjustments_made=["baseline_loaded"],
        )

    def _get_voiceprint_value(
        self,
        voiceprint_data: Dict[str, Any],
        path: str,
    ) -> List[str]:
        """
        Extract value from voiceprint using dot notation path.

        Args:
            voiceprint_data: The voiceprint dict (already inside "voiceprint" key)
            path: Dot notation path like "emotional_expressions.pride"

        Returns:
            List of strings from the voiceprint section
        """
        parts = path.split(".")
        current = voiceprint_data

        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return []

        # Return as list
        if isinstance(current, list):
            return current
        elif isinstance(current, str):
            return [current]
        return []

    def _select_opener(
        self,
        analyzed_context: "AnalyzedContext",
        voiceprint: Dict[str, Any],
        calibration: ResponseCalibration,
    ) -> str:
        """
        Select appropriate opener from voiceprint (profile-driven).

        Extracts openers from voiceprint sections based on style,
        never uses hardcoded templates.

        P1.0: Now checks if opener should be skipped for casual queries.
        """
        # P1.0: Check if opener should be skipped for this query type
        query = analyzed_context.resolved_query or ""
        if self._should_skip_opener(analyzed_context, query):
            calibration.adjustments_made.append("opener:skipped_casual")
            return ""

        # Get voiceprint data
        vp_data = voiceprint.get("voiceprint", {})

        # Check for style hint from rules
        opener_style = getattr(calibration, '_opener_style', 'default')

        # Get voiceprint sections for this style
        sections = self.OPENER_STYLE_TO_VOICEPRINT_SECTION.get(
            opener_style,
            self.OPENER_STYLE_TO_VOICEPRINT_SECTION["default"]
        )

        # Try each section in order until we find examples
        # FIXED: Use random selection instead of always returning first example
        for section_path in sections:
            examples = self._get_voiceprint_value(vp_data, section_path)
            if examples:
                # For enthusiastic style, prefer exclamation marks
                if opener_style == "enthusiastic":
                    matching = [ex for ex in examples
                                if "!" in ex or any(kw in ex.lower() for kw in ["proud", "great", "amazing", "exciting"])]
                    if matching:
                        return random.choice(matching)
                # For supportive/empathetic, prefer validation phrases
                elif opener_style in ["supportive", "empathetic"]:
                    matching = [ex for ex in examples
                                if any(kw in ex.lower() for kw in ["you", "here", "got this", "understand"])]
                    if matching:
                        return random.choice(matching)
                # Default: random selection from all examples
                return random.choice(examples)

        # Ultimate fallback: signature opener (the executive's main opening)
        # FIXED: Use random selection
        signature_examples = self._get_voiceprint_value(vp_data, "signature_opener.examples")
        if signature_examples:
            return random.choice(signature_examples)

        return ""

    def _select_signoff(
        self,
        analyzed_context: "AnalyzedContext",
        voiceprint: Dict[str, Any],
        calibration: ResponseCalibration,
    ) -> str:
        """
        Select appropriate signoff from voiceprint (profile-driven).

        Extracts signoffs from voiceprint sign_off.alternatives,
        filtering based on style hints for context-appropriate selection.

        P1.0: Now checks if signoff should be skipped for casual queries.
        """
        # P1.0: Check if signoff should be skipped for this query type
        query = analyzed_context.resolved_query or ""
        if self._should_skip_signoff(analyzed_context, query):
            calibration.adjustments_made.append("signoff:skipped_casual")
            return ""

        # Get voiceprint data
        vp_data = voiceprint.get("voiceprint", {})

        # Check for style hint from rules
        signoff_style = getattr(calibration, '_signoff_style', 'default')

        # Check if meeting should be offered
        if calibration.offer_to_meet:
            signoff_style = "offer_meeting"

        # Get all signoff alternatives from voiceprint
        signoff_alternatives = self._get_voiceprint_value(vp_data, "sign_off.alternatives")

        if not signoff_alternatives:
            return ""

        # Filter based on style
        if signoff_style == "offer_meeting":
            # Prefer signoffs mentioning meetings, calls, discussion
            meeting_keywords = ["meet", "call", "discuss", "talk", "chat", "live"]
            for signoff in signoff_alternatives:
                if any(kw in signoff.lower() for kw in meeting_keywords):
                    return signoff

        elif signoff_style == "offer_summary":
            # Prefer signoffs mentioning summary, recap
            summary_keywords = ["summar", "recap", "cover"]
            for signoff in signoff_alternatives:
                if any(kw in signoff.lower() for kw in summary_keywords):
                    return signoff

        elif signoff_style == "supportive":
            # Prefer supportive, encouraging signoffs
            support_keywords = ["here", "help", "reach", "need", "support"]
            for signoff in signoff_alternatives:
                if any(kw in signoff.lower() for kw in support_keywords):
                    return signoff

        # Check attention weights for context-aware selection
        if calibration.attention_weights:
            weights = calibration.attention_weights

            # High challenge_invitation → prefer question endings
            if weights.challenge_invitation >= 0.15:
                for signoff in signoff_alternatives:
                    if "?" in signoff:
                        return signoff

            # High deference_phrases → prefer trusting endings
            if weights.deference_phrases >= 0.10:
                for signoff in signoff_alternatives:
                    if any(kw in signoff.lower() for kw in ["trust", "judgment", "you know"]):
                        return signoff

        # Default: return first alternative (the executive's primary signoff)
        return signoff_alternatives[0]

    def _summarize_reason(
        self,
        analyzed_context: "AnalyzedContext",
        calibration: ResponseCalibration,
    ) -> str:
        """Summarize calibration reason for debugging."""
        parts = []

        # Add key context
        parts.append(f"theme={analyzed_context.theme.value}")
        parts.append(f"urgency={analyzed_context.urgency.value}")
        parts.append(f"emotion={analyzed_context.user_emotion.value}")

        # Add key adjustments
        if calibration.offer_to_meet:
            parts.append("offer_meeting")
        if calibration.include_precedent:
            parts.append("include_precedent")

        return "; ".join(parts)

    def _should_skip_opener(
        self,
        analyzed_context: "AnalyzedContext",
        query: str
    ) -> bool:
        """
        Determine if opener should be skipped for casual/short queries.

        Skip opener for:
        - Greetings ("hi", "hello", "hey", "how are you")
        - Follow-up turns in conversation
        - Slack DM / 1-on-1 formality
        - Very short queries (< 5 words)
        """
        # Import TurnType here to avoid circular imports at module level
        from ..analysis.models import TurnType

        query_lower = query.lower().strip()
        logger.info(f"[P1.0] _should_skip_opener checking query: '{query[:50]}' (len={len(query.split())} words)")

        # Greeting patterns - skip formal opener
        greeting_patterns = ("hi", "hello", "hey", "how are you", "good morning", "good afternoon", "good evening", "what's up", "sup")
        if any(query_lower.startswith(p) for p in greeting_patterns):
            logger.info(f"[P1.0] Skipping opener: greeting detected - '{query[:30]}'")
            return True

        # Follow-up turns - don't need opener
        if analyzed_context.turn_type == TurnType.FOLLOWUP:
            logger.info(f"[P1.0] Skipping opener: follow-up turn")
            return True

        # Clarification turns - don't need opener
        if analyzed_context.turn_type == TurnType.CLARIFICATION:
            logger.info(f"[P1.0] Skipping opener: clarification turn")
            return True

        # Slack DM or 1-on-1 formality - more casual, skip formal opener
        if analyzed_context.formality in ["slack_dm", "1on1", "slack"]:
            logger.info(f"[P1.0] Skipping opener: casual formality '{analyzed_context.formality}'")
            return True

        # Very short queries (< 5 words) - probably a quick question
        word_count = len(query.split())
        if word_count <= 5:
            logger.info(f"[P1.0] Skipping opener: short query ({word_count} words)")
            return True

        logger.info(f"[P1.0] NOT skipping opener: query has {word_count} words, no skip conditions met")
        return False

    def _should_skip_signoff(
        self,
        analyzed_context: "AnalyzedContext",
        query: str
    ) -> bool:
        """
        Determine if signoff should be skipped for casual queries.

        Skip signoff for:
        - Greetings (just reply casually)
        - Follow-up turns
        - Very short queries (quick Q&A)
        - Clarification requests
        """
        # Import TurnType here to avoid circular imports at module level
        from ..analysis.models import TurnType

        query_lower = query.lower().strip()

        # Greeting patterns - respond casually without formal signoff
        greeting_patterns = ("hi", "hello", "hey", "how are you", "good morning", "good afternoon", "good evening", "what's up", "sup")
        if any(query_lower.startswith(p) for p in greeting_patterns):
            logger.debug(f"Skipping signoff: greeting detected")
            return True

        # Follow-up turns - don't need signoff
        if analyzed_context.turn_type == TurnType.FOLLOWUP:
            logger.debug(f"Skipping signoff: follow-up turn")
            return True

        # Clarification turns - quick response
        if analyzed_context.turn_type == TurnType.CLARIFICATION:
            logger.debug(f"Skipping signoff: clarification turn")
            return True

        # Very short queries (< 4 words) - quick Q&A doesn't need signoff
        word_count = len(query.split())
        if word_count <= 4:
            logger.debug(f"Skipping signoff: very short query ({word_count} words)")
            return True

        return False


# Factory function for dependency injection
def create_response_calibrator(
    profile_manager: Optional["ProfileManager"] = None,
) -> ResponseCalibrator:
    """Create a new ResponseCalibrator instance."""
    return ResponseCalibrator(profile_manager=profile_manager)


# Singleton instance
_default_calibrator: ResponseCalibrator = None


def get_response_calibrator() -> ResponseCalibrator:
    """Get singleton ResponseCalibrator instance."""
    global _default_calibrator
    if _default_calibrator is None:
        _default_calibrator = ResponseCalibrator()
    return _default_calibrator
