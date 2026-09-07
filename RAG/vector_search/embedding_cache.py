"""
Two-Level Embedding Cache

L1: In-memory LRU cache (1000 entries)
L2: Optional Redis cache (7-day TTL)

Caches query embeddings to avoid redundant model inference.
"""

import hashlib
import pickle
import numpy as np
from collections import OrderedDict
from typing import Optional, Dict, Any, Tuple
import logging

from .config import VECTOR_SEARCH_CONFIG, REDIS_CONFIG

logger = logging.getLogger('vector_search.embedding_cache')


class EmbeddingCache:
    """
    Two-level cache for query embeddings.
    
    L1 (Memory): Fast OrderedDict-based LRU cache
    L2 (Redis): Optional persistent cache with TTL
    
    Cache Key: MD5 hash of query text
    Cache Value: NumPy array (embedding vector)
    """
    
    def __init__(
        self,
        max_size: int = 1000,
        enable_redis: bool = False,
        redis_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize the two-level cache.
        
        Args:
            max_size: Maximum entries in L1 cache
            enable_redis: Whether to enable L2 Redis cache
            redis_config: Optional Redis configuration
        """
        self.max_size = max_size
        self.enable_redis = enable_redis
        
        # L1: In-memory LRU cache
        self._l1_cache: OrderedDict[str, np.ndarray] = OrderedDict()
        
        # L2: Optional Redis cache
        self._redis_client = None
        if enable_redis:
            self._init_redis(redis_config or REDIS_CONFIG)
        
        # Statistics
        self.stats = {
            'l1_hits': 0,
            'l2_hits': 0,
            'misses': 0,
            'l1_evictions': 0,
            'total_gets': 0,
            'total_sets': 0,
        }
        
        logger.info(f"EmbeddingCache initialized (L1 size: {max_size}, Redis: {enable_redis})")
    
    def _init_redis(self, config: Dict[str, Any]):
        """Initialize Redis connection for L2 cache."""
        try:
            import redis
            self._redis_client = redis.Redis(
                host=config['host'],
                port=config['port'],
                db=config['db'],
                password=config['password'],
                decode_responses=config['decode_responses'],
                socket_timeout=config['socket_timeout'],
                socket_connect_timeout=config['socket_connect_timeout'],
            )
            # Test connection
            self._redis_client.ping()
            logger.info("Redis L2 cache connected successfully")
        except ImportError:
            logger.warning("Redis package not installed. L2 cache disabled.")
            self._redis_client = None
            self.enable_redis = False
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. L2 cache disabled.")
            self._redis_client = None
            self.enable_redis = False
    
    def _get_cache_key(self, query: str) -> str:
        """
        Generate cache key from query text using MD5 hash.
        
        Args:
            query: Query text
        
        Returns:
            MD5 hash as hex string
        """
        return hashlib.md5(query.encode('utf-8')).hexdigest()
    
    def get(self, query: str) -> Optional[np.ndarray]:
        """
        Retrieve embedding from cache.
        
        Lookup order: L1 (memory) → L2 (Redis)
        
        Args:
            query: Query text
        
        Returns:
            Cached embedding or None if not found
        """
        self.stats['total_gets'] += 1
        cache_key = self._get_cache_key(query)
        
        # Try L1 cache first
        if cache_key in self._l1_cache:
            # Move to end (most recently used)
            self._l1_cache.move_to_end(cache_key)
            self.stats['l1_hits'] += 1
            logger.debug(f"L1 cache hit for query hash {cache_key[:8]}...")
            return self._l1_cache[cache_key]
        
        # Try L2 cache (Redis)
        if self.enable_redis and self._redis_client:
            try:
                cached_bytes = self._redis_client.get(cache_key)
                if cached_bytes:
                    embedding = pickle.loads(cached_bytes)
                    # Promote to L1
                    self._set_l1(cache_key, embedding)
                    self.stats['l2_hits'] += 1
                    logger.debug(f"L2 cache hit for query hash {cache_key[:8]}...")
                    return embedding
            except Exception as e:
                logger.warning(f"L2 cache read failed: {e}")
        
        # Cache miss
        self.stats['misses'] += 1
        logger.debug(f"Cache miss for query hash {cache_key[:8]}...")
        return None
    
    def set(self, query: str, embedding: np.ndarray):
        """
        Store embedding in cache (both L1 and L2).
        
        Args:
            query: Query text
            embedding: Query embedding vector
        """
        self.stats['total_sets'] += 1
        cache_key = self._get_cache_key(query)
        
        # Store in L1
        self._set_l1(cache_key, embedding)
        
        # Store in L2 (Redis)
        if self.enable_redis and self._redis_client:
            try:
                ttl = VECTOR_SEARCH_CONFIG['cache_ttl_seconds']
                cached_bytes = pickle.dumps(embedding)
                self._redis_client.setex(
                    cache_key,
                    ttl,
                    cached_bytes
                )
                logger.debug(f"Stored in L2 cache with {ttl}s TTL")
            except Exception as e:
                logger.warning(f"L2 cache write failed: {e}")
    
    def _set_l1(self, cache_key: str, embedding: np.ndarray):
        """
        Store embedding in L1 cache with LRU eviction.
        
        Args:
            cache_key: Cache key (MD5 hash)
            embedding: Embedding vector
        """
        # Add or update
        if cache_key in self._l1_cache:
            # Move to end
            self._l1_cache.move_to_end(cache_key)
        else:
            self._l1_cache[cache_key] = embedding
        
        # Evict oldest if over capacity
        if len(self._l1_cache) > self.max_size:
            evicted_key, _ = self._l1_cache.popitem(last=False)  # FIFO
            self.stats['l1_evictions'] += 1
            logger.debug(f"Evicted from L1: {evicted_key[:8]}...")
    
    def clear(self):
        """Clear both L1 and L2 caches."""
        # Clear L1
        self._l1_cache.clear()
        
        # Clear L2 (optional - flushes entire Redis DB!)
        # Commented out for safety - use with caution
        # if self.enable_redis and self._redis_client:
        #     self._redis_client.flushdb()
        
        logger.info("Cache cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with hit rates and counts
        """
        total_gets = self.stats['total_gets']
        if total_gets == 0:
            hit_rate = 0.0
            l1_hit_rate = 0.0
            l2_hit_rate = 0.0
        else:
            l1_hits = self.stats['l1_hits']
            l2_hits = self.stats['l2_hits']
            total_hits = l1_hits + l2_hits
            
            hit_rate = (total_hits / total_gets) * 100
            l1_hit_rate = (l1_hits / total_gets) * 100
            l2_hit_rate = (l2_hits / total_gets) * 100
        
        return {
            'l1_size': len(self._l1_cache),
            'l1_max_size': self.max_size,
            'l1_hits': self.stats['l1_hits'],
            'l2_hits': self.stats['l2_hits'],
            'misses': self.stats['misses'],
            'total_gets': total_gets,
            'total_sets': self.stats['total_sets'],
            'hit_rate_percent': round(hit_rate, 2),
            'l1_hit_rate_percent': round(l1_hit_rate, 2),
            'l2_hit_rate_percent': round(l2_hit_rate, 2),
            'l1_evictions': self.stats['l1_evictions'],
            'redis_enabled': self.enable_redis,
        }
    
    def __repr__(self):
        """String representation with stats."""
        stats = self.get_stats()
        return (
            f"EmbeddingCache(size={stats['l1_size']}/{stats['l1_max_size']}, "
            f"hit_rate={stats['hit_rate_percent']}%, "
            f"redis={stats['redis_enabled']})"
        )
