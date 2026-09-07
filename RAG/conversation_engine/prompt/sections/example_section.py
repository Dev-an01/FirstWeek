"""
Example Section Builder - Communication example for style guidance.

Uses SelectedExample from Phase 4 to show tone/style.
Target: 120-180 tokens
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..examples.models import SelectedExample

logger = logging.getLogger(__name__)


class ExampleSection:
    """
    Builds the communication example section.

    Uses SelectedExample from Phase 4 to show tone/style.

    Output format:
        ═══════════════════════════════════════════════════════
        MATCH THIS EXAMPLE (tone, structure, warmth):
        ═══════════════════════════════════════════════════════

        @kenji-product Re: the feature deprecation decision

        I can feel your stress about this. Deprecating features
        is hard, especially when some customers still use them.
        ...
        Want to talk it through live? I've got 30 min.
        - A
        ═══════════════════════════════════════════════════════

    Provides the LLM with:
    - Concrete example of executive's communication style
    - Tone and structure to emulate
    - Length and format reference

    Target: 120-180 tokens
    """

    # Section delimiter
    DELIMITER = "═══════════════════════════════════════════════════════"

    def build(
        self,
        selected_example: "SelectedExample",
        max_tokens: int = 150,
    ) -> str:
        """
        Build example section from Phase 4 output.

        Args:
            selected_example: From Phase 4 SemanticExampleSelector
            max_tokens: Maximum tokens for section

        Returns:
            Example section string
        """
        if selected_example.is_fallback:
            return self._build_fallback_guidance()

        # Get truncated example to fit budget (account for header/footer)
        example_text = selected_example.get_truncated_example(max_tokens - 30)

        if not example_text:
            return self._build_fallback_guidance()

        # Build section with context
        section = f"""
{self.DELIMITER}
MATCH THIS EXAMPLE (tone, structure, warmth):
{self.DELIMITER}

{example_text}
{self.DELIMITER}
"""

        logger.debug(
            f"Built example section from {selected_example.example_id}: "
            f"{len(section)} chars"
        )

        return section

    def _build_fallback_guidance(self) -> str:
        """
        Build generic guidance when no example matches.

        Used when SelectedExample.is_fallback is True.
        """
        section = f"""
{self.DELIMITER}
COMMUNICATION STYLE:
Respond in a natural, professional tone appropriate to the situation.
Be direct but warm. Use conversational language, not formal business speak.
{self.DELIMITER}
"""
        logger.debug("Built fallback example section (no matching example)")
        return section
