"""
API Configuration
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from dotenv import load_dotenv

# Load .env file from project root (ai officer/.env)
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseSettings):
    """API configuration settings"""
    
    # API Metadata
    APP_NAME: str = "AI Officer RAG API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Executive Decision Intelligence System - Retrieval API"
    
    # Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # PostgreSQL Configuration
    POSTGRES_DB: str = "ai_officer"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres123"
    POSTGRES_HOST: str = "localhost" 
    POSTGRES_PORT: str = "5432"
    
    # Neo4j Configuration
    NEO4J_URI: str = "bolt://localhost:7687" 
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j123"
    NEO4J_HTTP_PORT: str = "7474"
    NEO4J_BOLT_PORT: str = "7687"
    
    # LLM Provider Configuration (at least one required)
    OPENAI_API_KEY: str = ""  # Optional
    GLM_API_KEY: str = ""  # Optional
    GEMINI_API_KEY: str = ""  # Optional
    GROQ_API_KEY: str = ""  # Optional
    LLM_PROVIDER: str = "groq"  # Default provider: openai, glm, gemini, or groq
    
    # Redis Configuration (optional)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: str = "6379"
    REDIS_DB: str = "0"
    REDIS_PASSWORD: str = ""
    
    # Cache Configuration
    CACHE_ENABLED: bool = True
    SEMANTIC_QUERY_CACHE_ENABLED: bool = True
    EMBEDDING_CACHE_ENABLED: bool = True
    SYSTEM_PROMPT_CACHE_ENABLED: bool = True
    CACHE_MONITORING_ENABLED: bool = True
    
    # Response Formatting Configuration
    CITATION_STYLE: str = "inline"  # inline, footnote, none
    CITATION_VALIDATION_ENABLED: bool = True
    CITATION_CONFIDENCE_THRESHOLD: float = 0.7

    # Dual-Stream Architecture Configuration
    DUAL_STREAM_ENABLED: bool = False  # DISABLED - Preparing for LangGraph/LangSmith observability
    DUAL_STREAM_ROLLOUT_PERCENTAGE: int = 0  # Disabled for baseline testing

    # =========================================================================
    # Conversation Engine Configuration
    # =========================================================================
    # Master toggle - when False, uses legacy prompt builders
    USE_CONVERSATION_ENGINE: bool = True  # Enable full 5-stage pipeline

    # Gradual rollout percentage (0-100)
    # Allows A/B testing by routing X% of requests to new engine
    CONVERSATION_ENGINE_ROLLOUT_PERCENT: int = 100  # Full rollout

    # Fallback behavior - if True, falls back to legacy on engine errors
    CONVERSATION_ENGINE_FALLBACK_ON_ERROR: bool = True

    # Session Configuration
    CONVERSATION_SESSION_TIMEOUT_MINUTES: int = 30  # Session idle timeout
    CONVERSATION_MAX_TURNS: int = 10  # Max turns to keep in history
    CONVERSATION_MAX_FACTS: int = 50  # Max facts to track for repetition avoidance
    CONVERSATION_MAX_ENTITIES: int = 30  # Max entities to track mentions
    CONVERSATION_MAX_TOPICS: int = 20  # Max topics in history

    # Embedding Configuration (for semantic example matching)
    CONVERSATION_EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"  # Fast, ~35ms
    CONVERSATION_EXAMPLE_MATCH_THRESHOLD: float = 0.6  # Min similarity for good match

    # Token Budgets per path
    CONVERSATION_TOKEN_BUDGET_FAST: int = 350
    CONVERSATION_TOKEN_BUDGET_STANDARD: int = 500
    CONVERSATION_TOKEN_BUDGET_AGENTIC: int = 650

    # =========================================================================
    # Attention Mechanism Configuration
    # =========================================================================
    # Master toggle for semantic attention refinement
    CONVERSATION_ENGINE_ATTENTION_ENABLED: bool = True

    # A/B testing rollout percentage (0-100)
    # Allows measuring impact by routing X% of requests to attention-enabled path
    ATTENTION_ROLLOUT_PERCENT: int = 100  # Start at 100% for initial deployment

    # Attention blend configuration
    ATTENTION_PATTERN_WEIGHT: float = 0.6  # Weight for pattern-based attention
    ATTENTION_SEMANTIC_WEIGHT: float = 0.4  # Weight for semantic refinement
    ATTENTION_TEMPERATURE: float = 0.5  # Softmax temperature

    # Weight sharpening to prevent over-smoothing
    ATTENTION_SHARPENING_ENABLED: bool = True
    ATTENTION_SHARPEN_THRESHOLD: float = 0.08  # Weights above this get sharpened
    ATTENTION_SHARPEN_MULTIPLIER: float = 1.4  # Boost factor for high weights
    ATTENTION_SHARPEN_CAP: float = 0.35  # Maximum weight after sharpening

    # CORS — controlled via CORS_ORIGINS env var (comma-separated).
    # Defaults to common dev origins. Set CORS_ORIGINS="*" in .env only if needed.
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:3003",  # Recall Service
        "http://localhost:3004",  # Avatar Interface
        "http://firstweek-frontend:5173",  # Frontend container (Docker)
        "http://frontend:5173",  # Frontend container (Docker alternate)
    ]
    
    # Rate Limiting (for future implementation)
    RATE_LIMIT_PER_MINUTE: int = 60
    
    # Timeouts
    REQUEST_TIMEOUT_SECONDS: int = 30
    
    model_config = SettingsConfigDict(
        # Look for .env in parent directory (project root) for consolidated config
        env_file=str(Path(__file__).parent.parent.parent / ".env"),
        case_sensitive=True,
        extra="ignore"  # Ignore extra environment variables
    )


# Global settings instance
settings = Settings()


def should_use_conversation_engine(request_id: str = None) -> bool:
    """
    Determine if ConversationEngine should be used for this request.

    Uses rollout percentage for gradual rollout:
    - If USE_CONVERSATION_ENGINE is False, always returns False
    - If rollout is 100%, always returns True
    - Otherwise, uses request_id hash to deterministically route

    Args:
        request_id: Optional request ID for deterministic routing

    Returns:
        True if ConversationEngine should be used
    """
    if not settings.USE_CONVERSATION_ENGINE:
        return False

    if settings.CONVERSATION_ENGINE_ROLLOUT_PERCENT >= 100:
        return True

    if settings.CONVERSATION_ENGINE_ROLLOUT_PERCENT <= 0:
        return False

    # Use hash of request_id for deterministic routing
    if request_id:
        hash_value = hash(request_id) % 100
        return hash_value < settings.CONVERSATION_ENGINE_ROLLOUT_PERCENT

    # Random fallback if no request_id
    import random
    return random.randint(0, 99) < settings.CONVERSATION_ENGINE_ROLLOUT_PERCENT


def should_use_attention(request_id: str = None) -> bool:
    """
    Determine if attention mechanism should be used for this request.

    Uses rollout percentage for A/B testing:
    - If CONVERSATION_ENGINE_ATTENTION_ENABLED is False, always returns False
    - If rollout is 100%, always returns True
    - Otherwise, uses request_id hash to deterministically route

    Args:
        request_id: Optional request ID for deterministic routing

    Returns:
        True if attention mechanism should be used
    """
    if not settings.CONVERSATION_ENGINE_ATTENTION_ENABLED:
        return False

    if settings.ATTENTION_ROLLOUT_PERCENT >= 100:
        return True

    if settings.ATTENTION_ROLLOUT_PERCENT <= 0:
        return False

    # Use hash of request_id for deterministic routing
    if request_id:
        hash_value = hash(request_id) % 100
        return hash_value < settings.ATTENTION_ROLLOUT_PERCENT

    # Random fallback if no request_id
    import random
    return random.randint(0, 99) < settings.ATTENTION_ROLLOUT_PERCENT


def get_attention_config() -> dict:
    """
    Get attention mechanism configuration for creating SemanticAttention instance.

    Returns:
        dict with attention configuration parameters
    """
    return {
        "pattern_weight": settings.ATTENTION_PATTERN_WEIGHT,
        "semantic_weight": settings.ATTENTION_SEMANTIC_WEIGHT,
        "temperature": settings.ATTENTION_TEMPERATURE,
        "enable_sharpening": settings.ATTENTION_SHARPENING_ENABLED,
        "sharpen_threshold": settings.ATTENTION_SHARPEN_THRESHOLD,
        "sharpen_multiplier": settings.ATTENTION_SHARPEN_MULTIPLIER,
        "sharpen_cap": settings.ATTENTION_SHARPEN_CAP,
    }
