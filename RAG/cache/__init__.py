"""
Cache Module - Three-Level Caching Strategy
========================================

Comprehensive caching system for AI Officer RAG with three levels:

Level 1: Semantic Query Cache (Redis) - 1-hour TTL
- Caches complete query results including vector search, graph context, and memory
- Semantic-aware cache key generation with user context and RBAC
- Target hit rate: 85%, Latency savings: 80%

Level 2: Embedding Cache (Redis) - 7-day TTL
- Separate caches for query and document embeddings
- Compression for memory efficiency
- Batch operations for performance
- Target hit rate: 70%, Latency savings: 75%

Level 3: System Prompt Cache (Redis) - Version-aware invalidation
- Profile-based and path-specific prompt caching
- Version-aware invalidation for prompt updates
- Context-aware prompt generation
- Target hit rate: 90%, Latency savings: 95%

Usage:
    from cache import CacheManager
    
    # Initialize cache manager
    cache_manager = CacheManager()
    
    # Check cache health
    health = cache_manager.health_check()
    
    # Get cached query result
    result = cache_manager.get_query_result(query, user_context, executive_id)
    
    # Cache query result
    cache_manager.set_query_result(query, user_context, executive_id, result)
    
    # Get metrics
    metrics = cache_manager.get_metrics()

Author: AI Officer Implementation Team
Date: 2025-10-30
"""

from .config import (
    REDIS_CONFIG,
    SEMANTIC_QUERY_CACHE_CONFIG,
    EMBEDDING_CACHE_CONFIG,
    SYSTEM_PROMPT_CACHE_CONFIG,
    CACHE_MONITORING_CONFIG,
    CACHE_PERFORMANCE_CONFIG,
    CACHE_INTEGRATION_CONFIG,
    CACHE_CONFIG,
    validate_cache_config,
    get_cache_config_summary
)

from .semantic_query_cache import (
    SemanticQueryCache,
    CacheEntry,
    CacheMetrics
)

from .embedding_cache import (
    EmbeddingCache,
    EmbeddingCacheEntry,
    EmbeddingCacheMetrics
)

from .system_prompt_cache import (
    SystemPromptCache,
    SystemPromptEntry,
    SystemPromptMetrics
)

from .cache_manager import (
    CacheManager,
    CacheManagerMetrics
)
from .monitoring import (
    CacheMonitor,
    CacheMetricsCollector,
    Alert,
    MonitoringReport,
    create_cache_monitor,
    create_metrics_collector,
    log_alert_callback,
    email_alert_callback
)

# Version information
__version__ = "1.0.0"
__author__ = "AI Officer Implementation Team"

# Export main classes and functions
__all__ = [
    # Main cache manager
    'CacheManager',
    'CacheManagerMetrics',
    
    # Individual cache levels
    'SemanticQueryCache',
    'EmbeddingCache',
    'SystemPromptCache',
    
    # Cache entry and metrics classes
    'CacheEntry',
    'CacheMetrics',
    'EmbeddingCacheEntry',
    'EmbeddingCacheMetrics',
    'SystemPromptEntry',
    'SystemPromptMetrics',
    
    # Configuration
    'REDIS_CONFIG',
    'SEMANTIC_QUERY_CACHE_CONFIG',
    'EMBEDDING_CACHE_CONFIG',
    'SYSTEM_PROMPT_CACHE_CONFIG',
    'CACHE_MONITORING_CONFIG',
    'CACHE_PERFORMANCE_CONFIG',
    'CACHE_INTEGRATION_CONFIG',
    'CACHE_CONFIG',
    'validate_cache_config',
    'get_cache_config_summary',
    
    # Monitoring
    'CacheMonitor',
    'CacheMetricsCollector',
    'Alert',
    'MonitoringReport',
    'create_cache_monitor',
    'create_metrics_collector',
    'log_alert_callback',
    'email_alert_callback',
    
    # Module info
    '__version__',
    '__author__'
]

# Convenience function for quick initialization
def create_cache_manager(redis_client=None) -> CacheManager:
    """
    Create and initialize a cache manager
    
    Args:
        redis_client: Optional Redis client (for testing/injection)
        
    Returns:
        Initialized CacheManager instance
    """
    return CacheManager(redis_client)

# Convenience function for health check
def check_cache_health(redis_client=None) -> dict:
    """
    Perform health check on all cache levels
    
    Args:
        redis_client: Optional Redis client (for testing/injection)
        
    Returns:
        Health status dictionary
    """
    cache_manager = create_cache_manager(redis_client)
    return cache_manager.health_check()

# Convenience function for getting metrics
def get_cache_metrics(redis_client=None) -> dict:
    """
    Get comprehensive cache metrics
    
    Args:
        redis_client: Optional Redis client (for testing/injection)
        
    Returns:
        Metrics dictionary
    """
    cache_manager = create_cache_manager(redis_client)
    return cache_manager.get_metrics()