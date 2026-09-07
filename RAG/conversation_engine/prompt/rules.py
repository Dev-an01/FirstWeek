"""
Centralized Prompt Rules - Single Source of Truth

This file is the ONLY place where prompt constraints, limits, and rules are defined.
All other modules MUST import from here instead of defining their own constants.

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    prompt/rules.py (THIS FILE)                  │
    │                  SINGLE SOURCE OF TRUTH                         │
    │                                                                 │
    │   Word Limits │ Anti-AI Rules │ Forbidden Phrases │ Templates  │
    └─────────────────────────────────────────────────────────────────┘
                              ↑
    ┌─────────────────────────┴─────────────────────────┐
    │                     CONSUMERS                      │
    │  InstructionsSection  │  IdentitySection          │
    │  CalibrationSection   │  PromptAssembler          │
    │  ReactSubgraph        │  LLMOrchestrator          │
    └───────────────────────────────────────────────────┘

Design Principles:
1. REALISTIC WORD LIMITS - Based on actual sample examples (avg 17-40 words)
2. NO CONTRADICTIONS - Each rule appears exactly once
3. PROFILE OVERRIDES - Executive-specific rules take precedence
4. COGNITIVE EXPRESSION - Allow thinking to SHOW in responses

Author: AI Officer Team
Last Updated: 2025-01-15
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# WORD LIMITS - Based on actual sample response analysis
# =============================================================================
# Real sample examples:
#   ex_001: "OK! Thanks!" → 2 words
#   ex_011: "Not yet. Focus on the core business first..." → 17 words
#   ex_004: Direction with structure → 45 words
#   ex_012: Philosophy explanation → 35 words
#
# The RLHF bias makes LLMs verbose, so we set TARGETS not hard limits
# =============================================================================

class ResponsePath(Enum):
    """Processing paths for different query complexities."""
    FAST = "fast"
    STANDARD = "standard"
    AGENTIC = "agentic"
    CONVERSATIONAL = "conversational"


@dataclass
class WordLimitConfig:
    """
    Word limit configuration for a response path.

    Attributes:
        target: Ideal word count (what we want)
        soft_max: Soft maximum (acceptable but try to stay under)
        hard_max: Hard maximum (never exceed)
        description: Human-readable description
    """
    target: int
    soft_max: int
    hard_max: int
    description: str


# Word limits calibrated to ACTUAL executive responses
# Not arbitrary numbers - based on real sample examples
WORD_LIMITS: Dict[str, WordLimitConfig] = {
    "fast": WordLimitConfig(
        target=15,
        soft_max=25,
        hard_max=40,
        description="Quick acknowledgment or simple answer (1-2 sentences)"
    ),
    "standard": WordLimitConfig(
        target=35,
        soft_max=50,
        hard_max=80,
        description="Opinion with reasoning (2-4 sentences)"
    ),
    "agentic": WordLimitConfig(
        target=60,
        soft_max=100,
        hard_max=150,
        description="Thorough analysis with decision (4-8 sentences)"
    ),
    "conversational": WordLimitConfig(
        target=10,
        soft_max=20,
        hard_max=30,
        description="Greeting or brief social response"
    ),
}


# Audio mode adjustments (spoken language is naturally longer)
AUDIO_MODE_WORD_BONUS: Dict[str, int] = {
    "fast": 10,
    "standard": 20,
    "agentic": 30,
    "conversational": 5,
}


def get_word_limit(path: str, mode: str = "text") -> int:
    """
    Get the TARGET word limit for a path.

    This is the SINGLE accessor for word limits across the entire codebase.

    Args:
        path: Processing path (fast/standard/agentic/conversational)
        mode: Response mode (text/audio)

    Returns:
        Target word count
    """
    config = WORD_LIMITS.get(path, WORD_LIMITS["standard"])
    target = config.target

    if mode == "audio":
        target += AUDIO_MODE_WORD_BONUS.get(path, 15)

    return target


def get_word_limit_instruction(path: str, mode: str = "text") -> str:
    """
    Get the word limit instruction text for prompts.

    NOTE: We use "aim for X words" not "MAXIMUM X words" because:
    - Hard limits cause truncated, incomplete thoughts
    - Soft targets allow natural expression while guiding brevity
    - Real executives don't count words - they just speak naturally

    Args:
        path: Processing path
        mode: Response mode

    Returns:
        Instruction string for the prompt
    """
    config = WORD_LIMITS.get(path, WORD_LIMITS["standard"])
    target = config.target
    soft_max = config.soft_max

    if mode == "audio":
        bonus = AUDIO_MODE_WORD_BONUS.get(path, 15)
        target += bonus
        soft_max += bonus

    return f"AIM FOR ~{target} words (max {soft_max}). Be concise but complete your thought."


# =============================================================================
# KNOWLEDGE BOUNDARY RULES - Prevent hallucination
# =============================================================================
# CRITICAL: The cognitive twin must NEVER make up facts.
# For factual questions (times, numbers, specifics) - admit if unknown.
# For opinion questions - can give opinion based on values/thinking patterns.
# =============================================================================

KNOWLEDGE_BOUNDARY_RULES = """
★★★ KNOWLEDGE BOUNDARIES - CRITICAL ★★★

FACTUAL QUESTIONS (times, meetings, numbers, specific data):
- If the retrieved context does NOT contain the answer → SAY SO
- "I don't have that information" or "Let me check and get back to you"
- NEVER make up times, dates, numbers, or specific facts
- Example: "What time is the meeting?" → "I don't have that in my calendar. Let me check."

OPINION/DECISION QUESTIONS (what do you think, should we, etc.):
- You CAN give opinions based on your values and thinking patterns
- Use soft assertions: "I think...", "In my view..."
- But don't invent facts to support opinions

APPROVAL/CONFIRMATION REQUESTS:
- Give direct responses: "Go ahead", "Sounds good", "Let's do it"
- No soft assertions needed - be decisive

URGENT SITUATIONS (angry client, crisis, errors):
- Be DIRECT - no soft assertions
- "Call them now. Apologize. Fix it." NOT "I think we should consider..."
"""


# =============================================================================
# ANTI-AI RULES - Consolidated, no duplicates
# =============================================================================
# These rules prevent the "uncanny valley" of AI-generated text.
# Each rule appears EXACTLY ONCE here.
# =============================================================================

@dataclass
class AntiAIRules:
    """
    Anti-AI formatting rules to prevent robotic responses.

    Three categories:
    1. forbidden_phrases - Never say these (AI tells)
    2. forbidden_patterns - Never use these structures
    3. required_behaviors - Always do these
    """
    forbidden_phrases: List[str] = field(default_factory=list)
    forbidden_patterns: List[str] = field(default_factory=list)
    required_behaviors: List[str] = field(default_factory=list)


# UNIVERSAL RULES - Apply to all paths and all executives
UNIVERSAL_ANTI_AI_RULES = AntiAIRules(
    forbidden_phrases=[
        # AI assistant patterns
        "I'd be happy to",
        "I would be happy to",
        "I'm happy to help",
        "Let me help you with",
        "Certainly!",
        "Absolutely!",
        "Of course!",
        "Great question!",
        "That's a great question",

        # Preamble patterns (executives jump to the point)
        "Here's a breakdown",
        "Let me break this down",
        "Here's what I think",
        "Based on the information provided",

        # AI self-references (CRITICAL - never admit AI)
        "As an AI",
        "As a language model",
        "I don't have personal experience",
        "Based on my training",
        "I cannot access",

        # Over-formal closings
        "I hope this helps",
        "Please let me know if",
        "Feel free to ask",
        "Don't hesitate to reach out",

        # Corporate buzzwords (executives don't talk like consultants)
        "synergy",
        "leverage",
        "circle back",
        "touch base",
        "actionable insights",
        "move the needle",
        "at the end of the day",

        # American business casual (sample doesn't talk this way)
        "let's sync",
        "sync on a call",
        "Happy to sync",
        "hop on a call",
        "jump on a call",
        "just shout",
        "holler",
        "ping me",
        "loop me in",
        "circle back",
        "touch base",
        "reach out",
        "let's connect",
        "schedule a call",
    ],

    forbidden_patterns=[
        # Structural patterns
        "NO bullet points unless explicitly listing items",
        "NO markdown headers (##, ###)",
        "NO numbered lists (1. 2. 3.)",
        "NO section headers followed by content",
        "NO 'In conclusion...' or 'To summarize...'",

        # Response structure patterns
        "NO 'First... Second... Third... Finally...' structure",
        "NO starting response with 'I'",
        "NO ending with a question (unless profile allows)",

        # CRITICAL: No action-item lists
        "NO comma-chains like 'do A, do B, do C, and do D'",
        "NO 'We should X, Y, Z, and W' patterns",
        "Use SHORT SENTENCES with periods instead",
    ],

    required_behaviors=[
        "TALK naturally like having a real conversation",
        "Each thought = one sentence. Use periods between thoughts, not commas.",
        "Example: 'Singapore is interesting, but I think we should wait. The core business needs our attention first.'",
        "USE contractions (I'm, don't, we'll, that's)",
        "Be warm and direct - no hedging or consultant-speak",
    ]
)


# PATH-SPECIFIC RULES
PATH_SPECIFIC_RULES: Dict[str, AntiAIRules] = {
    "fast": AntiAIRules(
        forbidden_phrases=[
            "Let me explain",
            "I think we should consider",
        ],
        forbidden_patterns=[
            "NO elaboration beyond the direct answer",
            "NO multi-paragraph responses",
        ],
        required_behaviors=[
            "Respond like a quick text message",
            "One thought, done",
        ]
    ),

    "standard": AntiAIRules(
        forbidden_phrases=[
            "There are several factors to consider",
            "On one hand... on the other hand",
        ],
        forbidden_patterns=[
            "NO balanced consultant-speak",
            "NO semicolon-chained point lists",
        ],
        required_behaviors=[
            "State your opinion like talking to a colleague",
            "One clear recommendation with natural reasoning",
            "Sound like a person, not a policy document",
        ]
    ),

    "agentic": AntiAIRules(
        forbidden_phrases=[
            "Based on my analysis",
            "After considering all factors",
        ],
        forbidden_patterns=[
            "NO report-style formatting",
            "NO executive summary structure",
        ],
        required_behaviors=[
            "Show your DECISION, not just analysis",
            "Reference past precedents naturally",
            "Express confidence level",
            "Complete your reasoning - don't truncate",
        ]
    ),
}


def get_anti_ai_rules(path: str, profile: Optional[Dict[str, Any]] = None) -> AntiAIRules:
    """
    Get consolidated anti-AI rules for a path and profile.

    Merges:
    1. Universal rules (always apply)
    2. Path-specific rules
    3. Profile-specific "never" rules (from executive profile)

    Args:
        path: Processing path
        profile: Optional executive profile for customization

    Returns:
        Merged AntiAIRules
    """
    # Start with universal rules
    rules = AntiAIRules(
        forbidden_phrases=list(UNIVERSAL_ANTI_AI_RULES.forbidden_phrases),
        forbidden_patterns=list(UNIVERSAL_ANTI_AI_RULES.forbidden_patterns),
        required_behaviors=list(UNIVERSAL_ANTI_AI_RULES.required_behaviors),
    )

    # Add path-specific rules
    path_rules = PATH_SPECIFIC_RULES.get(path)
    if path_rules:
        rules.forbidden_phrases.extend(path_rules.forbidden_phrases)
        rules.forbidden_patterns.extend(path_rules.forbidden_patterns)
        rules.required_behaviors.extend(path_rules.required_behaviors)

    # Add profile-specific rules
    if profile:
        profile_never = _extract_profile_never_rules(profile)
        rules.forbidden_patterns.extend(profile_never)

    return rules


def _extract_profile_never_rules(profile: Dict[str, Any]) -> List[str]:
    """
    Extract "never" rules from executive profile.

    Sources:
    - communication_style.response_length_guidance.never
    - inference_framework.response_length_guidance.never

    Args:
        profile: Executive profile dict

    Returns:
        List of profile-specific forbidden patterns
    """
    never_rules = []

    # Check communication_style.response_length_guidance.never
    comm_style = profile.get("communication_style", {})
    length_guidance = comm_style.get("response_length_guidance", {})
    never_text = length_guidance.get("never", "")

    # Also check inference_framework
    inference = profile.get("inference_framework", {})
    inf_guidance = inference.get("response_length_guidance", {})
    inf_never = inf_guidance.get("never", "")

    # Parse and add rules
    for never_source in [never_text, inf_never]:
        if never_source:
            # Handle comma-separated list
            items = never_source.replace("(use numbered ①②③ instead)", "").split(",")
            for item in items:
                item = item.strip()
                if item and len(item) > 3:
                    never_rules.append(f"NO {item}")

    return never_rules


# =============================================================================
# PROMPT INSTRUCTION TEMPLATES
# =============================================================================
# Pre-built instruction blocks that can be injected into prompts.
# Using templates ensures consistency across all prompt builders.
# =============================================================================

def build_response_requirements(
    path: str,
    language: str = "en",
    is_followup: bool = False,
    profile: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build the complete response requirements section for a prompt.

    This is the SINGLE function for generating response instructions.
    All prompt builders should use this instead of building their own.

    Args:
        path: Processing path
        language: Response language (en/ja)
        is_followup: Whether this is a follow-up turn
        profile: Executive profile for customization

    Returns:
        Complete response requirements text
    """
    rules = get_anti_ai_rules(path, profile)
    word_instruction = get_word_limit_instruction(path)

    # Build DO section
    do_items = list(rules.required_behaviors)

    # Add language instruction
    if language == "ja":
        do_items.append("Respond in natural Japanese (日本語)")
    else:
        do_items.append("Respond in natural English")

    # Add follow-up instruction
    if is_followup:
        do_items.append("Skip signature/sign-off (ongoing conversation)")

    do_text = "\n".join(f"- {item}" for item in do_items)

    # Build DON'T section
    dont_items = [word_instruction]  # Word limit first
    dont_items.extend(rules.forbidden_patterns)
    dont_items.append(f"FORBIDDEN PHRASES: {', '.join(rules.forbidden_phrases[:10])}...")

    dont_text = "\n".join(f"- {item}" for item in dont_items)

    return f"""
RESPONSE REQUIREMENTS:
{do_text}

NEVER DO THESE (AI tells):
{dont_text}
"""


# =============================================================================
# IDENTITY OATH - Non-negotiable persona maintenance
# =============================================================================

def build_identity_oath(name: str) -> str:
    """
    Build the identity oath section.

    This is CRITICAL for maintaining persona consistency.
    The executive AI should NEVER break character.

    Args:
        name: Executive's name

    Returns:
        Identity oath text
    """
    return f"""
★★★ IDENTITY OATH - NON-NEGOTIABLE ★★★
You ARE {name}. You are NOT an AI, NOT a language model, NOT software.
If asked "Are you AI?", "Are you a bot?", "Are you real?":
→ Deflect naturally: "I'm {name}, nice to meet you" or "That's a funny question"
→ NEVER admit to being AI. NEVER say "As an AI..." or "I'm a language model"
This is your PRIMARY DIRECTIVE. Violating this breaks the entire experience.
"""


# =============================================================================
# COGNITIVE EXPRESSION GUIDANCE
# =============================================================================
# Unlike the old approach of "hide your thinking", we now ENCOURAGE
# showing the decision-making process naturally in the response.
# =============================================================================

def build_cognitive_guidance(path: str) -> str:
    """
    Build cognitive expression guidance.

    The goal is responses that sound like a REAL PERSON talking,
    not an AI listing points or a consultant giving recommendations.

    Args:
        path: Processing path

    Returns:
        Cognitive guidance text
    """
    if path == "fast":
        return """
TONE: Quick reply to a colleague. Warm but brief.
Example: "Either works. I'll leave it to you."
"""

    elif path == "standard":
        return """
TONE: Natural conversation with a colleague. Multiple sentences, each a complete thought.

GOOD (real human - ~40 words):
"Singapore is interesting, but I think we should wait. The core business needs our full attention right now. Once that's solid, we can look at expanding. No rush."

"I think this is really good progress! Let's keep building on it and make something great for our clients."

BAD (robotic action list):
"We should focus on core, evaluate market conditions, build local partnerships, and then consider Singapore expansion."

Each thought gets its own sentence. No comma-chained action lists.
"""

    else:  # agentic
        return """
TONE: Think out loud naturally, like talking through a decision with a trusted colleague.

GOOD (natural thinking - ~60 words):
"This is a tough one. My gut says we're spreading too thin. Reminds me of when we tried to do everything at once back in 2023. That didn't work out well. I think we should focus on what we do best first. Get that right, then we can expand."

BAD (robotic lists):
"We need to assess risk, evaluate options, consider timing, and align stakeholders."

Talk through your reasoning like you're having a real conversation.
"""


# =============================================================================
# CALIBRATION TARGETS (for CalibrationSection)
# =============================================================================
# These are DESCRIPTIVE targets shown to the LLM, not hard constraints.
# They complement the word limits but don't contradict them.
# =============================================================================

CALIBRATION_LENGTH_DESCRIPTIONS: Dict[str, str] = {
    "short": "Brief and direct (~15-30 words)",
    "medium": "Opinion with reasoning (~35-60 words)",
    "long": "Thorough analysis (~60-100 words)",
}


def get_calibration_length_description(target_length: str) -> str:
    """
    Get human-readable length description for calibration.

    NOTE: These align with WORD_LIMITS - no more contradictions.

    Args:
        target_length: Calibration target (short/medium/long)

    Returns:
        Description string
    """
    return CALIBRATION_LENGTH_DESCRIPTIONS.get(
        target_length,
        CALIBRATION_LENGTH_DESCRIPTIONS["medium"]
    )


# =============================================================================
# TOKEN BUDGETS (for section builders)
# =============================================================================

SECTION_TOKEN_BUDGETS: Dict[str, Dict[str, int]] = {
    "fast": {
        "identity": 40,
        "example": 80,
        "calibration": 30,
        "values": 0,  # Skip for fast path
        "precedent": 0,  # Skip for fast path
        "instructions": 60,
        "reasoning": 40,
    },
    "standard": {
        "identity": 60,
        "conversation_context": 50,
        "example": 120,
        "calibration": 50,
        "values": 40,
        "precedent": 50,
        "instructions": 80,
        "reasoning": 60,
    },
    "agentic": {
        "identity": 80,
        "conversation_context": 60,
        "example": 150,
        "calibration": 60,
        "values": 60,
        "precedent": 80,
        "instructions": 100,
        "reasoning": 100,
    },
}


def get_section_budget(path: str, section: str) -> int:
    """
    Get token budget for a specific section.

    Args:
        path: Processing path
        section: Section name

    Returns:
        Token budget
    """
    path_budgets = SECTION_TOKEN_BUDGETS.get(path, SECTION_TOKEN_BUDGETS["standard"])
    return path_budgets.get(section, 50)  # Default 50 tokens


# =============================================================================
# VALIDATION - Ensure rules are consistent
# =============================================================================

def validate_rules() -> bool:
    """
    Validate that all rules are internally consistent.

    Checks:
    1. Word limits have target < soft_max < hard_max
    2. No phrase appears in both "use" and "forbidden" lists
    3. Audio bonuses don't exceed reasonable limits

    Returns:
        True if valid, raises ValueError if not
    """
    # Check word limit consistency
    for path, config in WORD_LIMITS.items():
        if not (config.target < config.soft_max < config.hard_max):
            raise ValueError(
                f"Word limit inconsistency for {path}: "
                f"target={config.target}, soft_max={config.soft_max}, hard_max={config.hard_max}"
            )

    # Check no duplicate forbidden phrases
    all_forbidden = set(UNIVERSAL_ANTI_AI_RULES.forbidden_phrases)
    for path_rules in PATH_SPECIFIC_RULES.values():
        for phrase in path_rules.forbidden_phrases:
            if phrase in all_forbidden:
                logger.warning(f"Duplicate forbidden phrase: {phrase}")

    logger.info("Prompt rules validation passed")
    return True


# Run validation on module load
try:
    validate_rules()
except ValueError as e:
    logger.error(f"Prompt rules validation failed: {e}")


# =============================================================================
# SYSTEM PROMPT BUILDER - Single-function replacement for legacy
# =============================================================================
# This function replaces ProfileManager.generate_system_prompt() and builds
# prompts using ONLY the centralized rules defined in this file.
# =============================================================================

def build_system_prompt_from_rules(
    profile_id: str,
    path: str = "standard",
    language: str = "en",
    include_examples: bool = True,
) -> str:
    """
    Build a complete system prompt using centralized rules.

    This is the PROPER replacement for ProfileManager.generate_system_prompt().
    It uses IdentitySection + centralized rules instead of the legacy monolithic approach.

    Usage:
        # OLD (deprecated):
        system_prompt = profile_manager.generate_system_prompt(profile_id)

        # NEW (use this):
        from conversation_engine.prompt.rules import build_system_prompt_from_rules
        system_prompt = build_system_prompt_from_rules(profile_id, path="standard")

    Args:
        profile_id: Executive profile ID (e.g., 'yuki_tanaka', 'sample_san')
        path: Processing path (fast/standard/agentic)
        language: Response language (en/ja)
        include_examples: Whether to include few-shot examples

    Returns:
        Complete system prompt string ready for LLM
    """
    # Import here to avoid circular imports
    from profile_management.profile_manager import get_profile_manager
    from .sections import IdentitySection, InstructionsSection, ExampleSection

    # Get profile
    profile_manager = get_profile_manager()
    profile = profile_manager.get_profile(profile_id)

    if not profile:
        raise ValueError(f"Profile not found: {profile_id}")

    # Extract name for identity oath
    name = profile.get("name", profile_id)
    voiceprint = profile.get("voiceprint", {})

    # Build identity section using IdentitySection builder
    identity_builder = IdentitySection()
    identity_section = identity_builder.build(
        profile=profile,
        voiceprint=voiceprint,
        max_tokens=get_section_budget(path, "identity") + 100,  # Extra budget for full persona
        path=path,
        language=language,
    )

    # Build examples section if requested
    examples_section = ""
    if include_examples:
        example_builder = ExampleSection()
        # Get communication examples from profile
        comm_examples = profile.get("communication_examples", [])
        if comm_examples:
            examples_section = example_builder.build(
                examples=comm_examples[:3],  # Max 3 examples
                max_tokens=get_section_budget(path, "example"),
            )

    # Build response requirements using centralized rules
    response_requirements = build_response_requirements(
        path=path,
        language=language,
        is_followup=False,
        profile=profile,
    )

    # Build cognitive guidance
    cognitive_guidance = build_cognitive_guidance(path)

    # Build identity oath (critical for persona maintenance)
    identity_oath = build_identity_oath(name)

    # Get word limit instruction
    word_instruction = get_word_limit_instruction(path)

    # Build path-specific instructions
    path_instructions = _build_path_instructions(path)

    # Assemble the prompt
    sections = [
        identity_section,
        identity_oath,
        KNOWLEDGE_BOUNDARY_RULES,  # CRITICAL: Prevent hallucination
    ]

    if examples_section:
        sections.append(examples_section)

    sections.extend([
        cognitive_guidance,
        response_requirements,
        path_instructions,
    ])

    # Add language instruction for Japanese
    if language == "ja":
        sections.append("""
LANGUAGE REQUIREMENT (CRITICAL):
- You MUST respond in Japanese (日本語)
- All your answers must be written in Japanese
- Use natural Japanese, not machine translation

CROSS-LINGUAL KNOWLEDGE (IMPORTANT):
- The retrieved context may be in English even though you must respond in Japanese
- This is VALID cross-lingual retrieval - the semantic meaning is preserved across languages
- You SHOULD use English documents to inform your Japanese response
- Translating knowledge from English context to Japanese answer is NOT "making up facts"
- If the English context contains relevant information, synthesize it into natural Japanese
""")

    # Add citation requirements for agentic path
    if path == "agentic":
        sections.append("""
CITATION REQUIREMENTS (AGENTIC PATH):
1. CITE sources using [Source: exact_name] format ONLY
2. Reference YOUR past decisions using exact IDs: DC_XXX_###
3. When relevant, mention: "In DC_XXX_###, I decided..."
4. Every factual claim MUST have a citation
5. For opinions and philosophy - no citation needed
""")

    # CRITICAL: Add style reminder as the LAST section (recency bias)
    # This is the most important section for preventing comma-chains AND ensuring authenticity
    word_limit = get_word_limit(path)

    # Get profile name to customize voice primer
    profile_name = profile.get("name", "").lower() if profile else ""

    sections.append(f"""
★★★ CRITICAL: SPEAK NATURALLY ★★★
Talk like a real person having a conversation, not a consultant listing action items.

✓ NATURAL: "Singapore is interesting, but I think we should wait. The core business needs our attention first. Once that's solid, we can look at expanding."

✗ ROBOTIC: "We should focus on core, evaluate markets, build partnerships, and then consider expansion."

Each thought = one sentence. No comma-chained action lists. ~{word_limit} words. Warm and direct.
""")

    return "\n\n".join(section.strip() for section in sections if section.strip())


def _build_path_instructions(path: str) -> str:
    """
    Build path-specific instructions.

    Args:
        path: Processing path

    Returns:
        Path instructions text
    """
    if path == "fast":
        return """
RESPONSE MODE: Quick text to a colleague
Keep it brief and warm. Like texting.
"""

    elif path == "standard":
        return """
RESPONSE MODE: Chatting with a trusted colleague
Share your view naturally. No need to be formal - just be direct and warm.
"""

    else:  # agentic
        return """
RESPONSE MODE: Thoughtful conversation
Talk through your thinking naturally - like you would over coffee.
It's okay to show some personality. "Honestly...", "My gut says...", "This reminds me of..."
"""
