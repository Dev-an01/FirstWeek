"""
Voiceprint Assembler - Takes extractor #7 output and produces voiceprint JSON.

Structure matches sample_profile_voiceprint.json (5 major sections).
"""

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def assemble_voiceprint(
    executive_id: str,
    extractions: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Assemble a voiceprint from the speaking_patterns extraction result.

    Args:
        executive_id: Executive ID (slug).
        extractions: Dict of extractor_name -> extraction result.

    Returns:
        Voiceprint JSON matching the reference structure.
    """
    sp = extractions.get("speaking_patterns", {})

    voiceprint = {
        "executive_id": executive_id,

        # 14 subsections
        "voiceprint": sp.get("voiceprint", {}),

        # 7 speaking pattern categories
        "speaking_patterns_video": sp.get("speaking_patterns_video", {}),

        # 9 casual response categories
        "casual_responses": sp.get("casual_responses", {}),

        # Lexicon
        "lexicon": sp.get("lexicon", {}),

        # Response adaptation
        "response_adaptation": sp.get("response_adaptation", {}),

        # Metadata
        "metadata": {
            "generated_by": "onboarding_service",
            "version": "1.0",
        },
    }

    logger.info(f"Voiceprint assembled for {executive_id}")
    return voiceprint
