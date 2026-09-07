"""
Local Extraction Client for Qwen3-30B
Implements Stage 1.5: Structured fact extraction using local LLM
"""

import httpx
import json
import logging
import re
from typing import Dict, List, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class LocalExtractorClient:
    """
    Calls local Qwen3-30B instance for structured fact extraction.
    Implements Gemini's JSON mode + ChatGPT's schema design.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:1234",
        model: str = "qwen/qwen3-30b-a3b-2507",
        timeout: float = 180.0  # Increased to 180s for large batches
    ):
        """
        Initialize the local extractor client.

        Args:
            base_url: Base URL of the local LLM server
            model: Model name/identifier
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = httpx.Timeout(timeout, connect=10.0)

        logger.info(f"[INIT] LocalExtractorClient initialized")
        logger.info(f"   Server: {self.base_url}")
        logger.info(f"   Model: {self.model}")

    async def extract_facts(
        self,
        query: str,
        compressed_docs: List[Dict],
        max_output_tokens: int = 600,
        batch_size: int = 2  # Process 2 documents at a time
    ) -> Dict[str, Any]:
        """
        Extract structured facts from compressed documents using local LLM.
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
                "server": self.base_url,
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
        Internal method: Extract facts from a single batch of documents.

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
            logger.info(f"[LLM] Calling local LLM for fact extraction ({len(compressed_docs)} docs)")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Call local server with proper system/user message separation
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "system",
                                "content": system_prompt
                            },
                            {
                                "role": "user",
                                "content": user_prompt
                            }
                        ],
                        "temperature": 0.0,  # Deterministic for consistent extraction
                        "max_tokens": max_output_tokens,
                        "top_p": 0.95,  # Slight randomness for natural JSON generation
                        "frequency_penalty": 0.0,
                        "presence_penalty": 0.0
                        # Note: response_format not supported by this server, rely on prompt
                    }
                )

            response.raise_for_status()
            result = response.json()

            # Extract the response content
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
            else:
                logger.error(f"Unexpected response format: {result}")
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
                "server": self.base_url,
                "extraction_tokens": result.get('usage', {}).get('completion_tokens', 0)
            }

            # Log extraction statistics
            measures_count = len(extracted_facts.get('measures', []))
            actions_count = len(extracted_facts.get('actions', []))
            decisions_count = len(extracted_facts.get('decisions', []))

            logger.info(
                f"[OK] Extraction complete: {measures_count} measures, {actions_count} actions, "
                f"{decisions_count} decisions"
            )

            return extracted_facts

        except httpx.HTTPStatusError as e:
            logger.error(f"[ERROR] HTTP error from local server: {e.response.status_code}")
            logger.error(f"   Response: {e.response.text[:500]}")
            raise

        except httpx.RequestError as e:
            logger.error(f"[ERROR] Request error to local server: {e}")
            logger.error(f"   Is the server running at {self.base_url}?")
            raise

        except Exception as e:
            logger.error(f"[ERROR] Extraction failed: {e}")
            raise

    def _empty_facts_structure(self, query: str) -> Dict[str, Any]:
        """
        Return empty facts structure as fallback.

        Args:
            query: Original query

        Returns:
            Empty facts dictionary
        """
        return {
            "entities": [],
            "measures": [],
            "decisions": [],
            "actions": [],
            "compliance": [],
            "outcomes": [],
            "timeline": [],
            "evidence": [],
            "_metadata": {
                "query": query,
                "error": "extraction_failed"
            }
        }

    async def test_connection(self) -> bool:
        """
        Test connection to local LLM server.

        Returns:
            True if connection successful
        """
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/v1/models")
                response.raise_for_status()
                logger.info(f"[OK] Local server connection OK: {self.base_url}")
                return True
        except Exception as e:
            logger.error(f"[ERROR] Cannot connect to local server: {e}")
            return False
