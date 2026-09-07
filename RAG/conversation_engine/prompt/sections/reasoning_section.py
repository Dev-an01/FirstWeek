"""
Reasoning Section - "The Cognitive Script"

Extracts and injects the executive's mental algorithm as a mandatory
System 2 thinking step before response generation.

This forces the LLM to "think" before it "speaks", solving the "Uncanny Valley"
problem where it mimics surface phrases but misses the underlying logic.

The cognitive script is dynamically built from:
- thinking_patterns.typical_questions → Internal questions to ask
- red_flags.never_approve → Hard stops that must trigger rejection
- decision_making.value_trade_offs → Weighted biases for conflicts
- inference_framework.delegation_default → Delegation rules
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ReasoningSection:
    """
    Builds the "Cognitive Scaffolding" section of the system prompt.

    This section is placed BEFORE Identity/Style instructions to establish
    the "Mental Operating System" first. The LLM reads:

    1. HOW TO THINK (ReasoningSection) ← This section
    2. WHO I AM (IdentitySection)
    3. WHAT TO SAY (Other sections)
    """

    def build(
        self,
        profile: Optional[Dict[str, Any]],
        max_tokens: int = 500,
        path: str = "standard",
        language: str = "en",
    ) -> str:
        """
        Build the reasoning section based on profile data.

        Args:
            profile: Executive profile dictionary
            max_tokens: Approximate token budget (not strictly enforced)
            path: Processing path (fast/standard/agentic)
            language: Response language (en/ja) - affects question display

        Returns:
            Formatted reasoning instructions string, or empty for conversational
        """
        # Skip cognitive scaffolding for conversational path (greetings, etc.)
        # These don't need deep reasoning - just respond naturally
        if path == "conversational":
            logger.debug("ReasoningSection: Skipping for conversational path")
            return ""

        # Handle missing profile gracefully
        if not profile:
            logger.warning("ReasoningSection: No profile provided, using defaults")
            return self._build_default_script()

        # Extract reasoning components from profile
        thinking = profile.get("thinking_patterns", {})
        red_flags = profile.get("red_flags", {})
        decision_making = profile.get("decision_making", {})
        inference = profile.get("inference_framework", {})

        # ═══════════════════════════════════════════
        # STEP 1: Data Check Questions
        # ═══════════════════════════════════════════
        questions = thinking.get("typical_questions", [])
        if questions:
            # Take first 4 questions - these are the internal prompts
            questions_text = "\n".join(f"  - {q}" for q in questions[:4])
        else:
            questions_text = "  - What are the facts?\n  - What does the data show?"

        # ═══════════════════════════════════════════
        # STEP 2: Red Flag Extraction
        # ═══════════════════════════════════════════
        never_approve = red_flags.get("never_approve", [])
        if never_approve:
            red_flags_text = "\n".join(f"  ✗ {flag}" for flag in never_approve[:5])
        else:
            red_flags_text = "  ✗ Compliance violations\n  ✗ Uncontrollable risks"

        # ═══════════════════════════════════════════
        # STEP 3: Delegation Logic
        # ═══════════════════════════════════════════
        value_trade_offs = decision_making.get("value_trade_offs", {})
        delegation_info = value_trade_offs.get("delegation_vs_hands_on", {})
        delegation_score = delegation_info.get("score", 5)
        delegation_bias = delegation_info.get("leans", "")

        # Also check inference_framework for CEO-only decisions
        delegation_default = inference.get("decision_making_for_unknowns", {}).get("delegation_default", {})
        ceo_only = delegation_default.get("only_ceo_decides", [])

        if delegation_score <= 2 or "maximum" in str(delegation_bias).lower():
            ceo_only_text = ", ".join(ceo_only[:3]) if ceo_only else "M&A, Compliance, Core strategy"
            delegation_text = f"""  BIAS: MAXIMUM DELEGATION ({delegation_score}/10 hands-on)
  → Delegate everything possible
  → Only YOU decide: {ceo_only_text}"""
        else:
            delegation_text = "  → Balance delegation with hands-on based on context"

        # ═══════════════════════════════════════════
        # STEP 4: Value Trade-offs (Strongest Biases)
        # ═══════════════════════════════════════════
        trade_offs = []
        for key, data in value_trade_offs.items():
            if key == "delegation_vs_hands_on":
                continue  # Already handled above
            score = data.get("score", 5)
            lean = data.get("leans", "")
            # Only include extreme biases (1-2 or 9-10)
            if score >= 9:
                clean_key = key.replace("_vs_", " vs ").replace("_", " ")
                trade_offs.append(f"  → {clean_key}: BIAS {lean.upper()} ({score}/10)")
            elif score <= 2:
                clean_key = key.replace("_vs_", " vs ").replace("_", " ")
                trade_offs.append(f"  → {clean_key}: BIAS {lean.upper()} ({10-score}/10)")

        if trade_offs:
            trade_offs_text = "\n".join(trade_offs[:4])
        else:
            trade_offs_text = "  → Balance competing priorities based on context"

        # ═══════════════════════════════════════════
        # STEP 5: Expression Pattern (from voiceprint)
        # ═══════════════════════════════════════════
        voiceprint = profile.get("voiceprint", {})
        decision_cadence = voiceprint.get("decision_cadence", {})

        if language == "ja":
            soft_pattern = decision_cadence.get("japanese_pattern", "〜と思います")
        else:
            soft_pattern = decision_cadence.get("english_pattern", "I think... / In my view...")

        # ═══════════════════════════════════════════
        # BUILD THE COGNITIVE SCRIPT
        # ═══════════════════════════════════════════
        script = f"""
═══════════════════════════════════════════════════════════════════════════════
                  MANDATORY COGNITIVE PROCESS (System 2 Reasoning)
═══════════════════════════════════════════════════════════════════════════════

Before generating your response, internally execute this reasoning loop.
Do NOT output this process - let it silently shape your answer.

STEP 1: DATA CHECK
  Ask yourself these questions:
{questions_text}
  → If data is missing, your instinct is to ASK before deciding.

STEP 2: RED FLAG SCAN (Hard Stops)
  Check for these fatal conditions:
{red_flags_text}
  → If ANY flag triggers: STOP. Express concern immediately. Do not proceed.

STEP 3: DELEGATION FILTER
{delegation_text}
  → Ask: "Must I personally decide this, or can someone else?"

STEP 4: VALUE WEIGHTING
  When conflicts arise, apply these biases:
{trade_offs_text}

STEP 5: FORM & EXPRESS
  → Arrive at a clear decision/opinion from the above steps
  → Use soft assertion pattern: "{soft_pattern}"
  → Drop AI preambles: No "Let me share...", No "I'd be happy to..."
  → Natural flow - provide direction with brief context, not numbered lists

═══════════════════════════════════════════════════════════════════════════════
"""
        logger.debug(f"ReasoningSection: Built cognitive script ({len(script)} chars)")
        return script

    def _build_default_script(self) -> str:
        """Build a minimal default script when no profile is available."""
        return """
═══════════════════════════════════════════════════════════════════════════════
                  MANDATORY COGNITIVE PROCESS
═══════════════════════════════════════════════════════════════════════════════

Before responding, internally process:
1. What are the facts? Is data missing?
2. Are there compliance or ethical concerns?
3. Can this be delegated?
4. What's the direct answer?

Then respond with a clear, direct conclusion. No AI preambles.
═══════════════════════════════════════════════════════════════════════════════
"""
