"""
Document Summarizer for Context Compression
Handles summarization of retrieved documents to fit token budgets
"""
import logging
import os
from typing import List, Dict, Any, Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Groq package not available. Document summarization will be disabled.")

logger = logging.getLogger(__name__)


class DocumentSummarizer:
    """
    Summarizes documents using Groq API to reduce token count
    while preserving decision-relevant context.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-oss-120b",
        max_summary_tokens: int = 150
    ):
        """
        Initialize document summarizer.

        Args:
            api_key: Groq API key (defaults to GROQ_SUMMARIZATION_API_KEY from env)
            model: Model to use for summarization
            max_summary_tokens: Maximum tokens per summary
        """
        # Use environment variable if api_key not provided
        if api_key is None:
            api_key = os.getenv("GROQ_SUMMARIZATION_API_KEY")
            
        if not GROQ_AVAILABLE:
            logger.warning("Groq package not installed. Summarization will be skipped.")
            self.client = None
            self.model = model
            self.max_summary_tokens = max_summary_tokens
            return
            
        if not api_key:
            logger.warning(
                "GROQ_SUMMARIZATION_API_KEY not found. Summarization will be skipped."
            )
            self.client = None
        else:
            self.client = Groq(api_key=api_key)
            logger.info(f"DocumentSummarizer initialized with model: {model}")
            
        self.model = model
        self.max_summary_tokens = max_summary_tokens

    def estimate_tokens(self, text: str) -> int:
        """
        Estimate tokens from text (4 chars ≈ 1 token).

        Args:
            text: Input text

        Returns:
            Estimated token count
        """
        if not text:
            return 0
        return max(1, len(text) // 4)

    def summarize_document(
        self,
        doc: Dict[str, Any],
        query: str,
        target_tokens: int = 120
    ) -> Dict[str, Any]:
        """
        Summarize a single document focusing on query relevance.

        Args:
            doc: Document dictionary with 'content', 'source_id', etc.
            query: User query for context
            target_tokens: Target summary length in tokens

        Returns:
            Summarized document with compressed content
        """
        content = doc.get('content', '')
        source_id = doc.get('source_id', 'unknown')

        if not content:
            logger.warning(f"Empty content for doc {source_id}")
            return doc

        # If already short enough, return as-is
        current_tokens = self.estimate_tokens(content)
        if current_tokens <= target_tokens:
            logger.debug(f"Doc {source_id} already short ({current_tokens} tokens)")
            return doc

        # If Groq client not available, skip summarization
        if not self.client:
            logger.debug(f"Groq not available, skipping summarization for doc {source_id}")
            return doc

        try:
            # Truncate very long documents before summarization
            max_input_chars = target_tokens * 20  # ~5x compression ratio
            truncated_content = content[:max_input_chars]

            # Create summarization prompt
            prompt = self._create_summary_prompt(query, truncated_content, source_id)

            # Call Groq API
            logger.debug(f"Summarizing doc {source_id} ({current_tokens} -> {target_tokens} tokens)")

            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for factual summarization
                max_tokens=target_tokens * 2,  # Allow some buffer
                top_p=0.9,
                stream=False
            )

            summary = completion.choices[0].message.content.strip()

            # Create summarized document
            summarized_doc = doc.copy()
            summarized_doc['content'] = summary
            summarized_doc['original_length'] = current_tokens
            summarized_doc['summary_length'] = self.estimate_tokens(summary)
            summarized_doc['is_summarized'] = True

            logger.info(
                f"Summarized doc {source_id}: "
                f"{current_tokens} -> {summarized_doc['summary_length']} tokens"
            )

            return summarized_doc

        except Exception as e:
            logger.error(f"Summarization failed for doc {source_id}: {e}")
            # Fallback: truncate to target length
            char_limit = target_tokens * 4
            truncated = content[:char_limit] + "..." if len(content) > char_limit else content
            fallback_doc = doc.copy()
            fallback_doc['content'] = truncated
            fallback_doc['is_summarized'] = False
            fallback_doc['summarization_error'] = str(e)
            return fallback_doc

    def summarize_documents(
        self,
        docs: List[Dict[str, Any]],
        query: str,
        target_tokens_per_doc: int = 120,
        max_docs: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Summarize multiple documents with token budget.

        Args:
            docs: List of documents to summarize
            query: User query for context
            target_tokens_per_doc: Target tokens per document summary
            max_docs: Maximum number of documents to include

        Returns:
            List of summarized documents
        """
        if not docs:
            return []

        # Limit number of docs
        docs_to_summarize = docs[:max_docs]

        logger.info(
            f"Summarizing {len(docs_to_summarize)} docs "
            f"(target: {target_tokens_per_doc} tokens each)"
        )

        summarized = []
        for i, doc in enumerate(docs_to_summarize):
            try:
                summarized_doc = self.summarize_document(
                    doc=doc,
                    query=query,
                    target_tokens=target_tokens_per_doc
                )
                summarized.append(summarized_doc)
            except Exception as e:
                logger.error(f"Failed to summarize doc {i}: {e}")
                # Include original doc on error
                summarized.append(doc)

        total_tokens = sum(
            self.estimate_tokens(doc.get('content', ''))
            for doc in summarized
        )

        logger.info(f"Total summarized content: {total_tokens} tokens")

        return summarized

    def _create_summary_prompt(
        self,
        query: str,
        content: str,
        source_id: str
    ) -> str:
        """
        Create query-focused summarization prompt.

        Args:
            query: User query
            content: Document content
            source_id: Document source ID

        Returns:
            Summarization prompt
        """
        prompt = f"""Task: Create up to 3 concise bullet points (max 40 words each) that capture facts from this document relevant to answering: "{query}"

Rules:
- Be factual; keep numbers, dates, and names verbatim.
- Add source tag at the end like [SOURCE:{source_id}]
- Focus only on information relevant to the query.
- If nothing is relevant, return "NOT RELEVANT [SOURCE:{source_id}]"

Document:
{content}

Output format:
• [bullet point 1] [SOURCE:{source_id}]
• [bullet point 2] [SOURCE:{source_id}]
• [bullet point 3] [SOURCE:{source_id}]"""

        return prompt

    def calculate_token_budget(
        self,
        model_max_tokens: int = 8192,
        expected_response_tokens: int = 1000,
        prompt_overhead: int = 500
    ) -> int:
        """
        Calculate available token budget for context.

        Args:
            model_max_tokens: Model's maximum context window
            expected_response_tokens: Expected response length
            prompt_overhead: Tokens for system prompt, profile, etc.

        Returns:
            Available tokens for document context
        """
        budget = model_max_tokens - expected_response_tokens - prompt_overhead
        logger.debug(
            f"Token budget: {budget} "
            f"(max: {model_max_tokens}, response: {expected_response_tokens}, "
            f"overhead: {prompt_overhead})"
        )
        return max(budget, 500)  # Minimum 500 tokens


def normalize_text(text: str) -> str:
    """
    Normalize unicode characters for safe printing.

    Args:
        text: Input text

    Returns:
        Normalized text
    """
    if not text:
        return text

    import unicodedata

    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)

    # Replace narrow no-break space (U+202F) with regular space
    text = text.replace("\u202f", " ")

    # Replace other problematic unicode
    text = text.replace("\u2500", "-")  # Box drawing
    text = text.replace("\u2501", "-")
    text = text.replace("\u2502", "|")

    return text
