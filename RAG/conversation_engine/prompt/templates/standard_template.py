"""
Standard Template - Full-featured prompt template.

~500 tokens total with all sections conditionally included.
"""

from typing import List, Dict

from .base_template import BaseTemplate


class StandardTemplate(BaseTemplate):
    """
    Template for standard path (~500 tokens).

    Full sections for comprehensive responses:
    - Identity: Executive identity (50 tokens)
    - Conversation Context: Multi-turn context (60 tokens, if session)
    - Example: Communication example (150 tokens)
    - Calibration: Response style guidance (70 tokens)
    - Values: Executive values (50 tokens)
    - Precedent: Past decision case (60 tokens, if decision query)
    - Instructions: Critical instructions (60 tokens)

    Conditional sections:
    - conversation_context: Only if has_session=True
    - precedent: Only if has_precedent=True
    """

    @property
    def path(self) -> str:
        return "standard"

    @property
    def total_budget(self) -> int:
        return 500

    @property
    def section_order(self) -> List[str]:
        return [
            "identity",
            "conversation_context",
            "example",
            "calibration",
            "values",
            "precedent",
            "instructions",
        ]

    @property
    def section_budgets(self) -> Dict[str, int]:
        return {
            "identity": 50,
            "conversation_context": 60,
            "example": 150,
            "calibration": 70,
            "values": 50,
            "precedent": 60,
            "instructions": 60,
        }
