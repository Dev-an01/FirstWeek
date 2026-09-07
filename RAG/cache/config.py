"""
Cache Configuration for Three-Level Caching Strategy
===================================================

Configuration for the comprehensive caching system according to Solution Manual specifications:

Level 1: Semantic Query Cache (Redis) - 1-hour TTL
Level 2: Embedding Cache (Redis) - 7-day TTL for queries and documents
Level 3: System Prompt Cache (Redis) - Version-aware invalidation

Performance Targets:
- Hit Rate: 85% for L1, 70% for L2, 90% for L3
- Latency Savings: 80% on cache hits
- Memory Usage: < 2GB total
"""

import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from project root (ai officer/.env)
load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ============================================================================
# REDIS CONFIGURATION
# ============================================================================

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', 'localhost'),
    'port': int(os.getenv('REDIS_PORT', '6379')),
    'db': int(os.getenv('REDIS_DB', '0')),
    'password': os.getenv('REDIS_PASSWORD'),
    'decode_responses': False,  # We'll handle encoding/decoding
    'socket_timeout': int(os.getenv('REDIS_SOCKET_TIMEOUT', '5')),
    'socket_connect_timeout': int(os.getenv('REDIS_CONNECT_TIMEOUT', '5')),
    'max_connections': int(os.getenv('REDIS_MAX_CONNECTIONS', '20')),
    'retry_on_timeout': True,
    'health_check_interval': 30,
}

# ============================================================================
# LEVEL 1: SEMANTIC QUERY CACHE CONFIGURATION
# ============================================================================

SEMANTIC_QUERY_CACHE_CONFIG = {
    # Cache settings
    'enabled': os.getenv('SEMANTIC_QUERY_CACHE_ENABLED', 'true').lower() == 'true',
    'ttl_seconds': int(os.getenv('SEMANTIC_QUERY_CACHE_TTL', '3600')),  # 1 hour
    'max_entries': int(os.getenv('SEMANTIC_QUERY_CACHE_MAX_ENTRIES', '10000')),
    
    # Key generation
    'key_prefix': 'semantic_query:',
    'include_user_context': True,
    'include_executive_context': True,
    'include_rbac_scopes': True,
    
    # Performance targets
    'target_hit_rate': 0.85,  # 85% hit rate
    'target_latency_savings': 0.80,  # 80% latency reduction
    
    # Cache invalidation
    'invalidate_on_data_update': True,
    'invalidate_on_profile_change': True,
    
    # Monitoring
    'track_access_patterns': True,
    'log_cache_misses': True,
}

# ============================================================================
# LEVEL 2: EMBEDDING CACHE CONFIGURATION
# ============================================================================

EMBEDDING_CACHE_CONFIG = {
    # Query embeddings cache
    'query_cache': {
        'enabled': os.getenv('EMBEDDING_QUERY_CACHE_ENABLED', 'true').lower() == 'true',
        'ttl_seconds': int(os.getenv('EMBEDDING_QUERY_CACHE_TTL', '604800')),  # 7 days
        'max_entries': int(os.getenv('EMBEDDING_QUERY_CACHE_MAX_ENTRIES', '50000')),
        'key_prefix': 'embed_query:',
    },
    
    # Document embeddings cache
    'document_cache': {
        'enabled': os.getenv('EMBEDDING_DOCUMENT_CACHE_ENABLED', 'true').lower() == 'true',
        'ttl_seconds': int(os.getenv('EMBEDDING_DOCUMENT_CACHE_TTL', '604800')),  # 7 days
        'max_entries': int(os.getenv('EMBEDDING_DOCUMENT_CACHE_MAX_ENTRIES', '100000')),
        'key_prefix': 'embed_doc:',
    },
    
    # Performance targets
    'target_hit_rate': 0.70,  # 70% hit rate
    'target_latency_savings': 0.75,  # 75% latency reduction
    
    # Cache warming
    'warm_popular_queries': True,
    'warm_document_embeddings': True,
    
    # Compression
    'compress_embeddings': True,
    'compression_level': 6,  # zlib compression level
}

# ============================================================================
# LEVEL 3: SYSTEM PROMPT CACHE CONFIGURATION
# ============================================================================

SYSTEM_PROMPT_CACHE_CONFIG = {
    # Cache settings
    'enabled': os.getenv('SYSTEM_PROMPT_CACHE_ENABLED', 'true').lower() == 'true',
    'ttl_seconds': int(os.getenv('SYSTEM_PROMPT_CACHE_TTL', '86400')),  # 24 hours default
    'max_entries': int(os.getenv('SYSTEM_PROMPT_CACHE_MAX_ENTRIES', '1000')),
    'key_prefix': 'sys_prompt:',
    
    # Version-aware invalidation
    'version_aware': True,
    'current_version': os.getenv('SYSTEM_PROMPT_VERSION', '1.0.0'),
    'version_key': 'system_prompt_version',
    
    # Cache keys
    'profile_based': True,
    'path_based': True,
    'context_based': True,
    
    # Performance targets
    'target_hit_rate': 0.90,  # 90% hit rate
    'target_latency_savings': 0.95,  # 95% latency reduction
    
    # Invalidation triggers
    'invalidate_on_version_change': True,
    'invalidate_on_profile_update': True,
    'invalidate_on_config_change': True,
}

# ============================================================================
# CACHE MONITORING CONFIGURATION
# ============================================================================

CACHE_MONITORING_CONFIG = {
    'enabled': os.getenv('CACHE_MONITORING_ENABLED', 'true').lower() == 'true',
    
    # Metrics collection
    'collect_hit_rates': True,
    'collect_latency_metrics': True,
    'collect_memory_usage': True,
    'collect_key_patterns': True,
    
    # Alerting thresholds
    'hit_rate_alert_threshold': 0.50,  # Alert if hit rate drops below 50%
    'latency_alert_threshold_ms': 100,  # Alert if cache latency exceeds 100ms
    'memory_alert_threshold_gb': 1.5,  # Alert if memory usage exceeds 1.5GB
    
    # Reporting
    'metrics_report_interval_seconds': int(os.getenv('CACHE_METRICS_INTERVAL', '300')),  # 5 minutes
    'detailed_logging': os.getenv('CACHE_DETAILED_LOGGING', 'false').lower() == 'true',
}

# ============================================================================
# CACHE PERFORMANCE CONFIGURATION
# ============================================================================

CACHE_PERFORMANCE_CONFIG = {
    # Connection pooling
    'connection_pool_size': int(os.getenv('CACHE_POOL_SIZE', '10')),
    'connection_pool_max': int(os.getenv('CACHE_POOL_MAX', '20')),
    
    # Batch operations
    'batch_get_size': int(os.getenv('CACHE_BATCH_SIZE', '100')),
    'batch_set_size': int(os.getenv('CACHE_BATCH_SIZE', '100')),
    
    # Async operations
    'async_operations': True,
    'async_timeout_seconds': int(os.getenv('CACHE_ASYNC_TIMEOUT', '10')),
    
    # Fallback behavior
    'fallback_on_error': True,
    'fallback_cache_type': 'memory',  # memory or none
    
    # Cache warming
    'warmup_enabled': os.getenv('CACHE_WARMUP_ENABLED', 'true').lower() == 'true',
    'warmup_concurrency': int(os.getenv('CACHE_WARMUP_CONCURRENCY', '5')),
}

# ============================================================================
# INTEGRATION CONFIGURATION
# ============================================================================

CACHE_INTEGRATION_CONFIG = {
    # Integration with existing systems
    'integrate_with_query_routing': True,
    'integrate_with_hybrid_retrieval': True,
    'integrate_with_llm_integration': True,
    
    # Cache coordination
    'coordinate_between_levels': True,
    'propagate_invalidation': True,
    
    # API integration
    'api_cache_headers': True,
    'api_cache_control': 'max-age=3600',  # 1 hour for API responses
    
    # Debugging
    'debug_mode': os.getenv('CACHE_DEBUG_MODE', 'false').lower() == 'true',
    'trace_cache_operations': os.getenv('CACHE_TRACE_OPERATIONS', 'false').lower() == 'true',
}

# ============================================================================
# COMBINED CONFIGURATION
# ============================================================================

CACHE_CONFIG = {
    'redis': REDIS_CONFIG,
    'semantic_query': SEMANTIC_QUERY_CACHE_CONFIG,
    'embedding': EMBEDDING_CACHE_CONFIG,
    'system_prompt': SYSTEM_PROMPT_CACHE_CONFIG,
    'monitoring': CACHE_MONITORING_CONFIG,
    'performance': CACHE_PERFORMANCE_CONFIG,
    'integration': CACHE_INTEGRATION_CONFIG,
}

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_cache_config() -> Dict[str, Any]:
    """
    Validate cache configuration and return validation report
    
    Returns:
        Dict with validation results
    """
    validation_results = {
        'valid': True,
        'errors': [],
        'warnings': []
    }
    
    # Check Redis configuration
    if not REDIS_CONFIG.get('host'):
        validation_results['errors'].append('Redis host not configured')
        validation_results['valid'] = False
    
    # Check TTL values
    if SEMANTIC_QUERY_CACHE_CONFIG['ttl_seconds'] <= 0:
        validation_results['errors'].append('Semantic query cache TTL must be positive')
        validation_results['valid'] = False
    
    if EMBEDDING_CACHE_CONFIG['query_cache']['ttl_seconds'] <= 0:
        validation_results['errors'].append('Embedding query cache TTL must be positive')
        validation_results['valid'] = False
    
    # Check performance targets
    if SEMANTIC_QUERY_CACHE_CONFIG['target_hit_rate'] > 1.0:
        validation_results['warnings'].append('Semantic query cache hit rate target exceeds 100%')
    
    # Check memory limits
    total_max_entries = (
        SEMANTIC_QUERY_CACHE_CONFIG['max_entries'] +
        EMBEDDING_CACHE_CONFIG['query_cache']['max_entries'] +
        EMBEDDING_CACHE_CONFIG['document_cache']['max_entries'] +
        SYSTEM_PROMPT_CACHE_CONFIG['max_entries']
    )
    
    if total_max_entries > 500000:  # 500k entries
        validation_results['warnings'].append(f'Total cache entries ({total_max_entries}) may exceed memory limits')
    
    return validation_results

def get_cache_config_summary() -> Dict[str, Any]:
    """
    Get a summary of cache configuration for monitoring
    
    Returns:
        Dict with configuration summary
    """
    return {
        'semantic_query_cache': {
            'enabled': SEMANTIC_QUERY_CACHE_CONFIG['enabled'],
            'ttl_hours': SEMANTIC_QUERY_CACHE_CONFIG['ttl_seconds'] / 3600,
            'max_entries': SEMANTIC_QUERY_CACHE_CONFIG['max_entries'],
            'target_hit_rate': SEMANTIC_QUERY_CACHE_CONFIG['target_hit_rate'],
        },
        'embedding_cache': {
            'query_enabled': EMBEDDING_CACHE_CONFIG['query_cache']['enabled'],
            'document_enabled': EMBEDDING_CACHE_CONFIG['document_cache']['enabled'],
            'ttl_days': EMBEDDING_CACHE_CONFIG['query_cache']['ttl_seconds'] / 86400,
            'max_query_entries': EMBEDDING_CACHE_CONFIG['query_cache']['max_entries'],
            'max_document_entries': EMBEDDING_CACHE_CONFIG['document_cache']['max_entries'],
            'target_hit_rate': EMBEDDING_CACHE_CONFIG['target_hit_rate'],
        },
        'system_prompt_cache': {
            'enabled': SYSTEM_PROMPT_CACHE_CONFIG['enabled'],
            'ttl_hours': SYSTEM_PROMPT_CACHE_CONFIG['ttl_seconds'] / 3600,
            'max_entries': SYSTEM_PROMPT_CACHE_CONFIG['max_entries'],
            'target_hit_rate': SYSTEM_PROMPT_CACHE_CONFIG['target_hit_rate'],
            'version_aware': SYSTEM_PROMPT_CACHE_CONFIG['version_aware'],
            'current_version': SYSTEM_PROMPT_CACHE_CONFIG['current_version'],
        },
        'redis': {
            'host': REDIS_CONFIG['host'],
            'port': REDIS_CONFIG['port'],
            'db': REDIS_CONFIG['db'],
            'max_connections': REDIS_CONFIG['max_connections'],
        }
    }

# Export configurations
__all__ = [
    'REDIS_CONFIG',
    'SEMANTIC_QUERY_CACHE_CONFIG',
    'EMBEDDING_CACHE_CONFIG',
    'SYSTEM_PROMPT_CACHE_CONFIG',
    'CACHE_MONITORING_CONFIG',
    'CACHE_PERFORMANCE_CONFIG',
    'CACHE_INTEGRATION_CONFIG',
    'CACHE_CONFIG',
    'validate_cache_config',
    'get_cache_config_summary'
]