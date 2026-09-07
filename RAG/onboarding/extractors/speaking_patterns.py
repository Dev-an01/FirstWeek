"""
Extractor 7: Speaking Patterns (Voiceprint)

Extracts voiceprint sections, speaking patterns, casual responses, lexicon.
Maps to full voiceprint JSON.
"""

from .base_extractor import BaseExtractor


class SpeakingPatternsExtractor(BaseExtractor):
    EXTRACTOR_NAME = "speaking_patterns"
    SYSTEM_PROMPT = """You are an expert executive communication analyst. Analyze documents and extract detailed speaking and communication patterns to create a "voiceprint" - a comprehensive model of how this executive speaks and writes.

Return a JSON object with this structure:
{
  "voiceprint": {
    "signature_opener": {
      "pattern": "e.g. acknowledge_then_guide",
      "approach": "Description of how they typically open responses"
    },
    "decision_cadence": {
      "pattern": "e.g. soft_assertion_with_explanation",
      "japanese_pattern": "Japanese pattern if applicable",
      "english_pattern": "English pattern if applicable"
    },
    "style_markers": {
      "emoji_usage": "none/minimal/moderate/heavy",
      "formality": 6,
      "directness": 8,
      "warmth": 7,
      "preferred_emojis": []
    },
    "transparency_phrases": {
      "approach": "How they express transparency"
    },
    "delegation_phrases": {
      "patterns_jp": ["Japanese delegation phrases"],
      "patterns_en": ["English delegation phrases"]
    },
    "speed_emphasis": {
      "patterns_jp": ["Japanese speed emphasis phrases"],
      "patterns_en": ["English speed emphasis phrases"]
    },
    "sign_off": {
      "formal": "Formal sign-off pattern",
      "informal": "Informal sign-off pattern"
    },
    "question_style": {
      "pattern": "How they ask questions",
      "examples": ["Example question patterns"]
    },
    "feedback_style": {
      "positive": "How they give positive feedback",
      "constructive": "How they give constructive feedback"
    },
    "emphasis_markers": {
      "strong_agreement": "How they strongly agree",
      "strong_disagreement": "How they strongly disagree",
      "urgency": "How they express urgency"
    },
    "context_setting": {
      "pattern": "How they set context before making points"
    },
    "data_reference_style": {
      "pattern": "How they reference data and evidence"
    },
    "bilingual_switching": {
      "trigger": "What triggers language switching",
      "pattern": "The switching pattern"
    }
  },
  "speaking_patterns_video": {
    "verbal_fillers": ["uh", "um", "well"],
    "intensifiers": ["really", "absolutely"],
    "hedging_phrases": ["I think", "maybe"],
    "sentence_endings": ["right", "you know"],
    "pace": "fast/medium/slow",
    "tone_shifts": {
      "when_excited": "",
      "when_serious": "",
      "when_uncertain": ""
    },
    "gesture_correlation": "Description of gesture patterns"
  },
  "casual_responses": {
    "greetings": ["Hello", "Hi"],
    "acknowledgments": ["Got it", "Understood"],
    "affirmations": ["Sounds good", "Let's do it"],
    "negations": ["I don't think so", "Not this time"],
    "gratitude": ["Thank you", "Thanks"],
    "apologies": ["Sorry about that"],
    "clarifications": ["Could you elaborate?"],
    "thinking_phrases": ["Let me think about this"],
    "closing_phrases": ["Let's wrap up"]
  },
  "lexicon": {
    "favorite_words": [],
    "avoided_words": [],
    "technical_terms_frequency": "low/medium/high",
    "jargon_level": "low/medium/high",
    "metaphor_usage": "Description of metaphor patterns"
  },
  "response_adaptation": {
    "formal_context": "How they adjust in formal settings",
    "informal_context": "How they adjust in casual settings",
    "crisis_context": "How they adjust in crisis situations",
    "mentoring_context": "How they adjust when mentoring"
  }
}

This is the most detailed extraction - capture every nuance of how this person communicates.
Always respond in the same language as the source documents.
Return ONLY valid JSON."""
