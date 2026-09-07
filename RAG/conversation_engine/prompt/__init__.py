"""
Prompt Assembly Module for the Conversation Engine.

Provides token budget management, templates, section builders,
and the main PromptAssembler for building final prompts.

Components:
- TokenBudgetManager: Manages token allocation across sections
- Templates: Path-specific prompt templates (Fast, Standard, Agentic)
- Section Builders: Build individual prompt sections
- PromptAssembler: Main orchestrator for prompt assembly
"""

# Budget management
from .budget import (
    TokenBudget,
    TokenBudgetManager,
    get_budget_manager,
    create_budget_manager,
)

# Templates
from .templates import (
    BaseTemplate,
    FastTemplate,
    StandardTemplate,
    AgenticTemplate,
)

# Section builders
from .sections import (
    IdentitySection,
    ConversationContextSection,
    ExampleSection,
    CalibrationSection,
    ValuesSection,
    PrecedentSection,
    RetrievedContextSection,
    InstructionsSection,
)

# Main assembler
from .assembler import (
    PromptAssembler,
    get_prompt_assembler,
    create_prompt_assembler,
)

__all__ = [
    # Budget management
    "TokenBudget",
    "TokenBudgetManager",
    "get_budget_manager",
    "create_budget_manager",
    # Templates
    "BaseTemplate",
    "FastTemplate",
    "StandardTemplate",
    "AgenticTemplate",
    # Section builders
    "IdentitySection",
    "ConversationContextSection",
    "ExampleSection",
    "CalibrationSection",
    "ValuesSection",
    "PrecedentSection",
    "RetrievedContextSection",
    "InstructionsSection",
    # Main assembler
    "PromptAssembler",
    "get_prompt_assembler",
    "create_prompt_assembler",
]
