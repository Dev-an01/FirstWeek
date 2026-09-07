"""
Executive Rules - Per-executive calibration adjustments.

Applies executive-specific overrides based on profile characteristics.
Dynamically extracts settings from voiceprint data for any executive.
"""

import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import ResponseCalibration

logger = logging.getLogger(__name__)


class ExecutiveRules:
    """
    Per-executive calibration adjustments.

    Applies executive-specific overrides based on voiceprint personality
    and known preferences.

    Data-Agnostic Design:
    - Extracts settings dynamically from voiceprint data
    - Works with ANY executive, not just predefined profiles
    - Falls back to sensible defaults for missing voiceprint fields

    Thread-safe: No mutable state.
    """

    # Default settings when no specific override exists
    DEFAULT_SETTINGS: Dict[str, Any] = {
        "min_warmth": 4,
        "max_warmth": 10,
        "min_formality": 3,
        "max_formality": 9,
        "emoji_policy": "context_aware",  # Default to context-aware
        "analogy_preference": False,
        "data_emphasis": False,
        "team_focus": False,
        "precision_preference": False,
        "signature_phrases": [],
    }

    def __init__(self):
        """Initialize executive rules."""
        # Cache for dynamically extracted settings
        self._voiceprint_cache: Dict[str, Dict[str, Any]] = {}
        logger.debug("ExecutiveRules initialized (data-agnostic mode)")

    def extract_settings_from_voiceprint(
        self,
        voiceprint: Dict[str, Any],
        profile_id: str = "",
    ) -> Dict[str, Any]:
        """
        Dynamically extract settings from voiceprint data.

        This makes the system work with ANY executive's voiceprint,
        not just predefined profiles.

        Args:
            voiceprint: Raw voiceprint data from database
            profile_id: Profile ID for caching

        Returns:
            Settings dict derived from voiceprint analysis
        """
        if not voiceprint:
            return dict(self.DEFAULT_SETTINGS)

        # Check cache first
        if profile_id and profile_id in self._voiceprint_cache:
            return self._voiceprint_cache[profile_id]

        settings = dict(self.DEFAULT_SETTINGS)

        # Extract from style_markers
        style_markers = voiceprint.get("style_markers", {})

        # Warmth from emotional language patterns
        emotional_lang = voiceprint.get("emotional_language", {})
        if emotional_lang.get("enthusiasm_markers") or emotional_lang.get("supportive_phrases"):
            settings["min_warmth"] = 6  # Warm communicator

        # Data emphasis from numbers_cadence
        numbers_cadence = voiceprint.get("numbers_cadence", {})
        if numbers_cadence.get("data_comfort") == "high" or numbers_cadence.get("precision_level") == "high":
            settings["data_emphasis"] = True

        # Analogy preference from thinking_patterns
        thinking = voiceprint.get("thinking_patterns", {})
        if thinking.get("analogy_types") or style_markers.get("uses_analogies"):
            settings["analogy_preference"] = True

        # Precision preference from style markers
        if style_markers.get("precision_markers") or thinking.get("clarity_phrases"):
            settings["precision_preference"] = True

        # Team focus from emotional language
        if emotional_lang.get("team_recognition") or emotional_lang.get("collaborative_phrases"):
            settings["team_focus"] = True

        # Decision style from decision_cadence
        decision_cadence = voiceprint.get("decision_cadence", {})
        if decision_cadence.get("collaborative_phrases"):
            settings["decision_style"] = "consultative"
        elif decision_cadence.get("directive_phrases"):
            settings["decision_style"] = "directive"
        else:
            settings["decision_style"] = "balanced"

        # Signature phrases from multiple sources
        signature_phrases = []

        # From signature_opener
        sig_opener = voiceprint.get("signature_opener", {})
        for opener_type in ["thinking", "supportive", "direct", "enthusiastic"]:
            openers = sig_opener.get(opener_type, [])
            if openers and isinstance(openers, list):
                signature_phrases.extend(openers[:2])

        # From decision_cadence
        if decision_cadence.get("key_phrases"):
            signature_phrases.extend(decision_cadence["key_phrases"][:2])

        # From risk_language
        risk_lang = voiceprint.get("risk_language", {})
        if risk_lang.get("concern_phrases"):
            signature_phrases.extend(risk_lang["concern_phrases"][:2])

        settings["signature_phrases"] = signature_phrases[:5]  # Limit to 5

        # Always use context-aware emoji policy for dynamic profiles
        settings["emoji_policy"] = "context_aware"

        # Cache the extracted settings
        if profile_id:
            self._voiceprint_cache[profile_id] = settings

        logger.debug(
            f"Extracted settings from voiceprint for {profile_id}: "
            f"warmth={settings['min_warmth']}, data={settings['data_emphasis']}, "
            f"analogy={settings['analogy_preference']}, phrases={len(settings['signature_phrases'])}"
        )

        return settings

    def apply(
        self,
        calibration: "ResponseCalibration",
        profile_id: str,
        formality_context: Optional[str] = None,
        voiceprint: Optional[Dict[str, Any]] = None,
    ) -> "ResponseCalibration":
        """
        Apply executive-specific rules to calibration.

        Args:
            calibration: Current ResponseCalibration
            profile_id: Executive profile ID
            formality_context: Optional context (e.g., "slack", "board")
            voiceprint: Optional voiceprint data for dynamic extraction

        Returns:
            Modified ResponseCalibration
        """
        adjustments_made = list(calibration.adjustments_made)

        # Get executive settings - prefer voiceprint extraction over hardcoded
        if voiceprint:
            settings = self.extract_settings_from_voiceprint(voiceprint, profile_id)
        else:
            settings = self.get_executive_settings(profile_id)

        # Apply minimum warmth
        min_warmth = settings.get("min_warmth", self.DEFAULT_SETTINGS["min_warmth"])
        if calibration.warmth_level < min_warmth:
            calibration.warmth_level = min_warmth
            adjustments_made.append(f"exec:min_warmth_{min_warmth}")

        # Apply maximum warmth
        max_warmth = settings.get("max_warmth", self.DEFAULT_SETTINGS["max_warmth"])
        if calibration.warmth_level > max_warmth:
            calibration.warmth_level = max_warmth

        # Apply formality bounds
        min_formality = settings.get("min_formality", self.DEFAULT_SETTINGS["min_formality"])
        max_formality = settings.get("max_formality", self.DEFAULT_SETTINGS["max_formality"])
        calibration.formality_level = max(
            min_formality,
            min(calibration.formality_level, max_formality)
        )

        # Apply context-aware emoji policy
        # Key insight: Emoji usage should be based on QUERY CONTEXT (urgency, emotion)
        # NOT restricted by default. The situation_rules and baseline already set
        # appropriate emoji_usage based on voiceprint and context.

        emoji_policy = settings.get("emoji_policy", "default")

        if emoji_policy == "context_aware":
            # ONLY restrict emojis in truly formal contexts
            # Let the situational calibration (urgency/emotion) drive emoji usage
            formal_contexts = ["board_meeting", "legal", "formal", "investor"]
            if formality_context and formality_context.lower() in formal_contexts:
                if calibration.emoji_usage != "none":
                    calibration.emoji_usage = "none"
                    adjustments_made.append("exec:emoji_formal_restricted")
            # Otherwise: KEEP the emoji_usage set by situation_rules (based on urgency/emotion)
        else:
            # Legacy behavior: use emoji_channels list
            emoji_channels = settings.get("emoji_channels", [])
            if emoji_channels and formality_context:
                if formality_context not in emoji_channels:
                    if calibration.emoji_usage != "none":
                        calibration.emoji_usage = "none"
                        adjustments_made.append("exec:emoji_restricted")
                elif calibration.emoji_usage == "none":
                    calibration.emoji_usage = "minimal"

        # Store preferences for later use
        calibration._analogy_preference = settings.get("analogy_preference", False)
        calibration._data_emphasis = settings.get("data_emphasis", False)
        calibration._team_focus = settings.get("team_focus", False)
        calibration._precision_preference = settings.get("precision_preference", False)
        calibration._signature_phrases = settings.get("signature_phrases", [])

        adjustments_made.append(f"exec:profile_{profile_id}")
        calibration.adjustments_made = adjustments_made

        logger.debug(f"Applied executive rules for {profile_id}")
        return calibration

    def get_executive_settings(
        self,
        profile_id: str,
        voiceprint: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Get settings for a specific executive.

        Priority:
        1. Voiceprint-extracted settings (if voiceprint provided)
        2. Cached voiceprint-extracted settings (from previous calls)
        3. Default settings

        Args:
            profile_id: Executive profile ID
            voiceprint: Optional voiceprint data

        Returns:
            Settings dict derived from voiceprint or defaults
        """
        # If voiceprint provided, extract and cache
        if voiceprint:
            return self.extract_settings_from_voiceprint(voiceprint, profile_id)

        # Check if we have cached settings from previous voiceprint extraction
        if profile_id in self._voiceprint_cache:
            return self._voiceprint_cache[profile_id]

        # Return defaults for unknown profiles
        return dict(self.DEFAULT_SETTINGS)

    def get_signature_phrases(self, profile_id: str) -> List[str]:
        """Get signature phrases for an executive."""
        settings = self.get_executive_settings(profile_id)
        return settings.get("signature_phrases", [])

    def get_decision_style(self, profile_id: str) -> str:
        """Get decision-making style for an executive."""
        settings = self.get_executive_settings(profile_id)
        return settings.get("decision_style", "balanced")

    def should_use_analogies(self, profile_id: str) -> bool:
        """Check if executive prefers analogies."""
        settings = self.get_executive_settings(profile_id)
        return settings.get("analogy_preference", False)

    def should_emphasize_data(self, profile_id: str) -> bool:
        """Check if executive prefers data emphasis."""
        settings = self.get_executive_settings(profile_id)
        return settings.get("data_emphasis", False)


# Singleton instance
_default_rules: ExecutiveRules = None


def get_executive_rules() -> ExecutiveRules:
    """Get singleton ExecutiveRules instance."""
    global _default_rules
    if _default_rules is None:
        _default_rules = ExecutiveRules()
    return _default_rules
