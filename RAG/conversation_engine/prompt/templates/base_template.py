"""
Base Template - Abstract base class for prompt templates.

Defines the interface and common functionality for all path templates.
"""

from abc import ABC, abstractmethod
from typing import List, Dict


class BaseTemplate(ABC):
    """
    Abstract base template for prompt assembly.

    Defines section ordering, budget allocation, and conditional
    section inclusion for each processing path.

    Subclasses implement:
    - path: Path identifier (fast/standard/agentic)
    - total_budget: Total token budget for system prompt
    - section_order: Ordered list of sections to include
    - BUDGETS: Dict of section -> token allocation
    """

    @property
    @abstractmethod
    def path(self) -> str:
        """Path identifier (fast/standard/agentic)."""
        pass

    @property
    @abstractmethod
    def total_budget(self) -> int:
        """Total token budget for system prompt."""
        pass

    @property
    @abstractmethod
    def section_order(self) -> List[str]:
        """
        Ordered list of section names to include.

        Sections are assembled in this order to create the final prompt.
        Conditional sections (conversation_context, precedent) are
        filtered out if not applicable.
        """
        pass

    @property
    @abstractmethod
    def section_budgets(self) -> Dict[str, int]:
        """Dict mapping section name to token budget."""
        pass

    def get_section_budget(self, section: str) -> int:
        """
        Get token budget for a section.

        Args:
            section: Section name (identity, example, etc.)

        Returns:
            Token budget for section, 0 if not found
        """
        return self.section_budgets.get(section, 0)

    def get_effective_sections(
        self,
        has_session: bool = False,
        has_precedent: bool = False,
    ) -> List[str]:
        """
        Get sections to include based on context.

        Filters out conditional sections that don't apply.

        Args:
            has_session: Include conversation_context section
            has_precedent: Include precedent section

        Returns:
            Filtered list of section names
        """
        sections = []

        for section in self.section_order:
            # Skip conversation_context if no session
            if section == "conversation_context" and not has_session:
                continue

            # Skip precedent if not applicable
            if section == "precedent" and not has_precedent:
                continue

            # Skip sections with 0 budget (path doesn't include them)
            if self.get_section_budget(section) == 0:
                continue

            sections.append(section)

        return sections

    def calculate_reallocation(
        self,
        has_session: bool,
        has_precedent: bool,
    ) -> int:
        """
        Calculate tokens to reallocate from unused sections.

        Args:
            has_session: Whether session context is included
            has_precedent: Whether precedent is included

        Returns:
            Total tokens available for reallocation
        """
        reallocate = 0

        if not has_session:
            reallocate += self.get_section_budget("conversation_context")

        if not has_precedent:
            reallocate += self.get_section_budget("precedent")

        return reallocate

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(path={self.path}, budget={self.total_budget})"
