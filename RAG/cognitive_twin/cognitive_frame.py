"""
Cognitive Frame - Layer 2 of the Cognitive Twin system.

Makes executives THINK differently by injecting their reasoning frameworks,
typical questions, and decision patterns into the response generation.

Key principle: Different executives approach problems differently.
A CFO thinks in financial models, a CTO thinks in technical architectures,
a CEO thinks in strategic frameworks.

All reasoning data comes from the database (thinking_patterns, red_flags,
decision_cases), NOT from hardcoded templates.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import numpy as np

from .config import is_layer_enabled, get_layer_config
from .profile_loader import (
    get_cognitive_profile_loader,
    ThinkingPatterns,
    RedFlags,
    DecisionCase,
)

logger = logging.getLogger(__name__)


@dataclass
class ReasoningFramework:
    """Executive's reasoning framework assembled from profile data."""
    framework_examples: List[str] = field(default_factory=list)
    typical_questions: List[str] = field(default_factory=list)
    thought_organization: str = ""
    decision_approach: str = ""

    # Guardrails
    never_approve: List[str] = field(default_factory=list)
    always_do: List[str] = field(default_factory=list)
    escalation_triggers: List[str] = field(default_factory=list)

    # Similar decision cases (for case-based reasoning)
    similar_cases: List[DecisionCase] = field(default_factory=list)


@dataclass
class CognitiveFrameResult:
    """Result of building cognitive frame for a query."""
    framework: ReasoningFramework
    prompt_section: str
    cases_matched: int
    reasoning: str


class CognitiveFrameBuilder:
    """
    Builds cognitive reasoning frames from executive profile data.

    Dynamically extracts thinking patterns, red flags, and decision cases
    from the database to create an executive-specific reasoning framework.

    This framework is injected into the prompt to guide the LLM's reasoning
    to match how the real executive would think about the problem.
    """

    def __init__(self, embedding_client=None):
        """
        Initialize the CognitiveFrameBuilder.

        Args:
            embedding_client: Optional EmbeddingServiceClient for case matching.
                            If None, uses the global singleton.
        """
        self._profile_loader = get_cognitive_profile_loader()
        self._config = get_layer_config("foundation.cognitive_frame")
        self._embedding_client = embedding_client

        logger.info("CognitiveFrameBuilder initialized")

    def _get_embedding_client(self):
        """Get or create embedding client (lazy loading)."""
        if self._embedding_client is None:
            from vector_search.embedding_client import get_embedding_client
            self._embedding_client = get_embedding_client()
        return self._embedding_client

    def build(
        self,
        query: str,
        profile_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> CognitiveFrameResult:
        """
        Build cognitive frame for a query.

        Args:
            query: User's query
            profile_id: Executive profile ID
            context: Optional additional context (e.g., detected theme)

        Returns:
            CognitiveFrameResult with framework and prompt section
        """
        # Check if frame is enabled
        if not is_layer_enabled("foundation.cognitive_frame"):
            return CognitiveFrameResult(
                framework=ReasoningFramework(),
                prompt_section="",
                cases_matched=0,
                reasoning="Cognitive frame disabled",
            )

        # Get thinking patterns
        thinking_patterns = self._profile_loader.get_thinking_patterns(profile_id)
        red_flags = self._profile_loader.get_red_flags(profile_id)
        decision_cases = self._profile_loader.get_decision_cases(profile_id)

        if not thinking_patterns:
            return CognitiveFrameResult(
                framework=ReasoningFramework(),
                prompt_section="",
                cases_matched=0,
                reasoning=f"No thinking patterns for {profile_id}",
            )

        # Build reasoning framework
        framework = ReasoningFramework(
            framework_examples=thinking_patterns.framework_examples,
            typical_questions=thinking_patterns.typical_questions,
            thought_organization=thinking_patterns.thought_organization,
            decision_approach=thinking_patterns.decision_approach,
        )

        # Add guardrails from red flags
        if red_flags:
            framework.never_approve = red_flags.never_approve
            framework.always_do = red_flags.always_do
            framework.escalation_triggers = red_flags.ai_should_escalate_when

        # Find similar decision cases
        cases_matched = 0
        if self._config.get("include_decision_cases", True) and decision_cases:
            max_cases = self._config.get("max_decision_cases", 3)
            similar_cases = self._find_similar_cases(query, decision_cases, max_cases)
            framework.similar_cases = similar_cases
            cases_matched = len(similar_cases)

        # Build prompt section
        prompt_section = self._build_prompt_section(framework, profile_id)

        logger.info(
            f"CognitiveFrame built for {profile_id}: "
            f"frameworks={len(framework.framework_examples)}, "
            f"questions={len(framework.typical_questions)}, "
            f"cases={cases_matched}"
        )

        return CognitiveFrameResult(
            framework=framework,
            prompt_section=prompt_section,
            cases_matched=cases_matched,
            reasoning=f"Built frame with {cases_matched} similar cases",
        )

    def _find_similar_cases(
        self,
        query: str,
        cases: List[DecisionCase],
        max_cases: int = 3,
    ) -> List[DecisionCase]:
        """
        Find decision cases similar to the current query.

        Uses embedding similarity to find relevant precedents.
        """
        if not cases:
            return []

        try:
            client = self._get_embedding_client()
            query_embedding = client.generate_embedding(query)

            # Score each case
            scored_cases = []
            for case in cases:
                # Create case text for embedding
                case_text = f"{case.title}. {case.situation}"
                case_embedding = client.generate_embedding(case_text[:1000])

                # Calculate similarity
                similarity = self._cosine_similarity(query_embedding, case_embedding)
                scored_cases.append((case, similarity))

            # Sort by similarity and take top N
            scored_cases.sort(key=lambda x: x[1], reverse=True)

            # Filter by minimum similarity
            min_similarity = 0.3
            similar = [
                case for case, score in scored_cases[:max_cases]
                if score >= min_similarity
            ]

            return similar

        except Exception as e:
            logger.warning(f"Failed to find similar cases: {e}")
            # Fallback: return most recent precedent cases
            precedents = [c for c in cases if c.is_precedent]
            return precedents[:max_cases] if precedents else cases[:max_cases]

    def _cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))

    def _build_prompt_section(
        self,
        framework: ReasoningFramework,
        profile_id: str,
    ) -> str:
        """
        Build the prompt section from the reasoning framework.

        This goes into the system prompt to guide the LLM's reasoning.
        """
        sections = []

        # Thinking frameworks
        if framework.framework_examples:
            sections.append(self._build_frameworks_section(framework.framework_examples))

        # Typical questions
        if framework.typical_questions:
            sections.append(self._build_questions_section(framework.typical_questions))

        # Thought organization
        if framework.thought_organization:
            sections.append(f"## HOW YOU ORGANIZE YOUR THINKING\n{framework.thought_organization}")

        # Decision approach
        if framework.decision_approach:
            sections.append(f"## YOUR DECISION APPROACH\n{framework.decision_approach}")

        # Guardrails
        if framework.never_approve or framework.always_do:
            sections.append(self._build_guardrails_section(framework))

        # Similar cases
        if framework.similar_cases:
            sections.append(self._build_cases_section(framework.similar_cases))

        return "\n\n".join(sections)

    def _build_frameworks_section(self, frameworks: List[str]) -> str:
        """Build the thinking frameworks section."""
        items = "\n".join(f"• {f}" for f in frameworks)
        return f"""## YOUR DECISION FRAMEWORKS
You naturally apply these mental models:
{items}"""

    def _build_questions_section(self, questions: List[str]) -> str:
        """Build the typical questions section."""
        items = "\n".join(f"• {q}" for q in questions)
        return f"""## QUESTIONS YOU ALWAYS ASK
{items}"""

    def _build_guardrails_section(self, framework: ReasoningFramework) -> str:
        """Build the guardrails section from red flags."""
        parts = []

        if framework.never_approve:
            never_items = "\n".join(f"• {item}" for item in framework.never_approve)
            parts.append(f"## WHAT YOU WOULD NEVER APPROVE\n{never_items}")

        if framework.always_do:
            always_items = "\n".join(f"• {item}" for item in framework.always_do)
            parts.append(f"## WHAT YOU ALWAYS DO\n{always_items}")

        if framework.escalation_triggers:
            escalate_items = "\n".join(f"• {item}" for item in framework.escalation_triggers)
            parts.append(f"## WHEN TO SAY 'I need to think about this more'\n{escalate_items}")

        return "\n\n".join(parts)

    def _build_cases_section(self, cases: List[DecisionCase]) -> str:
        """Build the similar cases section for case-based reasoning."""
        case_blocks = []

        for i, case in enumerate(cases, 1):
            block = f"""### SIMILAR SITUATION {i}: {case.title}

**Situation:** {case.situation}

**Your Decision:** {case.decision_made}

**Your Reasoning:** {case.rationale}"""

            # Add outcome if available
            if case.outcome:
                block += f"\n\n**What Happened:** {case.outcome}"

            # Add lessons learned if available
            if case.lessons_learned:
                block += f"\n\n**What You Learned:** {case.lessons_learned}"

            # Add options considered if available
            if case.options_considered:
                options_text = self._format_options(case.options_considered)
                block += f"\n\n**Options You Considered:**\n{options_text}"

            case_blocks.append(block)

        header = "## SIMILAR SITUATIONS YOU'VE HANDLED\nUse these as precedents for your thinking:\n"
        return header + "\n\n".join(case_blocks)

    def _format_options(self, options: List[dict]) -> str:
        """Format options_considered from decision case."""
        if not options:
            return ""

        lines = []
        for opt in options:
            option_name = opt.get("option", opt.get("name", "Option"))
            pros = opt.get("pros", [])
            cons = opt.get("cons", [])

            lines.append(f"- **{option_name}**")
            if pros:
                pros_text = ", ".join(pros) if isinstance(pros, list) else str(pros)
                lines.append(f"  - Pros: {pros_text}")
            if cons:
                cons_text = ", ".join(cons) if isinstance(cons, list) else str(cons)
                lines.append(f"  - Cons: {cons_text}")

        return "\n".join(lines)


# Singleton instance
_frame_builder: Optional[CognitiveFrameBuilder] = None


def get_cognitive_frame_builder() -> CognitiveFrameBuilder:
    """Get the singleton CognitiveFrameBuilder instance."""
    global _frame_builder
    if _frame_builder is None:
        _frame_builder = CognitiveFrameBuilder()
    return _frame_builder
