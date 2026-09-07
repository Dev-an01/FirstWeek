"""
Prompt Assembler - Stage 5 of the Conversation Engine.

REFACTORED (2025-01-15): Now uses centralized rules from rules.py
- Word limits come from rules.get_word_limit()
- Audio mode adjustments handled in rules.py
- Single source of truth eliminates contradictions

Builds final system and user prompts from all pipeline outputs.
Target latency: ~3ms (string assembly only).
"""

import time
import logging
from typing import Optional, Tuple, Dict, Any, TYPE_CHECKING

from .budget import TokenBudgetManager, TokenBudget, get_budget_manager
from .templates import (
    BaseTemplate,
    FastTemplate,
    StandardTemplate,
    AgenticTemplate,
)
from .sections import (
    IdentitySection,
    ConversationContextSection,
    ExampleSection,
    CalibrationSection,
    ValuesSection,
    PrecedentSection,
    RetrievedContextSection,
    InstructionsSection,
    SpeakingStyleSection,
    ReasoningSection,  # NEW: Cognitive Scaffolding
)
# Import from centralized rules - SINGLE SOURCE OF TRUTH
from .rules import get_word_limit, get_word_limit_instruction

if TYPE_CHECKING:
    from profile_management.profile_manager import ProfileManager
    from llm_integration.prompt_builder import RetrievalContext
    from ..context.models import ManagedContext, ConversationMode
    from ..analysis.models import AnalyzedContext
    from ..calibration.models import ResponseCalibration
    from ..examples.models import SelectedExample
    from ..precedents.models import SelectedPrecedent

logger = logging.getLogger(__name__)


class PromptAssembler:
    """
    Prompt Assembler (Stage 5).

    Builds final system and user prompts from all pipeline outputs.

    Process:
    1. Select template based on path
    2. Calculate section budgets with dynamic reallocation
    3. Build each section using section builders
    4. Assemble in template order
    5. Build user prompt with retrieved context
    6. Validate against token budget

    Target latency: ~3ms (string assembly only)

    Thread-safe: All operations are stateless.
    """

    def __init__(
        self,
        profile_manager: Optional["ProfileManager"] = None,
    ):
        """
        Initialize PromptAssembler.

        Args:
            profile_manager: Optional ProfileManager for loading profiles
        """
        self._profile_manager = profile_manager

        # Section builders
        self._reasoning = ReasoningSection()  # NEW: Initialize reasoning section
        self._identity = IdentitySection()
        self._conversation_context = ConversationContextSection()
        self._example = ExampleSection()
        self._calibration = CalibrationSection()
        self._values = ValuesSection()
        self._precedent = PrecedentSection()
        self._retrieved_context = RetrievedContextSection()
        self._instructions = InstructionsSection()
        self._speaking_style = SpeakingStyleSection()

        # Templates
        self._templates: Dict[str, BaseTemplate] = {
            "fast": FastTemplate(),
            "standard": StandardTemplate(),
            "agentic": AgenticTemplate(),
        }

        # Budget manager
        self._budget_manager = get_budget_manager()

        logger.debug("PromptAssembler initialized")

    def assemble(
        self,
        profile_id: str,
        path: str,
        language: str,
        retrieved_context: "RetrievalContext",
        managed_context: "ManagedContext",
        analyzed_context: "AnalyzedContext",
        calibration: "ResponseCalibration",
        selected_example: "SelectedExample",
        selected_precedent: "SelectedPrecedent",
        audio_mode: bool = False,
    ) -> Tuple[str, str]:
        """
        Assemble final prompts from all pipeline outputs.

        Args:
            profile_id: Executive profile ID
            path: Processing path (fast/standard/agentic)
            language: Response language (en/ja)
            retrieved_context: Vector/graph search results
            managed_context: From Phase 2
            analyzed_context: From Phase 3
            calibration: From Phase 3
            selected_example: From Phase 4
            selected_precedent: From Phase 4
            audio_mode: If True, include speaking style patterns for natural speech

        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        start = time.time()

        try:
            # Load profile
            profile = self._load_profile(profile_id)

            # Select template
            template = self._templates.get(path, self._templates["standard"])

            # Determine context flags for budget calculation
            from ..context.models import ConversationMode
            has_session = managed_context.mode != ConversationMode.STATELESS
            has_precedent = not selected_precedent.skipped

            # Calculate budgets with dynamic reallocation
            budget = self._budget_manager.create_budget(path, has_session, has_precedent)

            # Get effective sections for this context
            effective_sections = template.get_effective_sections(has_session, has_precedent)

            # CRITICAL: Inject "reasoning" section at the very beginning (before identity)
            # This ensures the cognitive scaffolding is the first thing the LLM processes
            if "reasoning" not in effective_sections:
                effective_sections.insert(0, "reasoning")

            # Build sections
            sections = []
            for section_name in effective_sections:
                section_budget = template.get_section_budget(section_name)

                section_text = self._build_section(
                    section_name=section_name,
                    budget=section_budget,
                    profile=profile,
                    managed_context=managed_context,
                    analyzed_context=analyzed_context,
                    calibration=calibration,
                    selected_example=selected_example,
                    selected_precedent=selected_precedent,
                    path=path,
                    language=language,
                )

                if section_text:
                    sections.append(section_text.strip())
                    # Record actual usage
                    actual_tokens = self._budget_manager.count_tokens(section_text)
                    budget.record_usage(section_name, actual_tokens)

            # Add speaking style section for audio mode (natural speech patterns)
            if audio_mode and profile:
                # speaking_patterns_video is at top level of profile (not inside voiceprint)
                speaking_patterns = None
                if isinstance(profile, dict):
                    speaking_patterns = profile.get("speaking_patterns_video")
                else:
                    speaking_patterns = getattr(profile, "speaking_patterns_video", None)

                if speaking_patterns:
                    # Create a dict with speaking_patterns_video for the section builder
                    speaking_style_text = self._speaking_style.build(
                        voiceprint={"speaking_patterns_video": speaking_patterns},
                        language=language,
                        max_tokens=90,
                    )
                    if speaking_style_text:
                        sections.append(speaking_style_text.strip())
                        logger.debug(f"Added speaking style section for audio_mode (lang={language})")

            # Assemble system prompt
            system_prompt = "\n\n".join(sections)

            # Build user prompt
            user_prompt = self._build_user_prompt(
                query=managed_context.resolved_query or managed_context.original_query,
                retrieved_context=retrieved_context,
                path=path,
                calibration=calibration,
                audio_mode=audio_mode,
                profile=profile,  # Pass profile for voice-specific guidance
            )

            # Log metrics
            assembly_time = (time.time() - start) * 1000
            system_tokens = self._budget_manager.count_tokens(system_prompt)
            user_tokens = self._budget_manager.count_tokens(user_prompt)

            logger.debug(
                f"Prompt assembled in {assembly_time:.1f}ms "
                f"(system: {system_tokens} tokens, user: {user_tokens} tokens, "
                f"path: {path}, sections: {len(sections)})"
            )

            return system_prompt, user_prompt

        except Exception as e:
            logger.error(f"Prompt assembly failed: {e}", exc_info=True)
            # Return empty prompts to trigger legacy fallback
            return "", ""

    def _load_profile(self, profile_id: str) -> Optional[Dict[str, Any]]:
        """
        Load executive profile.

        Args:
            profile_id: Executive profile ID

        Returns:
            Profile dict or None
        """
        if self._profile_manager:
            try:
                return self._profile_manager.get_profile(profile_id)
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_id}: {e}")

        # Fallback: try to import and get singleton
        try:
            from profile_management.profile_manager import get_profile_manager
            pm = get_profile_manager()
            return pm.get_profile(profile_id)
        except Exception as e:
            logger.warning(f"Failed to load profile via singleton: {e}")

        return None

    def _build_section(
        self,
        section_name: str,
        budget: int,
        profile: Optional[Dict[str, Any]],
        managed_context: "ManagedContext",
        analyzed_context: "AnalyzedContext",
        calibration: "ResponseCalibration",
        selected_example: "SelectedExample",
        selected_precedent: "SelectedPrecedent",
        path: str,
        language: str,
    ) -> str:
        """
        Build individual section by name.

        Args:
            section_name: Name of section to build
            budget: Token budget for section
            ... other context objects

        Returns:
            Section text string
        """
        # Determine if this is a follow-up turn (for skipping openers/signoffs/signatures)
        is_followup = False
        try:
            from ..analysis.models import TurnType
            if analyzed_context.turn_type in [TurnType.FOLLOWUP, TurnType.CLARIFICATION]:
                is_followup = True
        except (ImportError, AttributeError):
            pass

        try:
            if section_name == "reasoning":  # Cognitive scaffolding (System 2)
                return self._reasoning.build(
                    profile,
                    max_tokens=budget,
                    path=path,
                    language=language,
                )

            elif section_name == "identity":
                # Extract voiceprint and communication_examples from profile for personality injection
                voiceprint = None
                communication_examples = None
                if profile:
                    if isinstance(profile, dict):
                        voiceprint = profile.get("voiceprint")
                        communication_examples = profile.get("communication_examples")
                    else:
                        voiceprint = getattr(profile, "voiceprint", None)
                        communication_examples = getattr(profile, "communication_examples", None)

                return self._identity.build(
                    profile,
                    voiceprint=voiceprint,
                    calibration=calibration,  # Pass calibration for adaptive emoji/tone
                    communication_examples=communication_examples,
                    analyzed_context=analyzed_context,  # Pass context for adaptive voiceprint emphasis
                    max_tokens=budget,
                    path=path,
                    is_followup=is_followup,
                    language=language,  # Pass language for example/pattern selection
                )

            elif section_name == "conversation_context":
                return self._conversation_context.build(
                    managed_context,
                    analyzed_context,
                    calibration,
                    budget,
                )

            elif section_name == "example":
                return self._example.build(selected_example, budget)

            elif section_name == "calibration":
                return self._calibration.build(
                    calibration,
                    analyzed_context,
                    budget,
                    path=path,
                    is_followup=is_followup,
                )

            elif section_name == "values":
                return self._values.build(
                    profile,
                    analyzed_context,
                    budget,
                )

            elif section_name == "precedent":
                return self._precedent.build(selected_precedent, budget)

            elif section_name == "instructions":
                return self._instructions.build(
                    path,
                    language,
                    budget,
                    is_followup=is_followup,
                    profile=profile,  # Pass profile for word limits and "never" rules
                )

            else:
                logger.warning(f"Unknown section: {section_name}")
                return ""

        except Exception as e:
            logger.warning(f"Failed to build section {section_name}: {e}")
            return ""

    # DEPRECATED: Audio mode adjustments now handled in rules.py
    # Kept for backward compatibility but no longer used
    AUDIO_MODE_WORD_ADJUSTMENTS = {
        "fast": 10,      # DEPRECATED - use get_word_limit(path, "audio")
        "standard": 20,  # DEPRECATED - use get_word_limit(path, "audio")
        "agentic": 20,   # DEPRECATED - use get_word_limit(path, "audio")
    }

    def _build_user_prompt(
        self,
        query: str,
        retrieved_context: "RetrievalContext",
        path: str,
        calibration: "ResponseCalibration",
        audio_mode: bool = False,
        profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Build user prompt with retrieved context.

        Args:
            query: User's query (resolved)
            retrieved_context: Vector/graph search results
            path: Processing path
            calibration: Response calibration
            audio_mode: If True, use higher word limits for natural speech
            profile: Executive profile for voice-specific guidance

        Returns:
            User prompt string
        """
        # Build context section
        context_section = self._retrieved_context.build(retrieved_context, path)

        # Get word limit from centralized rules.py (SINGLE SOURCE OF TRUTH)
        # Audio mode adjustment is now handled internally by get_word_limit
        mode = "audio" if audio_mode else "text"
        max_words = get_word_limit(path, mode)

        # Determine if this is sample for voice-specific guidance
        profile_name = ""
        if profile:
            profile_name = profile.get("name", "").lower() if isinstance(profile, dict) else ""

        # Knowledge boundary rules (CRITICAL - prevent hallucination)
        knowledge_rules = """⛔ STOP - CHECK BEFORE ANSWERING ⛔
Is this asking for SPECIFIC FACTS (time, date, number, meeting, schedule)?
→ Look at the CONTEXT above. Is the answer there?
→ If NO: Say "I don't have that information" or "Let me check"
→ NEVER INVENT: times (like "7 pm"), dates, numbers, names
→ VIOLATING THIS = LYING TO THE USER

✓ "I don't have that meeting on my calendar. Let me check."
✗ "The meeting is at 7 pm" (when no meeting data exists)"""

        voice_guidance = f"""★★★ SPEAK LIKE A REAL PERSON ★★★
✓ REAL: "Singapore is interesting, but I think we should wait. The core business needs attention first."
✓ UNKNOWN: "I don't have that information. Let me check."
✗ AI: "We should focus on core, evaluate markets, and then consider expansion."
Each thought = one sentence. No comma-chains. ~{max_words} words. Warm and direct."""

        # Detect if query is asking for specific facts (time, date, number, schedule)
        factual_keywords = ['what time', 'when is', 'how many', 'how much', 'what date', 'schedule', 'meeting time', 'deadline']
        is_factual_query = any(kw in query.lower() for kw in factual_keywords)

        if is_factual_query:
            query_block = f"""⛔ FACTUAL QUERY DETECTED ⛔
The user is asking for SPECIFIC INFORMATION (time/date/number).
CHECK: Is this information in the CONTEXT above?
- If YES: Answer with the exact information from context
- If NO: You MUST say "I don't have that information" or "Let me check my calendar"
- NEVER INVENT times, dates, or numbers

USER QUERY: "{query}"

Remember: If the context doesn't contain meeting times, you DON'T KNOW the meeting time."""
        else:
            query_block = f"""Answer this query:
"{query}"

{knowledge_rules}"""

        user_prompt = f"""{context_section}

{query_block}

{voice_guidance}
"""
        logger.info(f"[DEBUG] PromptAssembler user prompt includes voice guidance for profile")
        return user_prompt


# Singleton instance
_default_assembler: Optional[PromptAssembler] = None


def get_prompt_assembler() -> PromptAssembler:
    """Get singleton PromptAssembler instance."""
    global _default_assembler
    if _default_assembler is None:
        _default_assembler = PromptAssembler()
    return _default_assembler


def create_prompt_assembler(
    profile_manager: Optional["ProfileManager"] = None,
) -> PromptAssembler:
    """Create a new PromptAssembler instance."""
    return PromptAssembler(profile_manager=profile_manager)
