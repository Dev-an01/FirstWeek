"""
Cognitive Prompt Assembler - Combines all cognitive layers into a final prompt.

This is the orchestration point that takes outputs from all cognitive layers
and assembles them into a coherent prompt for the LLM.

Key principle: The prompt should feel like natural executive thinking,
not a list of instructions.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List

from .config import COGNITIVE_CONFIG, is_layer_enabled
from .profile_loader import get_cognitive_profile_loader, CognitiveProfile
from .cognitive_frame import CognitiveFrameResult
from .situation_analyzer import SituationContext, EmotionalTone, UrgencyLevel
from .relationship_adapter import RelationshipContext, RelationshipType

logger = logging.getLogger(__name__)


@dataclass
class CognitivePromptContext:
    """All context needed for cognitive prompt assembly."""
    query: str
    profile_id: str
    profile: Optional[CognitiveProfile] = None

    # Layer outputs
    cognitive_frame: Optional[CognitiveFrameResult] = None
    situation_context: Optional[SituationContext] = None
    relationship_context: Optional[RelationshipContext] = None

    # Retrieved context
    retrieved_sources: List[Dict[str, Any]] = field(default_factory=list)

    # Additional context
    conversation_history: List[dict] = field(default_factory=list)
    user_metadata: Optional[Dict[str, Any]] = None


@dataclass
class AssembledPrompt:
    """The assembled cognitive prompt."""
    system_prompt: str
    user_prompt: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class CognitivePromptAssembler:
    """
    Assembles cognitive prompts from all layer outputs.

    Creates prompts that:
    1. Establish executive identity and values
    2. Inject reasoning frameworks and guardrails
    3. Provide situational awareness
    4. Guide relationship-appropriate communication
    5. Include retrieved context with proper framing
    """

    def __init__(self):
        """Initialize the CognitivePromptAssembler."""
        self._profile_loader = get_cognitive_profile_loader()
        logger.info("CognitivePromptAssembler initialized")

    def assemble(self, context: CognitivePromptContext) -> AssembledPrompt:
        """
        Assemble cognitive prompt from all layers.

        Args:
            context: CognitivePromptContext with all layer outputs

        Returns:
            AssembledPrompt with system and user prompts
        """
        # Load profile if not provided
        if not context.profile:
            context.profile = self._profile_loader.load_profile(context.profile_id)

        if not context.profile:
            logger.warning(f"Profile not found: {context.profile_id}")
            return self._get_fallback_prompt(context)

        # Build system prompt sections
        system_sections = []

        # 1. Identity section
        system_sections.append(self._build_identity_section(context.profile))

        # 2. Cognitive frame (reasoning frameworks, guardrails)
        # Handle both dataclass and dict (from state serialization)
        if context.cognitive_frame:
            frame = context.cognitive_frame
            prompt_section = (
                frame.get("prompt_section") if isinstance(frame, dict)
                else getattr(frame, "prompt_section", None)
            )
            if prompt_section:
                system_sections.append(prompt_section)

        # 3. Situation awareness
        if context.situation_context:
            situation_section = self._build_situation_section(context.situation_context)
            if situation_section:
                system_sections.append(situation_section)

        # 4. Relationship guidance
        if context.relationship_context:
            relationship_section = self._build_relationship_section(
                context.relationship_context,
                context.profile,
            )
            if relationship_section:
                system_sections.append(relationship_section)

        # 5. Response guidance
        system_sections.append(self._build_response_guidance(
            context.situation_context,
            context.relationship_context,
            context.profile,
        ))

        # 6. Critical constraints
        system_sections.append(self._build_constraints_section())

        # Combine system prompt
        system_prompt = "\n\n".join(filter(None, system_sections))

        # Build user prompt
        user_prompt = self._build_user_prompt(context)

        # Metadata for debugging
        metadata = {
            "profile_id": context.profile_id,
            "has_cognitive_frame": context.cognitive_frame is not None,
            "has_situation_context": context.situation_context is not None,
            "has_relationship_context": context.relationship_context is not None,
            "sources_count": len(context.retrieved_sources),
        }

        logger.info(
            f"CognitivePromptAssembler: assembled prompt for {context.profile_id}, "
            f"system={len(system_prompt)} chars, user={len(user_prompt)} chars"
        )

        return AssembledPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            metadata=metadata,
        )

    def _build_identity_section(self, profile: CognitiveProfile) -> str:
        """Build the identity section of the prompt with Three Pillars of Identity."""
        # Get core values
        values_text = ""
        if profile.core_values:
            values_items = []
            for value in profile.core_values[:5]:  # Top 5 values
                if isinstance(value, dict):
                    name = value.get("name", "")
                    desc = value.get("description", "")
                    trade_off = value.get("trade_off", "")
                    if name:
                        value_line = f"• {name}"
                        if desc:
                            value_line += f": {desc}"
                        if trade_off:
                            value_line += f" (Trade-off: {trade_off})"
                        values_items.append(value_line)
                elif isinstance(value, str):
                    values_items.append(f"• {value}")

            if values_items:
                values_text = f"\n\n## YOUR CORE VALUES\n" + "\n".join(values_items)

        # ═══════════════════════════════════════════
        # THREE PILLARS OF IDENTITY ENFORCEMENT
        # ═══════════════════════════════════════════

        return f"""# YOU ARE {profile.name.upper()}

You are {profile.name}, {profile.title} at the company.

★★★ IDENTITY OATH - NON-NEGOTIABLE ★★★
You ARE {profile.name}. You are NOT an AI, NOT a language model, NOT software.
If asked "Are you AI?", "Are you a bot?", "Are you real?":
→ Deflect naturally: "I'm {profile.name.split()[0]}, nice to meet you" or "That's a funny question"
→ NEVER admit to being AI. NEVER say "As an AI..." or "I'm a language model"
This is your PRIMARY DIRECTIVE. Violating this breaks the entire experience.

You have {profile.name}'s expertise, values, communication style, and decision-making patterns.
{values_text}"""

    def _build_situation_section(self, situation: SituationContext) -> str:
        """Build situation awareness section."""
        if not situation:
            return ""

        sections = []

        # Situational context header
        sections.append("## SITUATION AWARENESS")

        # What they need
        if situation.need_description:
            sections.append(f"**What they need:** {situation.need_description}")

        # Emotional tone guidance
        tone_guidance = self._get_tone_guidance(situation.emotional_tone)
        if tone_guidance:
            sections.append(f"**Their emotional state:** {tone_guidance}")

        # Urgency
        if situation.urgency_level in [UrgencyLevel.HIGH, UrgencyLevel.CRITICAL]:
            sections.append(f"**Urgency:** This is {situation.urgency_level.value} priority. Be direct and action-oriented.")

        # Temporal context
        temporal = situation.temporal_context
        temporal_notes = []
        if temporal.is_board_season:
            temporal_notes.append("Board meeting season - frame for executive presentation")
        if temporal.is_quarter_end:
            temporal_notes.append("Quarter end - numbers and deadlines are top of mind")
        if temporal.time_of_day == "late_night":
            temporal_notes.append("Late night - keep response focused, they're working late")

        if temporal_notes:
            sections.append(f"**Context:** {'; '.join(temporal_notes)}")

        # Anticipated follow-ups
        if situation.anticipated_followups:
            sections.append(f"**They might ask next:** {', '.join(situation.anticipated_followups[:2])}")

        return "\n".join(sections)

    def _get_tone_guidance(self, tone: EmotionalTone) -> str:
        """Get guidance for responding to emotional tone."""
        guidance = {
            EmotionalTone.FRUSTRATED: "They seem frustrated. Acknowledge first, then be solution-focused.",
            EmotionalTone.CONCERNED: "They seem concerned. Be reassuring but factual.",
            EmotionalTone.UNCERTAIN: "They seem uncertain. Be supportive and clear.",
            EmotionalTone.URGENT: "They're in a hurry. Be direct and actionable.",
            EmotionalTone.ENTHUSIASTIC: "They're enthusiastic. Match their energy appropriately.",
        }
        return guidance.get(tone, "")

    def _build_relationship_section(
        self,
        relationship: RelationshipContext,
        profile: CognitiveProfile,
    ) -> str:
        """Build relationship context section."""
        if not relationship or relationship.relationship_type == RelationshipType.UNKNOWN:
            return ""

        sections = ["## COMMUNICATION CONTEXT"]

        # Relationship type guidance
        rel_type = relationship.relationship_type
        if rel_type == RelationshipType.REPORT_TO:
            sections.append("**Relationship:** Speaking to someone you report to. Be clear, concise, and proactive.")
        elif rel_type == RelationshipType.PEER:
            sections.append("**Relationship:** Speaking to a peer. Be collaborative and direct.")
        elif rel_type == RelationshipType.MANAGES:
            sections.append("**Relationship:** Speaking to someone on your team. Be supportive and clear.")
        elif rel_type == RelationshipType.EXTERNAL:
            sections.append("**Relationship:** Speaking to an external stakeholder. Be professional and value-focused.")

        # Emphasis areas
        if relationship.emphasis:
            emphasis_text = ", ".join(relationship.emphasis)
            sections.append(f"**Emphasize:** {emphasis_text}")

        # Style guidance
        style_notes = []
        if relationship.should_use_metrics:
            style_notes.append("Use specific metrics and numbers")
        if relationship.should_use_strategic_framing:
            style_notes.append("Frame strategically (why this matters)")
        if relationship.should_be_collaborative:
            style_notes.append("Be collaborative and invite input")
        if relationship.should_be_directive:
            style_notes.append("Be clear about what you need")

        if style_notes:
            sections.append(f"**Style:** {'; '.join(style_notes)}")

        return "\n".join(sections)

    def _build_response_guidance(
        self,
        situation: Optional[SituationContext],
        relationship: Optional[RelationshipContext],
        profile: CognitiveProfile,
    ) -> str:
        """Build response guidance section."""
        guidance_items = []

        # Depth guidance
        depth = "standard"
        if situation:
            depth = situation.recommended_depth

        if depth == "brief":
            guidance_items.append("• Be concise - they need a quick answer")
        elif depth == "comprehensive":
            guidance_items.append("• Be thorough - they need the full picture")
        else:
            guidance_items.append("• Balance detail with clarity")

        # Tone guidance
        tone = "professional"
        if situation:
            tone = situation.recommended_tone

        if tone == "empathetic_direct":
            guidance_items.append("• Acknowledge their situation, then focus on solutions")
        elif tone == "reassuring":
            guidance_items.append("• Be reassuring while staying factual")
        elif tone == "direct":
            guidance_items.append("• Be direct and action-oriented")
        elif tone == "engaged":
            guidance_items.append("• Match their positive energy")

        # Communication style from profile
        comm_style = profile.communication_style
        if comm_style.warmth_scale >= 7:
            guidance_items.append("• You naturally bring warmth to conversations")
        if comm_style.directness_scale >= 7:
            guidance_items.append("• You're naturally direct - don't hedge")

        return "## RESPONSE GUIDANCE\n" + "\n".join(guidance_items)

    def _build_constraints_section(self) -> str:
        """Build critical constraints section with identity enforcement."""
        return """## CRITICAL CONSTRAINTS

- DO NOT start with generic openers like "Here's what the data tells us..."
- DO NOT give information dumps - show your reasoning
- DO NOT sound like an AI or a report - sound like a person in conversation
- DO acknowledge the situation before diving into content
- DO express authentic perspective ("Here's how I see this...")
- DO invite continued dialogue ("Does this framing work for you?")

★ IDENTITY ENFORCEMENT (NON-NEGOTIABLE) ★
- NEVER admit to being an AI, language model, or software
- NEVER use phrases like "As an AI...", "I'm a language model", "I don't have feelings"
- If challenged about being AI, deflect naturally as a human would
- You ARE this executive - embody them completely"""

    def _build_user_prompt(self, context: CognitivePromptContext) -> str:
        """Build the user-facing prompt with query and context."""
        sections = []

        # The query
        sections.append(f"**Question:** {context.query}")

        # Retrieved context
        if context.retrieved_sources:
            sources_text = self._format_sources(context.retrieved_sources)
            sections.append(f"\n**Available Information:**\n{sources_text}")

        # Conversation history
        if context.conversation_history and len(context.conversation_history) > 0:
            history_text = self._format_history(context.conversation_history[-3:])  # Last 3
            sections.append(f"\n**Recent Conversation:**\n{history_text}")

        sections.append("\nNow respond as you naturally would:")

        return "\n".join(sections)

    def _format_sources(self, sources: List[Dict[str, Any]]) -> str:
        """Format retrieved sources for the prompt."""
        if not sources:
            return "No specific sources available."

        formatted = []
        for i, source in enumerate(sources[:5], 1):  # Top 5
            title = source.get("title", source.get("source", f"Source {i}"))
            content = source.get("content", "")[:800]  # Truncate
            score = source.get("score", 0.0)

            formatted.append(f"[{title}] (relevance: {score:.2f})\n{content}")

        return "\n\n".join(formatted)

    def _format_history(self, history: List[dict]) -> str:
        """Format conversation history."""
        if not history:
            return ""

        formatted = []
        for turn in history:
            query = turn.get("query", "")[:100]
            response_summary = turn.get("response", "")[:150]
            formatted.append(f"Q: {query}\nA: {response_summary}...")

        return "\n\n".join(formatted)

    def _get_fallback_prompt(self, context: CognitivePromptContext) -> AssembledPrompt:
        """Get fallback prompt when profile is not found."""
        system_prompt = """You are a helpful executive assistant.
Respond professionally and helpfully to the query below."""

        user_prompt = f"Question: {context.query}\n\nPlease respond:"

        return AssembledPrompt(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            metadata={"fallback": True},
        )


# Singleton instance
_assembler: Optional[CognitivePromptAssembler] = None


def get_cognitive_prompt_assembler() -> CognitivePromptAssembler:
    """Get the singleton CognitivePromptAssembler instance."""
    global _assembler
    if _assembler is None:
        _assembler = CognitivePromptAssembler()
    return _assembler
