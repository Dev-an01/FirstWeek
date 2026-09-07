"""
Cache Integration Layer
======================

Integrates the three-level caching system with existing components:

- Query routing system
- Hybrid retrieval system
- LLM integration layer
- API endpoints

Provides seamless caching without disrupting existing workflows.

Author: AI Officer Implementation Team
Date: 2025-10-30
"""

import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from functools import wraps

from .cache_manager import CacheManager
from .config import CACHE_INTEGRATION_CONFIG

logger = logging.getLogger(__name__)


class CacheIntegratedHybridRetrieval:
    """
    Wrapper for hybrid retrieval with caching integration
    
    Adds caching to hybrid retrieval operations without modifying
    the original hybrid retrieval implementation.
    """
    
    def __init__(self, hybrid_retrieval, cache_manager: CacheManager):
        """
        Initialize cache-integrated hybrid retrieval
        
        Args:
            hybrid_retrieval: Original hybrid retrieval instance
            cache_manager: Cache manager instance
        """
        self.hybrid_retrieval = hybrid_retrieval
        self.cache_manager = cache_manager
        self.config = CACHE_INTEGRATION_CONFIG
        
        logger.info("CacheIntegratedHybridRetrieval initialized")
    
    def retrieve(self, query: str, executive_id: str, user_context: Dict[str, Any],
                top_k: int = 10, force_path: str = None) -> Dict[str, Any]:
        """
        Retrieve with caching integration
        
        Args:
            query: User query
            executive_id: Executive profile ID
            user_context: User context for RBAC
            top_k: Number of results to return
            force_path: Force specific path
            
        Returns:
            Retrieval results with cache metadata
        """
        # Check cache first (Level 1)
        cache_key_data = {
            'query': query,
            'executive_id': executive_id,
            'user_context': user_context,
            'top_k': top_k,
            'path': force_path
        }
        
        cached_result = self.cache_manager.get_query_result(
            query, user_context, executive_id, force_path
        )
        
        if cached_result:
            logger.info(f"CacheIntegratedHybridRetrieval: Cache hit for query: {query[:50]}...")
            
            # Add cache metadata
            cached_result['cache_hit'] = True
            cached_result['cache_level'] = 'semantic_query'
            
            return cached_result
        
        # Cache miss - proceed with original retrieval
        logger.info(f"CacheIntegratedHybridRetrieval: Cache miss for query: {query[:50]}...")
        
        start_time = time.time()
        result = self.hybrid_retrieval.retrieve(
            query, executive_id, user_context, top_k, force_path
        )
        retrieval_time = (time.time() - start_time) * 1000
        
        # Cache the result
        if result and result.get('results'):
            cache_metadata = {
                'retrieval_time_ms': retrieval_time,
                'path': force_path or result.get('metadata', {}).get('routing', {}).get('path'),
                'components_used': result.get('metadata', {}).get('components_used', []),
                'top_k': top_k
            }
            
            self.cache_manager.set_query_result(
                query, user_context, executive_id, result, force_path, cache_metadata
            )
        
        # Add cache metadata
        result['cache_hit'] = False
        result['cache_level'] = None
        result['retrieval_time_ms'] = retrieval_time
        
        return result
    
    def retrieve_with_llm(self, query: str, executive_id: str, user_context: Dict[str, Any],
                         top_k: int = 10, force_path: str = None) -> Dict[str, Any]:
        """
        Retrieve with LLM and caching integration
        
        Args:
            query: User query
            executive_id: Executive profile ID
            user_context: User context for RBAC
            top_k: Number of results to return
            force_path: Force specific path
            
        Returns:
            LLM response with cache metadata
        """
        # Check cache first (Level 1)
        cached_result = self.cache_manager.get_query_result(
            query, user_context, executive_id, force_path
        )
        
        if cached_result:
            logger.info(f"CacheIntegratedHybridRetrieval: LLM cache hit for query: {query[:50]}...")
            
            # Add cache metadata
            cached_result['cache_hit'] = True
            cached_result['cache_level'] = 'semantic_query'
            
            return cached_result
        
        # Cache miss - proceed with original retrieval
        logger.info(f"CacheIntegratedHybridRetrieval: LLM cache miss for query: {query[:50]}...")
        
        start_time = time.time()
        
        # Check if the hybrid retrieval has retrieve_with_llm method
        if hasattr(self.hybrid_retrieval, 'retrieve_with_llm'):
            result = self.hybrid_retrieval.retrieve_with_llm(
                query, executive_id, user_context, top_k, force_path
            )
        else:
            # Fallback to regular retrieve + LLM processing
            retrieval_result = self.hybrid_retrieval.retrieve(
                query, executive_id, user_context, top_k, force_path
            )
            
            # This would need LLM processing - simplified for now
            result = {
                'answer': 'LLM processing would happen here',
                'citations': [],
                'sources': [],
                'metadata': retrieval_result.get('metadata', {})
            }
        
        total_time = (time.time() - start_time) * 1000
        
        # Cache the result
        if result:
            cache_metadata = {
                'total_time_ms': total_time,
                'path': force_path or result.get('metadata', {}).get('path'),
                'llm_model': result.get('metadata', {}).get('llm_model'),
                'top_k': top_k
            }
            
            self.cache_manager.set_query_result(
                query, user_context, executive_id, result, force_path, cache_metadata
            )
        
        # Add cache metadata
        result['cache_hit'] = False
        result['cache_level'] = None
        result['total_time_ms'] = total_time
        
        return result


class CacheIntegratedLLMOrchestrator:
    """
    Wrapper for LLM orchestrator with caching integration
    
    Adds caching to LLM operations, especially for system prompts.
    """
    
    def __init__(self, llm_orchestrator, cache_manager: CacheManager):
        """
        Initialize cache-integrated LLM orchestrator
        
        Args:
            llm_orchestrator: Original LLM orchestrator instance
            cache_manager: Cache manager instance
        """
        self.llm_orchestrator = llm_orchestrator
        self.cache_manager = cache_manager
        self.config = CACHE_INTEGRATION_CONFIG
        
        logger.info("CacheIntegratedLLMOrchestrator initialized")
    
    def generate(self, query: str, vector_results: List[Dict[str, Any]],
                profile_id: str = "akiko_tanaka", graph_results: Optional[List[Dict[str, Any]]] = None,
                precedents: Optional[List[Dict[str, Any]]] = None, memory: Optional[List[Dict[str, Any]]] = None,
                force_path: Optional[str] = None, query_analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate response with caching integration
        
        Args:
            query: User's question
            vector_results: Vector search results
            profile_id: Executive profile ID
            graph_results: Optional graph context
            precedents: Optional historical precedents
            memory: Optional conversation history
            force_path: Optional path override
            query_analysis: Optional pre-analyzed query data
            
        Returns:
            Generated response with cache metadata
        """
        # Check system prompt cache (Level 3)
        path = force_path or 'standard'  # Default path
        context = {
            'has_graph_results': bool(graph_results),
            'has_precedents': bool(precedents),
            'has_memory': bool(memory),
            'vector_results_count': len(vector_results)
        }
        
        cached_prompt = self.cache_manager.get_system_prompt(profile_id, path, context)
        
        # Generate response using original orchestrator
        start_time = time.time()
        
        # The orchestrator will handle prompt generation internally
        # We're just caching the final response here
        response = self.llm_orchestrator.generate(
            query, vector_results, profile_id, graph_results,
            precedents, memory, force_path, query_analysis
        )
        
        generation_time = (time.time() - start_time) * 1000
        
        # Cache the system prompt for future use
        if cached_prompt is None and response:
            # Extract system prompt from response metadata if available
            system_prompt = response.get('metadata', {}).get('system_prompt')
            if system_prompt:
                self.cache_manager.set_system_prompt(
                    profile_id, path, system_prompt, context
                )
        
        # Add cache metadata
        response['cache_metadata'] = {
            'system_prompt_cached': cached_prompt is not None,
            'generation_time_ms': generation_time,
            'cache_integration_enabled': True
        }
        
        return response


def cache_integration_decorator(cache_manager: CacheManager, cache_level: str = 'semantic_query'):
    """
    Decorator for adding cache integration to functions
    
    Args:
        cache_manager: Cache manager instance
        cache_level: Level of caching to apply
        
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extract cache-relevant parameters
            query = kwargs.get('query') or (args[0] if args else None)
            user_context = kwargs.get('user_context') or (args[1] if len(args) > 1 else {})
            executive_id = kwargs.get('executive_id') or (args[2] if len(args) > 2 else None)
            
            # Skip caching if essential parameters missing
            if not all([query, user_context, executive_id]):
                return func(*args, **kwargs)
            
            # Check cache
            if cache_level == 'semantic_query':
                cached_result = cache_manager.get_query_result(
                    query, user_context, executive_id
                )
                
                if cached_result:
                    logger.debug(f"Cache decorator: Hit for {cache_level}")
                    return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            if cache_level == 'semantic_query' and result:
                cache_manager.set_query_result(
                    query, user_context, executive_id, result
                )
            
            return result
        
        return wrapper
    return decorator


class CacheIntegrationManager:
    """
    Manages integration of caching system with existing components
    
    Provides factory methods for creating cache-integrated components.
    """
    
    def __init__(self, cache_manager: CacheManager):
        """
        Initialize cache integration manager
        
        Args:
            cache_manager: Cache manager instance
        """
        self.cache_manager = cache_manager
        self.config = CACHE_INTEGRATION_CONFIG
        
        logger.info("CacheIntegrationManager initialized")
    
    def integrate_hybrid_retrieval(self, hybrid_retrieval) -> CacheIntegratedHybridRetrieval:
        """
        Create cache-integrated hybrid retrieval
        
        Args:
            hybrid_retrieval: Original hybrid retrieval instance
            
        Returns:
            Cache-integrated hybrid retrieval
        """
        if not self.config.get('integrate_with_hybrid_retrieval', True):
            return hybrid_retrieval
        
        return CacheIntegratedHybridRetrieval(hybrid_retrieval, self.cache_manager)
    
    def integrate_llm_orchestrator(self, llm_orchestrator) -> CacheIntegratedLLMOrchestrator:
        """
        Create cache-integrated LLM orchestrator
        
        Args:
            llm_orchestrator: Original LLM orchestrator instance
            
        Returns:
            Cache-integrated LLM orchestrator
        """
        if not self.config.get('integrate_with_llm_integration', True):
            return llm_orchestrator
        
        return CacheIntegratedLLMOrchestrator(llm_orchestrator, self.cache_manager)
    
    def get_cache_health(self) -> Dict[str, Any]:
        """Get cache health status"""
        return self.cache_manager.health_check()
    
    def get_cache_metrics(self) -> Dict[str, Any]:
        """Get cache metrics"""
        return self.cache_manager.get_metrics()
    
    def invalidate_cache_by_executive(self, executive_id: str) -> Dict[str, int]:
        """Invalidate cache for specific executive"""
        return self.cache_manager.invalidate_by_executive(executive_id)
    
    def update_system_prompt_version(self, version: str) -> bool:
        """Update system prompt version"""
        return self.cache_manager.update_system_prompt_version(version)


__all__ = [
    'CacheIntegratedHybridRetrieval',
    'CacheIntegratedLLMOrchestrator',
    'CacheIntegrationManager',
    'cache_integration_decorator'
]