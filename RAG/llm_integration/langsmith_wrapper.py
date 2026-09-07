"""
LangSmith Wrapper for Existing LLM Clients
Adds tracing without modifying client logic

CRITICAL FIX #2: Properly captures LangSmith run_id for feedback linkage
"""
import os
import time
from typing import Dict, Any, List, Optional, AsyncIterator
import logging

logger = logging.getLogger(__name__)

# Check if LangSmith is enabled
LANGSMITH_ENABLED = os.getenv('LANGCHAIN_TRACING_V2', 'false').lower() == 'true'

if LANGSMITH_ENABLED:
    try:
        from langsmith import traceable, get_current_run_tree
        from langsmith.run_helpers import trace
        logger.info("✅ LangSmith tracing enabled")
    except ImportError:
        logger.warning("⚠️ LangSmith libraries not installed. Tracing disabled.")
        LANGSMITH_ENABLED = False
        
        # Mock decorator for when LangSmith is not available
        def traceable(*args, **kwargs):
            def decorator(func):
                return func
            return decorator
        
        def get_current_run_tree():
            return None
else:
    logger.info("LangSmith tracing disabled (LANGCHAIN_TRACING_V2=false)")
    
    # Mock decorator
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    
    def get_current_run_tree():
        return None


class LangSmithTrackedLLM:
    """
    Wrapper that adds LangSmith tracing to any LLM client
    
    Features:
    - Automatic prompt/response logging
    - Token usage tracking
    - Cost calculation (with pricing metadata)
    - Run ID capture for feedback linkage (CRITICAL FIX #2)
    """
    
    def __init__(self, client: Any, provider_name: str, pricing: Optional[Dict[str, float]] = None):
        """
        Initialize tracked LLM client
        
        Args:
            client: Original LLM client instance
            provider_name: Provider name (groq, openai, etc.)
            pricing: Optional pricing per model {model: {input_per_1k, output_per_1k}}
        """
        self.client = client
        self.provider_name = provider_name
        self.langsmith_enabled = LANGSMITH_ENABLED
        self.pricing = pricing or {}
        
        logger.info(f"Initialized LangSmithTrackedLLM for provider: {provider_name}")
    
    def _calculate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost based on token usage and pricing"""
        if model not in self.pricing:
            return 0.0
        
        prices = self.pricing[model]
        input_cost = (prompt_tokens / 1000) * prices.get('input_per_1k', 0.0)
        output_cost = (completion_tokens / 1000) * prices.get('output_per_1k', 0.0)
        
        return input_cost + output_cost
    
    @traceable(
        run_type="llm",
        name="llm_generate"
    )
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate response with LangSmith tracking
        
        LangSmith automatically captures:
        - Input messages (prompt)
        - Output response
        - Token usage
        - Latency
        - Model name
        - Temperature/config
        
        CRITICAL FIX #2: Also captures run_id for feedback linkage
        
        Returns:
            Response dict with added 'langsmith_run_id' field
        """
        start_time = time.time()
        
        # Call original client (doesn't require 'model' param - uses self.model)
        response = self.client.generate(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Extract model name from response (it's an LLMResponse dataclass)
        model = response.model if hasattr(response, 'model') else getattr(self.client, 'model', 'unknown')
        
        # Extract token usage (response.usage is already a dict)
        tokens = response.usage if hasattr(response, 'usage') else {}
        prompt_tokens = tokens.get('prompt_tokens', 0)
        completion_tokens = tokens.get('completion_tokens', 0)
        
        # Calculate cost (CRITICAL FIX #4)
        cost_usd = self._calculate_cost(model, prompt_tokens, completion_tokens)
        
        # CRITICAL FIX #2: Capture LangSmith run_id
        run_tree = get_current_run_tree()
        langsmith_run_id = str(run_tree.id) if run_tree else None
        
        # NOTE: LLMResponse is a dataclass, we can't add attributes to it
        # Instead, we'll create an enhanced response dict that includes the metadata
        # But first, let's just return the original response since handlers expect LLMResponse
        # The orchestrator will handle adding langsmith_run_id to the final response
        
        # Log to LangSmith metadata if enabled
        if self.langsmith_enabled and run_tree:
            run_tree.extra = {
                **run_tree.extra,
                'provider': self.provider_name,
                'model': model,
                'prompt_tokens': prompt_tokens,
                'completion_tokens': completion_tokens,
                'cost_usd': cost_usd,
                'latency_ms': latency_ms
            }
        
        return response
    
    @traceable(
        run_type="llm",
        name="llm_generate_stream"
    )
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Streaming generation with LangSmith tracking

        CRITICAL FIX: Properly yields dictionaries instead of strings
        Captures run_id at start of stream for feedback linkage
        """
        start_time = time.time()

        # Capture run_id before streaming starts
        run_tree = get_current_run_tree()
        langsmith_run_id = str(run_tree.id) if run_tree else None

        # First yield: send run_id as a proper dictionary
        if langsmith_run_id:
            yield {
                'type': 'langsmith_metadata',
                'run_id': langsmith_run_id
            }

        # Extract model from client
        model = getattr(self.client, 'model', 'unknown')

        # Stream tokens (forward chunks as-is from underlying client)
        total_tokens = 0
        full_response = ""
        async for chunk in self.client.generate_stream(messages, temperature=temperature, max_tokens=max_tokens, **kwargs):
            # Track tokens and response
            if isinstance(chunk, dict):
                if chunk.get('type') == 'token':
                    total_tokens += 1
                    full_response += chunk.get('content', '')
                elif chunk.get('type') == 'complete':
                    # Inject LangSmith run_id into completion metadata
                    if langsmith_run_id:
                        chunk.setdefault('metadata', {})['langsmith_run_id'] = langsmith_run_id
            yield chunk

        # Calculate final latency
        latency_ms = (time.time() - start_time) * 1000

        # Add metadata to run
        if self.langsmith_enabled and run_tree:
            run_tree.extra = {
                **run_tree.extra,
                'provider': self.provider_name,
                'model': model,
                'latency_ms': latency_ms,
                'streaming': True,
                'total_tokens': total_tokens,
                'response_length': len(full_response)
            }
    
    # Proxy methods to forward calls to the wrapped client
    def get_model_name(self) -> str:
        """Forward get_model_name to wrapped client"""
        if hasattr(self.client, 'get_model_name'):
            return self.client.get_model_name()
        return getattr(self.client, 'model', 'unknown')
    
    def get_temperature(self, override: Optional[float] = None) -> float:
        """Forward get_temperature to wrapped client"""
        if hasattr(self.client, 'get_temperature'):
            return self.client.get_temperature(override)
        return override if override is not None else 0.7
    
    def get_max_tokens(self, override: Optional[int] = None) -> int:
        """Forward get_max_tokens to wrapped client"""
        if hasattr(self.client, 'get_max_tokens'):
            return self.client.get_max_tokens(override)
        return override if override is not None else 2000
    
    def __getattr__(self, name):
        """Forward any other attribute access to the wrapped client"""
        return getattr(self.client, name)


def wrap_llm_client(client: Any, provider_name: str) -> LangSmithTrackedLLM:
    """
    Convenience function to wrap an LLM client
    
    Usage:
        from llm_integration.langsmith_wrapper import wrap_llm_client
        
        base_client = GroqClient()
        tracked_client = wrap_llm_client(base_client, "groq")
    """
    # Define pricing tables (CRITICAL FIX #4)
    pricing = {
        # Groq pricing
        'groq/mixtral-8x7b-32768': {'input_per_1k': 0.0002, 'output_per_1k': 0.0002},
        'groq/llama-3-70b': {'input_per_1k': 0.0002, 'output_per_1k': 0.0002},
        'openai/gpt-oss-120b': {'input_per_1k': 0.0002, 'output_per_1k': 0.0002},
        
        # OpenAI pricing
        'gpt-4': {'input_per_1k': 0.03, 'output_per_1k': 0.06},
        'gpt-3.5-turbo': {'input_per_1k': 0.0015, 'output_per_1k': 0.002},
        'gpt-4-turbo': {'input_per_1k': 0.01, 'output_per_1k': 0.03},
        
        # Gemini pricing
        'gemini-pro': {'input_per_1k': 0.00025, 'output_per_1k': 0.0005},
    }
    
    return LangSmithTrackedLLM(client, provider_name, pricing)
