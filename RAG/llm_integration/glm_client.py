"""
GLM (Zhipu AI) LLM Client Implementation

Provides integration with Zhipu AI's GLM models (GLM-4, GLM-4-Flash, etc.)
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
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

logger = logging.getLogger(__name__)


class GLMClient(BaseLLMClient):
    """
    Z.AI GLM client implementation using OpenAI-compatible API.
    
    Supports GLM-4.6, GLM-4, and other GLM models via https://api.z.ai
    """
    
    def __init__(self, config: Dict[str, Any], path: str = "standard"):
        """
        Initialize GLM client.
        
        Args:
            config: GLM configuration from llm_config.json
            path: Processing path (fast/standard/agentic)
            
        Raises:
            LLMError: If openai package not installed or API key missing
        """
        super().__init__(config, path)
        
        if not OPENAI_AVAILABLE:
            raise LLMError(
                "openai package not installed. Install with: pip install openai>=1.0"
            )
        
        # Get API key from environment
        api_key_env = config.get("api_key_env", "GLM_API_KEY")
        api_key = os.getenv(api_key_env)
        
        if not api_key:
            raise LLMAuthenticationError(
                f"GLM API key not found. Set {api_key_env} environment variable."
            )
        
        # Initialize OpenAI client with Z.AI endpoint
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.z.ai/api/paas/v4/"
        )
        self.timeout = config.get("timeout", 30)
        
        logger.info(
            f"Initialized GLM client (Z.AI) for path={path}, model={self.get_model_name()}"
        )
    
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate response using GLM API.
        
        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            **kwargs: Additional GLM-specific parameters
            
        Returns:
            LLMResponse with generated content
        """
        start_time = time.time()
        
        # Convert messages to GLM format
        glm_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Prepare request parameters
        params = {
            "model": self.get_model_name(),
            "messages": glm_messages,
            "temperature": self.get_temperature(temperature),
            "max_tokens": self.get_max_tokens(max_tokens),
            **kwargs
        }
        
        try:
            logger.debug(f"Calling GLM API with model={params['model']}")
            
            response = self.client.chat.completions.create(**params)
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract token usage (GLM format may differ)
            usage = getattr(response, 'usage', None)
            token_usage = {
                "prompt_tokens": getattr(usage, 'prompt_tokens', 0),
                "completion_tokens": getattr(usage, 'completion_tokens', 0),
                "total_tokens": getattr(usage, 'total_tokens', 0)
            } if usage else {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            
            logger.info(
                f"GLM response received: {latency_ms:.0f}ms, "
                f"tokens={token_usage['total_tokens']}"
            )
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                finish_reason=response.choices[0].finish_reason,
                usage=token_usage,
                latency_ms=latency_ms,
                provider="glm",
                raw_response=response
            )
            
        except Exception as e:
            error_msg = str(e).lower()
            
            # Map common errors
            if "timeout" in error_msg:
                raise LLMTimeoutError(f"GLM request timed out: {e}")
            elif "authentication" in error_msg or "api key" in error_msg:
                raise LLMAuthenticationError(f"GLM authentication failed: {e}")
            elif "rate limit" in error_msg or "quota" in error_msg:
                raise LLMRateLimitError(f"GLM rate limit exceeded: {e}")
            else:
                raise LLMError(f"GLM API error: {e}")
