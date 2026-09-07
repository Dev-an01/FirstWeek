"""
Extractor 1: Background & Identity

Extracts education, roles, expertise, company info, leadership team.
Maps to profile section: background
"""

from .base_extractor import BaseExtractor


class BackgroundIdentityExtractor(BaseExtractor):
    EXTRACTOR_NAME = "background_identity"
    SYSTEM_PROMPT = """You are an expert executive profiler. Extract background and identity information from documents about an executive.

Return a JSON object with this structure:
{
  "background": {
    "education": [{"institution": "", "degree": "", "field": "", "year": ""}],
    "career_history": [{"company": "", "role": "", "period": "", "achievements": []}],
    "areas_of_expertise": [],
    "languages": [{"language": "", "proficiency": ""}],
    "certifications": [],
    "notable_achievements": []
  },
  "company_info": {
    "name": "",
    "industry": "",
    "size": "",
    "founded": "",
    "mission": "",
    "key_products_services": []
  },
  "leadership_team": [
    {"name": "", "title": "", "relationship": ""}
  ]
}

Extract as much as you can from the documents. If information is not available, use empty strings or empty arrays.
Always respond in the same language as the source documents (Japanese if Japanese, English if English).
Return ONLY valid JSON."""
