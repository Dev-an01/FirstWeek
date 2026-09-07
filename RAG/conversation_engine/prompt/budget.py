"""
Token Budget Manager - Phase 5 Component.

Manages token allocation across prompt sections with dynamic reallocation.
Target latency: ~0.1ms (simple calculations).
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenBudget:
    """
    Token allocation for a single prompt build.

    Contains budget allocations for each section and tracks
    remaining/unused tokens for reallocation.
    """

    total: int
    identity: int
    conversation_context: int
    example: int
    calibration: int
    values: int
    precedent: int
    instructions: int
    remaining: int = 0

    # Track what was actually used for logging
    used: Dict[str, int] = field(default_factory=dict)

    def get_section_budget(self, section_name: str) -> int:
        """Get budget for a specific section."""
        budgets = {
            "identity": self.identity,
            "conversation_context": self.conversation_context,
            "example": self.example,
            "calibration": self.calibration,
            "values": self.values,
            "precedent": self.precedent,
            "instructions": self.instructions,
        }
        return budgets.get(section_name, 0)

    def record_usage(self, section_name: str, tokens_used: int) -> None:
        """Record actual token usage for a section."""
        self.used[section_name] = tokens_used

    def get_total_used(self) -> int:
        """Get total tokens used across all sections."""
        return sum(self.used.values())

    def get_unused(self) -> int:
        """Get unused tokens (total - used)."""
        return self.total - self.get_total_used()


class TokenBudgetManager:
    """
    Manages token budgets for prompt assembly.

    Features:
    - Path-specific base budgets (fast: 350, standard: 500, agentic: 650)
    - Dynamic reallocation for unused sections
    - Token counting (~4 chars per token approximation)
    - Budget validation

    Thread-safe: Stateless operations.
    """

    # Approximation: ~4 characters per token for English text
    CHAR_PER_TOKEN = 4

    # Total token budgets by path
    # NOTE: Increased totals to accommodate larger identity section for personality data
    # Identity section contains voiceprint, communication examples, and thinking patterns
    # which require significantly more tokens than originally allocated
    PATH_BUDGETS = {
        "fast": 450,      # Was 350 - increased by 100 for personality
        "standard": 620,  # Was 500 - increased by 120 for personality
        "agentic": 780,   # Was 650 - increased by 130 for personality
    }

    # Base section budgets by path
    # Note: conversation_context and precedent are conditional
    # CRITICAL: Identity section needs 150-200 tokens to include:
    #   - Executive name/title/company (~20 tokens)
    #   - Voiceprint patterns: openers, sign-offs, key phrases (~50 tokens)
    #   - Communication examples from profile (~60 tokens)
    #   - Thinking patterns and soft assertions (~40 tokens)
    #   - Style markers and anti-AI rules (~30 tokens)
    SECTION_BUDGETS = {
        "fast": {
            "identity": 150,  # Was 40 - increased to fit personality data
            "conversation_context": 0,  # Not included in fast
            "example": 100,   # Was 160 - reduced since identity has examples
            "calibration": 50,
            "values": 0,  # Not included in fast
            "precedent": 0,  # Not included in fast
            "instructions": 50,
        },
        "standard": {
            "identity": 180,  # Was 50 - increased to fit personality data
            "conversation_context": 60,  # Conditional
            "example": 100,   # Was 150 - reduced since identity has examples
            "calibration": 70,
            "values": 70,     # Was 50 - increased for inference framework
            "precedent": 60,  # Conditional
            "instructions": 60,
        },
        "agentic": {
            "identity": 200,  # Was 60 - increased to fit personality data
            "conversation_context": 80,  # Conditional
            "example": 120,   # Was 180 - reduced since identity has examples
            "calibration": 80,
            "values": 100,    # Was 70 - increased for full inference framework
            "precedent": 80,  # Conditional
            "instructions": 100,
        },
    }

    def create_budget(
        self,
        path: str,
        has_session: bool = False,
        has_precedent: bool = False,
    ) -> TokenBudget:
        """
        Create token budget with dynamic allocation.

        Args:
            path: Processing path (fast/standard/agentic)
            has_session: Include conversation context section
            has_precedent: Include precedent section

        Returns:
            TokenBudget with allocated tokens per section
        """
        # Get base budgets for path (default to standard)
        base_budgets = self.SECTION_BUDGETS.get(path, self.SECTION_BUDGETS["standard"])
        total = self.PATH_BUDGETS.get(path, self.PATH_BUDGETS["standard"])

        # Start with base allocations
        budgets = dict(base_budgets)

        # Calculate reallocation from unused sections
        reallocate = 0

        # No session → reallocate conversation_context to example
        if not has_session and budgets["conversation_context"] > 0:
            reallocate += budgets["conversation_context"]
            budgets["conversation_context"] = 0

        # No precedent → reallocate precedent budget to example
        if not has_precedent and budgets["precedent"] > 0:
            reallocate += budgets["precedent"]
            budgets["precedent"] = 0

        # Reallocate to example section (primary beneficiary)
        budgets["example"] += reallocate

        # Calculate remaining buffer
        allocated = sum(budgets.values())
        remaining = max(0, total - allocated)

        budget = TokenBudget(
            total=total,
            identity=budgets["identity"],
            conversation_context=budgets["conversation_context"],
            example=budgets["example"],
            calibration=budgets["calibration"],
            values=budgets["values"],
            precedent=budgets["precedent"],
            instructions=budgets["instructions"],
            remaining=remaining,
        )

        logger.debug(
            f"Created budget for path={path} "
            f"(session={has_session}, precedent={has_precedent}): "
            f"total={total}, example={budgets['example']}"
        )

        return budget

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses character-based approximation (~4 chars per token).
        This is fast but approximate - suitable for budgeting.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return len(text) // self.CHAR_PER_TOKEN

    def truncate_to_budget(
        self,
        text: str,
        max_tokens: int,
        preserve_lines: bool = True,
    ) -> str:
        """
        Truncate text to fit within token budget.

        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            preserve_lines: If True, truncate at line boundary

        Returns:
            Truncated text (with ... if truncated)
        """
        if not text:
            return ""

        max_chars = max_tokens * self.CHAR_PER_TOKEN

        if len(text) <= max_chars:
            return text

        # Truncate to max chars
        truncated = text[:max_chars]

        if preserve_lines:
            # Find last complete line
            last_newline = truncated.rfind('\n')
            if last_newline > max_chars // 2:  # Don't truncate too much
                truncated = truncated[:last_newline]

        # Add ellipsis to indicate truncation
        return truncated.rstrip() + "..."

    def truncate_words(
        self,
        text: str,
        max_words: int,
    ) -> str:
        """
        Truncate text to fit within word budget.

        Args:
            text: Text to truncate
            max_words: Maximum words allowed

        Returns:
            Truncated text
        """
        if not text:
            return ""

        words = text.split()

        if len(words) <= max_words:
            return text

        return " ".join(words[:max_words]) + "..."

    def validate_budget(
        self,
        text: str,
        budget: TokenBudget,
        tolerance: float = 0.10,
    ) -> bool:
        """
        Validate that text fits within budget.

        Args:
            text: Text to validate
            budget: TokenBudget to check against
            tolerance: Allowed overflow percentage (default 10%)

        Returns:
            True if within budget (with tolerance)
        """
        token_count = self.count_tokens(text)
        max_allowed = int(budget.total * (1 + tolerance))

        if token_count > max_allowed:
            logger.warning(
                f"Budget exceeded: {token_count} tokens "
                f"(max: {budget.total}, tolerance: {max_allowed})"
            )
            return False

        return True


# Singleton instance
_default_manager: Optional[TokenBudgetManager] = None


def get_budget_manager() -> TokenBudgetManager:
    """Get singleton TokenBudgetManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = TokenBudgetManager()
    return _default_manager


def create_budget_manager() -> TokenBudgetManager:
    """Create a new TokenBudgetManager instance."""
    return TokenBudgetManager()
