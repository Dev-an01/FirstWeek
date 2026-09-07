"""
Synthesis LLM - Final pass for consistency checking and example generation.

Uses GROQ_SYNTHESIS_API_KEY (separate key to avoid rate limits).
Cross-checks all 7 extractions for consistency, generates communication examples.
"""

import json
import logging
import time
from typing import Dict, Any

from openai import OpenAI

from onboarding.config import (
    GROQ_BASE_URL,
    GROQ_MODEL,
    GROQ_SYNTHESIS_API_KEY,
    LLM_TEMPERATURE,
    LLM_RETRY_ATTEMPTS,
    LLM_RETRY_BASE_DELAY,
)

logger = logging.getLogger(__name__)

SYNTHESIS_SYSTEM_PROMPT = """You are an expert executive communication synthesizer. You will receive an assembled executive profile and voiceprint.

Your tasks:
1. Cross-check for internal consistency (flag contradictions).
2. Generate 5-10 communication_examples: realistic Q&A pairs showing how this executive would respond to typical business queries. Make them bilingual (Japanese + English) if the profile indicates bilingual communication.
3. Fill any gaps you notice by cross-referencing information across sections.

Return a JSON object with:
{
  "communication_examples": [
    {
      "query": "Example question/scenario",
      "response": "How the executive would respond",
      "context": "Brief context for this example",
      "language": "ja/en/bilingual"
    }
  ],
  "consistency_notes": [
    "Any inconsistencies found (or empty if none)"
  ],
  "gap_fills": {
    "section_name": {
      "field": "inferred_value"
    }
  }
}

Generate realistic, natural-sounding examples that capture the executive's voice.
Return ONLY valid JSON."""


def run_synthesis(
    profile: Dict[str, Any],
    voiceprint: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run the synthesis LLM to generate examples and check consistency.

    Args:
        profile: Assembled profile dict.
        voiceprint: Assembled voiceprint dict.

    Returns:
        Synthesis result with communication_examples, consistency_notes, gap_fills.
    """
    client = OpenAI(
        api_key=GROQ_SYNTHESIS_API_KEY,
        base_url=GROQ_BASE_URL,
    )

    user_prompt = (
        "Here is the assembled executive profile and voiceprint. "
        "Generate communication examples and check for consistency.\n\n"
        f"--- PROFILE ---\n{json.dumps(profile, ensure_ascii=False, indent=2)}\n\n"
        f"--- VOICEPRINT ---\n{json.dumps(voiceprint, ensure_ascii=False, indent=2)}\n"
    )

    # Truncate if too long for context window
    if len(user_prompt) > 60000:
        user_prompt = user_prompt[:60000] + "\n... [truncated]"

    last_error = None
    for attempt in range(1, LLM_RETRY_ATTEMPTS + 1):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=LLM_TEMPERATURE,
                max_tokens=8000,
                response_format={"type": "json_object"},
            )
            raw = response.choices[0].message.content
            result = json.loads(raw)
            logger.info(f"Synthesis LLM succeeded (attempt {attempt})")
            return result

        except Exception as e:
            logger.warning(f"Synthesis LLM failed (attempt {attempt}): {e}")
            last_error = e
            if attempt < LLM_RETRY_ATTEMPTS:
                delay = LLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                time.sleep(delay)

    logger.error(f"Synthesis LLM failed after {LLM_RETRY_ATTEMPTS} attempts")
    return {
        "communication_examples": [],
        "consistency_notes": [f"Synthesis failed: {last_error}"],
        "gap_fills": {},
    }


def apply_synthesis(
    profile: Dict[str, Any],
    voiceprint: Dict[str, Any],
    synthesis_result: Dict[str, Any],
) -> tuple:
    """
    Apply synthesis results back to profile and voiceprint.

    Returns:
        (updated_profile, updated_voiceprint)
    """
    # Add communication examples to profile
    examples = synthesis_result.get("communication_examples", [])
    if examples:
        profile["communication_examples"] = examples
        logger.info(f"Added {len(examples)} communication examples to profile")

    # Apply gap fills
    gap_fills = synthesis_result.get("gap_fills", {})
    for section, fills in gap_fills.items():
        if section in profile and isinstance(profile[section], dict) and isinstance(fills, dict):
            for key, value in fills.items():
                if key not in profile[section] or not profile[section][key]:
                    profile[section][key] = value
                    logger.debug(f"Filled gap: {section}.{key}")

    # Store consistency notes in metadata
    notes = synthesis_result.get("consistency_notes", [])
    if notes:
        profile.setdefault("metadata", {})["consistency_notes"] = notes

    return profile, voiceprint
