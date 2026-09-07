"""
Retrieved Context Section Builder - Vector/graph search results for user prompt.

This section goes in the USER prompt, not the system prompt.
Similar to legacy PromptBuilder._format_vector_results().

CRITICAL: Total token budget is CAPPED to prevent oversized prompts.
"""

import logging
from typing import TYPE_CHECKING, List, Dict, Any

if TYPE_CHECKING:
    from llm_integration.prompt_builder import RetrievalContext

logger = logging.getLogger(__name__)


class RetrievedContextSection:
    """
    Builds the retrieved context section for user prompt.

    CRITICAL: Total tokens are CAPPED per path to prevent oversized prompts.

    This goes in the USER prompt, not system prompt.
    Similar to legacy PromptBuilder._format_vector_results().

    Format varies by path:
    - Fast: Top 3 sources, max 1500 total chars (~500 tokens)
    - Standard: Top 5 sources, max 4500 total chars (~1500 tokens)
    - Agentic: Top 8 sources, max 6000 total chars (~2000 tokens)

    Output format:
        AVAILABLE SOURCES:
        Source: Market_Analysis_Q4.pdf (Relevance: 0.85)
            Content: Revenue increased 23% in Q4...

        (Mention sources naturally if relevant: "Market Analysis", etc.)
    """

    # Source limits by path (REDUCED for tighter budgets)
    SOURCE_LIMITS = {
        "fast": 3,
        "standard": 5,
        "agentic": 8,
    }

    # Per-source content limits
    # FIXED: Increased per-source limits for better context (was 400/800/700)
    CONTENT_LIMITS = {
        "fast": 800,      # ~267 tokens per source (was 133)
        "standard": 1200, # ~400 tokens per source (was 267)
        "agentic": 1500,  # ~500 tokens per source (was 233)
    }

    # CRITICAL: Total character budget for entire section
    # FIXED: Increased budgets for better context (was fast:1500, standard:4500, agentic:6000)
    TOTAL_CHAR_BUDGET = {
        "fast": 4000,      # ~1300 tokens total (was 500)
        "standard": 8000,  # ~2700 tokens total (was 1500)
        "agentic": 12000,  # ~4000 tokens total (was 2000)
    }

    def build(
        self,
        retrieved_context: "RetrievalContext",
        path: str,
    ) -> str:
        """
        Build retrieved context section for user prompt.

        CRITICAL: Enforces total character budget to prevent oversized prompts.

        Args:
            retrieved_context: From vector/graph search
            path: Processing path (fast/standard/agentic)

        Returns:
            Formatted context section (budget-capped)
        """
        # Handle None context
        if retrieved_context is None:
            return ""

        total_budget = self.TOTAL_CHAR_BUDGET.get(path, 4500)
        used_chars = 0
        sections = []

        # Vector search results (PRIMARY - gets most budget)
        if hasattr(retrieved_context, 'vector_results') and retrieved_context.vector_results:
            # Allocate 80% of budget to vector results
            vector_budget = int(total_budget * 0.80)
            vector_section = self._format_vector_results(
                retrieved_context.vector_results,
                path,
                max_chars=vector_budget,
            )
            if vector_section:
                sections.append(vector_section)
                used_chars += len(vector_section)

        remaining_budget = total_budget - used_chars

        # Graph context (10% of budget for standard/agentic)
        if remaining_budget > 200 and hasattr(retrieved_context, 'graph_results') and retrieved_context.graph_results and path in ["standard", "agentic"]:
            graph_budget = min(int(total_budget * 0.10), remaining_budget)
            graph_section = self._format_graph_results(retrieved_context.graph_results, max_chars=graph_budget)
            if graph_section:
                sections.append(graph_section)
                used_chars += len(graph_section)

        remaining_budget = total_budget - used_chars

        # Memory (10% of budget) - episodic memory from past sessions
        if remaining_budget > 200 and hasattr(retrieved_context, 'memory') and retrieved_context.memory:
            memory_budget = min(int(total_budget * 0.10), remaining_budget)
            memory_section = self._format_memory(retrieved_context.memory, max_chars=memory_budget)
            if memory_section:
                sections.append(memory_section)
                used_chars += len(memory_section)

        remaining_budget = total_budget - used_chars

        # Current Session Conversation History (CRITICAL for multi-turn)
        # This is different from episodic memory - it's the current session's turns
        if remaining_budget > 200 and hasattr(retrieved_context, 'conversation_history') and retrieved_context.conversation_history:
            history_budget = min(int(total_budget * 0.15), remaining_budget)
            history_section = self._format_conversation_history(
                retrieved_context.conversation_history,
                max_chars=history_budget
            )
            if history_section:
                sections.insert(0, history_section)  # Insert at beginning for visibility

        # Combine sections
        context_section = "\n\n".join(sections) if sections else ""

        logger.debug(f"Built retrieved context: {len(context_section)} chars (budget: {total_budget})")

        return f"""
AVAILABLE CONTEXT:

{context_section}
"""

    def _format_vector_results(
        self,
        results: List[Dict[str, Any]],
        path: str,
        max_chars: int = 3600,
    ) -> str:
        """
        Format vector search results with source names for citation validation.

        CRITICAL: Enforces max_chars budget to prevent oversized prompts.
        Each document shows its actual name that the LLM must use for citations.
        """
        max_results = self.SOURCE_LIMITS.get(path, 5)
        content_limit = self.CONTENT_LIMITS.get(path, 800)

        limited_results = results[:max_results]

        formatted = ["AVAILABLE SOURCES:\n"]
        current_chars = len(formatted[0])

        sources_included = []
        for i, result in enumerate(limited_results, 1):
            # Extract meaningful title - check multiple fields
            title = self._extract_title(result, i)
            content = (
                result.get('content') or
                result.get('text') or
                result.get('text_content') or
                ''
            )
            score = result.get('score', 0.0)

            if not content:
                content = f"[No content for {title}]"

            # Truncate content to per-source limit
            truncated_content = content[:content_limit]
            if len(content) > content_limit:
                truncated_content += "..."

            source_block = f"""Source: {title} (Relevance: {score:.2f})
    {truncated_content}
"""
            # Check if adding this would exceed budget (leave 300 chars for citation footer)
            if current_chars + len(source_block) > (max_chars - 300):
                break

            formatted.append(source_block)
            sources_included.append(title)
            current_chars += len(source_block)

        # NO citation reminder - CEOs don't cite documents in conversation
        # The context is for your knowledge, not to quote
        if sources_included:
            formatted.append(f"\n(Use this as background knowledge - do NOT cite or reference these documents in your response)")

        return "\n".join(formatted)

    def _format_graph_results(
        self,
        results: List[Dict[str, Any]],
        max_chars: int = 450,
    ) -> str:
        """Format graph context results with budget cap."""
        if not results:
            return ""

        formatted = ["GRAPH CONTEXT:"]
        current_chars = len(formatted[0])

        for i, result in enumerate(results[:3], 1):
            relationship = result.get('relationship', 'relates to')
            entity = result.get('entity', 'unknown')
            context = result.get('context', '')

            context_preview = context[:150]
            if len(context) > 150:
                context_preview += "..."

            entry = f"\n{entity} ({relationship}): {context_preview}"

            if current_chars + len(entry) > max_chars:
                break

            formatted.append(entry)
            current_chars += len(entry)

        return "\n".join(formatted)

    def _extract_title(self, result: Dict[str, Any], fallback_idx: int) -> str:
        """
        Extract meaningful title from result, trying multiple fields.

        Priority:
        1. title (if not generic like "Document")
        2. name
        3. document_id (extract human-readable part)
        4. source
        5. fallback to Document_{idx}
        """
        # Try title first
        title = result.get('title', '')
        if title and title.lower() not in ('document', 'unknown', ''):
            return title

        # Try name
        name = result.get('name', '')
        if name and name.lower() not in ('document', 'unknown', ''):
            return name

        # Try to extract from document_id (e.g., "doc_2024-10-20_marketing_performance_q3")
        doc_id = result.get('document_id', '') or result.get('id', '')
        if doc_id:
            # Remove "doc_" prefix and clean up
            clean_id = doc_id.replace('doc_', '').replace('document:', '')
            # Convert underscores to spaces and title case
            # e.g., "2024-10-20_marketing_performance_q3" -> "Marketing Performance Q3"
            parts = clean_id.split('_')
            # Find the descriptive parts (skip date-like parts)
            descriptive = []
            for part in parts:
                # Skip date parts like "2024-10-20"
                if '-' in part and len(part) > 6:
                    continue
                descriptive.append(part.replace('-', ' '))
            if descriptive:
                return ' '.join(descriptive).title()

        # Try source
        source = result.get('source', '')
        if source and source.lower() not in ('document', 'unknown', ''):
            return source

        return f"Document_{fallback_idx}"

    def _format_memory(
        self,
        memory: List[Dict[str, Any]],
        max_chars: int = 450,
    ) -> str:
        """Format memory/conversation history with budget cap."""
        if not memory:
            return ""

        formatted = ["CONVERSATION HISTORY:"]
        current_chars = len(formatted[0])

        for mem in memory[-2:]:  # Only last 2 entries
            query = mem.get('query', '')[:80]
            response_summary = mem.get('response', '')[:100]

            entry = f"\nQ: {query}\nA: {response_summary}..."

            if current_chars + len(entry) > max_chars:
                break

            formatted.append(entry)
            current_chars += len(entry)

        return "\n".join(formatted)

    def _format_conversation_history(
        self,
        conversation_history: List[Dict[str, Any]],
        max_chars: int = 800,
    ) -> str:
        """
        Format current session conversation history for multi-turn context.

        CRITICAL: This enables the LLM to resolve references like:
        - "the first one" / "the second project"
        - "it" / "that"
        - "tell me more"

        Args:
            conversation_history: List of {role: "user"|"assistant", content: str}
            max_chars: Maximum characters for this section

        Returns:
            Formatted conversation history with clear reference resolution instructions
        """
        if not conversation_history:
            return ""

        # Take last 6 messages (3 turns) for context
        recent_history = conversation_history[-6:]

        if not recent_history:
            return ""

        formatted = [
            "CURRENT SESSION CONVERSATION:",
            "IMPORTANT: Use this conversation to understand references like 'the first one', 'it', 'that', etc.",
            ""
        ]
        current_chars = sum(len(line) for line in formatted)

        for msg in recent_history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            # Truncate long messages
            if len(content) > 250:
                content = content[:250] + "..."

            if role == 'user':
                entry = f"User: {content}"
            else:
                entry = f"You: {content}"

            if current_chars + len(entry) + 1 > max_chars:
                break

            formatted.append(entry)
            current_chars += len(entry) + 1

        formatted.append("")  # Empty line at end

        return "\n".join(formatted)
