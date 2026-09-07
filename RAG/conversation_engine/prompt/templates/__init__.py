"""
Prompt Templates Module.

Provides path-specific templates for prompt assembly:
- FastTemplate: ~350 tokens, minimal sections
- StandardTemplate: ~500 tokens, full sections
- AgenticTemplate: ~650 tokens, extended reasoning
"""

from .base_template import BaseTemplate
from .fast_template import FastTemplate
from .standard_template import StandardTemplate
from .agentic_template import AgenticTemplate

__all__ = [
    "BaseTemplate",
    "FastTemplate",
    "StandardTemplate",
    "AgenticTemplate",
]
