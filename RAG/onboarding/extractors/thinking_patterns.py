"""
Extractor 2: Thinking Patterns

Extracts problem approach, frameworks, typical questions.
Maps to profile section: thinking_patterns
"""

from .base_extractor import BaseExtractor


class ThinkingPatternsExtractor(BaseExtractor):
    EXTRACTOR_NAME = "thinking_patterns"
    SYSTEM_PROMPT = """You are an expert executive profiler. Analyze documents about an executive and extract their thinking and decision-making patterns.

Return a JSON object with this structure:
{
  "thinking_patterns": {
    "problem_approach": "How they approach problems (one paragraph)",
    "framework_examples": ["framework1", "framework2", "..."],
    "typical_questions": [
      "Question they typically ask when evaluating something",
      "..."
    ],
    "thought_organization": "Step-by-step description of how they organize thoughts",
    "decision_approach": "Overall approach to making decisions"
  }
}

Focus on HOW the executive thinks, not WHAT they think about.
Look for patterns in their decision-making, analysis style, and problem-solving approach.
Always respond in the same language as the source documents.
Return ONLY valid JSON."""
