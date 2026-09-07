"""
Level 2: Embedding Cache
=======================

Redis-based cache for query and document embeddings with 7-day TTL.

Features:
- Separate caches for query and document embeddings
- Compression for memory efficiency
- Batch operations for performance
- Cache warming for popular content
- Hit rate targeting 70%
- Latency savings targeting 75%

Author: AI Officer Implementation Team
Date: 2025-10-30
"""

import json
import hashlib
import time
import logging
import pickle
import zlib
import numpy as np
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from .config import EMBEDDING_CACHE_CONFIG, REDIS_CONFIG, CACHE_MONITORING_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingCacheEntry:
    """Cache entry for embeddings"""
    embedding: np.ndarray
    timestamp: float
    ttl_seconds: int
    model_name: str
    embedding_dim: int
    compressed: bool = False
    metadata: Dict[str, Any] = None


@dataclass
class EmbeddingCacheMetrics:
    """Cache performance metrics for embeddings"""
    query_hits: int = 0
    query_misses: int = 0
    query_sets: int = 0
    document_hits: int = 0
    document_misses: int = 0
    document_sets: int = 0
    evictions: int = 0
    errors: int = 0
    total_get_time_ms: float = 0.0
    total_set_time_ms: float = 0.0
    compression_ratio: float = 0.0
    
    @property
    def query_hit_rate(self) -> float:
        """Calculate query hit rate"""
        total = self.query_hits + self.query_misses
        return self.query_hits / total if total > 0 else 0.0
    
    @property
    def document_hit_rate(self) -> float:
        """Calculate document hit rate"""
        total = self.document_hits + self.document_misses
        return self.document_hits / total if total > 0 else 0.0
    
    @property
    def overall_hit_rate(self) -> float:
        """Calculate overall hit rate"""
        total_hits = self.query_hits + self.document_hits
        total_misses = self.query_misses + self.document_misses
        total = total_hits + total_misses
        return total_hits / total if total > 0 else 0.0
    
    @property
    def avg_get_time_ms(self) -> float:
        """Calculate average get time"""
        total_ops = self.query_hits + self.query_misses + self.document_hits + self.document_misses
        return self.total_get_time_ms / total_ops if total_ops > 0 else 0.0
    
    @property
    def avg_set_time_ms(self) -> float:
        """Calculate average set time"""
        total_sets = self.query_sets + self.document_sets
        return self.total_set_time_ms / total_sets if total_sets > 0 else 0.0


class EmbeddingCache:
    """
    Level 2 cache for query and document embeddings
    
    Maintains separate caches for:
    - Query embeddings (frequently accessed)
    - Document embeddings (larger, less frequent)
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize embedding cache
        
        Args:
            redis_client: Optional Redis client (for testing/injection)
        """
        self.config = EMBEDDING_CACHE_CONFIG
        self.redis_config = REDIS_CONFIG
        self.monitoring_config = CACHE_MONITORING_CONFIG
        
        # Initialize Redis client
        self._redis_client = redis_client
        if not self._redis_client and (self.config['query_cache']['enabled'] or 
                                     self.config['document_cache']['enabled']):
            self._init_redis()
        
        # Metrics tracking
        self.metrics = EmbeddingCacheMetrics()
        self._last_metrics_reset = time.time()
        
        # Cache key prefixes
        self.query_key_prefix = self.config['query_cache']['key_prefix']
        self.document_key_prefix = self.config['document_cache']['key_prefix']
        
        logger.info(f"EmbeddingCache initialized (query={self.config['query_cache']['enabled']}, "
                   f"document={self.config['document_cache']['enabled']})")
    
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
            logger.info("EmbeddingCache: Redis connection established")
        except Exception as e:
            logger.error(f"EmbeddingCache: Failed to connect to Redis: {e}")
            self._redis_client = None
            self.config['query_cache']['enabled'] = False
            self.config['document_cache']['enabled'] = False
    
    def get_query_embedding(self, query: str, model_name: str = None) -> Optional[np.ndarray]:
        """
        Get cached query embedding
        
        Args:
            query: Query text
            model_name: Model name used for embedding
            
        Returns:
            Cached embedding or None
        """
        if not self.config['query_cache']['enabled'] or not self._redis_client:
            self.metrics.query_misses += 1
            return None
        
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_query_cache_key(query, model_name)
            
            # Get from Redis
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                # Deserialize cache entry
                cache_entry = pickle.loads(cached_data)
                
                # Check if expired
                if time.time() - cache_entry.timestamp < cache_entry.ttl_seconds:
                    self.metrics.query_hits += 1
                    self.metrics.total_get_time_ms += (time.time() - start_time) * 1000
                    
                    logger.debug(f"EmbeddingCache query HIT: {cache_key[:32]}...")
                    return cache_entry.embedding
                else:
                    # Expired, remove
                    self._redis_client.delete(cache_key)
                    logger.debug(f"EmbeddingCache query EXPIRED: {cache_key[:32]}...")
            
            self.metrics.query_misses += 1
            self.metrics.total_get_time_ms += (time.time() - start_time) * 1000
            
            return None
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"EmbeddingCache query get error: {e}")
            return None
    
    def set_query_embedding(self, query: str, embedding: np.ndarray, 
                          model_name: str = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache query embedding
        
        Args:
            query: Query text
            embedding: Embedding vector
            model_name: Model name used for embedding
            metadata: Additional metadata
            
        Returns:
            True if cached successfully
        """
        if not self.config['query_cache']['enabled'] or not self._redis_client:
            return False
        
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_query_cache_key(query, model_name)
            
            # Create cache entry
            cache_entry = EmbeddingCacheEntry(
                embedding=embedding,
                timestamp=time.time(),
                ttl_seconds=self.config['query_cache']['ttl_seconds'],
                model_name=model_name or 'default',
                embedding_dim=embedding.shape[0] if len(embedding.shape) > 0 else len(embedding),
                compressed=self.config['compress_embeddings'],
                metadata=metadata or {}
            )
            
            # Serialize and store
            serialized_data = pickle.dumps(cache_entry)
            
            # Store with TTL
            success = self._redis_client.setex(
                cache_key,
                self.config['query_cache']['ttl_seconds'],
                serialized_data
            )
            
            if success:
                self.metrics.query_sets += 1
                self.metrics.total_set_time_ms += (time.time() - start_time) * 1000
                
                # Check cache size and evict if necessary
                self._check_query_cache_size()
                
                logger.debug(f"EmbeddingCache query SET: {cache_key[:32]}...")
                return True
            else:
                logger.warning(f"EmbeddingCache query SET failed: {cache_key[:32]}...")
                return False
                
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"EmbeddingCache query set error: {e}")
            return False
    
    def get_document_embedding(self, document_id: str, model_name: str = None) -> Optional[np.ndarray]:
        """
        Get cached document embedding
        
        Args:
            document_id: Document identifier
            model_name: Model name used for embedding
            
        Returns:
            Cached embedding or None
        """
        if not self.config['document_cache']['enabled'] or not self._redis_client:
            self.metrics.document_misses += 1
            return None
        
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_document_cache_key(document_id, model_name)
            
            # Get from Redis
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                # Deserialize cache entry
                cache_entry = pickle.loads(cached_data)
                
                # Check if expired
                if time.time() - cache_entry.timestamp < cache_entry.ttl_seconds:
                    self.metrics.document_hits += 1
                    self.metrics.total_get_time_ms += (time.time() - start_time) * 1000
                    
                    logger.debug(f"EmbeddingCache document HIT: {cache_key[:32]}...")
                    return cache_entry.embedding
                else:
                    # Expired, remove
                    self._redis_client.delete(cache_key)
                    logger.debug(f"EmbeddingCache document EXPIRED: {cache_key[:32]}...")
            
            self.metrics.document_misses += 1
            self.metrics.total_get_time_ms += (time.time() - start_time) * 1000
            
            return None
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"EmbeddingCache document get error: {e}")
            return None
    
    def set_document_embedding(self, document_id: str, embedding: np.ndarray,
                            model_name: str = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache document embedding
        
        Args:
            document_id: Document identifier
            embedding: Embedding vector
            model_name: Model name used for embedding
            metadata: Additional metadata
            
        Returns:
            True if cached successfully
        """
        if not self.config['document_cache']['enabled'] or not self._redis_client:
            return False
        
        start_time = time.time()
        
        try:
            # Generate cache key
            cache_key = self._generate_document_cache_key(document_id, model_name)
            
            # Create cache entry
            cache_entry = EmbeddingCacheEntry(
                embedding=embedding,
                timestamp=time.time(),
                ttl_seconds=self.config['document_cache']['ttl_seconds'],
                model_name=model_name or 'default',
                embedding_dim=embedding.shape[0] if len(embedding.shape) > 0 else len(embedding),
                compressed=self.config['compress_embeddings'],
                metadata=metadata or {}
            )
            
            # Serialize and store
            serialized_data = pickle.dumps(cache_entry)
            
            # Store with TTL
            success = self._redis_client.setex(
                cache_key,
                self.config['document_cache']['ttl_seconds'],
                serialized_data
            )
            
            if success:
                self.metrics.document_sets += 1
                self.metrics.total_set_time_ms += (time.time() - start_time) * 1000
                
                # Check cache size and evict if necessary
                self._check_document_cache_size()
                
                logger.debug(f"EmbeddingCache document SET: {cache_key[:32]}...")
                return True
            else:
                logger.warning(f"EmbeddingCache document SET failed: {cache_key[:32]}...")
                return False
                
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"EmbeddingCache document set error: {e}")
            return False
    
    def get_batch_query_embeddings(self, queries: List[str], 
                                 model_name: str = None) -> Dict[str, Optional[np.ndarray]]:
        """
        Get multiple query embeddings in batch
        
        Args:
            queries: List of query texts
            model_name: Model name used for embeddings
            
        Returns:
            Dict mapping query to embedding or None
        """
        results = {}
        
        if not self.config['query_cache']['enabled'] or not self._redis_client:
            # Return all misses
            for query in queries:
                results[query] = None
                self.metrics.query_misses += 1
            return results
        
        try:
            # Generate cache keys
            cache_keys = [self._generate_query_cache_key(query, model_name) for query in queries]
            
            # Batch get from Redis
            cached_values = self._redis_client.mget(cache_keys)
            
            # Process results
            for i, query in enumerate(queries):
                cache_key = cache_keys[i]
                cached_data = cached_values[i]
                
                if cached_data:
                    try:
                        cache_entry = pickle.loads(cached_data)
                        
                        # Check if expired
                        if time.time() - cache_entry.timestamp < cache_entry.ttl_seconds:
                            results[query] = cache_entry.embedding
                            self.metrics.query_hits += 1
                        else:
                            # Expired
                            results[query] = None
                            self.metrics.query_misses += 1
                            # Schedule for deletion
                            self._redis_client.delete(cache_key)
                    except Exception as e:
                        logger.error(f"Error deserializing query embedding: {e}")
                        results[query] = None
                        self.metrics.query_misses += 1
                else:
                    results[query] = None
                    self.metrics.query_misses += 1
            
            return results
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"EmbeddingCache batch query get error: {e}")
            # Return all misses
            for query in queries:
                results[query] = None
                self.metrics.query_misses += 1
            return results
    
    def set_batch_query_embeddings(self, embeddings: Dict[str, np.ndarray],
                                 model_name: str = None) -> int:
        """
        Set multiple query embeddings in batch
        
        Args:
            embeddings: Dict mapping query to embedding
            model_name: Model name used for embeddings
            
        Returns:
            Number of embeddings cached successfully
        """
        if not self.config['query_cache']['enabled'] or not self._redis_client:
            return 0
        
        success_count = 0
        
        try:
            # Prepare batch operations
            pipe = self._redis_client.pipeline()
            
            for query, embedding in embeddings.items():
                # Generate cache key
                cache_key = self._generate_query_cache_key(query, model_name)
                
                # Create cache entry
                cache_entry = EmbeddingCacheEntry(
                    embedding=embedding,
                    timestamp=time.time(),
                    ttl_seconds=self.config['query_cache']['ttl_seconds'],
                    model_name=model_name or 'default',
                    embedding_dim=embedding.shape[0] if len(embedding.shape) > 0 else len(embedding),
                    compressed=self.config['compress_embeddings']
                )
                
                # Serialize
                serialized_data = pickle.dumps(cache_entry)
                
                # Add to pipeline
                pipe.setex(cache_key, self.config['query_cache']['ttl_seconds'], serialized_data)
            
            # Execute batch
            results = pipe.execute()
            
            # Count successes
            success_count = sum(1 for result in results if result)
            self.metrics.query_sets += success_count
            
            # Check cache size
            self._check_query_cache_size()
            
            logger.debug(f"EmbeddingCache batch query SET: {success_count}/{len(embeddings)} successful")
            return success_count
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"EmbeddingCache batch query set error: {e}")
            return 0
    
    def invalidate_query_cache(self, pattern: str = None) -> int:
        """
        Invalidate query cache entries
        
        Args:
            pattern: Pattern to match (default: all query entries)
            
        Returns:
            Number of entries invalidated
        """
        if not self.config['query_cache']['enabled'] or not self._redis_client:
            return 0
        
        try:
            if pattern is None:
                pattern = f"{self.query_key_prefix}*"
            
            # Find matching keys
            keys = self._redis_client.keys(pattern)
            
            if keys:
                # Delete keys
                deleted = self._redis_client.delete(*keys)
                self.metrics.evictions += deleted
                logger.info(f"EmbeddingCache query invalidated {deleted} entries matching {pattern}")
                return deleted
            
            return 0
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"EmbeddingCache query invalidate error: {e}")
            return 0
    
    def invalidate_document_cache(self, pattern: str = None) -> int:
        """
        Invalidate document cache entries
        
        Args:
            pattern: Pattern to match (default: all document entries)
            
        Returns:
            Number of entries invalidated
        """
        if not self.config['document_cache']['enabled'] or not self._redis_client:
            return 0
        
        try:
            if pattern is None:
                pattern = f"{self.document_key_prefix}*"
            
            # Find matching keys
            keys = self._redis_client.keys(pattern)
            
            if keys:
                # Delete keys
                deleted = self._redis_client.delete(*keys)
                self.metrics.evictions += deleted
                logger.info(f"EmbeddingCache document invalidated {deleted} entries matching {pattern}")
                return deleted
            
            return 0
            
        except Exception as e:
            self.metrics.errors += 1
            logger.error(f"EmbeddingCache document invalidate error: {e}")
            return 0
    
    def _generate_query_cache_key(self, query: str, model_name: str = None) -> str:
        """
        Generate cache key for query embedding
        
        Key format: embed_query:{hash}:{model}
        """
        # Normalize query
        normalized_query = query.lower().strip()
        
        # Hash query
        query_hash = hashlib.sha256(normalized_query.encode('utf-8')).hexdigest()[:16]
        
        # Build key
        model_part = f":{model_name}" if model_name else ""
        cache_key = f"{self.query_key_prefix}{query_hash}{model_part}"
        
        return cache_key
    
    def _generate_document_cache_key(self, document_id: str, model_name: str = None) -> str:
        """
        Generate cache key for document embedding
        
        Key format: embed_doc:{doc_id}:{model}
        """
        # Hash document ID
        doc_hash = hashlib.sha256(document_id.encode('utf-8')).hexdigest()[:16]
        
        # Build key
        model_part = f":{model_name}" if model_name else ""
        cache_key = f"{self.document_key_prefix}{doc_hash}{model_part}"
        
        return cache_key
    
    def _check_query_cache_size(self):
        """Check query cache size and evict if necessary"""
        try:
            # Get current cache size
            pattern = f"{self.query_key_prefix}*"
            keys = self._redis_client.keys(pattern)
            current_size = len(keys)
            
            # Evict if over limit
            if current_size > self.config['query_cache']['max_entries']:
                # Get oldest keys (by TTL)
                oldest_keys = sorted(keys, key=lambda k: self._redis_client.ttl(k))[:100]
                
                if oldest_keys:
                    deleted = self._redis_client.delete(*oldest_keys)
                    self.metrics.evictions += deleted
                    logger.info(f"EmbeddingCache query evicted {deleted} old entries")
        
        except Exception as e:
            logger.error(f"EmbeddingCache query size check error: {e}")
    
    def _check_document_cache_size(self):
        """Check document cache size and evict if necessary"""
        try:
            # Get current cache size
            pattern = f"{self.document_key_prefix}*"
            keys = self._redis_client.keys(pattern)
            current_size = len(keys)
            
            # Evict if over limit
            if current_size > self.config['document_cache']['max_entries']:
                # Get oldest keys (by TTL)
                oldest_keys = sorted(keys, key=lambda k: self._redis_client.ttl(k))[:100]
                
                if oldest_keys:
                    deleted = self._redis_client.delete(*oldest_keys)
                    self.metrics.evictions += deleted
                    logger.info(f"EmbeddingCache document evicted {deleted} old entries")
        
        except Exception as e:
            logger.error(f"EmbeddingCache document size check error: {e}")
    
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
            'query_hit_rate': self.metrics.query_hit_rate,
            'document_hit_rate': self.metrics.document_hit_rate,
            'overall_hit_rate': self.metrics.overall_hit_rate,
            'avg_get_time_ms': self.metrics.avg_get_time_ms,
            'avg_set_time_ms': self.metrics.avg_set_time_ms,
            'uptime_hours': uptime_hours,
            'target_hit_rate': self.config['target_hit_rate'],
            'target_latency_savings': self.config['target_latency_savings'],
            'query_cache_enabled': self.config['query_cache']['enabled'],
            'document_cache_enabled': self.config['document_cache']['enabled'],
            'compression_enabled': self.config['compress_embeddings'],
        })
        
        return metrics_dict
    
    def reset_metrics(self):
        """Reset metrics"""
        self.metrics = EmbeddingCacheMetrics()
        self._last_metrics_reset = time.time()
        logger.info("EmbeddingCache metrics reset")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check
        
        Returns:
            Health status
        """
        health = {
            'status': 'healthy',
            'redis_connected': False,
            'query_cache_enabled': self.config['query_cache']['enabled'],
            'document_cache_enabled': self.config['document_cache']['enabled'],
            'issues': []
        }
        
        if not (self.config['query_cache']['enabled'] or self.config['document_cache']['enabled']):
            health['status'] = 'disabled'
            return health
        
        try:
            if self._redis_client:
                # Test Redis connection
                self._redis_client.ping()
                health['redis_connected'] = True
                
                # Check hit rates
                if self.metrics.overall_hit_rate < self.config['target_hit_rate'] * 0.5:
                    health['issues'].append(f"Low hit rate: {self.metrics.overall_hit_rate:.2%}")
                
                # Check error rate
                total_ops = (self.metrics.query_hits + self.metrics.query_misses + 
                           self.metrics.document_hits + self.metrics.document_misses + 
                           self.metrics.query_sets + self.metrics.document_sets)
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


__all__ = ['EmbeddingCache', 'EmbeddingCacheEntry', 'EmbeddingCacheMetrics']