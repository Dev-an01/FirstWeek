"""
Profile Management Module

Handles executive profile loading, caching, and system prompt generation.
Implements singleton pattern for efficient profile access.
"""

from .profile_loader import ProfileLoader
from .profile_manager import ProfileManager, get_profile_manager
from .prompt_generator import PromptGenerator
from .example_selector import ExampleSelector

__all__ = [
    'ProfileLoader',
    'ProfileManager',
    'get_profile_manager',
    'PromptGenerator',
    'ExampleSelector',
]
