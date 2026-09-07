"""
Validation module for post-generation authenticity checking.

AuthenticityChecker validates AI responses to ensure:
1. Voiceprint elements are present (lexicon, signature)
2. No forbidden AI patterns ("I'd be happy to", numbered lists)
3. Correct emotional tone matches context
4. Auto-fix minor issues when possible
"""

from .authenticity_checker import AuthenticityChecker, ValidationResult

__all__ = ["AuthenticityChecker", "ValidationResult"]
