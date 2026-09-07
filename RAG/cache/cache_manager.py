"""
Cache Manager - Three-Level Caching Orchestration
================================================

Coordinates all three levels of caching:
- Level 1: Semantic Query Cache (Redis) - 1-hour TTL
- Level 2: Embedding Cache (Redis) - 7-day TTL
- Level 3: System Prompt Cache (Redis) - Version-aware invalidation

Features:
- Unified interface for all cache levels
- Cross-level cache coordination
- Performance monitoring and metrics
- Health checks and alerting
- Cache warming and optimization

Author: AI Officer Implementation Team
Date: 2025-10-30
"""

import time
import logging
import asyncio
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

from .config import CACHE_CONFIG, CACHE_MONITORING_CONFIG, validate_cache_config
from .semantic_query_cache import SemanticQueryCache
from .embedding_cache import EmbeddingCache
from .system_prompt_cache import SystemPromptCache

logger = logging.getLogger(__name__)


@dataclass
class CacheManagerMetrics:
    """Overall cache manager metrics"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    total_latency_saved_ms: float = 0.0
    total_cache_time_ms: float = 0.0
    
    # Level-specific metrics
    semantic_query_metrics: Dict[str, Any] = None
    embedding_metrics: Dict[str, Any] = None
    system_prompt_metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.semantic_query_metrics is None:
            self.semantic_query_metrics = {}
        if self.embedding_metrics is None:
            self.embedding_metrics = {}
        if self.system_prompt_metrics is None:
            self.system_prompt_metrics = {}
    
    @property
    def overall_hit_rate(self) -> float:
        """Calculate overall hit rate"""
        return self.cache_hits / self.total_requests if self.total_requests > 0 else 0.0
    
    @property
    def latency_savings_pct(self) -> float:
        """Calculate latency savings percentage"""
        if self.total_cache_time_ms + self.total_latency_saved_ms == 0:
            return 0.0
        return (self.total_latency_saved_ms / 
                (self.total_cache_time_ms + self.total_latency_saved_ms)) * 100


class CacheManager:
    """
    Unified cache manager for all three levels
    
    Provides a single interface for:
    - Query result caching (L1)
    - Embedding caching (L2)
    - System prompt caching (L3)
    """
    
    def __init__(self, redis_client=None):
        """
        Initialize cache manager
        
        Args:
            redis_client: Optional Redis client (for testing/injection)
        """
        self.config = CACHE_CONFIG
        self.monitoring_config = CACHE_MONITORING_CONFIG
        
        # Validate configuration
        validation_result = validate_cache_config()
        if not validation_result['valid']:
            logger.error(f"Cache configuration validation failed: {validation_result['errors']}")
            raise ValueError("Invalid cache configuration")
        
        # Initialize cache levels
        self._semantic_query_cache = SemanticQueryCache(redis_client)
        self._embedding_cache = EmbeddingCache(redis_client)
        self._system_prompt_cache = SystemPromptCache(redis_client)
        
        # Metrics tracking
        self.metrics = CacheManagerMetrics()
        self._last_metrics_reset = time.time()
        self._last_health_check = time.time()
        
        # Background tasks
        self._background_tasks_enabled = self.monitoring_config['enabled']
        self._metrics_task = None
        
        logger.info("CacheManager initialized with three-level caching strategy")
    
    # ========================================================================
    # LEVEL 1: SEMANTIC QUERY CACHE OPERATIONS
    # ========================================================================
    
    def get_query_result(self, query: str, user_context: Dict[str, Any], 
                       executive_id: str, path: str = None) -> Optional[Dict[str, Any]]:
        """
        Get cached query result (Level 1)
        
        Args:
            query: User query
            user_context: User context (role, scopes, etc.)
            executive_id: Executive profile ID
            path: Processing path (fast/standard/agentic)
            
        Returns:
            Cached result or None
        """
        start_time = time.time()
        self.metrics.total_requests += 1
        
        try:
            result = self._semantic_query_cache.get(query, user_context, executive_id, path)
            
            if result:
                self.metrics.cache_hits += 1
                cache_time = (time.time() - start_time) * 1000
                self.metrics.total_cache_time_ms += cache_time
                
                # Estimate latency savings (typical query processing time)
                estimated_processing_time = 1500 if path == 'fast' else (2500 if path == 'standard' else 5000)
                latency_saved = max(0, estimated_processing_time - cache_time)
                self.metrics.total_latency_saved_ms += latency_saved
                
                logger.debug(f"CacheManager L1 HIT: {query[:50]}... (saved {latency_saved:.1f}ms)")
                return result
            else:
                self.metrics.cache_misses += 1
                logger.debug(f"CacheManager L1 MISS: {query[:50]}...")
                return None
        
        except Exception as e:
            logger.error(f"CacheManager L1 get error: {e}")
            self.metrics.cache_misses += 1
            return None
    
    def set_query_result(self, query: str, user_context: Dict[str, Any], 
                       executive_id: str, result: Dict[str, Any], 
                       path: str = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache query result (Level 1)
        
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
        try:
            success = self._semantic_query_cache.set(
                query, user_context, executive_id, result, path, metadata
            )
            
            if success:
                logger.debug(f"CacheManager L1 SET: {query[:50]}...")
            
            return success
        
        except Exception as e:
            logger.error(f"CacheManager L1 set error: {e}")
            return False
    
    # ========================================================================
    # LEVEL 2: EMBEDDING CACHE OPERATIONS
    # ========================================================================
    
    def get_query_embedding(self, query: str, model_name: str = None) -> Optional['np.ndarray']:
        """
        Get cached query embedding (Level 2)
        
        Args:
            query: Query text
            model_name: Model name used for embedding
            
        Returns:
            Cached embedding or None
        """
        start_time = time.time()
        self.metrics.total_requests += 1
        
        try:
            embedding = self._embedding_cache.get_query_embedding(query, model_name)
            
            if embedding is not None:
                self.metrics.cache_hits += 1
                cache_time = (time.time() - start_time) * 1000
                self.metrics.total_cache_time_ms += cache_time
                
                # Estimate latency savings (typical embedding generation time)
                estimated_processing_time = 200  # 200ms for embedding generation
                latency_saved = max(0, estimated_processing_time - cache_time)
                self.metrics.total_latency_saved_ms += latency_saved
                
                logger.debug(f"CacheManager L2 query embedding HIT: {query[:30]}... (saved {latency_saved:.1f}ms)")
                return embedding
            else:
                self.metrics.cache_misses += 1
                logger.debug(f"CacheManager L2 query embedding MISS: {query[:30]}...")
                return None
        
        except Exception as e:
            logger.error(f"CacheManager L2 query embedding get error: {e}")
            self.metrics.cache_misses += 1
            return None
    
    def set_query_embedding(self, query: str, embedding: 'np.ndarray', 
                          model_name: str = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache query embedding (Level 2)
        
        Args:
            query: Query text
            embedding: Embedding vector
            model_name: Model name used for embedding
            metadata: Additional metadata
            
        Returns:
            True if cached successfully
        """
        try:
            success = self._embedding_cache.set_query_embedding(
                query, embedding, model_name, metadata
            )
            
            if success:
                logger.debug(f"CacheManager L2 query embedding SET: {query[:30]}...")
            
            return success
        
        except Exception as e:
            logger.error(f"CacheManager L2 query embedding set error: {e}")
            return False
    
    def get_document_embedding(self, document_id: str, model_name: str = None) -> Optional['np.ndarray']:
        """
        Get cached document embedding (Level 2)
        
        Args:
            document_id: Document identifier
            model_name: Model name used for embedding
            
        Returns:
            Cached embedding or None
        """
        start_time = time.time()
        self.metrics.total_requests += 1
        
        try:
            embedding = self._embedding_cache.get_document_embedding(document_id, model_name)
            
            if embedding is not None:
                self.metrics.cache_hits += 1
                cache_time = (time.time() - start_time) * 1000
                self.metrics.total_cache_time_ms += cache_time
                
                # Estimate latency savings
                estimated_processing_time = 200  # 200ms for embedding generation
                latency_saved = max(0, estimated_processing_time - cache_time)
                self.metrics.total_latency_saved_ms += latency_saved
                
                logger.debug(f"CacheManager L2 document embedding HIT: {document_id} (saved {latency_saved:.1f}ms)")
                return embedding
            else:
                self.metrics.cache_misses += 1
                logger.debug(f"CacheManager L2 document embedding MISS: {document_id}")
                return None
        
        except Exception as e:
            logger.error(f"CacheManager L2 document embedding get error: {e}")
            self.metrics.cache_misses += 1
            return None
    
    def set_document_embedding(self, document_id: str, embedding: 'np.ndarray',
                            model_name: str = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache document embedding (Level 2)
        
        Args:
            document_id: Document identifier
            embedding: Embedding vector
            model_name: Model name used for embedding
            metadata: Additional metadata
            
        Returns:
            True if cached successfully
        """
        try:
            success = self._embedding_cache.set_document_embedding(
                document_id, embedding, model_name, metadata
            )
            
            if success:
                logger.debug(f"CacheManager L2 document embedding SET: {document_id}")
            
            return success
        
        except Exception as e:
            logger.error(f"CacheManager L2 document embedding set error: {e}")
            return False
    
    # ========================================================================
    # LEVEL 3: SYSTEM PROMPT CACHE OPERATIONS
    # ========================================================================
    
    def get_system_prompt(self, profile_id: str, path: str, 
                        context: Dict[str, Any] = None) -> Optional[str]:
        """
        Get cached system prompt (Level 3)
        
        Args:
            profile_id: Executive profile ID
            path: Processing path (fast/standard/agentic)
            context: Additional context for prompt generation
            
        Returns:
            Cached prompt or None
        """
        start_time = time.time()
        self.metrics.total_requests += 1
        
        try:
            prompt = self._system_prompt_cache.get(profile_id, path, context)
            
            if prompt:
                self.metrics.cache_hits += 1
                cache_time = (time.time() - start_time) * 1000
                self.metrics.total_cache_time_ms += cache_time
                
                # Estimate latency savings (typical prompt generation time)
                estimated_processing_time = 100  # 100ms for prompt generation
                latency_saved = max(0, estimated_processing_time - cache_time)
                self.metrics.total_latency_saved_ms += latency_saved
                
                logger.debug(f"CacheManager L3 HIT: {profile_id}/{path} (saved {latency_saved:.1f}ms)")
                return prompt
            else:
                self.metrics.cache_misses += 1
                logger.debug(f"CacheManager L3 MISS: {profile_id}/{path}")
                return None
        
        except Exception as e:
            logger.error(f"CacheManager L3 get error: {e}")
            self.metrics.cache_misses += 1
            return None
    
    def set_system_prompt(self, profile_id: str, path: str, prompt: str,
                        context: Dict[str, Any] = None, metadata: Dict[str, Any] = None) -> bool:
        """
        Cache system prompt (Level 3)
        
        Args:
            profile_id: Executive profile ID
            path: Processing path (fast/standard/agentic)
            prompt: System prompt to cache
            context: Additional context for prompt generation
            metadata: Additional metadata
            
        Returns:
            True if cached successfully
        """
        try:
            success = self._system_prompt_cache.set(
                profile_id, path, prompt, context, metadata
            )
            
            if success:
                logger.debug(f"CacheManager L3 SET: {profile_id}/{path}")
            
            return success
        
        except Exception as e:
            logger.error(f"CacheManager L3 set error: {e}")
            return False
    
    # ========================================================================
    # CACHE INVALIDATION OPERATIONS
    # ========================================================================
    
    def invalidate_by_executive(self, executive_id: str) -> Dict[str, int]:
        """
        Invalidate all cache entries for a specific executive
        
        Args:
            executive_id: Executive profile ID
            
        Returns:
            Dict with counts of invalidated entries per level
        """
        results = {
            'semantic_query': 0,
            'system_prompt': 0
        }
        
        try:
            # Level 1: Semantic query cache
            results['semantic_query'] = self._semantic_query_cache.invalidate_by_executive(executive_id)
            
            # Level 3: System prompt cache
            results['system_prompt'] = self._system_prompt_cache.invalidate_by_profile(executive_id)
            
            logger.info(f"CacheManager invalidated cache entries for executive {executive_id}: {results}")
            return results
        
        except Exception as e:
            logger.error(f"CacheManager executive invalidate error: {e}")
            return results
    
    def invalidate_by_user_role(self, user_role: str) -> Dict[str, int]:
        """
        Invalidate all cache entries for a specific user role
        
        Args:
            user_role: User role
            
        Returns:
            Dict with counts of invalidated entries per level
        """
        results = {
            'semantic_query': 0
        }
        
        try:
            # Level 1: Semantic query cache
            results['semantic_query'] = self._semantic_query_cache.invalidate_by_user_role(user_role)
            
            logger.info(f"CacheManager invalidated cache entries for role {user_role}: {results}")
            return results
        
        except Exception as e:
            logger.error(f"CacheManager role invalidate error: {e}")
            return results
    
    def update_system_prompt_version(self, new_version: str) -> bool:
        """
        Update system prompt version and invalidate old entries
        
        Args:
            new_version: New version string
            
        Returns:
            True if updated successfully
        """
        try:
            success = self._system_prompt_cache.update_version(new_version)
            
            if success:
                logger.info(f"CacheManager updated system prompt version to {new_version}")
            
            return success
        
        except Exception as e:
            logger.error(f"CacheManager version update error: {e}")
            return False
    
    # ========================================================================
    # METRICS AND MONITORING
    # ========================================================================
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache metrics
        
        Returns:
            Metrics dictionary for all levels
        """
        # Update level-specific metrics
        self.metrics.semantic_query_metrics = self._semantic_query_cache.get_metrics()
        self.metrics.embedding_metrics = self._embedding_cache.get_metrics()
        self.metrics.system_prompt_metrics = self._system_prompt_cache.get_metrics()
        
        # Calculate overall metrics
        current_time = time.time()
        uptime_hours = (current_time - self._last_metrics_reset) / 3600
        
        metrics_dict = asdict(self.metrics)
        metrics_dict.update({
            'overall_hit_rate': self.metrics.overall_hit_rate,
            'latency_savings_pct': self.metrics.latency_savings_pct,
            'uptime_hours': uptime_hours,
            'cache_levels': {
                'semantic_query': {
                    'enabled': self.config['semantic_query']['enabled'],
                    'target_hit_rate': self.config['semantic_query']['target_hit_rate'],
                    'actual_hit_rate': self.metrics.semantic_query_metrics.get('hit_rate', 0.0),
                },
                'embedding': {
                    'enabled': self.config['embedding']['query_cache']['enabled'] or 
                              self.config['embedding']['document_cache']['enabled'],
                    'target_hit_rate': self.config['embedding']['target_hit_rate'],
                    'actual_hit_rate': self.metrics.embedding_metrics.get('overall_hit_rate', 0.0),
                },
                'system_prompt': {
                    'enabled': self.config['system_prompt']['enabled'],
                    'target_hit_rate': self.config['system_prompt']['target_hit_rate'],
                    'actual_hit_rate': self.metrics.system_prompt_metrics.get('hit_rate', 0.0),
                }
            }
        })
        
        return metrics_dict
    
    def reset_metrics(self):
        """Reset all metrics"""
        self.metrics = CacheManagerMetrics()
        self._last_metrics_reset = time.time()
        
        # Reset level-specific metrics
        self._semantic_query_cache.reset_metrics()
        self._embedding_cache.reset_metrics()
        self._system_prompt_cache.reset_metrics()
        
        logger.info("CacheManager metrics reset")
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive health check
        
        Returns:
            Health status for all levels
        """
        health = {
            'overall_status': 'healthy',
            'cache_levels': {},
            'issues': []
        }
        
        try:
            # Check each cache level
            semantic_health = self._semantic_query_cache.health_check()
            embedding_health = self._embedding_cache.health_check()
            prompt_health = self._system_prompt_cache.health_check()
            
            health['cache_levels'] = {
                'semantic_query': semantic_health,
                'embedding': embedding_health,
                'system_prompt': prompt_health
            }
            
            # Determine overall status
            all_statuses = [h['status'] for h in health['cache_levels'].values()]
            
            if 'unhealthy' in all_statuses:
                health['overall_status'] = 'unhealthy'
            elif 'degraded' in all_statuses:
                health['overall_status'] = 'degraded'
            elif 'disabled' in all_statuses and len(set(all_statuses)) == 1:
                health['overall_status'] = 'disabled'
            
            # Collect issues
            for level, level_health in health['cache_levels'].items():
                if level_health.get('issues'):
                    for issue in level_health['issues']:
                        health['issues'].append(f"{level}: {issue}")
            
            # Check overall hit rates
            overall_metrics = self.get_metrics()
            for level_name, level_config in health['cache_levels'].items():
                if level_config.get('enabled'):
                    target_rate = level_config.get('target_hit_rate', 0.8)
                    actual_rate = overall_metrics['cache_levels'][level_name]['actual_hit_rate']
                    
                    if actual_rate < target_rate * 0.5:
                        health['issues'].append(
                            f"{level_name}: Low hit rate {actual_rate:.2%} (target: {target_rate:.2%})"
                        )
            
            if health['issues'] and health['overall_status'] == 'healthy':
                health['overall_status'] = 'degraded'
        
        except Exception as e:
            health['overall_status'] = 'unhealthy'
            health['issues'].append(f'Health check error: {e}')
        
        return health
    
    # ========================================================================
    # CACHE WARMING AND OPTIMIZATION
    # ========================================================================
    
    async def warm_cache(self, warmup_data: Dict[str, Any] = None) -> Dict[str, int]:
        """
        Warm cache with popular data
        
        Args:
            warmup_data: Data to warm cache with
            
        Returns:
            Dict with counts of warmed entries per level
        """
        results = {
            'semantic_query': 0,
            'embedding_query': 0,
            'embedding_document': 0,
            'system_prompt': 0
        }
        
        if not self._background_tasks_enabled:
            logger.info("Cache warming disabled (monitoring disabled)")
            return results
        
        try:
            logger.info("CacheManager starting cache warming...")
            
            # This is a placeholder for cache warming logic
            # In practice, this would:
            # 1. Identify popular queries from analytics
            # 2. Pre-generate and cache their results
            # 3. Pre-generate and cache common embeddings
            # 4. Pre-generate and cache common system prompts
            
            logger.info(f"CacheManager warming completed: {results}")
            return results
        
        except Exception as e:
            logger.error(f"CacheManager warming error: {e}")
            return results
    
    def optimize_cache(self) -> Dict[str, Any]:
        """
        Optimize cache performance
        
        Returns:
            Optimization results
        """
        results = {
            'evicted_entries': 0,
            'compression_savings': 0,
            'optimizations_applied': []
        }
        
        try:
            logger.info("CacheManager starting cache optimization...")
            
            # This is a placeholder for optimization logic
            # In practice, this would:
            # 1. Analyze cache access patterns
            # 2. Evict least useful entries
            # 3. Apply compression if beneficial
            # 4. Adjust TTL values based on access patterns
            
            logger.info(f"CacheManager optimization completed: {results}")
            return results
        
        except Exception as e:
            logger.error(f"CacheManager optimization error: {e}")
            return results


__all__ = ['CacheManager', 'CacheManagerMetrics']