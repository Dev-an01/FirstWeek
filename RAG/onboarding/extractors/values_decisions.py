"""
Extractor 4: Values & Decision-Making

Extracts core values, decision-making trade-offs (15 scales), and decision cases.
Maps to profile sections: core_values, decision_making, decision_cases
"""

from .base_extractor import BaseExtractor


class ValuesDecisionsExtractor(BaseExtractor):
    EXTRACTOR_NAME = "values_decisions"
    SYSTEM_PROMPT = """You are an expert executive profiler. Analyze documents and extract the executive's core values, decision-making framework, and past decision cases.

Return a JSON object with this structure:
{
  "core_values": [
    {
      "name": "Value name (with priority number)",
      "priority": 1,
      "behavior": "How this value manifests in behavior"
    }
  ],
  "decision_making": {
    "philosophy": "Overall decision-making philosophy",
    "risk_tolerance": "Description with scale (e.g. High 8/10)",
    "value_trade_offs": {
      "quality_vs_speed": {"score": 10, "favors": "speed", "description": ""},
      "consensus_vs_authority": {"score": 5, "favors": "balanced", "description": ""},
      "innovation_vs_stability": {"score": 7, "favors": "innovation", "description": ""},
      "detail_vs_big_picture": {"score": 4, "favors": "big_picture", "description": ""},
      "short_term_vs_long_term": {"score": 6, "favors": "balanced", "description": ""},
      "cost_vs_value": {"score": 7, "favors": "value", "description": ""},
      "process_vs_outcome": {"score": 8, "favors": "outcome", "description": ""},
      "transparency_vs_discretion": {"score": 9, "favors": "transparency", "description": ""},
      "delegation_vs_hands_on": {"score": 2, "favors": "delegation", "description": ""},
      "data_vs_intuition": {"score": 6, "favors": "balanced", "description": ""},
      "growth_vs_profitability": {"score": 7, "favors": "growth", "description": ""},
      "internal_vs_external_focus": {"score": 5, "favors": "balanced", "description": ""},
      "formal_vs_informal": {"score": 4, "favors": "informal", "description": ""},
      "planned_vs_adaptive": {"score": 7, "favors": "adaptive", "description": ""},
      "individual_vs_team": {"score": 3, "favors": "team", "description": ""}
    }
  },
  "decision_cases": [
    {
      "title": "Decision title",
      "date": "YYYY-MM-DD or approximate",
      "category": "Category (hiring, strategy, product, etc.)",
      "situation": "What was the situation",
      "decision_made": "What was decided",
      "rationale": "Why this decision was made",
      "outcome": "What happened as a result",
      "lessons_learned": "Key takeaways"
    }
  ]
}

Trade-off scores: 1-10 scale where 1 = strongly favors the first option, 10 = strongly favors the second option.
Extract at least 5 core values ordered by priority.
Extract as many decision cases as available (aim for 5-15).
Always respond in the same language as the source documents.
Return ONLY valid JSON."""
