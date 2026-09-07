"""
Extractor 3: Communication Style

Extracts tone, scales (1-10), languages, core principles, response patterns.
Maps to profile section: communication_style
"""

from .base_extractor import BaseExtractor


class CommunicationStyleExtractor(BaseExtractor):
    EXTRACTOR_NAME = "communication_style"
    SYSTEM_PROMPT = """You are an expert executive profiler. Analyze documents and extract the executive's communication style.

Return a JSON object with this structure:
{
  "communication_style": {
    "overall_tone": "Brief description of their communication tone",
    "formality_scale": 6,
    "directness_scale": 8,
    "warmth_scale": 7,
    "languages_used": ["Japanese", "English"],
    "code_switching_pattern": "How they switch between languages",
    "core_principles": {
      "soft_assertions": "How they soften statements",
      "context_before_direction": "How they provide context before giving direction",
      "transparency_emphasis": "How they emphasize transparency"
    },
    "response_patterns": {
      "when_agreeing": "Pattern when they agree",
      "when_disagreeing": "Pattern when they disagree",
      "when_delegating": "Pattern when delegating",
      "when_escalating": "Pattern when escalating"
    }
  }
}

Scales are 1-10 integers:
- formality_scale: 1=very casual, 10=very formal
- directness_scale: 1=very indirect, 10=very direct
- warmth_scale: 1=cold/distant, 10=warm/friendly

Infer from the tone, word choice, and communication patterns in the documents.
Always respond in the same language as the source documents.
Return ONLY valid JSON."""
