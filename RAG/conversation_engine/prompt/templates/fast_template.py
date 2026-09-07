"""
Fast Template - Minimal prompt template for quick responses.

~350 tokens total with focus on essential sections only.
Skips: Values, Precedent, Conversation Context.
"""

from typing import List, Dict

from .base_template import BaseTemplate


class FastTemplate(BaseTemplate):
    """
    Template for fast path (~350 tokens).

    Minimal sections for quick, direct responses:
    - Identity: Executive identity (40 tokens)
    - Example: Communication example (160 tokens, larger allocation)
    - Calibration: Response style guidance (50 tokens)
    - Instructions: Critical instructions (50 tokens)

    Skips: Values, Precedent, Conversation Context
    """

    @property
    def path(self) -> str:
        return "fast"

    @property
    def total_budget(self) -> int:
        return 350

    @property
    def section_order(self) -> List[str]:
        return [
            "identity",
            "example",
            "calibration",
            "instructions",
        ]

    @property
    def section_budgets(self) -> Dict[str, int]:
        return {
            "identity": 40,
            "conversation_context": 0,  # Not included
            "example": 160,  # Larger since no values/precedent
            "calibration": 50,
            "values": 0,  # Not included
            "precedent": 0,  # Not included
            "instructions": 50,
        }
