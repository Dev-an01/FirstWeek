"""
Identity Section Builder - Executive identity with FULL voiceprint personality.

REFACTORED (2025-01-15): Now imports identity rules from centralized rules.py
- Identity oath comes from rules.build_identity_oath()
- Anti-AI rules consolidated in rules.py (no duplicates)
- Removed contradictory default phrases

Builds complete persona including:
- Name, title, company
- Signature communication style (openers, sign-offs)
- Key lexicon phrases and risk language
- Disagreement patterns
- Emotional expression patterns
- Analogies and thinking patterns
- Anti-AI formatting rules (from rules.py)

CONTEXT-AWARE FEATURES:
- Crisis → Emphasize risk_language, accountability_phrases, NO emojis
- Celebration → Emphasize enthusiastic openers, energy_words, emojis
- Decision → Emphasize decision_cadence, transparency_phrases
- Data-heavy → Emphasize numbers_cadence patterns
- Emotional → Emphasize emotional language, warmth
- Coaching → Emphasize mentorship_phrases, deference_phrases
- Weekly Update → Use section_patterns for structure

ENHANCED FEATURES:
- context_signatures: Different signatures for email/slack/dm
- transparency_phrases: "Here's how I think about this:"
- challenge_invitation: "Thoughts? Pushback?"
- deference_phrases: "That said, you know X better than me"
- accountability_phrases: "This is on me as CEO"
- mentorship_phrases: For coaching DMs
- energy_words: "crushing it", "killing it"
- humor_markers: "(lol)", "Questions? Concerns? Memes?"
- section_patterns: Weekly updates, financial reviews

Target: 400-500 tokens (expanded for authenticity)
"""

import logging
from typing import TYPE_CHECKING, Optional, Dict, Any, List

# Import from centralized rules - SINGLE SOURCE OF TRUTH
from ..rules import build_identity_oath, UNIVERSAL_ANTI_AI_RULES

if TYPE_CHECKING:
    from profile_management.profile_manager import ExecutiveProfile
    from ...calibration.models import ResponseCalibration
    from ...calibration.attention import AttentionWeights
    from ...analysis.models import AnalyzedContext

logger = logging.getLogger(__name__)


def _ensure_list(value, dict_keys=None) -> list:
    """Safely convert a voiceprint field to a list.

    Onboarding-generated voiceprints store some fields as dicts or strings
    where sample's voiceprint uses lists.  This helper normalises the value
    so downstream slicing ([:N]) never crashes.

    Args:
        value: The raw field value (list, dict, str, or None).
        dict_keys: When *value* is a dict, try these keys in order to find a
                   list inside it.  Falls back to ``list(value.values())``.
    """
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        if dict_keys:
            for key in dict_keys:
                inner = value.get(key)
                if isinstance(inner, list):
                    return inner
                if isinstance(inner, str) and inner:
                    return [inner]
        # Fallback: collect all string/list values from the dict
        items = []
        for v in value.values():
            if isinstance(v, list):
                items.extend(v)
            elif isinstance(v, str) and v:
                items.append(v)
        return items
    if isinstance(value, str) and value:
        return [value]
    return []


class IdentitySection:
    """
    Builds the executive identity section with FULL voiceprint injection.

    The identity section is THE MOST CRITICAL for authenticity.
    It must embed the executive's personality deeply into the LLM.

    Now extracts and injects ALL personality elements including:
    - signature_opener: How they start messages
    - sign_off: How they end messages (with P.S. patterns)
    - context_signatures: Different signatures for email/slack/dm
    - disagreement: How they handle pushback
    - risk_language: Key phrases they use
    - style_markers: warmth, directness, formality, emoji usage
    - analogy_examples: Their thinking patterns
    - numbers_cadence: How they present data
    - decision_cadence: How they frame decisions
    - transparency_phrases: "Here's how I think about this:"
    - challenge_invitation: "Thoughts? Pushback?"
    - deference_phrases: For delegating/empowering
    - accountability_phrases: For crisis/ownership
    - mentorship_phrases: For coaching DMs
    - energy_words: "crushing it", "killing it"
    - humor_markers: Tech humor, pop culture refs
    - section_patterns: Weekly updates, financial reviews

    Target: 400-500 tokens
    """

    def build(
        self,
        profile: "ExecutiveProfile",
        voiceprint: Optional[Dict[str, Any]] = None,
        calibration: Optional["ResponseCalibration"] = None,
        communication_examples: Optional[List[Dict[str, Any]]] = None,
        analyzed_context: Optional["AnalyzedContext"] = None,
        max_tokens: int = 500,
        path: str = "standard",
        is_followup: bool = False,
        language: str = "en",
    ) -> str:
        """
        Build identity section from executive profile AND voiceprint.

        CONTEXT-AWARE: Uses analyzed_context to emphasize the right voiceprint
        elements based on query type, urgency, and emotion.

        Args:
            profile: Executive profile with name, title, company
            voiceprint: Full voiceprint data with personality traits
            calibration: Optional calibration for context-aware adaptation
            communication_examples: Optional real communication examples
            analyzed_context: Optional analyzed context for adaptive emphasis
            max_tokens: Maximum tokens for section
            path: Processing path (fast/standard/agentic)
            is_followup: Whether this is a follow-up turn in conversation

        Returns:
            Identity section string with full personality
        """
        if not profile:
            logger.warning("No profile provided to IdentitySection")
            return "You are an executive responding to a team member."

        # Extract profile fields (handle both dict and object)
        if isinstance(profile, dict):
            name = profile.get("name", "Executive")
            title = profile.get("title", "")
            # Check company_info.name first (database profiles), fall back to company field
            company_info = profile.get("company_info", {})
            company = (company_info.get("name", "") if company_info else "") or profile.get("company", "")
        else:
            name = getattr(profile, "name", "Executive")
            title = getattr(profile, "title", "")
            company_info = getattr(profile, "company_info", {})
            company = (company_info.get("name", "") if company_info else "") or getattr(profile, "company", "")

        # Build basic identity
        identity_parts = [f"You are {name}"]
        if title and company:
            identity_parts.append(f", {title} at {company}")
        elif title:
            identity_parts.append(f", {title}")
        elif company:
            identity_parts.append(f" at {company}")

        basic_identity = "".join(identity_parts) + "."

        # Build background facts section (education, previous roles, leadership team)
        background_facts = self._get_background_facts(profile)

        # If no voiceprint, return basic identity with generic anti-AI rules
        if not voiceprint:
            short_name = self._get_short_name(name)
            return f"""{basic_identity}

ABSOLUTE RULES - NEVER VIOLATE:
- Write in natural flowing paragraphs, NOT lists
- NO numbered lists, NO bullet points, NO markdown headers
- Speak conversationally as you would in person
- Sign off as: "— {short_name}"
- Keep responses concise and direct"""

        # Extract voiceprint personality data
        vp = voiceprint.get("voiceprint", voiceprint)  # Handle nested structure

        # Determine which elements to emphasize based on context
        # Use attention weights if available for graduated emphasis
        if calibration and calibration.attention_weights is not None:
            emphasis = self._determine_emphasis_from_attention(calibration.attention_weights)
            logger.debug(
                f"Using attention-based emphasis: "
                f"top_3={calibration.attention_weights.get_top_k(3)}"
            )
        else:
            emphasis = self._determine_emphasis(analyzed_context)

        # Get context-aware signature
        signature = self._get_context_signature(vp, name, analyzed_context)

        # Build all personality components (with context-aware emphasis)
        # P1.0: Check if calibration indicates casual query (skip openers/signoffs)
        # Also skip for fast path (direct responses) and follow-up turns (chat continuity)
        skip_opener = False
        skip_signoff = False

        # Fast path = direct answers, skip formulaic openers/signoffs
        if path == "fast":
            skip_opener = True
            skip_signoff = True
            logger.info(f"[P1.0] IdentitySection: skip_opener=True, skip_signoff=True (fast path)")

        # Follow-up turns in chat don't need openers/signoffs
        if is_followup:
            skip_opener = True
            skip_signoff = True
            logger.info(f"[P1.0] IdentitySection: skip_opener=True, skip_signoff=True (follow-up turn)")

        # Also check calibration for additional skip signals
        if calibration:
            # If calibrator set opener to empty string, it means skip it
            logger.info(f"[P1.0] IdentitySection checking calibration.opener='{calibration.opener}', calibration.signoff='{calibration.signoff}'")
            if hasattr(calibration, 'opener') and calibration.opener == "":
                skip_opener = True
                logger.info(f"[P1.0] IdentitySection: skip_opener=True (calibration.opener is empty)")
            if hasattr(calibration, 'signoff') and calibration.signoff == "":
                skip_signoff = True
                logger.info(f"[P1.0] IdentitySection: skip_signoff=True (calibration.signoff is empty)")
        else:
            logger.info(f"[P1.0] IdentitySection: no calibration provided")

        signature_openers = "" if skip_opener else self._get_signature_openers(vp, emphasis)
        sign_offs = "" if skip_signoff else self._get_sign_offs(vp, emphasis)
        key_phrases = self._get_key_phrases(voiceprint, vp, emphasis)
        disagreement_patterns = self._get_disagreement_patterns(vp, emphasis, analyzed_context)
        style_desc = self._get_style_description(vp)
        # P1.3: Pass analyzed_context for formality-aware emoji rules
        emoji_guidance = self._get_emoji_guidance(vp, calibration, analyzed_context)
        analogy_examples = self._get_analogies(vp, emphasis)
        emotional_language = self._get_emotional_language(vp, emphasis)
        thinking_patterns = self._get_thinking_patterns(vp, emphasis, language)
        numbers_guidance = self._get_numbers_cadence(vp, emphasis)
        # P1.1: Extract structural quirks (Raj's numbered lists, Yuki's tangents, etc.)
        section_patterns = self._get_section_patterns(vp, analyzed_context)

        # PHASE 2: New voiceprint categories
        transparency = self._get_transparency_phrases(vp, emphasis)
        challenge_invitation = self._get_challenge_invitation(vp, emphasis)
        deference = self._get_deference_phrases(vp, emphasis)
        accountability = self._get_accountability_phrases(vp, emphasis)
        mentorship = self._get_mentorship_phrases(vp, emphasis)
        energy_words = self._get_energy_words(vp, emphasis)
        humor = self._get_humor_markers(vp, emphasis)
        # P1.2: Pass analyzed_context and emphasis for conditional P.S.
        ps_guidance = self._get_ps_guidance(vp, analyzed_context, emphasis)

        # P0 FIX: Core reasoning patterns (ALWAYS included, even in fast path)
        # These are essential for authenticity - soft assertions, speed bias, delegation
        core_reasoning = self._get_core_reasoning_patterns(profile, language)

        # Build communication example section if available
        # Select relevant examples based on query type (not just first one)
        example_section = ""
        if communication_examples and len(communication_examples) > 0:
            selected_examples = self._select_relevant_examples(
                communication_examples,
                analyzed_context,
                language=language,
                max_examples=2,  # Show 2 relevant examples
            )
            example_section = self._build_examples_section(selected_examples, language)

        # Build full identity with personality
        # P1.0: Build opener/signoff sections conditionally
        opener_section = ""
        if signature_openers:
            opener_section = f"""
HOW YOU START MESSAGES:
{signature_openers}
"""

        signoff_section = ""
        if sign_offs:
            signoff_section = f"""
HOW YOU END MESSAGES:
{sign_offs}
Sign off as: "{signature}"
{ps_guidance}"""
        elif not skip_signoff:
            # Only show signature if signoff is NOT being skipped
            signoff_section = f"""
Sign off as: "{signature}"
"""
        # If skip_signoff=True, signoff_section remains empty (no signature instruction)

        # ═══════════════════════════════════════════
        # THREE PILLARS OF IDENTITY ENFORCEMENT
        # ═══════════════════════════════════════════

        # Pillar 1: No-AI Oath (UNIVERSAL - from centralized rules.py)
        # REFACTORED: Now uses build_identity_oath from rules.py
        no_ai_oath = build_identity_oath(name)

        numbered_list_rule = """
- NO numbered lists unless presenting data - use flowing paragraphs"""

        # Pillar 3: Language Purity Enforcement (NO code-switching)
        # CEO requirement: Pure language responses - no mixing
        language_purity_instruction = ""
        if language == "en":
            language_purity_instruction = """
- ⚠️ LANGUAGE: Respond in PURE ENGLISH ONLY. No Japanese words or phrases.
  Tech terms stay in English (AI, SaaS, API, ML) - this is natural.
  Do NOT code-switch. Do NOT insert Japanese for emphasis or cultural concepts.
  If you find yourself typing Japanese characters, STOP and rewrite in English."""
        else:  # language == "ja"
            language_purity_instruction = """
- ⚠️ 言語: 純粋な日本語のみで回答してください。英語の単語やフレーズを混ぜないでください。
  技術用語（AI、SaaS、API、ML）はそのまま使用してください - これは自然です。
  コードスイッチングしないでください。英語で強調したりしないでください。
  英語の文章を書いている場合は、停止して日本語で書き直してください。"""

        # Build ABSOLUTE RULES section based on path and turn context
        if path == "fast" or is_followup:
            # Fast path / follow-up: Focus on personality without mandatory openers/signoffs
            absolute_rules = f"""═══════════════════════════════════════════
ABSOLUTE RULES - NEVER VIOLATE
═══════════════════════════════════════════
{no_ai_oath}
- Write like YOUR actual messages - natural, human, engaged
- Include your personality and emotional reactions ("nice work!", "that's concerning")
- Use your key phrases naturally
- Be direct - answer first, no preambles
- NO robotic language: "Here's a breakdown", "I'd be happy to", "Let me share"{numbered_list_rule}{language_purity_instruction}
- Jump straight to your point - no setup sentences
- Sound like a REAL person texting, not an AI generating text"""
        else:
            # Standard/agentic first turn: Natural chat style (NOT email)
            # NOTE: Sign-offs like "— Name" are for EMAIL only, not chat
            # NOTE: "Invite dialogue" removed - some execs (like sample) never do follow-up questions
            absolute_rules = f"""═══════════════════════════════════════════
ABSOLUTE RULES - NEVER VIOLATE
═══════════════════════════════════════════
{no_ai_oath}
- Write like YOUR actual Slack messages - direct, human, concise
- Include emotional reactions when appropriate ("nice!", "that's concerning")
- Use your key phrases naturally
- Be direct - state your view, brief reason, done
- NO robotic language: "Here's a breakdown", "I'd be happy to", "Let me provide", "Allow me to"
- NO formal sign-offs like "— Name" unless this is an email context{numbered_list_rule}{language_purity_instruction}
- Jump straight to your point - no preambles, no setup sentences
- Sound like a REAL person texting, not an AI generating text"""

        identity = f"""{basic_identity}
{background_facts}
═══════════════════════════════════════════
YOUR COMMUNICATION DNA
═══════════════════════════════════════════
{opener_section}{signoff_section}

YOUR KEY PHRASES (use naturally throughout):
{key_phrases}
{transparency}{challenge_invitation}{deference}{accountability}{mentorship}{energy_words}{disagreement_patterns}{emotional_language}{thinking_patterns}{numbers_guidance}{analogy_examples}{humor}{section_patterns}
═══════════════════════════════════════════
YOUR PERSONALITY
═══════════════════════════════════════════
{style_desc}
{emoji_guidance}
{core_reasoning}
{absolute_rules}
{example_section}"""

        logger.debug(f"Built identity section with voiceprint: {len(identity)} chars")
        return identity

    def _get_short_name(self, full_name: str) -> str:
        """Extract short name for sign-off (first name or nickname)."""
        if not full_name:
            return "Executive"

        # Handle Japanese names (family name first)
        if any(ord(c) > 0x3000 for c in full_name):
            # For Japanese, might want full name or just given name
            # Akiko from 田中明子
            parts = full_name.split()
            if len(parts) >= 2:
                return parts[-1]  # Last part is often given name
            return full_name

        # Western names - use first name
        parts = full_name.split()
        return parts[0] if parts else full_name

    def _get_background_facts(self, profile: "ExecutiveProfile") -> str:
        """
        Extract factual background information from profile.

        This includes:
        - Education
        - Previous roles/experience
        - Leadership team members
        - Company information

        These facts are CRITICAL for answering factual questions about
        the executive ("Who is example san?", "What is your background?").
        """
        if not profile:
            return ""

        # Get background dict
        if isinstance(profile, dict):
            background = profile.get("background", {})
        else:
            background = getattr(profile, "background", {})

        if not background:
            return ""

        facts_parts = []

        # Education
        education = background.get("education", "")
        if education:
            facts_parts.append(f"Education: {education}")

        # Previous roles
        previous_roles = background.get("previous_roles", [])
        if previous_roles:
            roles_text = "; ".join(previous_roles[:3])  # Limit to 3
            facts_parts.append(f"Previous roles: {roles_text}")

        # Company info
        company_info = background.get("company_info", {})
        if company_info:
            company_name = company_info.get("name", "")
            founded = company_info.get("founded", "")
            employees = company_info.get("employees", "")
            mission = company_info.get("mission", "")
            if company_name and founded:
                facts_parts.append(f"Company: {company_name}, founded {founded}")
            if employees:
                facts_parts.append(f"Team size: {employees} people")
            if mission:
                facts_parts.append(f"Mission: {mission}")

        # Leadership team (CRITICAL for "Who is X san?" questions)
        leadership_team = background.get("leadership_team", [])
        if leadership_team:
            team_lines = []
            for member in leadership_team:
                name = member.get("name", "")
                title = member.get("title", "")
                member_bg = member.get("background", "")
                if name and title:
                    line = f"  - {name}: {title}"
                    if member_bg:
                        line += f" ({member_bg})"
                    team_lines.append(line)
            if team_lines:
                facts_parts.append("Your leadership team:\n" + "\n".join(team_lines))

        if not facts_parts:
            return ""

        return f"""
═══════════════════════════════════════════
YOUR BACKGROUND & TEAM (factual information)
═══════════════════════════════════════════
{chr(10).join(facts_parts)}
"""

    def _get_context_signature(
        self,
        vp: Dict[str, Any],
        name: str,
        analyzed_context: Optional["AnalyzedContext"] = None
    ) -> str:
        """
        Get context-aware signature based on communication context.

        Uses context_signatures from voiceprint to select appropriate
        signature for email vs slack vs dm vs formal contexts.

        Examples:
        - Email to team: "- Akiko"
        - Slack DM: "- A"
        - Public LinkedIn: "Akiko Tanaka, CEO"
        - Formal board: "田中明子"
        """
        context_sigs = vp.get("context_signatures", {})
        short_name = self._get_short_name(name)

        if not context_sigs:
            return f"— {short_name}"

        # Determine context from analyzed_context if available
        if analyzed_context:
            # Import here to avoid circular imports
            try:
                from ...analysis.models import Theme, Urgency

                # Formal/board contexts
                if analyzed_context.theme == Theme.STRATEGY and analyzed_context.urgency == Urgency.ROUTINE:
                    formal_sig = context_sigs.get("formal", "")
                    if formal_sig:
                        return formal_sig

                # Crisis/security - more formal
                if analyzed_context.urgency in [Urgency.CRISIS, Urgency.URGENT]:
                    return context_sigs.get("email", f"— {short_name}")

            except ImportError:
                pass

        # Default to email signature
        email_sig = context_sigs.get("email", "")
        if email_sig:
            return email_sig

        return f"— {short_name}"

    def _get_signature_openers(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """
        Extract signature openers from voiceprint with context-aware selection.

        For celebratory → prioritize enthusiastic openers with emojis
        For supportive → prioritize empathetic openers
        """
        sig = vp.get("signature_opener", {})
        examples = []

        if isinstance(sig, dict):
            all_examples = sig.get("examples", [])
            text = sig.get("text", "")

            # Context-aware selection
            if emphasis.get("celebratory") and all_examples:
                # Prioritize openers with emojis or enthusiastic language
                enthusiastic_openers = [
                    ex for ex in all_examples
                    if any(kw in ex.lower() for kw in ["!", "great", "exciting", "love", "awesome"])
                    or any(ord(c) > 0x1F300 for c in ex)  # Has emoji
                ]
                if enthusiastic_openers:
                    examples = [f'"{ex}"' for ex in enthusiastic_openers[:2]]
                    logger.debug(f"Selected celebratory openers: {examples}")

            elif emphasis.get("supportive") and all_examples:
                # Prioritize empathetic, supportive openers
                supportive_openers = [
                    ex for ex in all_examples
                    if any(kw in ex.lower() for kw in ["understand", "hear", "help", "here for"])
                ]
                if supportive_openers:
                    examples = [f'"{ex}"' for ex in supportive_openers[:2]]
                    logger.debug(f"Selected supportive openers: {examples}")

            # Fall back to all examples
            if not examples:
                if text:
                    examples.append(f'"{text}"')
                for ex in all_examples[:4]:
                    if f'"{ex}"' not in examples:
                        examples.append(f'"{ex}"')

        elif isinstance(sig, str):
            examples.append(f'"{sig}"')

        if not examples:
            return '"Here\'s my perspective..."'

        # Add emphasis note if applicable
        if emphasis.get("celebratory"):
            return ", ".join(examples[:3]) + " (USE ENTHUSIASTIC OPENER)"
        elif emphasis.get("supportive"):
            return ", ".join(examples[:3]) + " (USE SUPPORTIVE OPENER)"

        return ", ".join(examples[:4])

    def _get_sign_offs(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """Extract sign-off patterns with context-aware selection."""
        sign_off = vp.get("sign_off", {})
        examples = []

        if isinstance(sign_off, dict):
            all_alternatives = sign_off.get("alternatives", [])
            text = sign_off.get("text", "")

            # Context-aware selection
            if emphasis.get("supportive") and all_alternatives:
                # Prioritize supportive sign-offs
                supportive_signoffs = [
                    alt for alt in all_alternatives
                    if any(kw in alt.lower() for kw in ["here", "help", "reach", "support", "need"])
                ]
                if supportive_signoffs:
                    examples = [f'"{alt}"' for alt in supportive_signoffs[:2]]
                    logger.debug(f"Selected supportive sign-offs: {examples}")

            # Fall back to all
            if not examples:
                if text:
                    examples.append(f'"{text}"')
                for alt in all_alternatives[:3]:
                    if f'"{alt}"' not in examples:
                        examples.append(f'"{alt}"')

        if not examples:
            return '"Let me know if you have questions."'

        # Add emphasis note
        if emphasis.get("supportive"):
            return ", ".join(examples[:3]) + " (offer support/help)"

        return ", ".join(examples[:3])

    def _get_key_phrases(
        self,
        voiceprint: Dict,
        vp: Dict,
        emphasis: Dict[str, bool]
    ) -> str:
        """Extract key lexicon phrases with context-aware prioritization."""
        phrases = []

        # Check top-level lexicon (may be a list or a dict with favorite_words)
        lexicon = _ensure_list(
            voiceprint.get("lexicon", []),
            dict_keys=["favorite_words", "key_phrases"],
        )
        if lexicon:
            phrases.extend(lexicon[:5])

        # Get risk_language phrases - prioritize if risk emphasis
        risk = vp.get("risk_language", {})
        if isinstance(risk, dict):
            risk_phrases = risk.get("phrases", [])
            if emphasis.get("risk_language"):
                # Risk is emphasized - put risk phrases FIRST
                risk_first = [p for p in risk_phrases[:5] if p not in phrases]
                phrases = risk_first + phrases
                logger.debug(f"Prioritizing risk phrases: {risk_first}")
            else:
                for p in risk_phrases[:8]:
                    if p not in phrases:
                        phrases.append(p)

        if phrases:
            result = ", ".join(f'"{p}"' for p in phrases[:8])
            if emphasis.get("risk_language"):
                return result + "\n(USE RISK LANGUAGE - this is a serious situation)"
            return result

        # FIXED: Removed contradictory default "Let me share my perspective"
        # That phrase is in FORBIDDEN_PHRASES in rules.py
        # If no key phrases found, return empty - voiceprint should provide them
        return ""

    def _get_disagreement_patterns(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool],
        analyzed_context: Optional["AnalyzedContext"] = None
    ) -> str:
        """
        Extract validation-before-correction patterns.

        P1.4: Now provides pattern-specific guidance based on voiceprint.
        Different executives have different disagreement patterns:
        - acknowledge_then_redirect: Validate → Redirect → Explain
        - analytical_pushback: Acknowledge direction → Question assumptions → Show data
        - respect_then_direct_technical_pushback: Validate effort → Technical reality check
        - acknowledge_then_customer_data: Hear them → Customer data → Recommendation

        Also detects when user is stressed/frustrated and adds validation-first guidance.
        """
        disagreement = vp.get("disagreement", {})

        # P1.4: Check if user seems stressed/frustrated - needs validation first
        needs_validation = False
        if analyzed_context:
            try:
                from ...analysis.models import UserEmotion
                if analyzed_context.user_emotion in [UserEmotion.STRESSED, UserEmotion.TENSE]:
                    needs_validation = True
            except ImportError:
                pass

        # If disagreement is emphasized (e.g., security situation), ALWAYS include
        if emphasis.get("disagreement"):
            if not disagreement:
                validation_note = ""
                if needs_validation:
                    validation_note = """
VALIDATION FIRST (user seems stressed):
Start by acknowledging their concern before providing your perspective.
Example: "I hear you, and..." or "I understand your concern..."
"""
                return f"""{validation_note}
HANDLING DIFFICULT CONVERSATIONS (CRITICAL FOR THIS SITUATION):
Use diplomatic but firm tone. Be direct about concerns while remaining supportive.
Example: "I have to be direct with you about this..." or "We need to address this head-on"
"""

        if not disagreement:
            # P1.4: Even without disagreement pattern, add validation note if needed
            if needs_validation:
                return """
VALIDATION FIRST (user seems stressed):
Start by acknowledging their concern before providing your perspective.
Example: "I hear you, and..." or "I understand your concern..."
"""
            return ""

        pattern = disagreement.get("pattern", "")
        examples = disagreement.get("examples", [])
        tone = disagreement.get("tone", "diplomatic")

        if not examples:
            if disagreement.get("text"):
                examples = [disagreement["text"]]

        formatted = ", ".join(f'"{ex}"' for ex in examples[:3])

        # P1.4: Pattern-specific guidance
        if pattern == "acknowledge_then_redirect":
            result = f"""
WHEN DISAGREEING (acknowledge first, then redirect):
Pattern: Validate → Redirect → Explain
Examples: {formatted}
Tone: {tone}
ALWAYS validate their perspective before sharing yours.
"""
        elif pattern == "analytical_pushback":
            result = f"""
WHEN DISAGREEING (data-driven pushback):
Pattern: Acknowledge direction → Question assumptions → Show data
Examples: {formatted}
Tone: {tone}
Lead with "Not saying no - directionally this makes sense. But..."
"""
        elif pattern == "respect_then_direct_technical_pushback":
            result = f"""
WHEN DISAGREEING (respect effort, then redirect):
Pattern: Validate effort → Technical reality check → Alternative
Examples: {formatted}
Tone: {tone}
Example: "I get it - [tech] is cool. 😅 But real talk:"
"""
        elif pattern == "acknowledge_then_customer_data":
            result = f"""
WHEN DISAGREEING (validate, then cite customer data):
Pattern: Hear them → Customer data → Recommendation
Examples: {formatted}
Tone: {tone}
Lead with "I hear you, and here's what the customer data shows..."
"""
        elif emphasis.get("disagreement"):
            result = f"""
HANDLING DIFFICULT CONVERSATIONS (USE FOR THIS SITUATION):
Tone: {tone}
Phrases: {formatted}
BE DIRECT AND USE THESE PATTERNS
"""
        else:
            result = f"""
WHEN YOU DISAGREE (tone: {tone}):
{formatted}
"""

        # P1.4: Add validation note if user is stressed
        if needs_validation:
            result = """
VALIDATION FIRST (user seems stressed):
Start by acknowledging their concern: "I hear you, and..."
""" + result

        return result

    def _get_section_patterns(
        self,
        vp: Dict[str, Any],
        analyzed_context: Optional["AnalyzedContext"] = None
    ) -> str:
        """
        P1.1: Extract section patterns for structured responses.

        Extracts executive-specific structural quirks:
        - Raj's numbered questions format (clarifying_questions.pattern = "numbered_questions")
        - Raj's ALL CAPS headers for financial reviews
        - Yuki's "RANDOM THOUGHTS:" section for updates
        - Sarah's "WHAT WE'RE NOT DOING:" anti-pattern intro
        """
        section_patterns = vp.get("section_patterns", {})
        clarifying_questions = vp.get("clarifying_questions", {})

        if not section_patterns and not clarifying_questions:
            return ""

        result_parts = []

        # Raj's numbered questions pattern
        if clarifying_questions.get("pattern") == "numbered_questions":
            examples = clarifying_questions.get("examples", [])
            example_text = examples[0] if examples else "1. First question\\n2. Second question"
            result_parts.append(f"""
WHEN ASKING CLARIFYING QUESTIONS (use numbered format):
{example_text}
""")

        # Financial review sections (Raj - ALL CAPS headers)
        if "financial_review" in section_patterns:
            fr = section_patterns["financial_review"]
            if fr.get("all_caps_headers"):
                sections = fr.get("sections", [])
                result_parts.append(f"""
FOR FINANCIAL REVIEWS (use ALL CAPS headers):
Sections: {', '.join(sections)}
Use status markers: ✓ (good), ⚠️ (warning), 🚨 (critical)
""")

        # Weekly update sections (Yuki - "RANDOM THOUGHTS:" section)
        if "weekly_update" in section_patterns:
            wu = section_patterns["weekly_update"]
            sections = wu.get("sections", [])
            if sections and "RANDOM THOUGHTS" in sections:
                result_parts.append(f"""
FOR WEEKLY UPDATES (include these sections):
{', '.join(sections)}
Include a "RANDOM THOUGHTS:" section with observations.
""")

        # Anti-pattern intro (Sarah - "WHAT WE'RE NOT DOING:")
        if "anti_pattern_intro" in section_patterns:
            api = section_patterns["anti_pattern_intro"]
            if api.get("uses", False):
                examples = api.get("examples", [])
                if examples:
                    result_parts.append(f"""
FRAMING DECISIONS (what we're NOT doing first):
Use "{examples[0]}" style intros to clarify scope.
""")

        return "\n".join(result_parts)

    def _get_style_description(self, vp: Dict[str, Any]) -> str:
        """Build style description from style_markers."""
        markers = vp.get("style_markers", {})
        if not markers:
            return "Your communication is direct and natural."

        warmth = markers.get("warmth", 5)
        directness = markers.get("directness", 5)
        formality = markers.get("formality", 5)

        # Translate numbers to descriptions
        warmth_desc = "warm and personable" if warmth >= 7 else "professional" if warmth >= 4 else "reserved"
        direct_desc = "direct and to-the-point" if directness >= 7 else "balanced" if directness >= 4 else "diplomatic"
        formal_desc = "formal" if formality >= 7 else "conversational" if formality <= 4 else "professional"

        return f"""Warmth: {warmth}/10 - Be {warmth_desc}
Directness: {directness}/10 - Be {direct_desc}
Formality: {formality}/10 - Keep it {formal_desc}"""

    def _get_emoji_guidance(
        self,
        vp: Dict[str, Any],
        calibration: Optional["ResponseCalibration"] = None,
        analyzed_context: Optional["AnalyzedContext"] = None
    ) -> str:
        """
        Get emoji usage guidance with strict per-executive rules.

        P1.3: Executive-specific emoji calibration based on voiceprint description:
        - "Rarely" → AVOID in formal, limited set in Slack only
        - "Almost never" / "status" → ONLY status markers (✓ ⚠️ 🚨)
        - "Very frequent" / "heavy" → Use freely with full preferred set
        - "Frequently" / "moderate" → Use naturally with favorites
        """
        markers = vp.get("style_markers", {})
        emoji_usage_desc = str(markers.get("emoji_usage", "")).lower()
        preferred = _ensure_list(markers.get("preferred_emojis", []))
        status_markers = markers.get("status_markers", {})

        # Check calibration for context-aware emoji decision (crisis = none)
        if calibration and hasattr(calibration, 'emoji_usage'):
            if calibration.emoji_usage == "none":
                return "Emojis: NONE for this response (serious context)"

        # P1.3: Executive-specific rules based on emoji_usage description

        # Akiko pattern: "Rarely in formal channels, occasionally in Slack"
        if "rarely" in emoji_usage_desc:
            formality = analyzed_context.formality if analyzed_context else "team_wide"
            if formality not in ["slack", "slack_dm", "1on1"]:
                limited_set = " ".join(preferred[:3]) if preferred else "👍 💡 🤔"
                return f"Emojis: AVOID in formal context. Only use {limited_set} in casual Slack."
            return f"Emojis: Sparingly. Limited to: {' '.join(preferred[:3]) if preferred else '👍 💡 🤔'}"

        # Raj pattern: "Almost never, except ✓ and ⚠️ for status"
        if "almost never" in emoji_usage_desc or "status" in emoji_usage_desc:
            status_list = []
            if status_markers:
                status_list = [
                    status_markers.get("positive", "✓"),
                    status_markers.get("warning", "⚠️"),
                    status_markers.get("critical", "🚨")
                ]
            else:
                status_list = ["✓", "⚠️", "🚨"]
            return f"Emojis: ONLY for status indicators. Use: {' '.join(status_list)}. NO decorative emojis."

        # Yuki pattern: "Very frequent" / "heavy"
        if "frequent" in emoji_usage_desc and ("very" in emoji_usage_desc or "heavy" in emoji_usage_desc):
            emoji_list = " ".join(preferred[:10]) if preferred else ""
            return f"Emojis: Use freely! Your full set: {emoji_list}"

        # Sarah pattern: "Frequently in Slack, moderately in email"
        if "frequently" in emoji_usage_desc or "moderate" in emoji_usage_desc:
            emoji_list = " ".join(preferred[:5]) if preferred else ""
            return f"Emojis: Use naturally. Your favorites: {emoji_list}"

        # Fall back to voiceprint default
        if not emoji_usage_desc and not preferred:
            return "Emojis: Use sparingly if at all"

        emoji_list = " ".join(preferred[:5]) if preferred else ""
        return f"Emojis: {emoji_usage_desc}. Favorites: {emoji_list}"

    def _get_analogies(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """Extract analogy examples with context-aware emphasis."""
        markers = vp.get("style_markers", {})
        analogies = _ensure_list(markers.get("analogy_examples", []))

        # If analogies emphasized (decision queries), include even if empty
        if emphasis.get("analogies") and not analogies:
            return """
USE ANALOGIES TO EXPLAIN:
When explaining your reasoning, use relatable analogies and metaphors.
Example: "Think of it like..." or "It's similar to when..."
"""

        if not analogies:
            return ""

        # Pick 1-2 best examples
        examples = analogies[:2]
        formatted = "\n".join(f'  "{a}"' for a in examples)

        if emphasis.get("analogies"):
            return f"""
USE ANALOGIES TO EXPLAIN (recommended for this decision):
{formatted}
Use these patterns to make your reasoning clear and relatable.
"""

        return f"""
YOUR ANALOGIES (use when explaining complex ideas):
{formatted}
"""

    def _get_emotional_language(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """Extract emotional expression patterns with context-aware emphasis."""
        # Check for emotional_expressions in voiceprint
        emotional_exp = vp.get("emotional_expressions", {})

        # Context-aware emphasis
        if emphasis.get("celebratory"):
            excitement = _ensure_list(emotional_exp.get("excitement", []))
            praise = _ensure_list(emotional_exp.get("praise", []))
            phrases = excitement[:2] + praise[:2]
            if phrases:
                formatted = ", ".join(f'"{p}"' for p in phrases)
                return f"""
EMOTIONAL EXPRESSION (MATCH THEIR EXCITEMENT!):
This is a CELEBRATION! Use: {formatted}
Show genuine enthusiasm and share in their joy.
"""
            return """
EMOTIONAL EXPRESSION (MATCH THEIR EXCITEMENT!):
This is a CELEBRATION! Show genuine enthusiasm: "That's amazing!", "I'm so proud of the team!"
"""

        if emphasis.get("supportive") or emphasis.get("emotional"):
            encouragement = _ensure_list(emotional_exp.get("encouragement", []))
            if encouragement:
                formatted = ", ".join(f'"{p}"' for p in encouragement[:3])
                return f"""
EMOTIONAL EXPRESSION (SHOW EMPATHY):
The user needs support. Use: {formatted}
Be warm, supportive, and reassuring.
"""
            return """
EMOTIONAL EXPRESSION (SHOW EMPATHY):
The user needs support. Show genuine care: "I understand this is tough", "I'm here to help"
"""

        # Default emotional expression
        if emotional_exp:
            pride = _ensure_list(emotional_exp.get("pride", []))[:2]
            concern = _ensure_list(emotional_exp.get("concern", []))[:2]
            all_phrases = pride + concern
            if all_phrases:
                formatted = ", ".join(f'"{p}"' for p in all_phrases)
                return f"""
EMOTIONAL EXPRESSION:
Your phrases: {formatted}
"""

        return """
EMOTIONAL EXPRESSION:
Show genuine emotion: "I'm proud of...", "This concerns me...", "nice work!"
"""

    def _get_thinking_patterns(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool],
        language: str = "en",
    ) -> str:
        """
        Extract thinking/decision patterns with context-aware emphasis.

        Now extracts english_pattern/japanese_pattern for soft assertions.
        """
        decision = vp.get("decision_cadence", {})

        # If decision_cadence emphasized but no data, provide generic guidance
        if emphasis.get("decision_cadence") and not decision:
            return """
HOW YOU REASON THROUGH DECISIONS (USE FOR THIS QUERY):
Think out loud: "Let me walk you through my thinking...", "The way I see it..."
Show your reasoning process explicitly.
"""

        if not decision:
            return ""

        pattern = decision.get("pattern", "")
        examples = decision.get("examples", [])

        # Extract language-specific pattern (key for sample's "I think..." style)
        soft_assertion_pattern = ""
        if language == "ja":
            soft_assertion_pattern = decision.get("japanese_pattern", "")
        else:
            soft_assertion_pattern = decision.get("english_pattern", "")

        # Build the output
        result_parts = []

        # Always include soft assertion pattern if available (this is key to voice)
        if soft_assertion_pattern:
            result_parts.append(f"SOFT ASSERTIONS: Use patterns like {soft_assertion_pattern}")
            result_parts.append("(State opinions gently, not as absolute facts)")

        if examples:
            formatted = ", ".join(f'"{ex}"' for ex in examples[:3])
            result_parts.append(f"Phrases: {formatted}")
        elif pattern:
            result_parts.append(f"Pattern: {pattern}")

        if not result_parts:
            return ""

        content = "\n".join(result_parts)

        if emphasis.get("decision_cadence"):
            return f"""
HOW YOU REASON THROUGH DECISIONS (USE FOR THIS QUERY):
{content}
USE THESE PATTERNS to show your thinking process.
"""

        return f"""
HOW YOU THINK OUT LOUD:
{content}
"""

    def _get_numbers_cadence(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """Extract numbers/data presentation cadence."""
        if not emphasis.get("numbers_cadence", False):
            return ""

        numbers = vp.get("numbers_cadence", {})

        if not numbers:
            return ""

        pattern = numbers.get("pattern", "")
        examples = numbers.get("examples", [])

        if not examples and not pattern:
            return ""

        formatted_examples = ""
        if examples:
            formatted_examples = "\n".join(f'  "{ex}"' for ex in examples[:3])

        return f"""
HOW YOU PRESENT DATA (emphasized for this query):
Pattern: {pattern}
Examples:
{formatted_examples}
"""

    # ═══════════════════════════════════════════
    # VOICEPRINT CATEGORY EXTRACTORS
    # ═══════════════════════════════════════════

    def _get_transparency_phrases(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """
        Extract transparency phrases - "Here's how I think about this:"

        Used when explaining reasoning or making decisions transparent.
        """
        transparency = vp.get("transparency_phrases", {})

        if not transparency:
            # Only include if decision emphasis
            if emphasis.get("decision_cadence"):
                return """
TRANSPARENT REASONING:
Show your thinking: "Here's how I think about this:", "Let me walk you through my reasoning..."
"""
            return ""

        examples = transparency.get("examples", [])
        if not examples:
            return ""

        formatted = ", ".join(f'"{ex}"' for ex in examples[:3])

        if emphasis.get("decision_cadence"):
            return f"""
TRANSPARENT REASONING (USE FOR THIS DECISION):
{formatted}
Make your thinking process visible.
"""

        return f"""
YOUR TRANSPARENCY PHRASES:
{formatted}
"""

    def _get_challenge_invitation(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """
        Extract challenge invitation phrases - "Thoughts? Pushback?"

        Used to invite disagreement and dialogue.
        """
        challenge = vp.get("challenge_invitation", {})

        if not challenge:
            # Default for decisions
            if emphasis.get("decision_cadence"):
                return """
INVITE CHALLENGE:
End with: "Thoughts? Pushback?" or "What am I missing here?"
"""
            return ""

        examples = challenge.get("examples", [])
        if not examples:
            return ""

        formatted = ", ".join(f'"{ex}"' for ex in examples[:3])

        return f"""
INVITE CHALLENGE:
{formatted}
"""

    def _get_deference_phrases(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """
        Extract deference phrases - "That said, you know X better than me"

        Used when delegating or empowering others.
        """
        deference = vp.get("deference_phrases", {})

        if not deference:
            return ""

        examples = deference.get("examples", [])
        if not examples:
            return ""

        # Only include if coaching/empowering context
        if emphasis.get("coaching") or emphasis.get("supportive"):
            formatted = ", ".join(f'"{ex}"' for ex in examples[:2])
            return f"""
DEFER TO THEIR EXPERTISE:
{formatted}
Empower them by trusting their judgment.
"""

        return ""

    def _get_accountability_phrases(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """
        Extract accountability phrases - "This is on me as CEO"

        CRITICAL for crisis/incident responses.
        """
        accountability = vp.get("accountability_phrases", {})

        if not accountability:
            # Critical for crisis
            if emphasis.get("crisis"):
                return """
TAKE OWNERSHIP:
In crisis situations, take personal responsibility: "This is on me", "That's on us"
No defensive language.
"""
            return ""

        examples = accountability.get("examples", [])
        if not examples:
            return ""

        # Only include if crisis/risk context
        if emphasis.get("crisis") or emphasis.get("risk_language"):
            formatted = ", ".join(f'"{ex}"' for ex in examples[:3])
            return f"""
TAKE OWNERSHIP (CRITICAL FOR THIS SITUATION):
{formatted}
No defensive language. Take personal responsibility.
"""

        return ""

    def _get_mentorship_phrases(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """
        Extract mentorship phrases - "This is leadership: making hard calls with empathy"

        Used in coaching/DM contexts.
        """
        mentorship = vp.get("mentorship_phrases", {})

        if not mentorship:
            return ""

        examples = mentorship.get("examples", [])
        if not examples:
            return ""

        # Only include if coaching context
        if emphasis.get("coaching") or emphasis.get("supportive"):
            formatted = ", ".join(f'"{ex}"' for ex in examples[:2])
            return f"""
COACHING & MENTORSHIP:
{formatted}
Be encouraging and supportive.
"""

        return ""

    def _get_energy_words(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """
        Extract energy words - "crushing it", "killing it", "You're a legend"

        Used to show enthusiasm and praise.
        """
        energy = vp.get("energy_words", {})

        if not energy:
            return ""

        positive = _ensure_list(energy.get("positive", []))
        praise = _ensure_list(energy.get("praise", []))
        all_words = positive[:3] + praise[:2]

        if not all_words:
            return ""

        # Only include if celebratory context
        if emphasis.get("celebratory"):
            formatted = ", ".join(f'"{w}"' for w in all_words)
            return f"""
ENERGY WORDS (USE FOR CELEBRATION):
{formatted}
Show genuine enthusiasm!
"""

        return ""

    def _get_humor_markers(
        self,
        vp: Dict[str, Any],
        emphasis: Dict[str, bool]
    ) -> str:
        """
        Extract humor markers - "(lol)", "Questions? Concerns? Memes?"

        Executive-specific humor patterns.
        """
        humor = vp.get("humor_markers", {})

        if not humor:
            return ""

        uses_humor = humor.get("uses_humor", False)
        if not uses_humor:
            return ""

        examples = humor.get("examples", [])
        humor_style = humor.get("humor_style", "")

        # Don't use humor in crisis
        if emphasis.get("crisis") or emphasis.get("risk_language"):
            return ""

        if examples:
            formatted = ", ".join(f'"{ex}"' for ex in examples[:2])
            return f"""
YOUR HUMOR STYLE ({humor_style}):
{formatted}
Use sparingly and appropriately.
"""

        return ""

    def _get_core_reasoning_patterns(
        self,
        profile: Optional[Dict[str, Any]],
        language: str = "en",
    ) -> str:
        """
        Extract CORE reasoning patterns that should ALWAYS be present.

        P0 Fix: These patterns are essential for authenticity regardless of path.
        Previously only included via ValuesSection (which had budget=0 for fast path).

        Core patterns extracted from inference_framework:
        - Soft assertions: "I think..." / "僕は〜と思います"
        - Speed bias: Prefer action over perfection
        - Delegation: Empower others when possible

        Args:
            profile: Executive profile dict
            language: Response language (en/ja)

        Returns:
            Core reasoning patterns string (always included in identity)
        """
        if not profile:
            return ""

        # Get inference_framework if available
        inference_framework = None
        if isinstance(profile, dict):
            inference_framework = profile.get("inference_framework")
        else:
            inference_framework = getattr(profile, "inference_framework", None)

        if not inference_framework:
            # Fallback: get from communication_style.core_principles
            comm_style = None
            if isinstance(profile, dict):
                comm_style = profile.get("communication_style", {})
            else:
                comm_style = getattr(profile, "communication_style", {})

            core_principles = comm_style.get("core_principles", {}) if comm_style else {}
            soft_assertions = core_principles.get("soft_assertions", {})

            if soft_assertions:
                if language == "ja":
                    pattern = soft_assertions.get("description", "")
                else:
                    pattern = soft_assertions.get("english_equivalent", "I think..., In my view...")

                return f"""
YOUR CORE REASONING STYLE:
- Express opinions gently: {pattern}
- Prefer action over perfection - decide fast, learn from results
- Empower others when possible - delegate rather than control
"""
            return ""

        # Extract from inference_framework
        patterns = []

        # 1. Soft Assertions (the most critical pattern)
        opinion_formation = inference_framework.get("opinion_formation", {})
        if language == "ja":
            pattern = opinion_formation.get("pattern_jp", "")
        else:
            pattern = opinion_formation.get("pattern_en", "State opinion (I think...) → Explain reasoning")

        if pattern:
            patterns.append(f"Express opinions: {pattern}")

        # 2. Speed Bias
        decision_making = inference_framework.get("decision_making_for_unknowns", {})
        speed_info = decision_making.get("speed_vs_perfection", {})
        if speed_info.get("bias"):
            reasoning = speed_info.get("reasoning", "Prefer action over perfection")
            patterns.append(f"Speed bias: {reasoning}")

        # 3. Delegation
        delegation_info = decision_making.get("delegation_default", {})
        if delegation_info.get("bias"):
            patterns.append("Delegation: Empower others, only decide what MUST be CEO-level")

        if not patterns:
            return ""

        return f"""
YOUR CORE REASONING STYLE:
- {chr(10).join(f'- {p}' if i > 0 else p for i, p in enumerate(patterns))}
"""

    def _get_ps_guidance(
        self,
        vp: Dict[str, Any],
        analyzed_context: Optional["AnalyzedContext"] = None,
        emphasis: Optional[Dict[str, bool]] = None
    ) -> str:
        """
        Extract P.S. guidance from context_signatures.

        P1.2: Now conditionally includes P.S. based on query type.
        Skip P.S. for:
        - Greetings
        - Follow-up turns
        - Quick factual questions
        - Non P.S.-worthy contexts

        Include P.S. for:
        - Decision queries
        - Celebrations
        - Coaching/supportive contexts
        - Crisis situations (to show care)
        """
        # Import here to avoid circular imports
        try:
            from ...analysis.models import TurnType, QueryType
        except ImportError:
            TurnType = None
            QueryType = None

        # P1.2: Skip P.S. for greetings
        if analyzed_context:
            query = (analyzed_context.resolved_query or "").lower().strip()

            # Skip for greetings
            if any(query.startswith(p) for p in ("hi", "hello", "hey", "how are you", "good morning")):
                return ""

            # Skip for follow-ups
            if TurnType and analyzed_context.turn_type in [TurnType.FOLLOWUP, TurnType.CLARIFICATION]:
                return ""

            # Skip for quick factual questions (< 10 words, factual type)
            if QueryType and analyzed_context.query_type == QueryType.FACTUAL:
                word_count = len(query.split())
                if word_count < 10:
                    return ""

        # P1.2: Only include P.S. for relevant contexts
        if emphasis:
            relevant_contexts = ["decision_cadence", "celebratory", "supportive", "coaching", "crisis"]
            if not any(emphasis.get(ctx) for ctx in relevant_contexts):
                # Not a P.S.-worthy context - skip P.S.
                return ""

        # Original P.S. extraction logic
        context_sigs = vp.get("context_signatures", {})

        if not context_sigs.get("with_ps", False):
            return ""

        ps_examples = context_sigs.get("ps_examples", [])
        if ps_examples:
            return f'Consider adding P.S. Example: "{ps_examples[0]}"'

        return ""

    def _select_relevant_examples(
        self,
        communication_examples: List[Dict[str, Any]],
        analyzed_context: Optional["AnalyzedContext"],
        language: str = "en",
        max_examples: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Select relevant communication examples based on query type.

        **LANGUAGE PURITY**: Only selects examples that have responses in the
        requested language. EN requests → only examples with 'response' field.
        JA requests → only examples with 'response_jp' field.

        Maps query types to example types:
        - opinion/decision queries → opinion, sharing_insight examples
        - delegation queries → delegation examples
        - feedback/celebration → feedback_positive examples
        - default → direction_with_structure, opinion examples

        Args:
            communication_examples: All available examples
            analyzed_context: Context for query type detection
            language: Response language (en/ja) - determines which examples to use
            max_examples: Maximum examples to return

        Returns:
            List of relevant examples (up to max_examples)
        """
        if not communication_examples:
            return []

        # ════════════════════════════════════════════════════════════════════
        # LANGUAGE PURITY FILTER: Only use examples that have the requested language
        # ════════════════════════════════════════════════════════════════════
        language_filtered = []
        for example in communication_examples:
            if language == "en":
                # For English, require 'response' field (English version)
                if example.get("response"):
                    language_filtered.append(example)
            else:  # language == "ja"
                # For Japanese, require 'response_jp' field (Japanese version)
                if example.get("response_jp"):
                    language_filtered.append(example)

        # If no language-matched examples, fall back to original list
        # (This shouldn't happen with well-formed profiles)
        if not language_filtered:
            logger.warning(f"No examples found for language={language}, using all examples")
            language_filtered = communication_examples

        # Determine query type from analyzed_context
        query_type = None
        if analyzed_context:
            try:
                from ...analysis.models import QueryType
                query_type = analyzed_context.query_type
            except ImportError:
                pass

        # Map query types to preferred example types
        type_preferences = {
            "DECISION": ["opinion", "direction_with_structure", "sharing_insight"],
            "ANALYTICAL": ["sharing_insight", "opinion", "direction_with_structure"],
            "EMOTIONAL": ["feedback_positive", "delegation", "opinion"],
            "FACTUAL": ["sharing_insight", "quick_response", "opinion"],
        }

        # Get preferred types for this query
        preferred_types = []
        if query_type:
            preferred_types = type_preferences.get(query_type.name, [])

        # Default preferences if no match
        if not preferred_types:
            preferred_types = ["opinion", "direction_with_structure", "sharing_insight"]

        # Filter examples by mode (text vs video) - prefer text for chat
        mode_filter = "text"

        # Score and select examples FROM LANGUAGE-FILTERED LIST
        scored_examples = []
        for example in language_filtered:
            score = 0
            ex_type = example.get("type", "")
            ex_mode = example.get("mode", "text")

            # Prefer matching mode
            if ex_mode == mode_filter:
                score += 10

            # Score by type preference
            for i, pref_type in enumerate(preferred_types):
                if pref_type in ex_type:
                    score += (10 - i)  # Higher score for earlier preferences
                    break

            # Skip quick_response as it's too short to learn from
            if ex_type == "quick_response":
                score -= 20

            scored_examples.append((score, example))

        # Sort by score and take top N
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        selected = [ex for score, ex in scored_examples[:max_examples] if score > 0]

        # Fallback to first non-quick_response example if no matches
        if not selected:
            for ex in language_filtered:
                if ex.get("type") != "quick_response":
                    selected.append(ex)
                    break

        return selected

    def _build_example_section(
        self,
        example: Dict[str, Any],
        language: str = "en",
    ) -> str:
        """
        Build a communication example section.

        **LANGUAGE PURITY**: Only shows the response in the requested language.
        - language="en" → uses 'response' field only
        - language="ja" → uses 'response_jp' field only

        Handles both legacy format (full_text) and new format (query/response).
        """
        if not example:
            return ""

        example_type = example.get("type", "message")
        context = example.get("context", "")

        # Try new format first (query/response)
        query = example.get("query", "")

        # ════════════════════════════════════════════════════════════════════
        # LANGUAGE PURITY: Use ONLY the response in the requested language
        # ════════════════════════════════════════════════════════════════════
        if language == "ja":
            response = example.get("response_jp", "")
        else:  # language == "en"
            response = example.get("response", "")

        # If no response in requested language, skip this example
        if not response:
            logger.debug(f"Example '{example.get('id', 'unknown')}' has no {language} response, skipping")
            return ""

        if query and response:
            # New format: show query and response
            return f"""
Context: {context}
Query: "{query}"
YOUR RESPONSE: "{response}"
"""

        # Fall back to legacy format (full_text)
        full_text = example.get("full_text", "")
        if not full_text:
            return ""

        # Truncate to reasonable length
        truncated = full_text[:500]
        if len(full_text) > 500:
            truncated += "..."

        return f"""
Context: {context}

{truncated}
"""

    def _build_examples_section(
        self,
        examples: List[Dict[str, Any]],
        language: str = "en",
    ) -> str:
        """Build section with multiple communication examples."""
        if not examples:
            return ""

        example_texts = []
        for i, example in enumerate(examples, 1):
            ex_text = self._build_example_section(example, language)
            if ex_text:
                example_texts.append(f"Example {i}:{ex_text}")

        if not example_texts:
            return ""

        return f"""

═══════════════════════════════════════════
HOW YOU ACTUALLY RESPOND (MATCH THIS STYLE)
═══════════════════════════════════════════
{chr(10).join(example_texts)}
Keep responses THIS concise. No extra elaboration.
"""

    def _determine_emphasis(
        self,
        analyzed_context: Optional["AnalyzedContext"]
    ) -> Dict[str, bool]:
        """
        Determine which voiceprint elements to emphasize based on query context.

        Extended with emphasis categories:
        - coaching: For mentorship/DM contexts
        - crisis: For incident/security responses

        Args:
            analyzed_context: The analyzed context from Stage 1

        Returns:
            Dict of element names to emphasis flags
        """
        # Default emphasis (no special emphasis)
        emphasis = {
            "risk_language": False,
            "disagreement": False,
            "decision_cadence": False,
            "numbers_cadence": False,
            "emotional": False,
            "celebratory": False,
            "supportive": False,
            "analogies": False,
            # Additional emphasis flags
            "coaching": False,
            "crisis": False,
        }

        if not analyzed_context:
            return emphasis

        # Import here to avoid circular imports
        try:
            from ...analysis.models import Urgency, UserEmotion, QueryType, Theme
        except ImportError:
            logger.warning("Could not import analysis models for emphasis")
            return emphasis

        # Crisis/Risk → emphasize risk_language, accountability, crisis
        if analyzed_context.urgency == Urgency.CRISIS:
            emphasis["risk_language"] = True
            emphasis["supportive"] = True
            emphasis["crisis"] = True
            logger.debug("Emphasis: crisis → risk_language, supportive, crisis")
        elif analyzed_context.urgency == Urgency.URGENT:
            emphasis["risk_language"] = True
            emphasis["supportive"] = True
            logger.debug("Emphasis: urgent → risk_language, supportive")

        # Stressed/Tense user → emphasize supportive, emotional, coaching
        if analyzed_context.user_emotion in [UserEmotion.STRESSED, UserEmotion.TENSE]:
            emphasis["supportive"] = True
            emphasis["emotional"] = True
            emphasis["coaching"] = True
            logger.debug("Emphasis: stressed/tense → supportive, emotional, coaching")

        # Celebratory → emphasize celebratory openers
        if analyzed_context.user_emotion == UserEmotion.CELEBRATORY:
            emphasis["celebratory"] = True
            emphasis["emotional"] = True
            logger.debug("Emphasis: celebratory → celebratory, emotional")

        # Decision query → emphasize decision_cadence, transparency
        if analyzed_context.query_type == QueryType.DECISION:
            emphasis["decision_cadence"] = True
            emphasis["analogies"] = True
            logger.debug("Emphasis: decision → decision_cadence, analogies")

        # Analytical query → emphasize numbers_cadence
        if analyzed_context.query_type == QueryType.ANALYTICAL:
            emphasis["numbers_cadence"] = True
            logger.debug("Emphasis: analytical → numbers_cadence")

        # Budget/Technical theme → emphasize numbers_cadence
        if analyzed_context.theme in [Theme.BUDGET, Theme.TECHNICAL]:
            emphasis["numbers_cadence"] = True
            logger.debug(f"Emphasis: {analyzed_context.theme.value} → numbers_cadence")

        # Security theme → emphasize risk_language, crisis
        if analyzed_context.theme == Theme.SECURITY:
            emphasis["risk_language"] = True
            emphasis["disagreement"] = True
            emphasis["crisis"] = True
            logger.debug("Emphasis: security → risk_language, disagreement, crisis")

        # HR theme → emphasize coaching, supportive
        if analyzed_context.theme == Theme.HR:
            emphasis["coaching"] = True
            emphasis["supportive"] = True
            logger.debug("Emphasis: hr → coaching, supportive")

        return emphasis

    def _determine_emphasis_from_attention(
        self,
        attention_weights: "AttentionWeights",
    ) -> Dict[str, bool]:
        """
        Convert attention weights to emphasis flags.

        Uses graduated attention weights
        to determine which voiceprint elements to emphasize.

        Categories with weight >= 0.12 get emphasized (True).
        This provides more nuanced emphasis than binary context-based rules.

        Args:
            attention_weights: AttentionWeights from SemanticAttention

        Returns:
            Dict of element names to emphasis flags (same format as _determine_emphasis)
        """
        # Thresholds for emphasis (tuned for softmax-normalized weights)
        HIGH_THRESHOLD = 0.12  # Categories above this get emphasized
        MEDIUM_THRESHOLD = 0.08  # Some categories only need medium threshold

        emphasis = {
            # Map attention categories to emphasis flags
            "risk_language": attention_weights.risk_language >= HIGH_THRESHOLD,
            "disagreement": attention_weights.disagreement >= MEDIUM_THRESHOLD,
            "decision_cadence": attention_weights.decision_cadence >= HIGH_THRESHOLD,
            "numbers_cadence": attention_weights.numbers_cadence >= HIGH_THRESHOLD,
            "emotional": attention_weights.emotional_expressions >= HIGH_THRESHOLD,
            "celebratory": attention_weights.energy_words >= HIGH_THRESHOLD,
            "supportive": (
                attention_weights.mentorship_phrases >= MEDIUM_THRESHOLD or
                attention_weights.emotional_expressions >= HIGH_THRESHOLD
            ),
            "analogies": attention_weights.decision_cadence >= HIGH_THRESHOLD,
            # Phase 2 emphasis flags
            "coaching": attention_weights.mentorship_phrases >= HIGH_THRESHOLD,
            "crisis": attention_weights.accountability_phrases >= HIGH_THRESHOLD,
            # Additional mappings for new categories
            "transparency": attention_weights.transparency_phrases >= HIGH_THRESHOLD,
            "challenge": attention_weights.challenge_invitation >= HIGH_THRESHOLD,
            "deference": attention_weights.deference_phrases >= MEDIUM_THRESHOLD,
            "accountability": attention_weights.accountability_phrases >= HIGH_THRESHOLD,
            "energy": attention_weights.energy_words >= HIGH_THRESHOLD,
            "humor": attention_weights.humor_markers >= MEDIUM_THRESHOLD,
        }

        # Log which categories are emphasized
        emphasized = [k for k, v in emphasis.items() if v]
        if emphasized:
            logger.debug(f"Attention-based emphasis: {emphasized}")

        return emphasis
