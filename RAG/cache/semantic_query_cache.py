"""
Level 1: Semantic Query Cache
============================

Redis-based cache for semantic query results with 1-hour TTL.

Features:
- Semantic-aware cache key generation
- User context and RBAC-aware caching
- Version-aware invalidation
- Performance monitoring and metrics
- Hit rate targeting 85%
- Latency savings targeting 80%

Author: AI Officer Implementation Team
Date: 2025-10-30
"""

import json
import hashlib
import time
import logging
import pickle
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from .config import SEMANTIC_QUERY_CACHE_CONFIG, REDIS_CONFIG, CACHE_MONITORING_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    data: Dict[str, Any]
    timestamp: float
    ttl_seconds: int
    query_hash: str
    user_context: Dict[str, Any]
    metadata: Dict[str, Any]


@dataclass
class CacheMetrics:
    """Cache performance metrics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    errors: int = 0
    total_get_time_ms: float = 0.0
    total_set_time_ms: float = 0.0
    
    @property
    def hit_rate(self) -> float:
        """Calculate hit rate"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
    
    @property
    def avg_get_time_ms(self) -> float:
        """Calculate average get time"""
        return self.total_get_time_ms / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0.0
    
    @property
    def avg_set_time_ms(self) -> float:
        """Calculate average set time"""
        return self.total_set_time_ms / self.sets if self.sets > 0 else 0.0


class SemanticQueryCache:
    """
    Level 1 cache for semantic query results
    
    Caches complete query results including:
    - Vector search results
    - Graph context results
    - Memory search results
    - Fused and reranked results
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize semantic query cache
        
        Args:
            redis_client: Optional Redis client (for testing/injection)
        """
        self.config = SEMANTIC_QUERY_CACHE_CONFIG
        self.redis_config = REDIS_CONFIG
        self.monitoring_config = CACHE_MONITORING_CONFIG
        
        # Initialize Redis client
        self._redis_client = redis_client
        if not self._redis_client and self.config['enabled']:
            self._init_redis()
        
        # Metrics tracking
        self.metrics = CacheMetrics()
        self._last_metrics_reset = time.time()
        
        # Cache key components
        self.key_prefix = self.config['key_prefix']
        
        logger.info(f"SemanticQueryCache initialized (enabled={self.config['enabled']})")
    
    def _init_redis(self):
        """Initialize Redis connection"""
        try:
            import redis
            self._redis_client = redis.Redis(
                host=self.redis_config['host'],
                port=self.redis_config['port'],
                db=self.redis_config['db'],
                password=self.redis_config['password'],
                decode_responses=False,
                socket_timeout=self.redis_config['socket_timeout'],
                socket_connect_timeout=self.redis_config['socket_connect_timeout'],
                retry_on_timeout=self.redis_config['retry_on_timeout'],
                health_check_interval=self.redis_config['health_check_interval'],
                max_connections=self.redis_config['max_connections']
            )
            # Test connection
            self._redis_client.ping()
            logger.info("SemanticQueryCache: Redis connection established")
        except Exception as e:
            logger.error(f"SemanticQueryCache: Failed to connect to Redis: {e}")
            self._redis_client = None
            self.config['enabled'] = False
    
    def get(self, query: str, user_context: Dict[str, Any], 
            executive_id: str, path: str = None) -> Optional[Dict[str, Any]]:
        """
        Get cached query result
        
        Args:
            query: User query
            user_context: User context (role, scopes, etc.)
            executive_id: Executive profile ID
            path: Processing path (fast/standard/agentic)
            
        Returns:
            Cached result or None
        """
        if not self.config['enabled'] or not self._redis_client:
            self.metrics.misses += 1
            return None
        
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(query, user_context, executive_id, path)
            
            # Get from Redis
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                # Deserialize cache entry
                cache_entry = pickle.loads(cached_data)
                
                # Check if expired (double-check TTL)
                if time.time() - cache_entry.timestamp < cache_entry.ttl_seconds:
                    self.metrics.hits += 1
                    self.metrics.total_get_time_ms += (time.time() - start_time) * 1000
                    
                    logger.debug(f"SemanticQueryCache HIT: {cache_key[:32]}...")
                    return cache_entry.data
                else:
                    # Expired, remove
                    self._redis_client.delete(cache_key)
                    logger.debug(f"SemanticQueryCache EXPIRED: {cache_key[:32]}...")
            
            self.metrics.misses += 1
            self.metrics.total_get_time_ms += (time.time() - start_time) * 1000
            
            if self.monitoring_config['log_cache_misses']:
                logger.debug(f"SemanticQueryCache MISS: {cache_key[:32]}...")
            
            return None
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"SemanticQueryCache get error: {e}")
            return None
    
    def set(self, query: str, user_context: Dict[str, Any], 
            executive_id: str, result: Dict[str, Any], 
            path: str = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache query result
        
        Args:
            query: User query
            user_context: User context
            executive_id: Executive profile ID
            result: Query result to cache
            path: Processing path
            metadata: Additional metadata
            
        Returns:
            True if cached successfully
        """
        if not self.config['enabled'] or not self._redis_client:
            return False
        
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(query, user_context, executive_id, path)
            
            # Create cache entry
            cache_entry = CacheEntry(
                data=result,
                timestamp=time.time(),
                ttl_seconds=self.config['ttl_seconds'],
                query_hash=self._hash_query(query),
                user_context=user_context,
                metadata=metadata or {}
            )
            
            # Serialize and store
            serialized_data = pickle.dumps(cache_entry)
            
            # Store with TTL
            success = self._redis_client.setex(
                cache_key,
                self.config['ttl_seconds'],
                serialized_data
            )
            
            if success:
                self.metrics.sets += 1
                self.metrics.total_set_time_ms += (time.time() - start_time) * 1000
                
                # Check cache size and evict if necessary
                self._check_cache_size()
                
                logger.debug(f"SemanticQueryCache SET: {cache_key[:32]}...")
                return True
            else:
                logger.warning(f"SemanticQueryCache SET failed: {cache_key[:32]}...")
                return False
                
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"SemanticQueryCache set error: {e}")
            return False
    
    def invalidate(self, pattern: str = None) -> int:
        """
        Invalidate cache entries
        
        Args:
            pattern: Pattern to match (default: all entries)
            
        Returns:
            Number of entries invalidated
        """
        if not self.config['enabled'] or not self._redis_client:
            return 0
        
        try:
            if pattern is None:
                pattern = f"{self.key_prefix}*"
            
            # Find matching keys
            keys = self._redis_client.keys(pattern)
            
            if keys:
                # Delete keys
                deleted = self._redis_client.delete(*keys)
                self.metrics.evictions += deleted
                logger.info(f"SemanticQueryCache invalidated {deleted} entries matching {pattern}")
                return deleted
            
            return 0
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"SemanticQueryCache invalidate error: {e}")
            return 0
    
    def invalidate_by_executive(self, executive_id: str) -> int:
        """
        Invalidate all cache entries for a specific executive
        
        Args:
            executive_id: Executive profile ID
            
        Returns:
            Number of entries invalidated
        """
        pattern = f"{self.key_prefix}*exec:{executive_id}:*"
        return self.invalidate(pattern)
    
    def invalidate_by_user_role(self, user_role: str) -> int:
        """
        Invalidate all cache entries for a specific user role
        
        Args:
            user_role: User role
            
        Returns:
            Number of entries invalidated
        """
        pattern = f"{self.key_prefix}*role:{user_role}:*"
        return self.invalidate(pattern)
    
    def _generate_cache_key(self, query: str, user_context: Dict[str, Any], 
                           executive_id: str, path: str = None) -> str:
        """
        Generate cache key from query and context
        
        Key format: semantic_query:{hash}:{user_id}:{role}:{exec}:{path}
        """
        # Normalize query
        normalized_query = query.lower().strip()
        
        # Build key components
        components = {
            'query': self._hash_query(normalized_query),
        }
        
        # Add user context if enabled
        if self.config['include_user_context']:
            components['user_id'] = user_context.get('user_id', 'unknown')
            components['role'] = user_context.get('role', 'employee')
        
        # Add executive context if enabled
        if self.config['include_executive_context']:
            components['exec'] = executive_id
        
        # Add company context for tenant isolation
        components['company'] = user_context.get('company_id', 'unknown')

        # Add RBAC scopes if enabled
        if self.config['include_rbac_scopes']:
            scopes = user_context.get('allowed_scopes', [])
            components['scopes'] = ','.join(sorted(scopes))
        
        # Add path if provided
        if path:
            components['path'] = path
        
        # Create key string
        key_parts = [self.key_prefix]
        for k, v in components.items():
            key_parts.append(f"{k}:{v}")
        
        cache_key = ':'.join(key_parts)
        return cache_key
    
    def _hash_query(self, query: str) -> str:
        """
        Hash query for cache key
        
        Args:
            query: Query string
            
        Returns:
            SHA256 hash
        """
        return hashlib.sha256(query.encode('utf-8')).hexdigest()[:16]
    
    def _check_cache_size(self):
        """Check cache size and evict if necessary"""
        try:
            # Get current cache size
            pattern = f"{self.key_prefix}*"
            keys = self._redis_client.keys(pattern)
            current_size = len(keys)
            
            # Evict if over limit
            if current_size > self.config['max_entries']:
                # Get oldest keys (by TTL)
                oldest_keys = sorted(keys, key=lambda k: self._redis_client.ttl(k))[:100]
                
                if oldest_keys:
                    deleted = self._redis_client.delete(*oldest_keys)
                    self.metrics.evictions += deleted
                    logger.info(f"SemanticQueryCache evicted {deleted} old entries")
        
        except Exception as e:
            logger.error(f"SemanticQueryCache size check error: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get cache performance metrics
        
        Returns:
            Metrics dictionary
        """
        current_time = time.time()
        uptime_hours = (current_time - self._last_metrics_reset) / 3600
        
        metrics_dict = asdict(self.metrics)
        metrics_dict.update({
            'hit_rate': self.metrics.hit_rate,
            'avg_get_time_ms': self.metrics.avg_get_time_ms,
            'avg_set_time_ms': self.metrics.avg_set_time_ms,
            'uptime_hours': uptime_hours,
            'target_hit_rate': self.config['target_hit_rate'],
            'target_latency_savings': self.config['target_latency_savings'],
            'enabled': self.config['enabled'],
        })
        
        return metrics_dict
    
    def reset_metrics(self):
        """Reset metrics"""
        self.metrics = CacheMetrics()
        self._last_metrics_reset = time.time()
        logger.info("SemanticQueryCache metrics reset")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check
        
        Returns:
            Health status
        """
        health = {
            'status': 'healthy',
            'redis_connected': False,
            'cache_enabled': self.config['enabled'],
            'issues': []
        }
        
        if not self.config['enabled']:
            health['status'] = 'disabled'
            return health
        
        try:
            if self._redis_client:
                # Test Redis connection
                self._redis_client.ping()
                health['redis_connected'] = True
                
                # Check hit rate
                if self.metrics.hit_rate < self.config['target_hit_rate'] * 0.5:
                    health['issues'].append(f"Low hit rate: {self.metrics.hit_rate:.2%}")
                
                # Check error rate
                total_ops = self.metrics.hits + self.metrics.misses + self.metrics.sets
                if total_ops > 0 and self.metrics.errors / total_ops > 0.05:
                    health['issues'].append(f"High error rate: {self.metrics.errors/total_ops:.2%}")
                
                if health['issues']:
                    health['status'] = 'degraded'
            else:
                health['status'] = 'unhealthy'
                health['issues'].append('Redis client not initialized')
        
        except Exception as e:
            health['status'] = 'unhealthy'
            health['issues'].append(f'Redis connection error: {e}')
        
        return health


__all__ = ['SemanticQueryCache', 'CacheEntry', 'CacheMetrics']