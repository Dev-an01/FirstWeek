"""
Base extractor: Groq client + shared LLM call logic.

Uses GROQ_EXTRACTION_API_KEY via OpenAI-compatible client.
Model: openai/gpt-oss-120b
"""

import json
import logging
import time
from typing import Dict, Any, Optional

from openai import OpenAI

from onboarding.config import (
    GROQ_BASE_URL,
    GROQ_MODEL,
    GROQ_EXTRACTION_API_KEY,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_RETRY_ATTEMPTS,
    LLM_RETRY_BASE_DELAY,
    LLM_MAX_INPUT_CHARS,
)

logger = logging.getLogger(__name__)


class BaseExtractor:
    """
    Base class for all 7 extractors.

    Provides shared Groq LLM call logic with JSON response format,
    retries with exponential backoff.
    """

    # Subclasses must set these
    EXTRACTOR_NAME: str = "base"
    SYSTEM_PROMPT: str = ""

    def __init__(self, api_key: Optional[str] = None):
        self._client = OpenAI(
            api_key=api_key or GROQ_EXTRACTION_API_KEY,
            base_url=GROQ_BASE_URL,
        )

    def extract(self, document_text: str) -> Dict[str, Any]:
        """
        Run extraction on the given document text.

        Returns parsed JSON dict from the LLM response.
        """
        # Truncate text if exceeds limit (for rate-limited tiers)
        if len(document_text) > LLM_MAX_INPUT_CHARS:
            logger.warning(
                f"[{self.EXTRACTOR_NAME}] Text too long ({len(document_text)} chars), "
                f"truncating to {LLM_MAX_INPUT_CHARS} chars. "
                f"Consider upgrading Groq to Developer tier for full document processing."
            )
            document_text = document_text[:LLM_MAX_INPUT_CHARS]

        user_prompt = self._build_user_prompt(document_text)
        return self._call_llm(user_prompt)

    def _build_user_prompt(self, document_text: str) -> str:
        """Build the user message. Subclasses can override for custom formatting."""
        return (
            "Analyze the following document(s) about an executive and extract the requested information.\n"
            "Return ONLY valid JSON matching the requested structure.\n\n"
            f"--- DOCUMENT TEXT ---\n{document_text}\n--- END ---"
        )

    def _call_llm(self, user_prompt: str) -> Dict[str, Any]:
        """
        Call the Groq LLM with retries and exponential backoff.
        Returns parsed JSON.
        """
        last_error = None
        for attempt in range(1, LLM_RETRY_ATTEMPTS + 1):
            try:
                response = self._client.chat.completions.create(
                    model=GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=LLM_TEMPERATURE,
                    max_tokens=LLM_MAX_TOKENS,
                    response_format={"type": "json_object"},
                )
                raw = response.choices[0].message.content
                result = json.loads(raw)
                logger.info(f"[{self.EXTRACTOR_NAME}] Extraction succeeded (attempt {attempt})")
                return result

            except json.JSONDecodeError as e:
                logger.warning(f"[{self.EXTRACTOR_NAME}] JSON parse error (attempt {attempt}): {e}")
                last_error = e
            except Exception as e:
                logger.warning(f"[{self.EXTRACTOR_NAME}] LLM call failed (attempt {attempt}): {e}")
                last_error = e

            if attempt < LLM_RETRY_ATTEMPTS:
                delay = LLM_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.info(f"[{self.EXTRACTOR_NAME}] Retrying in {delay}s...")
                time.sleep(delay)

        logger.error(f"[{self.EXTRACTOR_NAME}] All {LLM_RETRY_ATTEMPTS} attempts failed")
        return {"error": str(last_error), "extractor": self.EXTRACTOR_NAME}
