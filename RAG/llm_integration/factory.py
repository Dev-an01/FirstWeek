"""
LLM Client Factory

Provides provider-agnostic creation of LLM clients based on configuration.
Implements the Factory pattern for clean provider selection.

WEEK 1, DAY 2: Added LangSmith wrapper integration
"""

from typing import Dict, Any
import logging
import os

from .base_client import BaseLLMClient, LLMError
from .openai_client import OpenAIClient
from .glm_client import GLMClient
from .gemini_client import GeminiClient
from .groq_client import GroqClient
from .openrouter_client import OpenRouterClient
from .langsmith_wrapper import wrap_llm_client

logger = logging.getLogger(__name__)


class LLMClientFactory:
    """
    Factory for creating LLM clients.
    
    Supports automatic provider selection based on configuration,
    with extensibility for additional providers.
    """
    
    # Registry of available providers
    _providers = {
        "openai": OpenAIClient,
        "glm": GLMClient,
        "gemini": GeminiClient,
        "groq": GroqClient,
        "openrouter": OpenRouterClient,
    }
    
    @classmethod
    def create(
        cls,
        provider: str,
        config: Dict[str, Any],
        path: str = "standard",
        enable_langsmith: bool = None
    ) -> BaseLLMClient:
        """
        Create an LLM client for the specified provider.
        
        WEEK 1, DAY 2: Now wraps clients with LangSmith tracking
        
        Args:
            provider: Provider name (openai, glm, etc.)
            config: Provider configuration from llm_config.yaml
            path: Processing path (fast/standard/agentic)
            enable_langsmith: Override LangSmith tracing (default: from env)
            
        Returns:
            LLM client instance (wrapped with LangSmith if enabled)
            
        Raises:
            LLMError: If provider not found or initialization fails
        """
        provider_lower = provider.lower()
        
        if provider_lower not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise LLMError(
                f"Unknown LLM provider: {provider}. Available: {available}"
            )
        
        # Check if provider is enabled
        if not config.get("enabled", False):
            raise LLMError(
                f"Provider {provider} is disabled in configuration. "
                f"Set providers.{provider}.enabled=true in llm_config.yaml"
            )
        
        client_class = cls._providers[provider_lower]
        
        try:
            logger.info(f"Creating {provider} client for path={path}")
            base_client = client_class(config, path)
            
            # WEEK 1, DAY 2: Wrap with LangSmith tracking if enabled
            langsmith_enabled = enable_langsmith if enable_langsmith is not None else (
                os.getenv('LANGCHAIN_TRACING_V2', 'false').lower() == 'true'
            )
            
            if langsmith_enabled:
                logger.info(f"✅ Wrapping {provider} client with LangSmith tracking")
                return wrap_llm_client(base_client, provider)
            else:
                logger.debug(f"LangSmith tracing disabled for {provider} client")
                return base_client
                
        except Exception as e:
            raise LLMError(f"Failed to create {provider} client: {e}")
    
    @classmethod
    def register_provider(cls, name: str, client_class: type):
        """
        Register a new LLM provider.
        
        Allows extension with custom providers without modifying this module.
        
        Args:
            name: Provider name (e.g., "anthropic", "cohere")
            client_class: Class implementing BaseLLMClient
        """
        if not issubclass(client_class, BaseLLMClient):
            raise ValueError(
                f"Provider class must inherit from BaseLLMClient, "
                f"got {client_class.__name__}"
            )
        
        cls._providers[name.lower()] = client_class
        logger.info(f"Registered custom LLM provider: {name}")
    
    @classmethod
    def list_providers(cls) -> list:
        """Get list of registered provider names"""
        return list(cls._providers.keys())
