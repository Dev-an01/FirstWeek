"""
State Management Module for the Conversation Engine.

Provides post-response state updates for multi-turn conversations.

Components:
- StateUpdater: Updates session state after LLM response
- StateUpdateResult: Result of state update operation
"""

from .updater import (
    StateUpdater,
    StateUpdateResult,
    get_state_updater,
    create_state_updater,
)

__all__ = [
    "StateUpdater",
    "StateUpdateResult",
    "get_state_updater",
    "create_state_updater",
]
