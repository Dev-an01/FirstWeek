"""
Gemini Fact Extractor
Implements Stage 1.5: Structured fact extraction using Google Gemini API
Uses the GEMINI_API_KEY from .env
More reliable and capable than free-tier models.
"""

import os
import json
import logging
import re
import asyncio
from typing import Dict, List, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logging.warning("Google Generative AI package not available. Install: pip install google-genai")

logger = logging.getLogger(__name__)


class GeminiFactExtractor:
    """
    Calls Google Gemini API for structured fact extraction.
    Uses GEMINI_API_KEY environment variable.
    Gemini is known for superior instruction-following and JSON reliability.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.0-flash-exp",
        timeout: float = 180.0
    ):
        """
        Initialize the Gemini fact extractor client.

        Args:
            api_key: Gemini API key (defaults to GEMINI_API_KEY from env)
            model: Model name (default: gemini-2.0-flash-exp for speed and capability)
            timeout: Request timeout in seconds
        """
        if not GEMINI_AVAILABLE:
            logger.error("Google Generative AI package not installed. Please install: pip install google-genai")
            raise ImportError("Google Generative AI package not available")

        # Gemini SDK automatically reads GEMINI_API_KEY from environment
        # Client() constructor reads the API key automatically
        self.client = genai.Client()
        self.model_name = model
        self.timeout = timeout

        logger.info(f"[INIT] GeminiFactExtractor initialized")
        logger.info(f"   Model: {self.model_name}")
        logger.info(f"   Timeout: {self.timeout}s")

    async def extract_facts(
        self,
        query: str,
        compressed_docs: List[Dict],
        max_output_tokens: int = 600,
        batch_size: int = 1
    ) -> Dict[str, Any]:
        """
        Extract structured facts from documents using Gemini API.

        NOTE: This is called in parallel for each document in the Map-Reduce pattern.
        batch_size should always be 1 for Map-Reduce.

        Args:
            query: User query
            compressed_docs: List of documents (should be single doc for Map-Reduce)
            max_output_tokens: Maximum tokens for extraction output
            batch_size: Number of documents to process (should be 1)

        Returns:
            JSON object with extracted facts
        """
        if not compressed_docs:
            return self._empty_facts_structure(query)

        # For Map-Reduce, we should only get 1 document
        if len(compressed_docs) != 1:
            logger.warning(f"[GEMINI] Expected 1 document, got {len(compressed_docs)}")

        return await self._extract_facts_single(query, compressed_docs, max_output_tokens)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _extract_facts_single(
        self,
        query: str,
        docs: List[Dict],
        max_output_tokens: int = 600
    ) -> Dict[str, Any]:
        """
        Internal method: Extract facts from documents using Gemini API.

        Args:
            query: User query
            docs: Documents to process
            max_output_tokens: Maximum tokens for extraction output

        Returns:
            JSON object with extracted facts
        """
        # Build context from documents
        context_parts = []
        for idx, doc in enumerate(docs):
            doc_id = doc.get('id', f'doc_{idx+1}')
            doc_title = doc.get('title', 'Untitled')
            content = doc['content']

            context_parts.append(f"""
Document {idx + 1}:
ID: {doc_id}
Title: {doc_title}
Content: {content}
""")

        full_context = "\n\n---\n\n".join(context_parts)

        # System instruction for Gemini
        system_instruction = """You are a precise business fact extractor. Extract ONLY explicit facts from documents.

Rules:
- Extract ONLY facts explicitly stated in the documents
- Preserve EXACT number formatting (¥8M, 47%, etc.)
- Return ONLY valid JSON, no other text
- Empty fields should be []
- Focus on: metrics, actions, compliance items, outcomes"""

        # User prompt with context and query
        user_prompt = f"""**User Query:**
{query}

**Documents to Analyze:**
---
{full_context}
---

Extract key business facts as JSON. Preserve exact formatting (¥8M, 47%):

{{
  "measures": [{{"label": "metric name", "value": "¥8M or 47%"}}],
  "actions": [{{"what": "action taken", "when": "date/timeframe"}}],
  "compliance": [{{"framework": "SOC 2", "status": "achieved"}}],
  "outcomes": [{{"description": "result with metrics"}}]
}}

Rules: Extract only explicit facts, exact formatting, empty=[], pure JSON only.
Output JSON:"""

        try:
            logger.info(f"[GEMINI API] Calling Gemini for fact extraction ({len(docs)} docs)")

            # Generate content with Gemini using new SDK
            # client.models.generate_content is synchronous, run in executor
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_content(
                    model=self.model_name,
                    contents=user_prompt
                )
            )

            # Extract the response content
            if not response or not response.text:
                logger.error(f"Unexpected response format from Gemini API")
                return self._empty_facts_structure(query)

            content = response.text.strip()

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
                "documents_processed": len(docs),
                "model": self.model_name,
                "service": "gemini_api",
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
            logger.error(f"[ERROR] Gemini API call failed: {e}", exc_info=True)
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
                "model": self.model_name,
                "service": "gemini_api",
                "error": "extraction_failed"
            }
        }
