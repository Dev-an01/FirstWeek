"""
Section Builders Module.

Provides builders for each prompt section:
- ReasoningSection: Cognitive scaffolding (System 2 thinking) - MUST be first
- IdentitySection: Executive identity
- ConversationContextSection: Multi-turn session context
- ExampleSection: Communication style example
- CalibrationSection: Response tone/style guidance
- ValuesSection: Executive values
- PrecedentSection: Past decision cases
- RetrievedContextSection: Vector/graph search results
- InstructionsSection: Critical response instructions
- SpeakingStyleSection: Natural speech patterns for audio/video mode
"""

from .reasoning_section import ReasoningSection
from .identity_section import IdentitySection
from .conversation_context_section import ConversationContextSection
from .example_section import ExampleSection
from .calibration_section import CalibrationSection
from .values_section import ValuesSection
from .precedent_section import PrecedentSection
from .retrieved_context_section import RetrievedContextSection
from .instructions_section import InstructionsSection
from .speaking_style_section import SpeakingStyleSection

__all__ = [
    "ReasoningSection",
    "IdentitySection",
    "ConversationContextSection",
    "ExampleSection",
    "CalibrationSection",
    "ValuesSection",
    "PrecedentSection",
    "RetrievedContextSection",
    "InstructionsSection",
    "SpeakingStyleSection",
]
