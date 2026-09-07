"""
Google Gemini LLM Client Implementation

Provides integration with Google's Gemini models (Gemini 2.5 Pro, Flash, etc.)
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
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    genai = None

logger = logging.getLogger(__name__)


class GeminiClient(BaseLLMClient):
    """
    Google Gemini client implementation.
    
    Supports Gemini 2.5 Pro, Gemini 2.5 Flash, and other Gemini models.
    """
    
    def __init__(self, config: Dict[str, Any], path: str = "standard"):
        """
        Initialize Gemini client.
        
        Args:
            config: Gemini configuration from llm_config.json
            path: Processing path (fast/standard/agentic)
            
        Raises:
            LLMError: If google-genai package not installed or API key missing
        """
        super().__init__(config, path)
        
        if not GEMINI_AVAILABLE:
            raise LLMError(
                "google-genai package not installed. Install with: pip install google-genai"
            )
        
        # Get API key from environment
        api_key_env = config.get("api_key_env", "GEMINI_API_KEY")
        api_key = os.getenv(api_key_env)
        
        if not api_key:
            raise LLMAuthenticationError(
                f"Gemini API key not found. Set {api_key_env} environment variable."
            )
        
        # Initialize client
        self.client = genai.Client(api_key=api_key)
        self.timeout = config.get("timeout", 30)
        
        logger.info(
            f"Initialized Gemini client for path={path}, model={self.get_model_name()}"
        )
    
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using Gemini API.
        
        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Gemini-specific parameters
            
        Returns:
            LLMResponse with generated content
        """
        start_time = time.time()
        
        # Convert messages to Gemini format
        # For simplicity, combine all user messages into a single prompt
        gemini_contents = self._format_messages_simple(messages)
        
        # Prepare generation config
        # Note: Gemini 2.5 Pro has thinking mode which uses tokens
        # We need to ensure enough tokens for both thinking and output
        max_tokens_requested = self.get_max_tokens(max_tokens)
        generation_config = {
            "temperature": self.get_temperature(temperature),
            "max_output_tokens": max_tokens_requested,
            # Disable automatic thinking to get faster responses
            # "thinking_config": {"mode": "disabled"}  # Uncomment if needed
        }
        
        try:
            logger.debug(f"Calling Gemini API with model={self.get_model_name()}")
            
            response = self.client.models.generate_content(
                model=self.get_model_name(),
                contents=gemini_contents,
                config=generation_config
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract token usage from Gemini response
            usage_metadata = getattr(response, 'usage_metadata', None)
            token_usage = {
                "prompt_tokens": getattr(usage_metadata, 'prompt_token_count', 0) if usage_metadata else 0,
                "completion_tokens": getattr(usage_metadata, 'candidates_token_count', 0) if usage_metadata else 0,
                "total_tokens": getattr(usage_metadata, 'total_token_count', 0) if usage_metadata else 0
            }
            
            # Get the generated text - Gemini response structure
            generated_text = ""
            try:
                # Check if candidates exists and is not None
                if response.candidates and len(response.candidates) > 0:
                    candidate = response.candidates[0]
                    # Check if content has parts
                    if hasattr(candidate.content, 'parts') and candidate.content.parts:
                        generated_text = candidate.content.parts[0].text
                    elif hasattr(response, 'text') and response.text:
                        generated_text = response.text
                    else:
                        # Model finished with MAX_TOKENS - likely all used for thinking
                        if candidate.finish_reason.name == 'MAX_TOKENS':
                            raise LLMError(
                                "Gemini used all tokens for thinking. "
                                "Increase max_tokens or disable thinking mode."
                            )
                        raise LLMError(f"No text in response. finish_reason={candidate.finish_reason}")
                elif hasattr(response, 'text') and response.text:
                    generated_text = response.text  
                else:
                    logger.error(f"Unexpected response structure: candidates={response.candidates}")
                    raise LLMError(f"Could not extract text from Gemini response")
            except (AttributeError, IndexError, TypeError) as e:
                logger.error(f"Error extracting text: {e}, response={response}")
                raise LLMError(f"Could not extract text from Gemini response: {e}")
            
            logger.info(
                f"Gemini response received: {latency_ms:.0f}ms, "
                f"tokens={token_usage['total_tokens']}"
            )
            
            return LLMResponse(
                content=generated_text,
                model=self.get_model_name(),
                finish_reason="stop",
                usage=token_usage,
                latency_ms=latency_ms,
                provider="gemini",
                raw_response=response
            )
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Map common errors
            if "timeout" in error_msg:
                raise LLMTimeoutError(f"Gemini request timed out: {e}")
            elif "authentication" in error_msg or "api key" in error_msg or "invalid" in error_msg:
                raise LLMAuthenticationError(f"Gemini authentication failed: {e}")
            elif "rate limit" in error_msg or "quota" in error_msg or "429" in error_msg:
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            else:
                raise LLMError(f"Gemini API error: {e}")
    
    def _format_messages_simple(self, messages: List[LLMMessage]) -> str:
        """
        Convert message list to simple string format for Gemini.
        Takes the last user message as the primary prompt.
        """
        # Get system message if any
        system_parts = [msg.content for msg in messages if msg.role == "system"]
        system_prompt = system_parts[0] if system_parts else ""
        
        # Get user messages
        user_parts = [msg.content for msg in messages if msg.role == "user"]
        user_prompt = user_parts[-1] if user_parts else ""
        
        # Combine
        if system_prompt:
            return f"{system_prompt}\n\n{user_prompt}"
        return user_prompt
    
    async def generate_stream_live(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Generate streaming response using Gemini Live API (WebSocket-based).
        Provides lower latency than REST streaming.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Gemini-specific parameters

        Yields:
            Dict with chunk data: {'type': 'token', 'content': '...'}
        """
        from google.genai import types

        start_time = time.time()

        # Convert messages to text prompt
        prompt_text = self._format_messages_simple(messages)

        # Prepare Live API config
        config = types.LiveConnectConfig(
            response_modalities=["TEXT"],  # Text-only responses
            generation_config=types.GenerationConfig(
                temperature=self.get_temperature(temperature),
                max_output_tokens=self.get_max_tokens(max_tokens),
            )
        )

        try:
            logger.debug(f"Starting Gemini Live API streaming with model={self.get_model_name()}")

            full_text = ""
            total_tokens = 0

            # Connect to Live API with WebSocket
            async with self.client.aio.live.connect(
                model=self.get_model_name(),
                config=config
            ) as session:

                # Send the query via Live API (google-genai 1.x uses send())
                await session.send(input=prompt_text, end_of_turn=True)

                # Stream responses as they arrive
                async for message in session.receive():
                    try:
                        # Check for text response
                        if hasattr(message, 'text') and message.text:
                            chunk_text = message.text
                            full_text += chunk_text

                            # Yield token immediately
                            yield {
                                'type': 'token',
                                'content': chunk_text
                            }

                        # Check for server content (turn-based responses)
                        elif hasattr(message, 'server_content') and message.server_content:
                            server_content = message.server_content
                            if hasattr(server_content, 'model_turn') and server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if hasattr(part, 'text') and part.text:
                                        chunk_text = part.text
                                        full_text += chunk_text

                                        yield {
                                            'type': 'token',
                                            'content': chunk_text
                                        }

                        # Check for completion
                        elif hasattr(message, 'tool_call_cancellation'):
                            break

                    except (AttributeError, TypeError) as e:
                        logger.warning(f"Error processing Live API message: {e}")
                        continue

            latency_ms = (time.time() - start_time) * 1000

            # Yield completion metadata
            yield {
                'type': 'complete',
                'metadata': {
                    'model': self.get_model_name(),
                    'latency_ms': latency_ms,
                    'total_tokens': total_tokens,
                    'provider': 'gemini',
                    'api_type': 'live',
                    'full_text': full_text
                }
            }

        except Exception as e:
            error_msg = str(e).lower()

            # Map common errors
            if "timeout" in error_msg:
                raise LLMTimeoutError(f"Gemini Live API streaming timed out: {e}")
            elif "authentication" in error_msg or "api key" in error_msg:
                raise LLMAuthenticationError(f"Gemini Live API authentication failed: {e}")
            elif "rate limit" in error_msg or "quota" in error_msg:
                raise LLMRateLimitError(f"Gemini Live API rate limit exceeded: {e}")
            else:
                raise LLMError(f"Gemini Live API streaming error: {e}")

    async def generate_stream(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        Generate streaming response using Gemini API.

        Now uses Live API by default for better latency.
        Falls back to REST streaming if Live API fails.

        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Gemini-specific parameters

        Yields:
            Dict with chunk data: {'type': 'token', 'content': '...'}
        """
        # Try Live API first for better latency
        try:
            async for chunk in self.generate_stream_live(messages, temperature, max_tokens, **kwargs):
                yield chunk
            return
        except Exception as e:
            logger.warning(f"Live API failed, falling back to REST streaming: {e}")

        # Fallback to REST streaming
        import asyncio
        import queue
        import threading

        start_time = time.time()

        # Convert messages to Gemini format
        gemini_contents = self._format_messages_simple(messages)

        # Prepare generation config
        max_tokens_requested = self.get_max_tokens(max_tokens)
        generation_config = {
            "temperature": self.get_temperature(temperature),
            "max_output_tokens": max_tokens_requested,
        }

        try:
            logger.debug(f"Starting Gemini streaming with model={self.get_model_name()}")

            # Create a queue for thread-safe communication
            chunk_queue = queue.Queue()

            def stream_in_thread():
                """Run synchronous Gemini streaming in a separate thread"""
                try:
                    # Use generate_content_stream for streaming
                    response_stream = self.client.models.generate_content_stream(
                        model=self.get_model_name(),
                        contents=gemini_contents,
                        config=generation_config
                    )

                    # Iterate synchronously (safe in thread)
                    for chunk in response_stream:
                        chunk_queue.put(('chunk', chunk))

                    # Signal completion
                    chunk_queue.put(('done', None))

                except Exception as e:
                    chunk_queue.put(('error', e))

            # Start streaming in background thread
            thread = threading.Thread(target=stream_in_thread, daemon=True)
            thread.start()

            full_text = ""
            total_tokens = 0
            chunk_count = 0

            # Process chunks as they arrive from the thread
            while True:
                # Wait for next chunk with timeout
                try:
                    msg_type, data = await asyncio.get_event_loop().run_in_executor(
                        None, chunk_queue.get, True, 60  # 60s timeout
                    )
                except queue.Empty:
                    raise LLMTimeoutError("Gemini streaming timed out waiting for chunks")

                if msg_type == 'error':
                    raise data
                elif msg_type == 'done':
                    break
                elif msg_type == 'chunk':
                    chunk = data
                    chunk_count += 1
                    try:
                        # Extract text from chunk
                        if chunk.candidates and len(chunk.candidates) > 0:
                            candidate = chunk.candidates[0]
                            if hasattr(candidate.content, 'parts') and candidate.content.parts:
                                chunk_text = candidate.content.parts[0].text
                                full_text += chunk_text

                                # Yield token immediately
                                yield {
                                    'type': 'token',
                                    'content': chunk_text
                                }

                            # Track token usage if available
                            if hasattr(chunk, 'usage_metadata'):
                                total_tokens = getattr(chunk.usage_metadata, 'total_token_count', total_tokens)

                    except (AttributeError, IndexError, TypeError) as e:
                        logger.warning(f"Error processing chunk: {e}")
                        continue

            latency_ms = (time.time() - start_time) * 1000

            logger.info(f"✅ Gemini REST streaming complete: {chunk_count} chunks, {len(full_text)} chars in {latency_ms:.0f}ms")

            # Yield completion metadata
            yield {
                'type': 'complete',
                'metadata': {
                    'model': self.get_model_name(),
                    'latency_ms': latency_ms,
                    'total_tokens': total_tokens,
                    'provider': 'gemini',
                    'full_text': full_text,
                    'chunk_count': chunk_count
                }
            }

        except Exception as e:
            error_msg = str(e).lower()

            # Map common errors
            if "timeout" in error_msg:
                raise LLMTimeoutError(f"Gemini streaming timed out: {e}")
            elif "authentication" in error_msg or "api key" in error_msg:
                raise LLMAuthenticationError(f"Gemini authentication failed: {e}")
            elif "rate limit" in error_msg or "quota" in error_msg:
                raise LLMRateLimitError(f"Gemini rate limit exceeded: {e}")
            else:
                raise LLMError(f"Gemini streaming error: {e}")
