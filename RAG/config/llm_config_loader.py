"""
Configuration loader for LLM integration system.
Provides type-safe access to YAML configuration.
"""
import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class LLMConfig:
    """
    Singleton configuration loader for LLM integration.
    
    Loads and provides type-safe access to llm_config.yaml settings.
    """
    
    _instance = None
    _config: Dict[str, Any] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """Load YAML configuration file."""
        config_path = Path(__file__).parent.parent / "config" / "llm_config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError(f"LLM config not found: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        logger.info(f"Loaded LLM configuration from {config_path}")
        logger.info(f"Active provider: {self.active_provider}")
    
    def reload(self):
        """Reload configuration from file."""
        self._config = None
        self._load_config()
        logger.info("Configuration reloaded")
    
    # ===== Active Provider =====
    
    @property
    def active_provider(self) -> str:
        """Get active LLM provider name (openai, glm, anthropic)."""
        return self._config.get('active_provider', 'openai')
    
    def get_provider_config(self, provider_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get configuration for a specific provider.
        
        Args:
            provider_name: Provider name, defaults to active provider
            
        Returns:
            Provider configuration dict
        """
        provider = provider_name or self.active_provider
        providers = self._config.get('providers', {})
        
        if provider not in providers:
            raise ValueError(f"Unknown provider: {provider}")
        
        return providers[provider]
    
    def get_api_key(self, provider_name: Optional[str] = None) -> str:
        """
        Get API key for provider from environment variable.
        
        Args:
            provider_name: Provider name, defaults to active provider
            
        Returns:
            API key string
            
        Raises:
            ValueError: If API key not found in environment
        """
        provider_config = self.get_provider_config(provider_name)
        env_var = provider_config.get('api_key_env')
        
        api_key = os.getenv(env_var)
        if not api_key:
            raise ValueError(
                f"API key not found in environment variable: {env_var}. "
                f"Please set it before using {provider_name or self.active_provider} provider."
            )
        
        return api_key
    
    def get_model_for_path(self, path: str, provider_name: Optional[str] = None) -> str:
        """
        Resolve model name for a specific path.
        
        Args:
            path: Path name (fast, standard, complex)
            provider_name: Provider name, defaults to active provider
            
        Returns:
            Model name string
        """
        provider_config = self.get_provider_config(provider_name)
        models = provider_config.get('models', {})
        
        if path not in models:
            raise ValueError(f"No model configured for path: {path}")
        
        return models[path]
    
    def get_pricing(self, model: str, provider_name: Optional[str] = None) -> Dict[str, float]:
        """
        Get pricing for a specific model.
        
        Args:
            model: Model name
            provider_name: Provider name, defaults to active provider
            
        Returns:
            Dict with 'input' and 'output' costs per 1M tokens
        """
        provider_config = self.get_provider_config(provider_name)
        pricing = provider_config.get('pricing', {})
        
        if model not in pricing:
            logger.warning(f"No pricing found for model: {model}, using default")
            return {"input": 0.0, "output": 0.0}
        
        return pricing[model]
    
    # ===== Path Settings =====
    
    def get_path_settings(self, path: str) -> Dict[str, Any]:
        """
        Get settings for a specific path.
        
        Args:
            path: Path name (fast, standard, agentic)
            
        Returns:
            Path settings dict with temperature, max_tokens, etc.
        """
        path_settings = self._config.get('path_settings', {})
        
        if path not in path_settings:
            raise ValueError(f"No settings found for path: {path}")
        
        return path_settings[path]
    
    # ===== Retry Configuration =====
    
    @property
    def retry_config(self) -> Dict[str, Any]:
        """Get retry configuration."""
        return self._config.get('retry', {
            'max_attempts': 3,
            'initial_delay_seconds': 1,
            'max_delay_seconds': 10,
            'exponential_base': 2
        })
    
    # ===== Cache Configuration =====
    
    @property
    def cache_config(self) -> Dict[str, Any]:
        """Get cache configuration."""
        return self._config.get('cache', {})
    
    # ===== Profile Management =====
    
    @property
    def profiles_config(self) -> Dict[str, Any]:
        """Get profile management configuration."""
        return self._config.get('profiles', {})
    
    @property
    def profiles_directory(self) -> Path:
        """Get path to executive profiles directory."""
        profiles_dir = self.profiles_config.get('directory', 'test_data/executive_profiles')
        return Path(__file__).parent.parent / profiles_dir
    
    # ===== Logging =====
    
    @property
    def logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self._config.get('logging', {})
    
    # ===== Utility Methods =====
    
    def estimate_cost(self, 
                     input_tokens: int, 
                     output_tokens: int, 
                     model: str,
                     provider_name: Optional[str] = None) -> float:
        """
        Estimate cost for a request in USD.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name
            provider_name: Provider name, defaults to active provider
            
        Returns:
            Estimated cost in USD
        """
        pricing = self.get_pricing(model, provider_name)
        
        input_cost = (input_tokens / 1_000_000) * pricing['input']
        output_cost = (output_tokens / 1_000_000) * pricing['output']
        
        return input_cost + output_cost
    
    def get_all_models(self, provider_name: Optional[str] = None) -> Dict[str, str]:
        """
        Get all model mappings for a provider.
        
        Args:
            provider_name: Provider name, defaults to active provider
            
        Returns:
            Dict mapping path names to model names
        """
        provider_config = self.get_provider_config(provider_name)
        return provider_config.get('models', {})


# Global singleton instance
_config = LLMConfig()


def get_config() -> LLMConfig:
    """Get the singleton configuration instance."""
    return _config
