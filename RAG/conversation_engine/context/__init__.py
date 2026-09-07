"""
Context Management Module

Handles conversation mode detection, session state management,
and reference resolution for multi-turn conversations.
"""

# Core Models
from .models import (
    ConversationMode,
    ConversationState,
    ConversationTurn,
    ManagedContext,
)

# Context Management Components
from .context_manager import ContextManager, create_context_manager
from .session_store import SessionStore
from .reference_resolver import ReferenceResolver, get_reference_resolver

__all__ = [
    # Models
    "ConversationMode",
    "ConversationState",
    "ConversationTurn",
    "ManagedContext",
    # Components
    "ContextManager",
    "create_context_manager",
    "SessionStore",
    "ReferenceResolver",
    "get_reference_resolver",
]
