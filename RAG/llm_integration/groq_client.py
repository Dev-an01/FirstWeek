"""
Groq LLM Client

OpenAI-compatible client for Groq API using custom base URL.
"""

import os
import time
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from .base_client import BaseLLMClient, LLMResponse, LLMMessage

logger = logging.getLogger(__name__)


class GroqClient(BaseLLMClient):
    """
    Groq LLM client using OpenAI-compatible API.
    
    Groq provides ultra-fast inference with OpenAI-compatible endpoints.
    We use the OpenAI client with a custom base URL.
    """
    
    def __init__(self, config: Dict[str, Any], path: str = "standard"):
        """
        Initialize Groq client.
        
        Args:
            config: Provider configuration from llm_config.yaml
            path: Query path (fast/standard/agentic)
        """
        super().__init__(config, path)
        
        # Get API key
        api_key_env = config.get('api_key_env', 'GROQ_API_KEY')
        api_key = os.getenv(api_key_env)
        
        if not api_key:
            raise ValueError(
                f"Groq API key not found. Set {api_key_env} environment variable."
            )
        
        # Get base URL (Groq's OpenAI-compatible endpoint)
        base_url = config.get('api_base', 'https://api.groq.com/openai/v1')
        
        # Initialize OpenAI client with Groq base URL
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            **{key: config[key] for key in ('timeout', 'max_retries') if key in config}
        )
        
        logger.info(f"Initialized GroqClient (path={path}, base_url={base_url})")
    
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate completion using Groq API.
        
        Args:
            messages: List of message dicts with 'role' and 'content' OR LLMMessage objects
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse object
        """
        start_time = time.time()
        
        # Convert LLMMessage objects to dicts if needed
        if messages and isinstance(messages[0], LLMMessage):
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
        
        # Use path-specific settings if not overridden
        if temperature is None:
            temperature = self.get_temperature()
        if max_tokens is None:
            max_tokens = self.get_max_tokens()
        
        model = self.get_model_name()
        
        logger.info(
            f"Calling Groq API: model={model}, "
            f"temp={temperature}, max_tokens={max_tokens}"
        )
        
        try:
            # Call Groq using OpenAI client
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract response
            message = response.choices[0].message
            content = message.content
            
            # Build usage info
            usage = {
                'prompt_tokens': response.usage.prompt_tokens,
                'completion_tokens': response.usage.completion_tokens,
                'total_tokens': response.usage.total_tokens
            }
            
            logger.info(
                f"Groq response received: {latency_ms:.0f}ms, "
                f"{usage['total_tokens']} tokens, {len(content)} chars"
            )
            
            # Return standardized LLMResponse
            return LLMResponse(
                content=content,
                model=model,
                finish_reason=response.choices[0].finish_reason,
                usage=usage,
                latency_ms=latency_ms,
                provider='groq',
                raw_response=response
            )
            
        except Exception as e:
            logger.error(f"Groq API call failed: {e}", exc_info=True)
            raise
    
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Stream completion tokens using Groq API.

        PHASE 3: True LLM Streaming - tokens are yielded as they arrive
        from the Groq API, not simulated by word-splitting a complete response.

        Args:
            messages: List of message dicts with 'role' and 'content' OR LLMMessage objects
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Dict with streaming chunks:
            - {'type': 'token', 'content': '...'} - Text tokens
            - {'type': 'complete', 'metadata': {...}} - Final metadata
        """
        import asyncio

        start_time = time.time()

        # Convert LLMMessage objects to dicts if needed
        if messages and isinstance(messages[0], LLMMessage):
            messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]

        # Use path-specific settings if not overridden
        if temperature is None:
            temperature = self.get_temperature()
        if max_tokens is None:
            max_tokens = self.get_max_tokens()

        model = self.get_model_name()

        logger.info(
            f"Starting Groq streaming: model={model}, "
            f"temp={temperature}, max_tokens={max_tokens}"
        )

        try:
            # Call Groq with stream=True for real-time token streaming
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,  # Enable streaming!
                **kwargs
            )

            full_content = ""
            prompt_tokens = 0
            completion_tokens = 0

            # Stream tokens as they arrive from Groq
            for chunk in response:
                # Check if there's content in this chunk
                if chunk.choices and chunk.choices[0].delta.content:
                    token_content = chunk.choices[0].delta.content
                    full_content += token_content
                    completion_tokens += 1  # Approximate

                    # DEBUG: Log each token with timestamp to prove real streaming
                    elapsed_ms = (time.time() - start_time) * 1000
                    if completion_tokens <= 10 or completion_tokens % 50 == 0:
                        logger.info(f"[STREAM TOKEN #{completion_tokens}] +{elapsed_ms:.0f}ms: '{token_content}'")

                    # Yield token immediately
                    yield {
                        'type': 'token',
                        'content': token_content
                    }

                # Check for usage info (sent in final chunk by some providers)
                if hasattr(chunk, 'usage') and chunk.usage:
                    prompt_tokens = getattr(chunk.usage, 'prompt_tokens', 0)
                    completion_tokens = getattr(chunk.usage, 'completion_tokens', completion_tokens)

                # Small yield to allow other async tasks
                await asyncio.sleep(0)

            latency_ms = (time.time() - start_time) * 1000

            logger.info(
                f"Groq streaming complete: {latency_ms:.0f}ms, "
                f"~{completion_tokens} tokens, {len(full_content)} chars"
            )

            # Yield completion metadata
            yield {
                'type': 'complete',
                'metadata': {
                    'model': model,
                    'latency_ms': latency_ms,
                    'provider': 'groq',
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens,
                    'full_response': full_content
                }
            }

        except Exception as e:
            logger.error(f"Groq streaming failed: {e}", exc_info=True)
            raise

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count (approximation).

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
        # Simple approximation: ~4 chars per token
        return len(text) // 4
