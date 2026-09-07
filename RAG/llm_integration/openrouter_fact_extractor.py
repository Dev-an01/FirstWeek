"""
OpenRouter Fact Extractor
Implements Stage 1.5: Structured fact extraction using OpenRouter API
Uses the OPENROUTER_API_KEY from .env
More reliable than Groq API based on testing.
"""

import os
import json
import logging
import re
import asyncio
from typing import Dict, List, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logging.warning("OpenAI package not available. Fact extraction will be disabled.")

logger = logging.getLogger(__name__)


class OpenRouterFactExtractor:
    """
    Calls OpenRouter API for structured fact extraction.
    Uses OPENROUTER_API_KEY environment variable.
    OpenRouter provides access to multiple models with better reliability than Groq.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "minimax/minimax-m2:free",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout: float = 180.0
    ):
        """
        Initialize the OpenRouter fact extractor client.

        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY from env)
            model: Model name/identifier (default: minimax/minimax-m2:free)
            base_url: OpenRouter API base URL
            timeout: Request timeout in seconds
        """
        # Use environment variable if api_key not provided
        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY")

        if not OPENAI_AVAILABLE:
            logger.error("OpenAI package not installed. Please install: pip install openai")
            raise ImportError("OpenAI package not available")

        if not api_key:
            logger.error("OPENROUTER_API_KEY not found in environment variables")
            raise ValueError("OPENROUTER_API_KEY not found. Set it in your .env file.")

        # Initialize OpenAI client with OpenRouter base URL
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
        self.timeout = timeout

        logger.info(f"[INIT] OpenRouterFactExtractor initialized")
        logger.info(f"   Model: {self.model}")
        logger.info(f"   Base URL: {base_url}")
        logger.info(f"   Timeout: {self.timeout}s")

    async def extract_facts(
        self,
        query: str,
        compressed_docs: List[Dict],
        max_output_tokens: int = 600,
        batch_size: int = 2
    ) -> Dict[str, Any]:
        """
        Extract structured facts from compressed documents using OpenRouter API.
        Processes documents in batches to avoid timeouts with large document sets.

        Args:
            query: User query
            compressed_docs: List of documents with compressed content
            max_output_tokens: Maximum tokens for extraction output
            batch_size: Number of documents to process per batch (default: 2)

        Returns:
            JSON object with extracted facts (merged from all batches)
        """
        if len(compressed_docs) <= batch_size:
            # Process all at once if batch size is sufficient
            return await self._extract_facts_batch(query, compressed_docs, max_output_tokens)

        # Process in batches
        logger.info(f"[BATCH] Processing {len(compressed_docs)} documents in batches of {batch_size}")

        all_measures = []
        all_actions = []
        all_compliance = []
        all_outcomes = []
        total_docs_processed = 0

        for i in range(0, len(compressed_docs), batch_size):
            batch = compressed_docs[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(compressed_docs) + batch_size - 1) // batch_size

            logger.info(f"   Processing batch {batch_num}/{total_batches} ({len(batch)} documents)...")

            try:
                batch_facts = await self._extract_facts_batch(query, batch, max_output_tokens)

                # Merge results
                all_measures.extend(batch_facts.get('measures', []))
                all_actions.extend(batch_facts.get('actions', []))
                all_compliance.extend(batch_facts.get('compliance', []))
                all_outcomes.extend(batch_facts.get('outcomes', []))
                total_docs_processed += batch_facts.get('_metadata', {}).get('documents_processed', len(batch))

                logger.info(f"   [OK] Batch {batch_num} complete")

            except Exception as e:
                logger.warning(f"   [WARN] Batch {batch_num} failed: {e}, continuing with other batches...")
                continue

        # Return merged results
        merged_facts = {
            "measures": all_measures,
            "actions": all_actions,
            "compliance": all_compliance,
            "outcomes": all_outcomes,
            "_metadata": {
                "query": query,
                "documents_processed": total_docs_processed,
                "model": self.model,
                "service": "openrouter_api",
                "batches": total_batches,
                "batch_size": batch_size
            }
        }

        logger.info(
            f"[OK] All batches complete: {len(all_measures)} measures, {len(all_actions)} actions, "
            f"{len(all_compliance)} compliance items"
        )

        return merged_facts

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _extract_facts_batch(
        self,
        query: str,
        compressed_docs: List[Dict],
        max_output_tokens: int = 600
    ) -> Dict[str, Any]:
        """
        Internal method: Extract facts from a single batch of documents using OpenRouter API.

        Args:
            query: User query
            compressed_docs: Batch of documents to process
            max_output_tokens: Maximum tokens for extraction output

        Returns:
            JSON object with extracted facts for this batch
        """
        # Build context from compressed documents
        context_parts = []
        for idx, doc in enumerate(compressed_docs):
            doc_id = doc.get('id', f'doc_{idx+1}')
            doc_title = doc.get('title', 'Untitled')
            content = doc['content']

            # Include compression metadata for transparency
            original_len = doc.get('original_length', len(content))
            method = doc.get('extraction_method', 'unknown')

            context_parts.append(f"""
Document {idx + 1}:
ID: {doc_id}
Title: {doc_title}
Content: {content}
[Extracted {len(content)} chars from {original_len} chars using {method}]
""")

        full_context = "\n\n---\n\n".join(context_parts)

        # System prompt - concise for faster processing
        system_prompt = """Extract business facts from documents as JSON. Output ONLY valid JSON, no other text.

Rules:
- Extract ONLY explicit facts (never infer)
- Preserve EXACT number formatting (¥8M, 47%, etc.)
- Empty fields = []
- Focus on: metrics, actions, compliance, dates"""

        # User prompt with context and query
        user_prompt = f"""**User Query:**
{query}

**Documents to Analyze:**
---
{full_context}
---

Extract key facts as JSON (preserve exact formatting like ¥8M, 47%):

{{
  "measures": [{{"label": "metric", "value": "¥8M or 47%"}}],
  "actions": [{{"what": "action taken", "when": "date"}}],
  "compliance": [{{"framework": "SOC 2", "status": "achieved"}}],
  "outcomes": [{{"description": "result with metrics"}}]
}}

Rules: Exact formatting, empty=[], pure JSON only.
Extract:"""

        try:
            logger.info(f"[OPENROUTER API] Calling OpenRouter for fact extraction ({len(compressed_docs)} docs)")

            # Call OpenRouter API via OpenAI client (synchronous, so use executor)
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://localhost:8000",
                        "X-Title": "AI Officer RAG System"
                    },
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": user_prompt
                        }
                    ],
                    temperature=0.0,  # Deterministic for consistent extraction
                    max_tokens=max_output_tokens,
                    top_p=0.95
                )
            )

            # Extract the response content
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
            else:
                logger.error(f"Unexpected response format from OpenRouter API")
                return self._empty_facts_structure(query)

            # Parse the JSON response
            try:
                # Try direct JSON parsing first
                extracted_facts = json.loads(content)
            except json.JSONDecodeError as e:
                logger.warning(f"Direct JSON parse failed: {e}")
                logger.debug(f"Response content: {content[:500]}...")

                # Try to extract JSON from markdown code blocks
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    try:
                        extracted_facts = json.loads(json_match.group(1))
                        logger.info("Extracted JSON from markdown code block")
                    except json.JSONDecodeError:
                        logger.error("Failed to parse JSON from code block")
                        return self._empty_facts_structure(query)
                else:
                    # Try to find JSON object without code blocks
                    json_match = re.search(r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', content, re.DOTALL)
                    if json_match:
                        try:
                            extracted_facts = json.loads(json_match.group(1))
                            logger.info("Extracted JSON from response text")
                        except json.JSONDecodeError:
                            logger.error("Failed to parse extracted JSON")
                            return self._empty_facts_structure(query)
                    else:
                        logger.error("No JSON found in response")
                        return self._empty_facts_structure(query)

            # Add metadata
            extracted_facts["_metadata"] = {
                "query": query,
                "documents_processed": len(compressed_docs),
                "model": self.model,
                "service": "openrouter_api",
                "extraction_tokens": response.usage.completion_tokens if response.usage else 0
            }

            # Log extraction statistics
            measures_count = len(extracted_facts.get('measures', []))
            actions_count = len(extracted_facts.get('actions', []))
            compliance_count = len(extracted_facts.get('compliance', []))

            logger.info(
                f"[OK] Extraction complete: {measures_count} measures, {actions_count} actions, "
                f"{compliance_count} compliance items"
            )

            return extracted_facts

        except Exception as e:
            logger.error(f"[ERROR] OpenRouter API call failed: {e}", exc_info=True)
            raise

    def _empty_facts_structure(self, query: str) -> Dict[str, Any]:
        """
        Return empty facts structure when extraction fails.

        Args:
            query: Original query

        Returns:
            Empty facts dict with metadata
        """
        return {
            "measures": [],
            "actions": [],
            "compliance": [],
            "outcomes": [],
            "_metadata": {
                "query": query,
                "documents_processed": 0,
                "model": self.model,
                "service": "openrouter_api",
                "error": "extraction_failed"
            }
        }
