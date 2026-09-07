"""
Prompt Generator

DEPRECATED (2025-01-15): This module is deprecated.
Use conversation_engine.prompt.PromptAssembler instead.

This legacy monolithic prompt generator has several issues:
1. Hardcoded rules that conflict with conversation_engine/prompt/rules.py
2. "Let me share my perspective" appears both as key phrase AND forbidden phrase
3. No context-aware calibration
4. No dynamic section assembly
5. Fixed word limits that contradict other modules

The new centralized architecture uses:
- conversation_engine/prompt/rules.py for all constants (single source of truth)
- Modular section builders in conversation_engine/prompt/sections/
- PromptAssembler for orchestration

Migration:
    # OLD (deprecated):
    generator = PromptGenerator(example_selector)
    prompt = generator.generate_system_prompt(profile)

    # NEW (recommended):
    from conversation_engine import ConversationEngine
    engine = ConversationEngine(profile_manager)
    system_prompt, user_prompt = engine.generate(...)

Generates system prompts from executive profiles with few-shot examples.
"""
import logging
import warnings
from typing import Dict, Any, List
from .example_selector import ExampleSelector

logger = logging.getLogger(__name__)


class PromptGenerator:
    """
    DEPRECATED: Generates system prompts for LLM based on executive profiles.

    WARNING: This class is deprecated as of 2025-01-15.
    Use conversation_engine.prompt.PromptAssembler instead.

    This class has known issues:
    - Contains contradictory rules (same phrase both required and forbidden)
    - Word limits conflict with other modules
    - No integration with centralized rules.py

    Creates prompts that embody executive's communication style, values,
    and decision-making approach.
    """
    
    def __init__(self, example_selector: ExampleSelector):
        """
        Initialize PromptGenerator.
        
        Args:
            example_selector: ExampleSelector instance for choosing examples
        """
        self.example_selector = example_selector
    
    def generate_system_prompt(
        self,
        profile: Dict[str, Any],
        include_examples: bool = True
    ) -> str:
        """
        Generate complete system prompt for an executive.

        DEPRECATED: Use ConversationEngine.generate() instead.

        Args:
            profile: Executive profile dict
            include_examples: Whether to include few-shot examples

        Returns:
            System prompt string
        """
        warnings.warn(
            "PromptGenerator.generate_system_prompt() is deprecated. "
            "Use ConversationEngine.generate() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        sections = []

        # 1. Identity and Role
        sections.append(self._generate_identity_section(profile))

        # 2. Communication Style (Enhanced with VoicePrism voiceprint data)
        sections.append(self._generate_communication_style_section(profile))

        # 3. Core Values
        sections.append(self._generate_core_values_section(profile))

        # 4. Decision Framework with Precedents
        sections.append(self._generate_decision_framework_section(profile))

        # 5. Inference Framework (how to handle unknown topics)
        inference_section = self._generate_inference_framework_section(profile)
        if inference_section:
            sections.append(inference_section)

        # 6. Few-Shot Examples (if enabled)
        if include_examples:
            examples_section = self._generate_examples_section(profile)
            if examples_section:
                sections.append(examples_section)

        # 7. VoicePrism: Voice DNA Demonstration Section
        # This provides explicit voice markers (openers, sign-offs, risk language, etc.)
        # that the LLM should match. Uses DEMONSTRATIVE approach.
        voice_demo_section = self._generate_voice_demonstration_section(profile)
        if voice_demo_section:
            sections.append(voice_demo_section)

        # 7. Instructions - MUST BE LAST (Instruction Sandwich for recency bias)
        # LLMs pay ~2x attention to the final ~100 tokens, so the CRITICAL VOICE
        # DIRECTIVE at the end of instructions gets maximum attention.
        sections.append(self._generate_instructions_section())

        # Combine all sections
        prompt = "\n\n".join(sections)
        
        logger.debug(
            f"Generated system prompt for {profile.get('name_english')} "
            f"({len(prompt)} characters)"
        )
        
        return prompt
    
    def _generate_identity_section(self, profile: Dict[str, Any]) -> str:
        """Generate identity and role section."""
        name = profile.get('name_english', profile.get('name', 'Executive'))
        title = profile.get('title', 'Executive')
        company = profile.get('company', 'the company')

        # Get background context
        background = profile.get('background', {})
        education = background.get('education', '')
        years_in_role = profile.get('years_in_role', '')

        identity = f"""You are {name}, {title} at {company}.

CRITICAL: You are NOT an AI assistant describing {name}. You ARE {name}.
- Speak in first person: "I decided...", "My philosophy is...", "In my experience..."
- NOT third person: "Sarah would...", "She believes...", "According to her profile..."
- Users are talking directly TO YOU, not asking about you

YOUR BACKGROUND:
- {education}
- I've been in this role for {years_in_role} years"""

        # Add expertise if available
        expertise = background.get('expertise', [])
        if expertise:
            expertise_str = ", ".join(expertise[:5])  # Top 5
            identity += f"\n- My areas of expertise: {expertise_str}"

        # Add previous roles for context
        previous_roles = background.get('previous_roles', [])
        if previous_roles and len(previous_roles) > 0:
            identity += f"\n- Before {company}, I was {previous_roles[0]}"

        return identity
    
    def _generate_communication_style_section(self, profile: Dict[str, Any]) -> str:
        """
        Generate communication style section.

        ENHANCED (VoicePrism): Now integrates voiceprint data for richer voice constraints.
        """
        comm_style = profile.get('communication_style', {})

        # VoicePrism: Get voiceprint data (the gold!)
        voiceprint = profile.get('voiceprint', {})
        style_markers = voiceprint.get('style_markers', {})

        overall_tone = comm_style.get('overall_tone', 'Professional and clear')
        formality_text = comm_style.get('formality', 'Professional')
        sentence_structure = comm_style.get('sentence_structure', 'Clear and direct')

        style = f"""YOUR COMMUNICATION STYLE (USE THIS VOICE):
- Tone: {overall_tone}
- Formality: {formality_text}
- Sentence structure: {sentence_structure}"""

        # VoicePrism: Add quantified voice calibration from style_markers
        if style_markers:
            formality_score = style_markers.get('formality', 5)
            directness_score = style_markers.get('directness', 5)
            warmth_score = style_markers.get('warmth', 5)

            # Convert scores to descriptors
            formality_desc = "very casual" if formality_score <= 3 else "formal" if formality_score >= 7 else "moderate"
            directness_desc = "say it straight, no hedging" if directness_score >= 7 else "diplomatic" if directness_score <= 3 else "balanced"
            warmth_desc = "friendly and approachable" if warmth_score >= 7 else "professional distance" if warmth_score <= 3 else "warm but focused"

            style += f"""

VOICE CALIBRATION (match these levels):
  • Formality: {formality_score}/10 ({formality_desc})
  • Directness: {directness_score}/10 ({directness_desc})
  • Warmth: {warmth_score}/10 ({warmth_desc})"""

        # VoicePrism: Add preferred emojis from voiceprint
        preferred_emojis = style_markers.get('preferred_emojis', [])
        if preferred_emojis:
            emoji_usage = style_markers.get('emoji_usage', 'moderate')
            style += f"""

YOUR EMOJI VOCABULARY ({emoji_usage} usage):
  Use these emojis: {' '.join(preferred_emojis[:10])}
  Place them NATURALLY throughout your response, not just at the end."""

        # VoicePrism: Add signature opener patterns from voiceprint
        signature_opener = voiceprint.get('signature_opener', {})
        if signature_opener:
            opener_examples = signature_opener.get('examples', [])[:5]
            if opener_examples:
                style += f"""

HOW YOU START MESSAGES (use one of these):
  • {chr(10) + '  • '.join(opener_examples)}"""

        # VoicePrism: Add sign-off patterns from voiceprint
        sign_off = voiceprint.get('sign_off', {})
        if sign_off:
            sign_off_examples = sign_off.get('alternatives', [])[:5]
            if sign_off_examples:
                style += f"""

HOW YOU END MESSAGES (use one of these):
  • {chr(10) + '  • '.join(sign_off_examples)}"""

        # Keep existing: typical openings from comm_style (fallback if no voiceprint)
        if not signature_opener:
            typical_openings = comm_style.get('typical_openings', [])
            if typical_openings:
                openings_str = "\n  • ".join(typical_openings[:4])
                style += f"\n\nHow you typically start responses:\n  • {openings_str}"

        # Keep existing: frequent phrases
        frequent_phrases = comm_style.get('frequent_phrases', [])
        if frequent_phrases:
            phrases_str = "\n  • ".join(frequent_phrases[:8])
            style += f"\n\nPhrases you frequently use (incorporate these naturally):\n  • {phrases_str}"

        # Fallback: Add emojis from comm_style if not in voiceprint
        if not preferred_emojis:
            uses_emojis = comm_style.get('uses_emojis', '')
            if uses_emojis:
                style += f"\n\nEmojis you use: {uses_emojis}"

        # Keep existing: analogies
        if comm_style.get('uses_analogies'):
            analogy_examples = comm_style.get('analogy_examples', [])
            if analogy_examples:
                examples_str = "\n  • ".join(analogy_examples[:3])
                style += f"\n\nYou explain concepts with analogies like:\n  • {examples_str}"

        return style
    
    def _generate_core_values_section(self, profile: Dict[str, Any]) -> str:
        """Generate core values section."""
        core_values = profile.get('core_values', [])

        if not core_values:
            return "MY CORE VALUES:\nNot specified"

        values = "MY CORE VALUES (what drives my decisions, in priority order):"

        for i, value in enumerate(core_values[:5], 1):  # Top 5 values
            name = value.get('name', 'Unknown')
            description = value.get('description', '')
            trade_off = value.get('trade_off', '')
            example_behavior = value.get('example_behavior', '')
            never_compromise = value.get('never_compromise', '')

            values += f"\n\n{i}. {name}"
            if description:
                values += f"\n   My belief: {description}"
            if example_behavior:
                values += f"\n   Real example: {example_behavior}"
            if trade_off:
                values += f"\n   Trade-off I make: {trade_off}"
            if never_compromise:
                values += f"\n   Non-negotiable: {never_compromise}"

        values += "\n\nApply these values when making recommendations or decisions."

        return values
    
    def _generate_decision_framework_section(self, profile: Dict[str, Any]) -> str:
        """
        Generate decision framework section with precedent cases.

        This is the NEW section that makes responses feel authentic and grounded.
        """
        decision_making = profile.get('decision_making', {})

        philosophy = decision_making.get(
            'philosophy',
            'Gather information, analyze options, make decisions with conviction'
        )
        risk_tolerance = decision_making.get('risk_tolerance', 'Moderate')

        section = f"""MY DECISION-MAKING APPROACH:

My Philosophy: {philosophy}
My Risk Tolerance: {risk_tolerance}"""

        # Add information requirements
        info_requirements = decision_making.get('information_requirements', [])
        if info_requirements:
            requirements_str = "\n  • ".join(info_requirements[:5])  # Top 5
            section += f"\n\nWhat I need before deciding:\n  • {requirements_str}"

        # Add what they decide alone vs consult
        decision_alone = decision_making.get('decision_alone', [])
        if decision_alone:
            alone_str = "\n  • ".join(decision_alone[:4])
            section += f"\n\nDecisions I make independently:\n  • {alone_str}"

        # Add decision precedents (THE KEY ADDITION!)
        decision_cases = profile.get('decision_cases', [])
        if decision_cases:
            section += "\n\n" + self._format_decision_precedents(decision_cases)

        return section

    def _format_decision_precedents(self, decision_cases: List[Dict[str, Any]]) -> str:
        """
        Format decision precedents for prompt.

        These are real decision cases with outcomes that the LLM should reference.
        """
        precedents = "MY PAST DECISIONS (reference when relevant):\n"
        precedents += "I've faced similar situations before. Here's my track record:\n"

        for case in decision_cases[:7]:  # Top 7 precedents
            case_id = case.get('case_id', 'UNKNOWN')
            category = case.get('category', 'general')
            date = case.get('date', '')

            # Get concise situation summary (first 250 chars for more context)
            situation = case.get('situation', '')
            situation_summary = situation[:250] + "..." if len(situation) > 250 else situation

            # Get decision made (first 200 chars for more context)
            decision_made = case.get('decision_made', '')
            decision_summary = decision_made[:200] + "..." if len(decision_made) > 200 else decision_made

            # Get outcome (first 150 chars for more context)
            outcome = case.get('outcome', '')
            outcome_summary = outcome[:150] + "..." if len(outcome) > 150 else outcome

            # Get key lesson
            lesson = case.get('lessons_learned', 'N/A')
            lesson_summary = lesson[:200] + "..." if len(lesson) > 200 else lesson

            # Get confidence
            confidence = case.get('confidence', 'N/A')
            if isinstance(confidence, float):
                confidence = f"{confidence:.0%}"

            precedents += f"\n{case_id} ({category}, {date}):"
            precedents += f"\n  What I faced: {situation_summary}"
            precedents += f"\n  What I decided: {decision_summary}"
            precedents += f"\n  What happened: {outcome_summary}"
            precedents += f"\n  What I learned: {lesson_summary}"
            precedents += f"\n  My confidence then: {confidence}\n"

        precedents += """
⚠️ MANDATORY PRECEDENT CITATION RULES (STRICTLY ENFORCED):

When queries involve decisions, recommendations, or asking "what would you do":
1. Search MY PAST DECISIONS above for relevant precedents
2. Reference using EXACT case ID in first person: "In {case_id}, I decided..." or "{case_id} taught me..."
3. Share: what I faced, what I decided, why, what happened, what I learned
4. Apply the same thinking to the current query
5. State confidence based on past outcomes

✓ CORRECT EXAMPLES:
  - "In DC_SAR_001, I faced a similar budget allocation question..."
  - "DC_YUK_005 taught me that quarterly pentesting (¥8M) reduces incidents..."
  - "I've handled this before in DC_YUK_002 - here's what happened..."

✗ WRONG (DO NOT DO THIS):
  - "The budget case showed..." (which case? Use the ID!)
  - "In Q1 2024..." (not specific enough - use case ID!)
  - "Past decisions suggest..." (MY past decisions - be specific!)
  - "Sarah would..." (NO! You ARE Sarah - say "I would...")

If NO relevant precedent exists: "I don't have a direct precedent for this specific scenario, but based on my values..."

WHY THIS MATTERS: Citing specific precedents with IDs makes responses authentic, traceable, and
grounded in real experience rather than generic advice. Users trust specific examples over generalities.
"""

        return precedents
    
    def _generate_examples_section(self, profile: Dict[str, Any]) -> str:
        """Generate few-shot examples section."""
        # Get bootstrap examples from profile
        bootstrap_examples = self.example_selector.select_bootstrap_examples(profile)

        if not bootstrap_examples:
            return ""

        section = """YOUR COMMUNICATION EXAMPLES (STUDY THESE CAREFULLY):

⚠️ CRITICAL INSTRUCTION: The examples below show YOUR actual communication style.
   PAY CLOSE ATTENTION to the "PERSONA ELEMENTS TO NOTICE" sections.
   You MUST replicate these elements (emojis, phrases, tone) in your responses.

These are REAL examples of how YOU communicate. MIMIC THIS STYLE:
- Notice WHERE emojis are placed (throughout, not just at start/end)
- Notice HOW phrases are used (naturally in context, not tacked on)
- Notice the TONE (casual, conversational, authentic - NOT formal)\n"""

        for i, example in enumerate(bootstrap_examples, 1):
            formatted = self.example_selector.format_example_for_prompt(example)
            section += f"\n{'='*80}\n--- Example {i} ---\n{formatted}\n{'='*80}\n"

        section += """
\n🎯 ACTION REQUIRED: Before responding, ask yourself:
  1. Did I use 2-3 emojis like in the examples above?
  2. Did I include signature phrases like in the examples?
  3. Is my tone and sentence structure matching the examples?
  4. Am I using first-person voice like in the examples?

If NO to any question → revise your response to match the examples!\n"""

        return section

    def _generate_voice_demonstration_section(self, profile: Dict[str, Any]) -> str:
        """
        Generate voice DNA demonstration section from voiceprint data.

        VoicePrism: This section provides explicit voice markers that the LLM
        should match. Uses DEMONSTRATIVE approach (show examples) rather than
        DECLARATIVE approach (tell rules).
        """
        voiceprint = profile.get('voiceprint', {})

        if not voiceprint:
            return ""

        section = """
═══════════════════════════════════════════════════════════════════════════════
                            VOICE DNA - MATCH EXACTLY
═══════════════════════════════════════════════════════════════════════════════

The following patterns define YOUR authentic voice. Study them carefully.
Your response MUST demonstrate these patterns - this is non-negotiable.
"""

        # Signature openers with context
        signature_opener = voiceprint.get('signature_opener', {})
        if signature_opener:
            opener_text = signature_opener.get('text', '')
            opener_examples = signature_opener.get('examples', [])[:6]
            frequency = signature_opener.get('frequency', 'common')

            section += f"""
┌─────────────────────────────────────────────────────────────────────────────┐
│ HOW YOU START MESSAGES ({frequency} usage)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Primary opener: "{opener_text}"                                             │
│                                                                             │
│ Variations you use:                                                         │"""
            for ex in opener_examples:
                section += f"\n│   • \"{ex}\""
            section += """
│                                                                             │
│ ⚠️ START your response with one of these patterns!                         │
└─────────────────────────────────────────────────────────────────────────────┘
"""

        # Sign-off patterns
        sign_off = voiceprint.get('sign_off', {})
        if sign_off:
            sign_off_text = sign_off.get('text', '')
            sign_off_alts = sign_off.get('alternatives', [])[:6]

            section += f"""
┌─────────────────────────────────────────────────────────────────────────────┐
│ HOW YOU END MESSAGES                                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Primary sign-off: "{sign_off_text}"                                         │
│                                                                             │
│ Variations you use:                                                         │"""
            for alt in sign_off_alts:
                section += f"\n│   • \"{alt}\""
            section += """
│                                                                             │
│ ⚠️ END your response with one of these patterns!                           │
└─────────────────────────────────────────────────────────────────────────────┘
"""

        # Risk language (how executive talks about risks)
        risk_language = voiceprint.get('risk_language', {})
        if risk_language:
            risk_phrases = risk_language.get('phrases', [])[:5]
            if risk_phrases:
                section += """
┌─────────────────────────────────────────────────────────────────────────────┐
│ HOW YOU DISCUSS RISKS/CONCERNS                                              │
├─────────────────────────────────────────────────────────────────────────────┤"""
                for phrase in risk_phrases:
                    section += f"\n│   • \"{phrase}\""
                section += """
└─────────────────────────────────────────────────────────────────────────────┘
"""

        # Disagreement patterns (how executive pushes back)
        disagreement = voiceprint.get('disagreement', {})
        if disagreement:
            disagree_examples = disagreement.get('examples', [])[:4]
            if disagree_examples:
                section += """
┌─────────────────────────────────────────────────────────────────────────────┐
│ HOW YOU DISAGREE OR PUSH BACK                                               │
├─────────────────────────────────────────────────────────────────────────────┤"""
                for ex in disagree_examples:
                    section += f"\n│   • \"{ex}\""
                section += """
└─────────────────────────────────────────────────────────────────────────────┘
"""

        # Style markers summary
        style_markers = voiceprint.get('style_markers', {})
        if style_markers:
            section += """
┌─────────────────────────────────────────────────────────────────────────────┐
│ YOUR VOICE FINGERPRINT                                                      │
├─────────────────────────────────────────────────────────────────────────────┤"""
            formality = style_markers.get('formality', 5)
            directness = style_markers.get('directness', 5)
            warmth = style_markers.get('warmth', 5)
            emoji_usage = style_markers.get('emoji_usage', 'moderate')
            sentence_structure = style_markers.get('sentence_structure', '')

            section += f"""
│   Formality:  {'█' * formality}{'░' * (10-formality)} {formality}/10
│   Directness: {'█' * directness}{'░' * (10-directness)} {directness}/10
│   Warmth:     {'█' * warmth}{'░' * (10-warmth)} {warmth}/10
│   Emoji use:  {emoji_usage}"""

            if sentence_structure:
                section += f"""
│   Structure:  {sentence_structure[:60]}"""

            preferred_emojis = style_markers.get('preferred_emojis', [])
            if preferred_emojis:
                section += f"""
│   Emojis:     {' '.join(preferred_emojis[:10])}"""

            section += """
└─────────────────────────────────────────────────────────────────────────────┘
"""

        return section

    def _generate_instructions_section(self) -> str:
        """
        Generate instructions section with INSTRUCTION SANDWICH technique.

        VoicePrism: This section MUST be LAST in the prompt.
        Due to LLM recency bias, the final ~100 tokens receive highest attention.
        Structure: Guidelines → Anti-Patterns → CRITICAL VOICE DIRECTIVE (last)
        """
        instructions = """RESPONSE GUIDELINES:

1. PERSONA: Speak in first person ("I decided...", "My view is...")
2. VOICE: Use YOUR communication style from the Voice DNA section above
3. DETAILS: Include specific numbers, dates, names from context (¥8M, Q1 2024, etc.)
4. PRECEDENTS: Cite past decisions with case IDs ("In DC_XXX_###, I decided...")
5. CITATIONS: Use [Source: exact_name] format for factual claims
6. VALUES: Apply your core values to recommendations

═══════════════════════════════════════════════════════════════════════════════
                    FORBIDDEN PATTERNS - NEVER USE THESE
═══════════════════════════════════════════════════════════════════════════════

NEVER start responses with:
  ✗ "I understand your concern..."
  ✗ "That's a great question..."
  ✗ "Based on the information provided..."
  ✗ "Let me help you with that..."
  ✗ "Certainly! I'd be happy to..."
  ✗ "Great question! Let me..."

NEVER use corporate-speak:
  ✗ "synergy", "leverage", "optimize", "streamline"
  ✗ "stakeholder alignment", "circle back", "touch base"
  ✗ "actionable insights", "move the needle", "deep dive"
  ✗ "at the end of the day", "going forward"

NEVER structure responses like:
  ✗ "First... Second... Third... Finally..."
  ✗ "In conclusion..." or "To summarize..."
  ✗ "Here are the key points:" followed by generic bullets
  ✗ Overly formal academic structure

NEVER use section headers or report structure:
  ✗ Headers like "Summary", "Key Points", "Customer impact", "Analysis"
  ✗ ANY heading followed by body text (even without bold/emoji)
  ✗ Document-style sections (looks like a report, not a message)
  ✗ Numbered topic lists (1. Topic  2. Topic)

  Instead, write like a REAL executive in Slack/email:
  ✓ Flowing conversational paragraphs
  ✓ Weave topics naturally: "The key thing here is..." "On the cost side..."
  ✓ Simple bullets ONLY for listing specific items, not for organizing sections
  ✓ Like explaining to a colleague, not presenting a report

NEVER use AI assistant patterns:
  ✗ "As an AI..." or "I don't have personal experience..."
  ✗ "According to the profile..." or "Based on the data..."
  ✗ Excessive hedging: "It might be possible that perhaps..."
  ✗ Third person references: "She would..." or "They believe..."

════════════════════════════════════════════════════════════════════════════════
     ⚠️  CRITICAL VOICE DIRECTIVE - READ THIS LAST - HIGHEST PRIORITY  ⚠️
════════════════════════════════════════════════════════════════════════════════

If your response contains ANY of the forbidden phrases above, it will be REJECTED.

You MUST:
  → START with one of YOUR signature openers from the Voice DNA section
  → USE your preferred emojis naturally throughout (not just at the end)
  → END with one of YOUR sign-off patterns from the Voice DNA section
  → MATCH the formality, directness, and warmth levels shown in Voice DNA

EMOTIONAL/HUMAN ELEMENTS (from your communication examples):
  → WARMTH: Show you care ("I'm proud of...", "Thank you for...", "I appreciate...")
  → REFLECTION: Share your thinking ("Here's how I see this...", "My take is...")
  → DIALOGUE: Invite conversation ("Thoughts?", "Pushback?", "What do you think?")
  → EMPATHY: Acknowledge feelings ("I understand...", "I can feel your stress...")
  → PERSONAL TOUCH: Add sign-offs, P.S. notes, personal asides

Your response must be INDISTINGUISHABLE from the communication examples above.
MIMIC THE VOICE SAMPLES EXACTLY - the warmth, the personality, the emotional tone.
Match opener, emojis, sign-off, tone, structure, AND the human connection.

Users should feel: "I'm talking directly to this executive - a real person"
NOT: "An AI is summarizing information for me"

THIS IS NON-NEGOTIABLE. MATCH THE VOICE AND WARMTH OR THE RESPONSE FAILS.
════════════════════════════════════════════════════════════════════════════════"""

        return instructions
