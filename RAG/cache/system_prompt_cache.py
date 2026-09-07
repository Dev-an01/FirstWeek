"""
Level 3: System Prompt Cache
============================

Redis-based cache for system prompts with version-aware invalidation.

Features:
- Version-aware cache invalidation
- Profile-based prompt caching
- Path-specific prompt optimization
- Context-aware prompt generation
- Hit rate targeting 90%
- Latency savings targeting 95%

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

from .config import SYSTEM_PROMPT_CACHE_CONFIG, REDIS_CONFIG, CACHE_MONITORING_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class SystemPromptEntry:
    """Cache entry for system prompts"""
    prompt: str
    timestamp: float
    ttl_seconds: int
    version: str
    profile_id: str
    path: str
    context_hash: str
    metadata: Dict[str, Any]


@dataclass
class SystemPromptMetrics:
    """Cache performance metrics for system prompts"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0
    version_invalidations: int = 0
    profile_invalidations: int = 0
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


class SystemPromptCache:
    """
    Level 3 cache for system prompts
    
    Caches system prompts based on:
    - Executive profile
    - Processing path (fast/standard/agentic)
    - Query context
    - System version
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize system prompt cache
        
        Args:
            redis_client: Optional Redis client (for testing/injection)
        """
        self.config = SYSTEM_PROMPT_CACHE_CONFIG
        self.redis_config = REDIS_CONFIG
        self.monitoring_config = CACHE_MONITORING_CONFIG
        
        # Initialize Redis client
        self._redis_client = redis_client
        if not self._redis_client and self.config['enabled']:
            self._init_redis()
        
        # Metrics tracking
        self.metrics = SystemPromptMetrics()
        self._last_metrics_reset = time.time()
        
        # Cache key components
        self.key_prefix = self.config['key_prefix']
        self.version_key = self.config['version_key']
        
        # Initialize current version
        self._current_version = self.config['current_version']
        self._initialize_version()
        
        logger.info(f"SystemPromptCache initialized (enabled={self.config['enabled']}, "
                   f"version={self._current_version})")
    
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
            logger.info("SystemPromptCache: Redis connection established")
        except Exception as e:
            logger.error(f"SystemPromptCache: Failed to connect to Redis: {e}")
            self._redis_client = None
            self.config['enabled'] = False
    
    def _initialize_version(self):
        """Initialize version tracking"""
        if not self.config['enabled'] or not self._redis_client:
            return
        
        try:
            # Get current version from Redis
            stored_version = self._redis_client.get(self.version_key)
            
            if stored_version:
                stored_version = stored_version.decode('utf-8')
                
                # Check if version changed
                if stored_version != self._current_version:
                    logger.info(f"SystemPromptCache version changed: {stored_version} -> {self._current_version}")
                    self._invalidate_all_for_version_change()
                    self.metrics.version_invalidations += 1
            else:
                # Set initial version
                self._redis_client.set(self.version_key, self._current_version.encode('utf-8'))
                logger.info(f"SystemPromptCache initialized version: {self._current_version}")
        
        except Exception as e:
            logger.error(f"SystemPromptCache version initialization error: {e}")
    
    def get(self, profile_id: str, path: str, context: Dict[str, Any] = None) -> Optional[str]:
        """
        Get cached system prompt
        
        Args:
            profile_id: Executive profile ID
            path: Processing path (fast/standard/agentic)
            context: Additional context for prompt generation
            
        Returns:
            Cached prompt or None
        """
        if not self.config['enabled'] or not self._redis_client:
            self.metrics.misses += 1
            return None
        
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(profile_id, path, context)
            
            # Get from Redis
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                # Deserialize cache entry
                cache_entry = pickle.loads(cached_data)
                
                # Check if expired
                if time.time() - cache_entry.timestamp < cache_entry.ttl_seconds:
                    # Check version compatibility
                    if cache_entry.version == self._current_version:
                        self.metrics.hits += 1
                        self.metrics.total_get_time_ms += (time.time() - start_time) * 1000
                        
                        logger.debug(f"SystemPromptCache HIT: {cache_key[:32]}...")
                        return cache_entry.prompt
                    else:
                        # Version mismatch, invalidate
                        self._redis_client.delete(cache_key)
                        logger.debug(f"SystemPromptCache VERSION MISMATCH: {cache_key[:32]}...")
                else:
                    # Expired, remove
                    self._redis_client.delete(cache_key)
                    logger.debug(f"SystemPromptCache EXPIRED: {cache_key[:32]}...")
            
            self.metrics.misses += 1
            self.metrics.total_get_time_ms += (time.time() - start_time) * 1000
            
            return None
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"SystemPromptCache get error: {e}")
            return None
    
    def set(self, profile_id: str, path: str, prompt: str, 
            context: Dict[str, Any] = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache system prompt
        
        Args:
            profile_id: Executive profile ID
            path: Processing path (fast/standard/agentic)
            prompt: System prompt to cache
            context: Additional context for prompt generation
            metadata: Additional metadata
            
        Returns:
            True if cached successfully
        """
        if not self.config['enabled'] or not self._redis_client:
            return False
        
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(profile_id, path, context)
            
            # Create cache entry
            cache_entry = SystemPromptEntry(
                prompt=prompt,
                timestamp=time.time(),
                ttl_seconds=self.config['ttl_seconds'],
                version=self._current_version,
                profile_id=profile_id,
                path=path,
                context_hash=self._hash_context(context),
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
                
                logger.debug(f"SystemPromptCache SET: {cache_key[:32]}...")
                return True
            else:
                logger.warning(f"SystemPromptCache SET failed: {cache_key[:32]}...")
                return False
                
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"SystemPromptCache set error: {e}")
            return False
    
    def invalidate_by_profile(self, profile_id: str) -> int:
        """
        Invalidate all cache entries for a specific profile
        
        Args:
            profile_id: Executive profile ID
            
        Returns:
            Number of entries invalidated
        """
        if not self.config['enabled'] or not self._redis_client:
            return 0
        
        try:
            pattern = f"{self.key_prefix}*profile:{profile_id}:*"
            
            # Find matching keys
            keys = self._redis_client.keys(pattern)
            
            if keys:
                # Delete keys
                deleted = self._redis_client.delete(*keys)
                self.metrics.profile_invalidations += deleted
                logger.info(f"SystemPromptCache invalidated {deleted} entries for profile {profile_id}")
                return deleted
            
            return 0
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"SystemPromptCache profile invalidate error: {e}")
            return 0
    
    def invalidate_by_path(self, path: str) -> int:
        """
        Invalidate all cache entries for a specific path
        
        Args:
            path: Processing path
            
        Returns:
            Number of entries invalidated
        """
        if not self.config['enabled'] or not self._redis_client:
            return 0
        
        try:
            pattern = f"{self.key_prefix}*path:{path}:*"
            
            # Find matching keys
            keys = self._redis_client.keys(pattern)
            
            if keys:
                # Delete keys
                deleted = self._redis_client.delete(*keys)
                self.metrics.evictions += deleted
                logger.info(f"SystemPromptCache invalidated {deleted} entries for path {path}")
                return deleted
            
            return 0
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"SystemPromptCache path invalidate error: {e}")
            return 0
    
    def update_version(self, new_version: str) -> bool:
        """
        Update system prompt version and invalidate old entries
        
        Args:
            new_version: New version string
            
        Returns:
            True if updated successfully
        """
        if not self.config['enabled'] or not self._redis_client:
            return False
        
        try:
            if new_version != self._current_version:
                # Update version
                old_version = self._current_version
                self._current_version = new_version
                
                # Store new version
                self._redis_client.set(self.version_key, new_version.encode('utf-8'))
                
                # Invalidate all old entries
                invalidated = self._invalidate_all_for_version_change()
                
                logger.info(f"SystemPromptCache version updated: {old_version} -> {new_version} "
                           f"(invalidated {invalidated} entries)")
                
                self.metrics.version_invalidations += invalidated
                return True
            
            return False
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"SystemPromptCache version update error: {e}")
            return False
    
    def _invalidate_all_for_version_change(self) -> int:
        """Invalidate all cache entries due to version change"""
        try:
            pattern = f"{self.key_prefix}*"
            
            # Find matching keys
            keys = self._redis_client.keys(pattern)
            
            if keys:
                # Delete keys
                deleted = self._redis_client.delete(*keys)
                return deleted
            
            return 0
            
        except Exception as e:
            logger.error(f"SystemPromptCache version invalidate error: {e}")
            return 0
    
    def _generate_cache_key(self, profile_id: str, path: str, 
                          context: Dict[str, Any] = None) -> str:
        """
        Generate cache key for system prompt
        
        Key format: sys_prompt:{version}:{profile}:{path}:{context_hash}
        """
        # Build key components
        components = {
            'version': self._current_version,
        }
        
        # Add profile if enabled
        if self.config['profile_based']:
            components['profile'] = profile_id
        
        # Add path if enabled
        if self.config['path_based']:
            components['path'] = path
        
        # Add context if enabled
        if self.config['context_based'] and context:
            components['context'] = self._hash_context(context)
        
        # Create key string
        key_parts = [self.key_prefix]
        for k, v in components.items():
            key_parts.append(f"{k}:{v}")
        
        cache_key = ':'.join(key_parts)
        return cache_key
    
    def _hash_context(self, context: Dict[str, Any] = None) -> str:
        """
        Hash context for cache key
        
        Args:
            context: Context dictionary
            
        Returns:
            SHA256 hash (shortened)
        """
        if not context:
            return 'none'
        
        # Sort keys for consistent hashing
        sorted_context = {k: context[k] for k in sorted(context.keys())}
        
        # Convert to JSON and hash
        context_json = json.dumps(sorted_context, sort_keys=True, default=str)
        return hashlib.sha256(context_json.encode('utf-8')).hexdigest()[:16]
    
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
                oldest_keys = sorted(keys, key=lambda k: self._redis_client.ttl(k))[:50]
                
                if oldest_keys:
                    deleted = self._redis_client.delete(*oldest_keys)
                    self.metrics.evictions += deleted
                    logger.info(f"SystemPromptCache evicted {deleted} old entries")
        
        except Exception as e:
            logger.error(f"SystemPromptCache size check error: {e}")
    
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
            'current_version': self._current_version,
            'version_aware': self.config['version_aware'],
        })
        
        return metrics_dict
    
    def reset_metrics(self):
        """Reset metrics"""
        self.metrics = SystemPromptMetrics()
        self._last_metrics_reset = time.time()
        logger.info("SystemPromptCache metrics reset")
    
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
            'current_version': self._current_version,
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
                
                # Check version consistency
                stored_version = self._redis_client.get(self.version_key)
                if stored_version:
                    stored_version = stored_version.decode('utf-8')
                    if stored_version != self._current_version:
                        health['issues'].append(f"Version mismatch: stored={stored_version}, current={self._current_version}")
                
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


__all__ = ['SystemPromptCache', 'SystemPromptEntry', 'SystemPromptMetrics']