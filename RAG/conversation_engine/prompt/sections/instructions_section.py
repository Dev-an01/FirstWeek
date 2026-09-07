"""
Instructions Section Builder - Critical response instructions with ANTI-AI rules.

REFACTORED: Now imports from centralized rules.py instead of defining own constants.
This eliminates contradictions and ensures single source of truth.

Includes:
- Response mode instructions
- Information boundaries
- STRICT anti-AI formatting rules (from rules.py)
- Profile-specific word limits and "never" rules

Target: 80-120 tokens
"""

import logging
from typing import Optional, Dict, Any, List

# Import from centralized rules - SINGLE SOURCE OF TRUTH
from ..rules import (
    get_word_limit,
    get_word_limit_instruction,
    get_anti_ai_rules,
    build_response_requirements,
    build_cognitive_guidance,
    WORD_LIMITS,
)

logger = logging.getLogger(__name__)


class InstructionsSection:
    """
    Builds critical instructions section WITH anti-AI formatting rules.

    REFACTORED (2025-01-15):
    - All word limits now come from rules.py
    - All anti-AI rules now come from rules.py
    - This class is now a thin wrapper that adds path-specific logic

    The anti-AI rules are ESSENTIAL - they prevent the LLM from
    generating verbose, structured, obviously-AI output.

    Output format:
        RESPONSE REQUIREMENTS:
        - Give YOUR opinion directly
        - 2-3 sentences MAX. Opinion + brief reason. Done.

        NEVER DO THESE (AI tells):
        - AIM FOR ~35 words (max 50). Be concise but complete your thought.
        - NO bullet points, numbered lists, or markdown
        - FORBIDDEN PHRASES: Let me share, Here's my perspective...

    Target: 80-120 tokens
    """

    # Path-specific DO instructions
    # CRITICAL: Sound like a real person talking, not an AI generating text
    PATH_DO_INSTRUCTIONS = {
        "fast": [
            "Quick reply like texting a colleague",
            "Warm but brief - 1-2 sentences",
        ],
        "standard": [
            "Talk like you're chatting with a trusted colleague",
            "Share your opinion naturally with brief reasoning",
            "Flow between thoughts - don't chain points with semicolons",
        ],
        "agentic": [
            "Have a thoughtful conversation, not a structured analysis",
            "Share your thinking naturally as you would in person",
            "It's okay to say 'honestly' or 'my gut says' - be human",
        ],
        "conversational": [
            "Brief, warm response",
            "Match their energy",
        ],
    }

    # Language-specific instructions
    LANGUAGE_INSTRUCTIONS = {
        "ja": "Respond in Japanese (日本語). Use natural Japanese.",
        "en": "Respond in English. Use natural, conversational English.",
    }

    @classmethod
    def get_word_limit(cls, path: str, mode: str = "text") -> int:
        """
        Get word limit for a specific path.

        DELEGATES TO rules.py - this method exists for backward compatibility.
        All new code should import get_word_limit directly from rules.py.

        Args:
            path: Processing path (fast/standard/agentic/conversational)
            mode: Response mode (text/audio)

        Returns:
            Target word limit for the path
        """
        return get_word_limit(path, mode)

    def build(
        self,
        path: str,
        language: str,
        max_tokens: int = 100,
        is_followup: bool = False,
        profile: Optional[Dict[str, Any]] = None,
        mode: str = "text",
    ) -> str:
        """
        Build instructions section with anti-AI rules.

        REFACTORED: Uses centralized rules from rules.py

        Args:
            path: Processing path (fast/standard/agentic)
            language: Response language (en/ja)
            max_tokens: Maximum tokens for section
            is_followup: Whether this is a follow-up turn in conversation
            profile: Executive profile for profile-specific limits
            mode: Response mode (text/audio)

        Returns:
            Instructions section string with anti-AI rules
        """
        # Get path-specific DO instructions
        do_instructions = list(self.PATH_DO_INSTRUCTIONS.get(
            path,
            self.PATH_DO_INSTRUCTIONS["standard"],
        ))

        # Add language instruction
        lang_instruction = self.LANGUAGE_INSTRUCTIONS.get(language)
        if lang_instruction:
            do_instructions.append(lang_instruction)

        # Add follow-up specific instruction
        if is_followup:
            do_instructions.append("Skip signature - this is a follow-up in ongoing conversation")

        # Format DO section
        do_text = "\n".join(f"- {i}" for i in do_instructions)

        # Get word limit instruction from centralized rules
        # Use profile-specific limit if available
        word_limit = self._get_profile_word_limit(profile, path, mode)
        word_limit_instruction = f"AIM FOR ~{word_limit} words. Be concise but complete your thought."

        # Get anti-AI rules from centralized rules
        rules = get_anti_ai_rules(path, profile)

        # Build NEVER DO section
        never_items = [word_limit_instruction]
        never_items.extend(rules.forbidden_patterns)

        # Add select forbidden phrases (not all - keep prompt concise)
        key_forbidden = rules.forbidden_phrases[:8]
        if key_forbidden:
            never_items.append(f"FORBIDDEN PHRASES: {', '.join(key_forbidden[:5])}...")

        never_text = "\n".join(f"- {r}" for r in never_items)

        # Get cognitive guidance for the path
        cognitive = build_cognitive_guidance(path)

        section = f"""
RESPONSE REQUIREMENTS:
{do_text}

NEVER DO THESE (they reveal you're AI):
{never_text}
{cognitive}
"""

        logger.debug(
            f"Built instructions section for path={path}, lang={language}, followup={is_followup}: "
            f"{len(section)} chars, word_limit={word_limit}"
        )

        return section

    def _get_profile_word_limit(
        self,
        profile: Optional[Dict[str, Any]],
        path: str,
        mode: str = "text"
    ) -> int:
        """
        Get word limit from profile's response_length_guidance, or fall back to global.

        UPDATED: Now uses soft targets from rules.py instead of hard limits.

        Profile guidance maps to approximate word counts:
        - "1-2 sentences" → ~20 words (soft target)
        - "2-4 sentences" → ~40 words (soft target)
        - "5-10 sentences" → ~80 words (soft target)

        Args:
            profile: Executive profile dict
            path: Processing path
            mode: Response mode (text/audio)

        Returns:
            Word limit for this context
        """
        # Get base limit from centralized rules
        base_limit = get_word_limit(path, mode)

        if not profile:
            return base_limit

        # Check for profile-specific length guidance
        comm_style = profile.get("communication_style", {})
        length_guidance = comm_style.get("response_length_guidance", {})

        # Also check inference_framework (sample has guidance there)
        inference = profile.get("inference_framework", {})
        inf_guidance = inference.get("response_length_guidance", {})

        # Merge guidance sources
        guidance = {**length_guidance, **inf_guidance}

        if not guidance:
            return base_limit

        # Map path to guidance key and adjust limit
        if path == "fast":
            simple_guidance = guidance.get("simple_questions", "")
            if "1-2 sentences" in simple_guidance:
                return 20  # Slightly higher than base for natural expression
        elif path == "standard":
            opinion_guidance = guidance.get("opinion_questions", "")
            if "2-4 sentences" in opinion_guidance:
                return 45  # Allow room for opinion + reasoning
            elif "5-10 sentences" in opinion_guidance:
                return 70
        elif path == "agentic":
            complex_guidance = guidance.get("complex_decisions", "")
            if "5-10 sentences" in complex_guidance:
                return 80
            elif "10+" in complex_guidance.lower():
                return 120

        return base_limit

    def _get_profile_never_rules(self, profile: Optional[Dict[str, Any]]) -> List[str]:
        """
        Extract "never" rules from profile's communication_style.

        DEPRECATED: This logic is now in rules.py _extract_profile_never_rules()
        Kept for backward compatibility but delegates to centralized function.

        Args:
            profile: Executive profile dict

        Returns:
            List of profile-specific forbidden patterns
        """
        if not profile:
            return []

        # Get rules from centralized function
        rules = get_anti_ai_rules("standard", profile)

        # Return only the profile-specific patterns (not universal ones)
        # This is approximate since we merged them in get_anti_ai_rules
        comm_style = profile.get("communication_style", {})
        length_guidance = comm_style.get("response_length_guidance", {})

        never_rules = []
        never_text = length_guidance.get("never", "")

        if never_text:
            items = [item.strip() for item in never_text.replace("(use numbered ①②③ instead)", "").split(",")]
            for item in items:
                if item and len(item) > 3:
                    never_rules.append(f"NO {item}")

        return never_rules


# =============================================================================
# BACKWARD COMPATIBILITY EXPORTS
# =============================================================================
# These are kept so existing code that imports from this module still works.
# New code should import directly from rules.py

def get_word_limit_for_path(path: str) -> int:
    """
    DEPRECATED: Use rules.get_word_limit() instead.
    """
    logger.warning(
        "get_word_limit_for_path is deprecated. "
        "Import get_word_limit from conversation_engine.prompt.rules instead."
    )
    return get_word_limit(path)
