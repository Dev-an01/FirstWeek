"""
Abstract Base Class for LLM Clients

Defines the interface that all LLM provider implementations must follow.
Enables provider-agnostic usage in path handlers.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


@dataclass
class LLMMessage:
    """Represents a message in the conversation"""
    role: str  # system, user, assistant
    content: str
    

@dataclass
class LLMResponse:
    """Standardized response from any LLM provider"""
    content: str
    model: str
    finish_reason: str
    usage: Dict[str, int]  # prompt_tokens, completion_tokens, total_tokens
    latency_ms: float
    provider: str
    raw_response: Optional[Any] = None


class BaseLLMClient(ABC):
    """
    Abstract base class for LLM clients.
    
    All provider implementations (OpenAI, GLM, etc.) must inherit from this
    and implement the generate() method.
    """
    
    def __init__(self, config: Dict[str, Any], path: str = "standard"):
        """
        Initialize the LLM client.
        
        Args:
            config: Provider configuration from llm_config.yaml
            path: Processing path (fast/standard/agentic) for model selection
        """
        self.config = config
        self.path = path
        self.provider_name = self.__class__.__name__.replace("Client", "").lower()
        
    @abstractmethod
    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of conversation messages
            temperature: Sampling temperature (overrides config)
            max_tokens: Maximum tokens to generate (overrides config)
            **kwargs: Additional provider-specific parameters
            
        Returns:
            LLMResponse with standardized fields
            
        Raises:
            LLMError: If generation fails
        """
        pass
    
    def get_model_name(self) -> str:
        """Get the model name for the current path"""
        return self.config["models"][self.path]
    
    def get_temperature(self, override: Optional[float] = None) -> float:
        """Get temperature for the current path"""
        return override if override is not None else self.config["temperature"][self.path]
    
    def get_max_tokens(self, override: Optional[int] = None) -> int:
        """Get max tokens for the current path"""
        return override if override is not None else self.config["max_tokens"][self.path]


class LLMError(Exception):
    """Base exception for LLM-related errors"""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out"""
    pass


class LLMAuthenticationError(LLMError):
    """Raised when API key is invalid or missing"""
    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded"""
    pass
