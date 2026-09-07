"""
Values Section Builder - Executive values for decision guidance.

Included for standard/agentic paths to guide decision-making.
Target: 50-70 tokens
Skip if: Fast path
"""

import logging
from typing import TYPE_CHECKING, Optional, List, Dict, Any

if TYPE_CHECKING:
    from profile_management.profile_manager import ExecutiveProfile
    from ..analysis.models import AnalyzedContext, Theme

logger = logging.getLogger(__name__)


class ValuesSection:
    """
    Builds executive values section.

    Included for standard/agentic paths to guide decision-making.

    Output format:
        MY VALUES (apply when relevant):
        • Customer Success First: Long-term value over short
        • Radical Transparency: Share context, even if hard

    Provides the LLM with:
    - Core executive values
    - Decision-making philosophy
    - Priority guidance

    Target: 50-70 tokens
    Skip if: Fast path (no values section in fast template)
    """

    # Theme to value relevance mapping
    THEME_VALUE_RELEVANCE = {
        "security": ["security", "trust", "compliance", "integrity"],
        "budget": ["efficiency", "roi", "investment", "cost"],
        "people": ["team", "growth", "development", "talent", "culture"],
        "strategy": ["vision", "innovation", "customer", "market"],
        "product": ["quality", "innovation", "customer", "user"],
        "customer": ["customer", "success", "relationship", "trust"],
    }

    def build(
        self,
        profile: "ExecutiveProfile",
        analyzed_context: "AnalyzedContext",
        max_tokens: int = 60,
    ) -> str:
        """
        Build values section from profile.

        Args:
            profile: Executive profile with values
            analyzed_context: From Phase 3 ContextAnalyzer
            max_tokens: Maximum tokens for section

        Returns:
            Values section string
        """
        if not profile:
            logger.warning("No profile provided to ValuesSection")
            return ""

        # Get values from profile
        values = self._get_values(profile)

        if not values:
            logger.debug("No values in profile, skipping values section")
            return ""

        # Select most relevant values based on theme
        theme_str = analyzed_context.theme.value if analyzed_context.theme else None
        selected_values = self._select_relevant_values(values, theme_str, max_count=2)

        if not selected_values:
            # Fallback to first 2 values
            selected_values = values[:2]

        # Build section
        value_bullets = []
        for v in selected_values:
            name = v.get("name", v.get("title", ""))
            # Support both 'summary' and 'description' fields
            summary = v.get("summary", "") or v.get("description", "")
            # Truncate description if too long (keep it concise)
            if summary and len(summary) > 100:
                summary = summary[:100].rsplit(" ", 1)[0] + "..."
            if name and summary:
                value_bullets.append(f"• {name}: {summary}")
            elif name:
                value_bullets.append(f"• {name}")

        if not value_bullets:
            return ""

        section = f"""
YOUR INTERNAL VALUES (embody these - NEVER state them in response):
{chr(10).join(value_bullets)}
(Let these guide your thinking, but express as natural opinions, not value statements)
"""

        # Add inference framework if available (for handling unknown topics)
        inference_section = self._build_inference_framework(profile, analyzed_context)
        if inference_section:
            section += inference_section

        logger.debug(f"Built values section: {len(section)} chars, {len(value_bullets)} values")
        return section

    def _get_values(self, profile: "ExecutiveProfile") -> List[Dict[str, Any]]:
        """Extract values from profile (handles dict or object)."""
        if isinstance(profile, dict):
            # Try both 'values' and 'core_values' (profile format uses core_values)
            values = profile.get("values", []) or profile.get("core_values", [])
        else:
            values = getattr(profile, "values", None) or getattr(profile, "core_values", [])

        # Normalize to list of dicts
        if not values:
            return []

        if isinstance(values, list):
            return values

        return []

    def _select_relevant_values(
        self,
        values: List[Dict[str, Any]],
        theme: Optional[str],
        max_count: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Select values most relevant to the current theme.

        Args:
            values: All executive values
            theme: Current query theme
            max_count: Maximum values to select

        Returns:
            List of most relevant values
        """
        if not theme or not values:
            return values[:max_count]

        # Get relevant keywords for theme
        relevant_keywords = self.THEME_VALUE_RELEVANCE.get(theme, [])
        if not relevant_keywords:
            return values[:max_count]

        # Score values by keyword overlap
        scored_values = []
        for v in values:
            name = v.get("name", "").lower()
            summary = v.get("summary", "").lower()
            text = f"{name} {summary}"

            # Count keyword matches
            score = sum(1 for kw in relevant_keywords if kw in text)
            scored_values.append((v, score))

        # Sort by score descending
        scored_values.sort(key=lambda x: x[1], reverse=True)

        # Return top values with positive scores, or first values if no matches
        top_values = [v for v, score in scored_values if score > 0][:max_count]

        if not top_values:
            return values[:max_count]

        return top_values

    def _build_inference_framework(
        self,
        profile: "ExecutiveProfile",
        analyzed_context: "AnalyzedContext",
    ) -> str:
        """
        Build inference framework section for handling unknown topics.

        This tells the LLM HOW to think like the executive when there's
        no specific data or precedent available.

        Args:
            profile: Executive profile with inference_framework
            analyzed_context: Context for conditional inclusion

        Returns:
            Inference framework section or empty string
        """
        if not profile:
            return ""

        # Get inference_framework from profile
        if isinstance(profile, dict):
            inference = profile.get("inference_framework", {})
        else:
            inference = getattr(profile, "inference_framework", {})

        if not inference:
            return ""

        section_parts = []
        section_parts.append("""
YOUR INTERNAL REASONING PROCESS (use silently - never explain this in response):""")

        # Add reasoning steps
        when_no_data = inference.get("when_no_data_available", {})
        if when_no_data:
            approach = when_no_data.get("approach", "")
            steps = when_no_data.get("steps", [])

            if approach:
                section_parts.append(f"Approach: {approach}")

            if steps:
                # P2 Fix: Include all 6 steps (was only 3)
                # Step 5 is critical: "Form an opinion using soft assertions"
                # Step 6 is critical: "Use voiceprint style"
                # Note: Values section only runs for standard/agentic paths
                for step in steps:
                    section_parts.append(f"  {step}")

        # Add decision biases
        decision_making = inference.get("decision_making_for_unknowns", {})
        if decision_making:
            section_parts.append("\nMY DEFAULT BIASES:")

            # Speed vs perfection
            speed = decision_making.get("speed_vs_perfection", {})
            if speed:
                bias = speed.get("bias", "")
                reasoning = speed.get("reasoning", "")
                if bias:
                    section_parts.append(f"  • Speed vs Perfection: {bias}")
                    if reasoning:
                        section_parts.append(f"    ({reasoning})")

            # Risk assessment
            risk = decision_making.get("risk_assessment", {})
            if risk:
                key_principle = risk.get("key_principle", "")
                if key_principle:
                    section_parts.append(f"  • Risk: {key_principle}")

            # Delegation
            delegation = decision_making.get("delegation_default", {})
            if delegation:
                bias = delegation.get("bias", "")
                if bias:
                    section_parts.append(f"  • Delegation: {bias}")

            # Focus
            focus = decision_making.get("focus", {})
            if focus:
                principle = focus.get("principle", "")
                if principle:
                    section_parts.append(f"  • Focus: {principle}")

        # Add opinion formation guidance
        opinion = inference.get("opinion_formation", {})
        if opinion:
            approach = opinion.get("approach", "")
            pattern_jp = opinion.get("pattern_jp", "")

            if approach:
                section_parts.append(f"\nForming opinions: {approach}")
            if pattern_jp:
                section_parts.append(f"  Pattern: {pattern_jp}")

        # Add response length guidance
        length = inference.get("response_length_guidance", {})
        if length:
            never = length.get("never", "")
            if never:
                section_parts.append(f"\nNEVER: {never}")

        if len(section_parts) > 1:  # More than just the header
            return "\n".join(section_parts)

        return ""
