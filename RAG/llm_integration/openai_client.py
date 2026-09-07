"""
OpenAI LLM Client Implementation

Provides integration with OpenAI's API (GPT-3.5, GPT-4, etc.)
"""

import os
import time
from typing import List, Optional, Dict, Any
import logging

from .base_client import (
    BaseLLMClient, 
    LLMMessage, 
    LLMResponse,
    LLMError,
    LLMTimeoutError,
    LLMAuthenticationError,
    LLMRateLimitError
)

try:
    from openai import OpenAI, OpenAIError, APITimeoutError, AuthenticationError, RateLimitError
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """
    OpenAI API client implementation.
    
    Supports GPT-3.5-turbo, GPT-4, and GPT-4-turbo models.
    """
    
    def __init__(self, config: Dict[str, Any], path: str = "standard"):
        """
        Initialize OpenAI client.
        
        Args:
            config: OpenAI configuration from llm_config.yaml
            path: Processing path (fast/standard/agentic)
            
        Raises:
            LLMError: If OpenAI package not installed or API key missing
        """
        super().__init__(config, path)
        
        if not OPENAI_AVAILABLE:
            raise LLMError(
                "OpenAI package not installed. Install with: pip install openai"
            )
        
        # Get API key from environment
        api_key_env = config.get("api_key_env", "OPENAI_API_KEY")
        api_key = os.getenv(api_key_env)
        
        if not api_key:
            raise LLMAuthenticationError(
                f"OpenAI API key not found. Set {api_key_env} environment variable."
            )
        
        # Initialize client
        self.client = OpenAI(
            api_key=api_key,
            timeout=config.get("timeout", 30)
        )
        
        logger.info(
            f"Initialized OpenAI client for path={path}, model={self.get_model_name()}"
        )
    
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using OpenAI API.
        
        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI-specific parameters
            
        Returns:
            LLMResponse with generated content
        """
        start_time = time.time()
        
        # Convert messages to OpenAI format
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Prepare request parameters
        params = {
            "model": self.get_model_name(),
            "messages": openai_messages,
            "temperature": self.get_temperature(temperature),
            "max_tokens": self.get_max_tokens(max_tokens),
            **kwargs
        }
        
        try:
            logger.debug(f"Calling OpenAI API with model={params['model']}")
            
            response = self.client.chat.completions.create(**params)
            
            latency_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"OpenAI response received: {latency_ms:.0f}ms, "
                f"tokens={response.usage.total_tokens}"
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                finish_reason=response.choices[0].finish_reason,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                latency_ms=latency_ms,
                provider="openai",
                raw_response=response
            )
            
        except APITimeoutError as e:
            raise LLMTimeoutError(f"OpenAI request timed out: {e}")
        except AuthenticationError as e:
            raise LLMAuthenticationError(f"OpenAI authentication failed: {e}")
        except RateLimitError as e:
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}")
        except OpenAIError as e:
            raise LLMError(f"OpenAI API error: {e}")
        except Exception as e:
            raise LLMError(f"Unexpected error calling OpenAI: {e}")

    async def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Stream completion tokens using OpenAI API.

        True LLM Streaming - tokens are yielded as they arrive
        from the OpenAI API, not simulated by word-splitting.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional parameters

        Yields:
            Dict with streaming chunks:
            - {'type': 'token', 'content': '...'} - Text tokens
            - {'type': 'complete', 'metadata': {...}} - Final metadata
        """
        import asyncio

        start_time = time.time()

        # Convert LLMMessage objects to dicts
        openai_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Use path-specific settings if not overridden
        temp = self.get_temperature(temperature)
        max_tok = self.get_max_tokens(max_tokens)
        model = self.get_model_name()

        logger.info(
            f"Starting OpenAI streaming: model={model}, "
            f"temp={temp}, max_tokens={max_tok}"
        )

        try:
            # Call OpenAI with stream=True for real-time token streaming
            response = self.client.chat.completions.create(
                model=model,
                messages=openai_messages,
                temperature=temp,
                max_tokens=max_tok,
                stream=True,  # Enable streaming!
                **kwargs
            )

            full_content = ""
            prompt_tokens = 0
            completion_tokens = 0

            # Stream tokens as they arrive from OpenAI
            for chunk in response:
                # Check if there's content in this chunk
                if chunk.choices and chunk.choices[0].delta.content:
                    token_content = chunk.choices[0].delta.content
                    full_content += token_content
                    completion_tokens += 1  # Approximate

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
                f"OpenAI streaming complete: {latency_ms:.0f}ms, "
                f"~{completion_tokens} tokens, {len(full_content)} chars"
            )

            # Yield completion metadata
            yield {
                'type': 'complete',
                'metadata': {
                    'model': model,
                    'latency_ms': latency_ms,
                    'provider': 'openai',
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                    'total_tokens': prompt_tokens + completion_tokens,
                    'full_response': full_content
                }
            }

        except APITimeoutError as e:
            logger.error(f"OpenAI streaming timed out: {e}", exc_info=True)
            raise LLMTimeoutError(f"OpenAI streaming timed out: {e}")
        except AuthenticationError as e:
            logger.error(f"OpenAI streaming auth failed: {e}", exc_info=True)
            raise LLMAuthenticationError(f"OpenAI authentication failed: {e}")
        except RateLimitError as e:
            logger.error(f"OpenAI streaming rate limited: {e}", exc_info=True)
            raise LLMRateLimitError(f"OpenAI rate limit exceeded: {e}")
        except Exception as e:
            logger.error(f"OpenAI streaming failed: {e}", exc_info=True)
            raise LLMError(f"OpenAI streaming error: {e}")
