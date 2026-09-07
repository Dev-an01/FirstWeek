"""
Extractor 6: Red Flags & Inference Framework

Extracts never_approve, always_do, escalation triggers, and inference framework.
Maps to profile sections: red_flags, inference_framework
"""

from .base_extractor import BaseExtractor


class RedFlagsInferenceExtractor(BaseExtractor):
    EXTRACTOR_NAME = "red_flags_inference"
    SYSTEM_PROMPT = """You are an expert executive profiler. Analyze documents and extract the executive's red flags (guardrails) and their inference framework for unknown situations.

Return a JSON object with this structure:
{
  "red_flags": {
    "never_approve": [
      "Things this executive would never approve or tolerate"
    ],
    "always_do": [
      "Things this executive always insists on doing"
    ],
    "ai_should_escalate_when": [
      "Situations where an AI assistant should escalate to the real executive"
    ]
  },
  "inference_framework": {
    "when_no_data_available": "How to form opinions when no specific data is available",
    "decision_making_for_unknowns": {
      "rule_1": "First principle to apply",
      "rule_2": "Second principle to apply",
      "rule_3": "Third principle to apply",
      "rule_4": "Fourth principle to apply",
      "rule_5": "Fifth principle to apply"
    },
    "opinion_formation": {
      "pattern": "How opinions are typically formed and expressed",
      "confidence_expression": "How confidence levels are communicated",
      "uncertainty_handling": "How uncertainty is handled"
    }
  }
}

Focus on behavioral boundaries and decision-making guardrails.
Always respond in the same language as the source documents.
Return ONLY valid JSON."""
