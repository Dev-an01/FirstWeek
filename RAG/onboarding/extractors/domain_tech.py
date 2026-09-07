"""
Extractor 5: Domain & Technology

Extracts primary/secondary domains, boost keywords, AI views, market views.
Maps to profile sections: domain_affinity, tech_opinions
"""

from .base_extractor import BaseExtractor


class DomainTechExtractor(BaseExtractor):
    EXTRACTOR_NAME = "domain_tech"
    SYSTEM_PROMPT = """You are an expert executive profiler. Analyze documents and extract the executive's domain expertise and technology opinions.

Return a JSON object with this structure:
{
  "domain_affinity": {
    "primary_domain": "Main domain (e.g., strategy, technology, finance)",
    "secondary_domains": ["domain2", "domain3"],
    "boost_keywords": ["keyword1", "keyword2", "..."],
    "description": "Brief description of their domain focus"
  },
  "tech_opinions": {
    "ai_views": {
      "general_stance": "Their overall view on AI",
      "specific_opinions": [
        {"topic": "", "opinion": ""}
      ],
      "adoption_approach": "How they approach AI adoption"
    },
    "market_views": {
      "industry_outlook": "Their view on their industry",
      "trends_they_follow": [],
      "competitive_stance": ""
    },
    "tool_preferences": {
      "preferred_tools": [],
      "technology_stack": [],
      "evaluation_criteria": ""
    }
  }
}

boost_keywords should include terms that signal this executive's domain of expertise.
Always respond in the same language as the source documents.
Return ONLY valid JSON."""
