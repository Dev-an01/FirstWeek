"""
Agentic Template - Extended prompt template for thorough analysis.

~650 tokens total with larger budgets for reasoning support.
"""

from typing import List, Dict

from .base_template import BaseTemplate


class AgenticTemplate(BaseTemplate):
    """
    Template for agentic path (~650 tokens).

    Extended sections with reasoning support:
    - Identity: Executive identity (60 tokens)
    - Conversation Context: Multi-turn context (80 tokens, if session)
    - Example: Communication example (180 tokens)
    - Calibration: Response style guidance (80 tokens)
    - Values: Executive values (70 tokens)
    - Precedent: Past decision case (80 tokens, if decision query)
    - Instructions: Extended instructions (100 tokens)

    Larger instruction budget supports:
    - Multi-step reasoning
    - Trade-off analysis
    - Scenario exploration
    - Tool context (future)
    """

    @property
    def path(self) -> str:
        return "agentic"

    @property
    def total_budget(self) -> int:
        return 650

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
            "identity": 60,
            "conversation_context": 80,
            "example": 180,
            "calibration": 80,
            "values": 70,
            "precedent": 80,
            "instructions": 100,
        }
