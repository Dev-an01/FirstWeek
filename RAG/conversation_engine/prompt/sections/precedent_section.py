"""
Precedent Section Builder - Past decision case for decision queries.

Uses SelectedPrecedent from Phase 4.
Target: 60-80 tokens
Skip if: Not decision query or no relevant precedent
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..precedents.models import SelectedPrecedent

logger = logging.getLogger(__name__)


class PrecedentSection:
    """
    Builds precedent section for decision queries.

    Uses SelectedPrecedent from Phase 4.

    Output format:
        RELEVANT PAST DECISION:
        In DC_AKIKO_001, I approved 18% discount for MegaCorp with
        multi-year commitment because it protected relationship value.
        Outcome: Retained account, expanded next year.

    Provides the LLM with:
    - Past decision to reference
    - Reasoning pattern to follow
    - Outcome context

    Target: 60-80 tokens
    Skip if: Not decision query or no relevant precedent
    """

    def build(
        self,
        selected_precedent: "SelectedPrecedent",
        max_tokens: int = 60,
    ) -> str:
        """
        Build precedent section from Phase 4 output.

        Args:
            selected_precedent: From Phase 4 PrecedentSelector
            max_tokens: Maximum tokens for section

        Returns:
            Precedent section string, empty if skipped/irrelevant
        """
        # Skip if precedent was skipped (non-decision query)
        if selected_precedent.skipped:
            logger.debug(f"Skipping precedent section: {selected_precedent.skip_reason}")
            return ""

        # Skip if not relevant enough
        if not selected_precedent.is_relevant():
            logger.debug(
                f"Skipping precedent section: low relevance "
                f"({selected_precedent.relevance_score:.2f})"
            )
            return ""

        # Get prompt summary with token budget
        summary = selected_precedent.get_prompt_summary(max_tokens - 10)

        if not summary:
            return ""

        section = f"""
RELEVANT PAST DECISION:
{summary}
"""

        logger.debug(
            f"Built precedent section for {selected_precedent.case_id}: "
            f"{len(section)} chars"
        )

        return section
