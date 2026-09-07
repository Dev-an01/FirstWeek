"""
Unified Retrieval System
=====================

Integrates hybrid retrieval system with query routing to ensure they work together seamlessly.
This creates a unified retrieval system that follows Solution Manual specifications.

The UnifiedRetrieval class orchestrates all hybrid retrieval components and integrates
with query routing system to provide the appropriate retrieval strategy based on query
complexity while respecting latency and cost targets.

Author: AI Officer Implementation Team
Date: 2025-10-29
"""

import logging
import time
import asyncio
import concurrent.futures
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import threading
from functools import lru_cache
import hashlib

# Import existing components
from .query_analyzer import QueryAnalyzer
from .memory_search import MultiSignalMemorySearch
from .result_fusion import ResultFusion
from .adaptive_reranker import AdaptiveReranker
from .response_builder import ResponseBuilder
from .graph_enhanced_search import GraphConstrainedVectorSearch
from .config import HYBRID_RETRIEVAL_CONFIG
from .metrics import PerformanceMetrics

# Import query routing
from query_routing.router import QueryRouter, RouteDecision, ProcessingPath

# Import vector search
try:
    from vector_search.postgres_client import PostgresVectorClient
except ImportError:
    # Fallback if postgres_client not available
    PostgresVectorClient = None

# Import graph context
try:
    from graph_context.provider import GraphContextProvider
except ImportError:
    # Fallback if provider not available
    GraphContextProvider = None

# Import profile management
try:
    from profile_management.profile_manager import ProfileManager
except ImportError:
    # Fallback if profile manager not available
    ProfileManager = None

# Import configurations
try:
    from vector_search.config import POSTGRES_CONFIG
except ImportError:
    # Fallback config with provided credentials
    POSTGRES_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ai_officer_dev',
        'user': 'postgres',
        'password': '1234'
    }

try:
    from graph_context.config import NEO4J_CONFIG
except ImportError:
    # Fallback config with provided credentials
    NEO4J_CONFIG = {
        'uri': 'bolt://localhost:7687',
        'user': 'neo4j',
        'password': '12341234'
    }

# Redis configuration for caching
try:
    import redis
    REDIS_CONFIG = {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'decode_responses': True
    }
except ImportError:
    REDIS_CONFIG = None
    redis = None

logger = logging.getLogger(__name__)


class RetrievalPath(Enum):
    """Retrieval paths corresponding to query routing"""
    FAST = "fast"
    STANDARD = "standard"
    AGENTIC = "agentic"


@dataclass
class PathPerformanceMetrics:
    """Performance metrics for each retrieval path"""
    path: str
    latency_ms: float
    cost_estimate: float
    target_met: bool
    components_used: List[str]
    error_occurred: bool
    error_message: Optional[str] = None


class UnifiedRetrieval:
    """
    Unified retrieval system that orchestrates all hybrid retrieval components
    and integrates with query routing system.
    
    This class provides a single interface for different query paths and ensures
    consistent behavior across all paths while respecting latency and cost targets.
    """
    
    def __init__(
        self,
        postgres_config: Optional[Dict] = None,
        neo4j_config: Optional[Dict] = None,
        enable_cache: bool = True,
        enable_metrics: bool = True,
        config_overrides: Optional[Dict] = None,
        enable_parallel: bool = True,
        max_workers: int = 4
    ):
        """
        Initialize the unified retrieval system with enhanced performance optimizations
        
        Args:
            postgres_config: PostgreSQL configuration (defaults to config)
            neo4j_config: Neo4j configuration (defaults to config)
            enable_cache: Enable result caching (default: True)
            enable_metrics: Enable performance metrics (default: True)
            config_overrides: Configuration overrides
            enable_parallel: Enable parallel processing (default: True)
            max_workers: Maximum number of parallel workers (default: 4)
        """
        # Use provided configs or defaults
        self.postgres_config = postgres_config or POSTGRES_CONFIG
        self.neo4j_config = neo4j_config or NEO4J_CONFIG
        
        # Merge configuration
        self.config = {**HYBRID_RETRIEVAL_CONFIG, **(config_overrides or {})}
        
        # Performance and parallel processing settings
        self.enable_cache = enable_cache
        self.enable_metrics = enable_metrics
        self.enable_parallel = enable_parallel
        self.max_workers = max_workers
        
        # Initialize query router
        self.query_router = QueryRouter()
        
        # Initialize core components
        self.query_analyzer = QueryAnalyzer()
        self.result_fusion = ResultFusion()
        self.adaptive_reranker = AdaptiveReranker()
        self.response_builder = ResponseBuilder()
        
        # Initialize performance metrics
        self.performance_metrics = PerformanceMetrics() if enable_metrics else None
        
        # Initialize connection pools and specialized components
        self._init_vector_search()
        self._init_graph_search()
        self._init_memory_search()
        self._init_graph_provider()
        self._init_profile_manager()
        
        # Initialize caching
        self._init_caching()
        
        # Initialize thread pool for parallel processing
        if self.enable_parallel:
            self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        else:
            self.executor = None
        
        # Performance tracking
        self.path_metrics = {
            RetrievalPath.FAST.value: [],
            RetrievalPath.STANDARD.value: [],
            RetrievalPath.AGENTIC.value: []
        }
        
        # Component health status
        self.component_health = {
            'vector_search': False,
            'graph_search': False,
            'memory_search': False,
            'graph_provider': False,
            'profile_manager': False,
            'cache': False
        }
        
        # Path-specific configurations from Solution Manual
        self.path_configs = {
            RetrievalPath.FAST.value: {
                'latency_target_ms': 1500,  # 0.8-1.5s
                'cost_estimate': 0.02,      # ~$0.02 per query
                'description': 'Simple factual queries with direct retrieval',
                'components': ['vector', 'graph_light', 'rerank_lightweight']
            },
            RetrievalPath.STANDARD.value: {
                'latency_target_ms': 2500,  # 1.5-2.5s
                'cost_estimate': 0.06,      # ~$0.06 per query
                'description': 'Decision/recommendation queries with precedent checking',
                'components': ['vector', 'graph', 'memory', 'rerank_medium']
            },
            RetrievalPath.AGENTIC.value: {
                'latency_target_ms': 5000,  # 3-5s
                'cost_estimate': 0.12,      # ~$0.12 per query
                'description': 'Complex analysis with ReAct reasoning',
                'components': ['vector', 'graph', 'memory', 'rerank_full']
            }
        }
        
        # Perform health checks
        self._perform_health_checks()
        
        logger.info("UnifiedRetrieval initialized with all components and optimizations")
        logger.info(f"Path configurations: {list(self.path_configs.keys())}")
        logger.info(f"Component health: {self.component_health}")
    
    def retrieve(
        self,
        query: str,
        executive_id: str,
        user_context: Optional[Dict] = None,
        top_k: int = 10,
        force_path: Optional[str] = None
    ) -> Dict:
        """
        Main entry point for unified retrieval
        
        Routes to appropriate path based on query complexity and applies
        the corresponding retrieval strategy.
        
        Args:
            query: User's natural language question
            executive_id: Which executive context (exec_001, exec_002, etc.)
            user_context: User info for RBAC
            top_k: Number of results to return (default: 10)
            force_path: Force a specific path (for testing)
            
        Returns:
            Unified response with results and metadata
        """
        start_time = time.time()
        
        # Default user context
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "allowed_scopes": ["public", "internal"]
            }
        
        # Step 1: Route query to appropriate path
        if force_path:
            # Use forced path for testing
            route_decision = RouteDecision(
                path=force_path,
                complexity="forced",
                confidence=1.0,
                reasoning=f"Forced to {force_path} path",
                features={},
                processing_time_ms=self.path_configs[force_path]['latency_target_ms'],
                cost_estimate=self.path_configs[force_path]['cost_estimate']
            )
        else:
            # Use query router to determine path
            query_analysis = self.query_analyzer.analyze(query)
            route_decision = self.query_router.route(query, query_analysis)
        
        logger.info(f"Routing to {route_decision.path} path: {route_decision.reasoning}")
        
        # Step 2: Execute path-specific retrieval
        try:
            if route_decision.path == ProcessingPath.FAST.value:
                results, performance = self.fast_path_retrieve(
                    query, executive_id, user_context, top_k
                )
            elif route_decision.path == ProcessingPath.STANDARD.value:
                results, performance = self.standard_path_retrieve(
                    query, executive_id, user_context, top_k
                )
            else:  # AGENTIC
                results, performance = self.agentic_path_retrieve(
                    query, executive_id, user_context, top_k
                )
            
            # Step 3: Build unified response
            total_time = (time.time() - start_time) * 1000
            
            response = {
                "results": results,
                "metadata": {
                    "query": query,
                    "executive_id": executive_id,
                    "routing": {
                        "path": route_decision.path,
                        "complexity": route_decision.complexity,
                        "confidence": route_decision.confidence,
                        "reasoning": route_decision.reasoning,
                        "features": route_decision.features
                    },
                    "performance": {
                        "total_time_ms": total_time,
                        "target_time_ms": route_decision.processing_time_ms,
                        "target_met": total_time <= route_decision.processing_time_ms,
                        "cost_estimate": route_decision.cost_estimate,
                        "path_performance": performance
                    },
                    "components_used": self.path_configs[route_decision.path]['components']
                }
            }
            
            # Step 4: Track metrics
            if self.enable_metrics:
                self._track_path_metrics(route_decision.path, performance)
            
            logger.info(f"Unified retrieval completed in {total_time:.1f}ms "
                       f"(target: {route_decision.processing_time_ms}ms, "
                       f"met: {total_time <= route_decision.processing_time_ms})")
            
            return response
            
        except Exception as e:
            # Step 5: Error handling and fallback
            logger.error(f"Retrieval failed for {route_decision.path} path: {e}", exc_info=True)
            
            # Fallback to simpler path
            fallback_path = self._get_fallback_path(route_decision.path)
            if fallback_path:
                logger.info(f"Falling back to {fallback_path} path")
                return self.retrieve(
                    query, executive_id, user_context, top_k, force_path=fallback_path
                )
            
            # Ultimate fallback - return empty results
            return {
                "results": [],
                "metadata": {
                    "query": query,
                    "executive_id": executive_id,
                    "error": str(e),
                    "routing": {
                        "path": route_decision.path,
                        "complexity": route_decision.complexity,
                        "confidence": route_decision.confidence,
                        "reasoning": route_decision.reasoning,
                        "features": route_decision.features
                    },
                    "performance": {
                        "total_time_ms": (time.time() - start_time) * 1000,
                        "error": True
                    }
                }
            }
    
    def fast_path_retrieve(
        self,
        query: str,
        executive_id: str,
        user_context: Dict,
        top_k: int
    ) -> Tuple[List[Dict], PathPerformanceMetrics]:
        """
        Fast path retrieval for simple queries (0.8-1.5s target)
        
        Uses:
        - Simple graph-enhanced search
        - Lightweight reranking
        - No memory search (for speed)
        - Parallel processing and caching
        """
        start_time = time.time()
        components_used = []
        
        # Check cache first
        cache_key = self._get_cache_key("fast", query, executive_id, str(top_k), user_context.get("company_id", ""))
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.debug("Fast path: Using cached result")
            execution_time = (time.time() - start_time) * 1000
            target_met = execution_time <= self.path_configs[RetrievalPath.FAST.value]['latency_target_ms']
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.FAST.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.FAST.value]['cost_estimate'],
                target_met=target_met,
                components_used=['cache'],
                error_occurred=False
            )
            
            return cached_result["results"], performance
        
        try:
            # Step 1: Graph-enhanced vector search (lightweight)
            logger.debug("Fast path: Executing graph-enhanced search")
            components_used.append('vector')
            
            if self.graph_search:
                components_used.append('graph_light')
                graph_results = self.graph_search.execute_hybrid_search(
                    query=query,
                    user_context=user_context,
                    top_k=top_k * 2,  # Get more for reranking
                    allowed_scopes=user_context.get("allowed_scopes"),
                    company_id=user_context.get("company_id"),
                )
            else:
                # Fallback to vector-only search
                logger.warning("Graph search not available, falling back to vector-only")
                graph_results = {"results": []}
                if self.vector_search:
                    vector_results = self.vector_search.vector_search(
                        query_embedding=self.vector_search.embedding_client.generate_embedding(query),
                        top_k=top_k * 2,
                        min_score=0.3,
                        company_id=user_context.get("company_id"),
                        executive_id=user_context.get("executive_id"),
                    )
                    graph_results["results"] = self._convert_vector_results(vector_results)
            
            # Step 2: Convert to standard format
            results = self._convert_graph_results(graph_results.get("results", []))
            
            # Step 3: Lightweight reranking
            logger.debug("Fast path: Applying lightweight reranking")
            components_used.append('rerank_lightweight')
            
            reranked = self.adaptive_reranker.apply_lightweight_reranking(results, query)
            
            # Step 4: Limit to top_k
            final_results = reranked[:top_k]
            
            # Step 5: Cache result
            self._cache_result(cache_key, {"results": final_results})
            
            # Step 6: Calculate performance metrics
            execution_time = (time.time() - start_time) * 1000
            target_met = execution_time <= self.path_configs[RetrievalPath.FAST.value]['latency_target_ms']
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.FAST.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.FAST.value]['cost_estimate'],
                target_met=target_met,
                components_used=components_used,
                error_occurred=False
            )
            
            # Track metrics
            if self.performance_metrics:
                self.performance_metrics.record_query(
                    latency_ms=execution_time,
                    strategy="fast",
                    sources=components_used,
                    cache_hit=False,
                    error=False
                )
            
            logger.debug(f"Fast path completed in {execution_time:.1f}ms (target met: {target_met})")
            return final_results, performance
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Fast path failed: {e}")
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.FAST.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.FAST.value]['cost_estimate'],
                target_met=False,
                components_used=components_used,
                error_occurred=True,
                error_message=str(e)
            )
            
            # Track error metrics
            if self.performance_metrics:
                self.performance_metrics.record_query(
                    latency_ms=execution_time,
                    strategy="fast",
                    sources=components_used,
                    cache_hit=False,
                    error=True
                )
            
            return [], performance
    
    def standard_path_retrieve(
        self,
        query: str,
        executive_id: str,
        user_context: Dict,
        top_k: int
    ) -> Tuple[List[Dict], PathPerformanceMetrics]:
        """
        Standard path retrieval for medium queries (1.5-2.5s target)
        
        Uses:
        - Full graph-enhanced search
        - Memory search
        - Medium reranking
        - Parallel processing and caching
        """
        start_time = time.time()
        components_used = []
        
        # Check cache first
        cache_key = self._get_cache_key("standard", query, executive_id, str(top_k), user_context.get("company_id", ""))
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.debug("Standard path: Using cached result")
            execution_time = (time.time() - start_time) * 1000
            target_met = execution_time <= self.path_configs[RetrievalPath.STANDARD.value]['latency_target_ms']
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.STANDARD.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.STANDARD.value]['cost_estimate'],
                target_met=target_met,
                components_used=['cache'],
                error_occurred=False
            )
            
            return cached_result["results"], performance
        
        try:
            # Step 1: Execute graph and memory search in parallel
            logger.debug("Standard path: Executing parallel search")
            
            # Prepare parallel tasks
            tasks = []
            
            # Graph search task
            if self.graph_search:
                components_used.append('vector')
                components_used.append('graph')
                tasks.append((
                    self._execute_graph_search,
                    query, user_context, top_k * 2
                ))
            elif self.vector_search:
                components_used.append('vector')
                tasks.append((
                    self._execute_vector_search,
                    query, user_context, top_k * 2
                ))
            
            # Memory search task
            if self.memory_search:
                components_used.append('memory')
                tasks.append((
                    self._execute_memory_search,
                    query, executive_id, user_context
                ))
            
            # Execute tasks in parallel
            if tasks:
                results = self._execute_parallel(tasks)
                graph_results = results[0] if len(results) > 0 else {"results": []}
                memory_results = results[1] if len(results) > 1 else {"results": []}
            else:
                graph_results = {"results": []}
                memory_results = {"results": []}
            
            # Step 2: Fuse results
            logger.debug("Standard path: Fusing results")
            retrieval_results = {
                "vector": {"results": self._convert_graph_results(graph_results.get("results", []))},
                "graph": graph_results,
                "memory": memory_results
            }
            
            fused_results = self.result_fusion.fuse(
                retrieval_results,
                weights=self.config["composite_weights"]
            )
            
            # Step 3: Medium reranking
            logger.debug("Standard path: Applying medium reranking")
            components_used.append('rerank_medium')
            
            reranked = self.adaptive_reranker.apply_medium_reranking(fused_results, query)
            
            # Step 4: Limit to top_k
            final_results = reranked[:top_k]
            
            # Step 5: Cache result
            self._cache_result(cache_key, {"results": final_results})
            
            # Step 6: Calculate performance metrics
            execution_time = (time.time() - start_time) * 1000
            target_met = execution_time <= self.path_configs[RetrievalPath.STANDARD.value]['latency_target_ms']
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.STANDARD.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.STANDARD.value]['cost_estimate'],
                target_met=target_met,
                components_used=components_used,
                error_occurred=False
            )
            
            # Track metrics
            if self.performance_metrics:
                self.performance_metrics.record_query(
                    latency_ms=execution_time,
                    strategy="standard",
                    sources=components_used,
                    cache_hit=False,
                    error=False
                )
            
            logger.debug(f"Standard path completed in {execution_time:.1f}ms (target met: {target_met})")
            return final_results, performance
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Standard path failed: {e}")
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.STANDARD.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.STANDARD.value]['cost_estimate'],
                target_met=False,
                components_used=components_used,
                error_occurred=True,
                error_message=str(e)
            )
            
            # Track error metrics
            if self.performance_metrics:
                self.performance_metrics.record_query(
                    latency_ms=execution_time,
                    strategy="standard",
                    sources=components_used,
                    cache_hit=False,
                    error=True
                )
            
            return [], performance
    
    def _execute_graph_search(self, query: str, user_context: Dict, top_k: int) -> Dict:
        """Execute graph search with error handling"""
        try:
            return self.graph_search.execute_hybrid_search(
                query=query,
                user_context=user_context,
                top_k=top_k,
                allowed_scopes=user_context.get("allowed_scopes"),
                company_id=user_context.get("company_id"),
            )
        except Exception as e:
            logger.error(f"Graph search failed: {e}")
            return {"results": []}
    
    def _execute_vector_search(self, query: str, user_context: Dict, top_k: int) -> Dict:
        """Execute vector search with error handling"""
        try:
            vector_results = self.vector_search.vector_search(
                query_embedding=self.vector_search.embedding_client.generate_embedding(query),
                top_k=top_k,
                min_score=0.3,
                company_id=user_context.get("company_id"),
                executive_id=user_context.get("executive_id"),
            )
            return {"results": self._convert_vector_results(vector_results)}
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return {"results": []}
    
    def _execute_memory_search(self, query: str, executive_id: str, user_context: Dict) -> Dict:
        """Execute memory search with error handling"""
        try:
            return self.memory_search.search_executive_memory(
                query=query,
                executive_id=executive_id,
                current_user_id=user_context.get("user_id"),
                current_user_role=user_context.get("role"),
                top_k=self.config["memory_config"]["max_results"],
                min_similarity=self.config["memory_config"]["min_similarity"],
                time_window_days=self.config["memory_config"]["time_window_days"]
            )
        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            return {"results": []}
    
    def agentic_path_retrieve(
        self,
        query: str,
        executive_id: str,
        user_context: Dict,
        top_k: int
    ) -> Tuple[List[Dict], PathPerformanceMetrics]:
        """
        Agentic path retrieval for complex queries (3-5s target)
        
        Uses:
        - Full graph-enhanced search
        - Memory search
        - Full reranking
        - Profile-based optimizations
        - Parallel processing and caching
        """
        start_time = time.time()
        components_used = []
        
        # Check cache first
        cache_key = self._get_cache_key("agentic", query, executive_id, str(top_k), user_context.get("company_id", ""))
        cached_result = self._get_cached_result(cache_key)
        if cached_result:
            logger.debug("Agentic path: Using cached result")
            execution_time = (time.time() - start_time) * 1000
            target_met = execution_time <= self.path_configs[RetrievalPath.AGENTIC.value]['latency_target_ms']
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.AGENTIC.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.AGENTIC.value]['cost_estimate'],
                target_met=target_met,
                components_used=['cache'],
                error_occurred=False
            )
            
            return cached_result["results"], performance
        
        try:
            # Step 1: Get executive profile for optimizations
            logger.debug("Agentic path: Loading executive profile")
            components_used.append('profile')
            
            profile = self.profile_manager.get_profile(executive_id) if self.profile_manager else {}
            
            # Step 2: Apply path-specific optimizations
            optimized_query = self.apply_path_specific_optimizations(
                query, RetrievalPath.AGENTIC.value, profile
            )
            
            # Step 3: Execute graph, vector, and memory search in parallel
            logger.debug("Agentic path: Executing parallel search")
            components_used.append('vector')
            
            # Prepare parallel tasks
            tasks = []
            
            # Graph search task
            if self.graph_search:
                components_used.append('graph')
                tasks.append((
                    self._execute_graph_search,
                    optimized_query, user_context, top_k * 3
                ))
            elif self.vector_search:
                components_used.append('vector')
                tasks.append((
                    self._execute_vector_search,
                    optimized_query, user_context, top_k * 3
                ))
            
            # Memory search task
            if self.memory_search:
                components_used.append('memory')
                tasks.append((
                    self._execute_agentic_memory_search,
                    optimized_query, executive_id, user_context
                ))
            
            # Execute tasks in parallel
            if tasks:
                results = self._execute_parallel(tasks)
                graph_results = results[0] if len(results) > 0 else {"results": []}
                memory_results = results[1] if len(results) > 1 else {"results": []}
            else:
                graph_results = {"results": []}
                memory_results = {"results": []}
            
            # Step 4: Fuse results with profile-aware weights
            logger.debug("Agentic path: Fusing with profile-aware weights")
            retrieval_results = {
                "vector": {"results": self._convert_graph_results(graph_results.get("results", []))},
                "graph": graph_results,
                "memory": memory_results
            }
            
            # Adjust weights based on profile
            fusion_weights = self._get_profile_aware_weights(profile)
            fused_results = self.result_fusion.fuse(
                retrieval_results,
                weights=fusion_weights
            )
            
            # Step 5: Full reranking
            logger.debug("Agentic path: Applying full reranking")
            components_used.append('rerank_full')
            
            reranked = self.adaptive_reranker.apply_full_reranking(fused_results, query)
            
            # Step 6: Limit to top_k
            final_results = reranked[:top_k]
            
            # Step 7: Cache result
            self._cache_result(cache_key, {"results": final_results})
            
            # Step 8: Calculate performance metrics
            execution_time = (time.time() - start_time) * 1000
            target_met = execution_time <= self.path_configs[RetrievalPath.AGENTIC.value]['latency_target_ms']
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.AGENTIC.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.AGENTIC.value]['cost_estimate'],
                target_met=target_met,
                components_used=components_used,
                error_occurred=False
            )
            
            # Track metrics
            if self.performance_metrics:
                self.performance_metrics.record_query(
                    latency_ms=execution_time,
                    strategy="agentic",
                    sources=components_used,
                    cache_hit=False,
                    error=False
                )
            
            logger.debug(f"Agentic path completed in {execution_time:.1f}ms (target met: {target_met})")
            return final_results, performance
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Agentic path failed: {e}")
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.AGENTIC.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.AGENTIC.value]['cost_estimate'],
                target_met=False,
                components_used=components_used,
                error_occurred=True,
                error_message=str(e)
            )
            
            # Track error metrics
            if self.performance_metrics:
                self.performance_metrics.record_query(
                    latency_ms=execution_time,
                    strategy="agentic",
                    sources=components_used,
                    cache_hit=False,
                    error=True
                )
            
            return [], performance
    
    def _execute_agentic_memory_search(self, query: str, executive_id: str, user_context: Dict) -> Dict:
        """Execute memory search with agentic-specific parameters"""
        try:
            return self.memory_search.search_executive_memory(
                query=query,
                executive_id=executive_id,
                current_user_id=user_context.get("user_id"),
                current_user_role=user_context.get("role"),
                top_k=self.config["memory_config"]["max_results"],
                min_similarity=0.3,  # Lower threshold for complex queries
                time_window_days=365  # Extended window for complex queries
            )
        except Exception as e:
            logger.error(f"Agentic memory search failed: {e}")
            return {"results": []}
    def agentic_path_retrieve(
        self,
        query: str,
        executive_id: str,
        user_context: Dict,
        top_k: int
    ) -> Tuple[List[Dict], PathPerformanceMetrics]:
        """
        Agentic path retrieval for complex queries (3-5s target)
        
        Uses:
        - Full graph-enhanced search
        - Memory search
        - Full reranking
        - Profile-based optimizations
        """
        start_time = time.time()
        components_used = []
        
        try:
            # Step 1: Get executive profile for optimizations
            logger.debug("Agentic path: Loading executive profile")
            components_used.append('profile')
            
            profile = self.profile_manager.get_profile(executive_id)
            
            # Step 2: Graph-enhanced search with profile optimizations
            logger.debug("Agentic path: Executing optimized graph-enhanced search")
            components_used.append('vector')
            
            if self.graph_search:
                components_used.append('graph')
                
                # Apply path-specific optimizations
                optimized_query = self.apply_path_specific_optimizations(
                    query, RetrievalPath.AGENTIC.value, profile
                )
                
                graph_results = self.graph_search.execute_hybrid_search(
                    query=optimized_query,
                    user_context=user_context,
                    top_k=top_k * 3,  # Get more for comprehensive reranking
                    allowed_scopes=user_context.get("allowed_scopes")
                )
            else:
                # Fallback if graph search not available
                logger.warning("Graph search not available, falling back to vector-only")
                graph_results = {"results": []}
                if self.vector_search:
                    vector_results = self.vector_search.search(
                        query=query,
                        top_k=top_k * 3,
                        role=user_context.get("role", "employee")
                    )
                    graph_results["results"] = self._convert_vector_results(vector_results.get("results", []))
            
            # Step 3: Memory search with extended window
            components_used.append('memory')
            
            if self.memory_search:
                logger.debug("Agentic path: Executing extended memory search")
                memory_results = self.memory_search.search_executive_memory(
                    query=optimized_query,
                    executive_id=executive_id,
                    current_user_id=user_context.get("user_id"),
                    current_user_role=user_context.get("role"),
                    top_k=self.config["memory_config"]["max_results"],
                    min_similarity=0.3,  # Lower threshold for complex queries
                    time_window_days=365  # Extended window for complex queries
                )
            else:
                # Fallback if memory search not available
                logger.warning("Memory search not available, skipping")
                memory_results = {"results": []}
            
            # Step 4: Fuse results with profile-aware weights
            logger.debug("Agentic path: Fusing with profile-aware weights")
            retrieval_results = {
                "vector": {"results": self._convert_graph_results(graph_results.get("results", []))},
                "graph": graph_results,
                "memory": memory_results
            }
            
            # Adjust weights based on profile
            fusion_weights = self._get_profile_aware_weights(profile)
            fused_results = self.result_fusion.fuse(
                retrieval_results,
                weights=fusion_weights
            )
            
            # Step 5: Full reranking
            logger.debug("Agentic path: Applying full reranking")
            components_used.append('rerank_full')
            
            reranked = self.adaptive_reranker.apply_full_reranking(fused_results, query)
            
            # Step 6: Limit to top_k
            final_results = reranked[:top_k]
            
            # Step 7: Calculate performance metrics
            execution_time = (time.time() - start_time) * 1000
            target_met = execution_time <= self.path_configs[RetrievalPath.AGENTIC.value]['latency_target_ms']
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.AGENTIC.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.AGENTIC.value]['cost_estimate'],
                target_met=target_met,
                components_used=components_used,
                error_occurred=False
            )
            
            logger.debug(f"Agentic path completed in {execution_time:.1f}ms (target met: {target_met})")
            return final_results, performance
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Agentic path failed: {e}")
            
            performance = PathPerformanceMetrics(
                path=RetrievalPath.AGENTIC.value,
                latency_ms=execution_time,
                cost_estimate=self.path_configs[RetrievalPath.AGENTIC.value]['cost_estimate'],
                target_met=False,
                components_used=components_used,
                error_occurred=True,
                error_message=str(e)
            )
            
            return [], performance
    
    def fuse_results(
        self,
        vector_results: List[Dict],
        graph_results: List[Dict],
        memory_results: List[Dict],
        weights: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Fuse results from multiple sources with composite scoring
        
        Args:
            vector_results: Results from vector search
            graph_results: Results from graph search
            memory_results: Results from memory search
            weights: Optional custom weights
            
        Returns:
            Fused results with composite scores
        """
        # Use default weights if not provided
        if weights is None:
            weights = self.config["composite_weights"]
        
        # Combine all results
        retrieval_results = {
            "vector": {"results": vector_results},
            "graph": {"results": graph_results},
            "memory": {"results": memory_results}
        }
        
        # Fuse using result fusion component
        fused = self.result_fusion.fuse(retrieval_results, weights)
        
        return fused
    
    def apply_path_specific_optimizations(
        self,
        query: str,
        path: str,
        profile: Optional[Dict] = None
    ) -> str:
        """
        Apply path-specific optimizations to the query
        
        Args:
            query: Original query
            path: Retrieval path (fast, standard, agentic)
            profile: Executive profile (optional)
            
        Returns:
            Optimized query
        """
        optimized_query = query
        
        # Apply profile-based optimizations if available
        if profile:
            # Add executive-specific context
            if path == RetrievalPath.AGENTIC.value:
                # For complex queries, add executive's decision patterns
                decision_patterns = profile.get('decision_patterns', [])
                if decision_patterns:
                    # This is a simplified example - in practice, this would be more sophisticated
                    logger.debug(f"Applying executive decision patterns: {len(decision_patterns)} patterns")
        
        # Apply path-specific optimizations
        if path == RetrievalPath.FAST.value:
            # For fast path, simplify query for quick processing
            optimized_query = self._simplify_query(query)
        elif path == RetrievalPath.AGENTIC.value:
            # For agentic path, expand query with related concepts
            optimized_query = self._expand_query(query)
        
        return optimized_query
    
    def _convert_graph_results(self, graph_results: List[Dict]) -> List[Dict]:
        """
        Convert graph-enhanced search results to standard format
        
        Args:
            graph_results: Results from GraphConstrainedVectorSearch
            
        Returns:
            Results in standard format
        """
        standard_results = []
        
        for result in graph_results:
            standard_result = {
                "id": result.get("id"),
                "type": result.get("type"),
                "title": result.get("title"),
                "content": result.get("content"),
                "composite_score": result.get("hybrid_score", result.get("vector_score", 0)),
                "source_scores": {
                    "vector": result.get("vector_score", 0),
                    "graph": result.get("graph_score", 0)
                },
                "provenance": {
                    "found_in": ["vector", "graph"],
                    "graph_distance": result.get("graph_distance"),
                    "why_relevant": "Graph-enhanced vector similarity"
                }
            }
            standard_results.append(standard_result)
        
        return standard_results
    
    def _convert_vector_results(self, vector_results: List[Dict]) -> List[Dict]:
        """
        Convert vector search results to standard format
        
        Args:
            vector_results: Results from VectorSearchEngine
            
        Returns:
            Results in standard format
        """
        standard_results = []
        
        for result in vector_results:
            standard_result = {
                "id": result.get("source_id") or result.get("id"),
                "type": result.get("source_type"),
                "title": result.get("title"),
                "content": result.get("content"),
                "composite_score": result.get("similarity_score", 0),
                "source_scores": {
                    "vector": result.get("similarity_score", 0),
                    "graph": 0.0,
                    "memory": 0.0
                },
                "provenance": {
                    "found_in": ["vector"],
                    "why_relevant": "Vector similarity match"
                }
            }
            standard_results.append(standard_result)
        
        return standard_results
    
    def _get_profile_aware_weights(self, profile: Optional[Dict]) -> Dict:
        """
        Get fusion weights adjusted based on executive profile
        
        Args:
            profile: Executive profile
            
        Returns:
            Adjusted weights for result fusion
        """
        # Start with default weights
        weights = self.config["composite_weights"].copy()
        
        if profile:
            # Adjust weights based on profile characteristics
            formality = profile.get('formality_scale', 0.5)
            
            # More formal executives might rely more on precedents (memory)
            if formality > 0.7:
                weights["memory"] = min(0.2, weights["memory"] * 1.5)
                weights["vector"] = max(0.4, weights["vector"] * 0.9)
            
            # Less formal executives might prefer more recent information
            elif formality < 0.3:
                weights["memory"] = max(0.05, weights["memory"] * 0.7)
                weights["vector"] = min(0.7, weights["vector"] * 1.1)
        
        # Normalize weights to sum to 1.0
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        
        return weights
    
    def _simplify_query(self, query: str) -> str:
        """
        Simplify query for fast path processing
        
        Args:
            query: Original query
            
        Returns:
            Simplified query
        """
        # Remove filler words and focus on key terms
        # This is a simplified implementation
        filler_words = ['the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for']
        
        words = query.split()
        key_words = [word for word in words if word.lower() not in filler_words]
        
        return ' '.join(key_words)
    
    def _expand_query(self, query: str) -> str:
        """
        Expand query with related concepts for agentic path
        
        Args:
            query: Original query
            
        Returns:
            Expanded query
        """
        # This is a simplified implementation
        # In practice, this would use more sophisticated expansion techniques
        
        # Add related business terms
        expansions = {
            'decision': ['decision making', 'choice', 'judgment', 'resolution'],
            'policy': ['guideline', 'rule', 'procedure', 'protocol'],
            'approval': ['authorization', 'permission', 'consent', 'sanction']
        }
        
        expanded_query = query
        for term, related_terms in expansions.items():
            if term.lower() in query.lower():
                # Add one related term to avoid query bloat
                expanded_query += f" {related_terms[0]}"
        
        return expanded_query
    
    def _get_fallback_path(self, failed_path: str) -> Optional[str]:
        """
        Get fallback path when a path fails
        
        Args:
            failed_path: The path that failed
            
        Returns:
            Fallback path or None if no fallback available
        """
        fallback_map = {
            RetrievalPath.AGENTIC.value: RetrievalPath.STANDARD.value,
            RetrievalPath.STANDARD.value: RetrievalPath.FAST.value,
            RetrievalPath.FAST.value: None  # No fallback for fast path
        }
        
        return fallback_map.get(failed_path)
    
    def _track_path_metrics(self, path: str, performance: PathPerformanceMetrics):
        """
        Track performance metrics for a path
        
        Args:
            path: Retrieval path
            performance: Performance metrics
        """
        if not self.enable_metrics:
            return
        
        # Add to path metrics
        self.path_metrics[path].append(performance)
        
        # Keep only last 100 metrics per path
        if len(self.path_metrics[path]) > 100:
            self.path_metrics[path] = self.path_metrics[path][-100:]
    
    def get_performance_summary(self) -> Dict:
        """
        Get performance summary for all paths
        
        Returns:
            Dictionary with performance metrics for each path
        """
        if not self.enable_metrics:
            return {"enabled": False}
        
        summary = {"enabled": True, "paths": {}}
        
        for path, metrics in self.path_metrics.items():
            if not metrics:
                continue
            
            # Calculate statistics
            latencies = [m.latency_ms for m in metrics]
            targets_met = sum(1 for m in metrics if m.target_met)
            errors = sum(1 for m in metrics if m.error_occurred)
            
            path_summary = {
                "total_queries": len(metrics),
                "avg_latency_ms": sum(latencies) / len(latencies),
                "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
                "target_met_pct": (targets_met / len(metrics)) * 100,
                "error_rate_pct": (errors / len(metrics)) * 100,
                "target_latency_ms": self.path_configs[path]['latency_target_ms'],
                "cost_estimate": self.path_configs[path]['cost_estimate']
            }
            
            summary["paths"][path] = path_summary
        
        return summary
    
    def reset_metrics(self):
        """Reset all performance metrics"""
        if self.enable_metrics:
            for path in self.path_metrics:
                self.path_metrics[path] = []
            logger.info("Unified retrieval metrics reset")
    
    def _init_vector_search(self):
        """Initialize vector search with connection pooling"""
        try:
            if PostgresVectorClient:
                self.vector_search = PostgresVectorClient(config=self.postgres_config)
                self.component_health['vector_search'] = True
                logger.info("✅ Vector search initialized with connection pooling")
            else:
                self.vector_search = None
                self.component_health['vector_search'] = False
                logger.warning("⚠️ PostgresVectorClient not available")
        except Exception as e:
            self.vector_search = None
            self.component_health['vector_search'] = False
            logger.error(f"❌ Vector search initialization failed: {e}")
    
    def _init_graph_search(self):
        """Initialize graph-enhanced search with connection pooling"""
        try:
            if GraphConstrainedVectorSearch:
                self.graph_search = GraphConstrainedVectorSearch(
                    neo4j_config=self.neo4j_config,
                    enable_caching=self.enable_cache,
                    max_candidates=self.config.get("max_candidates", {}).get("graph", 50)
                )
                self.component_health['graph_search'] = True
                logger.info("✅ Graph-enhanced search initialized with connection pooling")
            else:
                self.graph_search = None
                self.component_health['graph_search'] = False
                logger.warning("⚠️ GraphConstrainedVectorSearch not available")
        except Exception as e:
            self.graph_search = None
            self.component_health['graph_search'] = False
            logger.error(f"❌ Graph search initialization failed: {e}")
    
    def _init_memory_search(self):
        """Initialize memory search with connection pooling"""
        try:
            if MultiSignalMemorySearch:
                self.memory_search = MultiSignalMemorySearch(
                    postgres_config=self.postgres_config,
                    preload_model=True
                )
                self.component_health['memory_search'] = True
                logger.info("✅ Memory search initialized with connection pooling")
            else:
                self.memory_search = None
                self.component_health['memory_search'] = False
                logger.warning("⚠️ MultiSignalMemorySearch not available")
        except Exception as e:
            self.memory_search = None
            self.component_health['memory_search'] = False
            logger.error(f"❌ Memory search initialization failed: {e}")
    
    def _init_graph_provider(self):
        """Initialize graph context provider with connection pooling"""
        try:
            if GraphContextProvider:
                self.graph_provider = GraphContextProvider(
                    neo4j_config=self.neo4j_config,
                    entity_confidence_threshold=self.config.get("entity_confidence_threshold", 0.7)
                )
                self.component_health['graph_provider'] = True
                logger.info("✅ Graph context provider initialized with connection pooling")
            else:
                self.graph_provider = None
                self.component_health['graph_provider'] = False
                logger.warning("⚠️ GraphContextProvider not available")
        except Exception as e:
            self.graph_provider = None
            self.component_health['graph_provider'] = False
            logger.error(f"❌ Graph provider initialization failed: {e}")
    
    def _init_profile_manager(self):
        """Initialize profile manager"""
        try:
            if ProfileManager:
                self.profile_manager = ProfileManager()
                self.component_health['profile_manager'] = True
                logger.info("✅ Profile manager initialized")
            else:
                self.profile_manager = None
                self.component_health['profile_manager'] = False
                logger.warning("⚠️ ProfileManager not available")
        except Exception as e:
            self.profile_manager = None
            self.component_health['profile_manager'] = False
            logger.error(f"❌ Profile manager initialization failed: {e}")
    
    def _init_caching(self):
        """Initialize caching layer"""
        try:
            if self.enable_cache and redis and REDIS_CONFIG:
                import redis
                self.cache_client = redis.Redis(**REDIS_CONFIG)
                # Test connection
                self.cache_client.ping()
                self.component_health['cache'] = True
                logger.info("✅ Redis cache initialized")
            else:
                self.cache_client = None
                self.component_health['cache'] = False
                logger.warning("⚠️ Redis not available, using in-memory caching")
                
                # Fallback to simple in-memory cache
                self._memory_cache = {}
                self._cache_lock = threading.Lock()
        except Exception as e:
            self.cache_client = None
            self.component_health['cache'] = False
            logger.error(f"❌ Cache initialization failed: {e}")
            
            # Fallback to simple in-memory cache
            self._memory_cache = {}
            self._cache_lock = threading.Lock()
    
    def _perform_health_checks(self):
        """Perform health checks on all components"""
        logger.info("Performing component health checks...")
        
        health_status = {
            'vector_search': self._check_vector_search_health(),
            'graph_search': self._check_graph_search_health(),
            'memory_search': self._check_memory_search_health(),
            'graph_provider': self._check_graph_provider_health(),
            'profile_manager': self._check_profile_manager_health(),
            'cache': self._check_cache_health()
        }
        
        self.component_health.update(health_status)
        
        # Log overall health
        healthy_components = sum(1 for status in health_status.values() if status)
        total_components = len(health_status)
        health_percentage = (healthy_components / total_components) * 100
        
        logger.info(f"Health check complete: {healthy_components}/{total_components} components healthy ({health_percentage:.1f}%)")
        
        if health_percentage < 80:
            logger.warning("⚠️ System health below 80%, some features may be degraded")
    
    def _check_vector_search_health(self) -> bool:
        """Check vector search component health"""
        if not self.vector_search:
            return False
        try:
            # Simple health check - try to get a connection
            conn = self.vector_search.get_connection()
            self.vector_search.return_connection(conn)
            return True
        except Exception as e:
            logger.debug(f"Vector search health check failed: {e}")
            return False
    
    def _check_graph_search_health(self) -> bool:
        """Check graph search component health"""
        if not self.graph_search:
            return False
        try:
            # Simple health check - test Neo4j connection
            with self.graph_search.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            return True
        except Exception as e:
            logger.debug(f"Graph search health check failed: {e}")
            return False
    
    def _check_memory_search_health(self) -> bool:
        """Check memory search component health"""
        if not self.memory_search:
            return False
        try:
            # Simple health check - test PostgreSQL connection
            conn = self.memory_search.pg_pool.getconn()
            self.memory_search.pg_pool.putconn(conn)
            return True
        except Exception as e:
            logger.debug(f"Memory search health check failed: {e}")
            return False
    
    def _check_graph_provider_health(self) -> bool:
        """Check graph provider component health"""
        if not self.graph_provider:
            return False
        try:
            # Simple health check - test Neo4j connection
            with self.graph_provider.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                result.single()
            return True
        except Exception as e:
            logger.debug(f"Graph provider health check failed: {e}")
            return False
    
    def _check_profile_manager_health(self) -> bool:
        """Check profile manager component health"""
        if not self.profile_manager:
            return False
        try:
            # Simple health check - try to list profiles
            self.profile_manager.list_profiles()
            return True
        except Exception as e:
            logger.debug(f"Profile manager health check failed: {e}")
            return False
    
    def _check_cache_health(self) -> bool:
        """Check cache component health"""
        if self.cache_client:
            try:
                # Test Redis connection
                self.cache_client.ping()
                return True
            except Exception as e:
                logger.debug(f"Redis health check failed: {e}")
                return False
        else:
            # In-memory cache is always "healthy"
            return True
    
    def _get_cache_key(self, *args) -> str:
        """Generate cache key from arguments"""
        key_str = "|".join(str(arg) for arg in args)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """Get cached result if available"""
        if not self.enable_cache:
            return None
            
        try:
            if self.cache_client:
                cached_data = self.cache_client.get(cache_key)
                if cached_data:
                    import json
                    return json.loads(cached_data)
            else:
                # Fallback to in-memory cache
                with self._cache_lock:
                    if cache_key in self._memory_cache:
                        cached_data, timestamp = self._memory_cache[cache_key]
                        # Check if cache is still valid (5 minutes TTL)
                        if time.time() - timestamp < 300:
                            return cached_data
                        else:
                            # Remove expired entry
                            del self._memory_cache[cache_key]
        except Exception as e:
            logger.debug(f"Cache retrieval failed: {e}")
        
        return None
    
    def _cache_result(self, cache_key: str, result: Dict):
        """Cache result for future use"""
        if not self.enable_cache:
            return
            
        try:
            if self.cache_client:
                import json
                self.cache_client.setex(
                    cache_key,
                    300,  # 5 minutes TTL
                    json.dumps(result)
                )
            else:
                # Fallback to in-memory cache
                with self._cache_lock:
                    self._memory_cache[cache_key] = (result, time.time())
                    
                    # Limit in-memory cache size
                    if len(self._memory_cache) > 100:
                        # Remove oldest entry
                        oldest_key = min(
                            self._memory_cache.keys(),
                            key=lambda k: self._memory_cache[k][1]
                        )
                        del self._memory_cache[oldest_key]
        except Exception as e:
            logger.debug(f"Cache storage failed: {e}")
    
    def _execute_parallel(self, tasks: List[Tuple]) -> List[Any]:
        """Execute tasks in parallel using thread pool"""
        if not self.enable_parallel or not self.executor or len(tasks) == 1:
            # Execute sequentially
            results = []
            for task_func, *task_args in tasks:
                results.append(task_func(*task_args))
            return results
        
        # Execute in parallel
        futures = []
        for task_func, *task_args in tasks:
            future = self.executor.submit(task_func, *task_args)
            futures.append(future)
        
        # Collect results
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result(timeout=30)  # 30 second timeout per task
                results.append(result)
            except Exception as e:
                logger.error(f"Parallel task failed: {e}")
                results.append(None)
        
        return results
    
    def get_component_health(self) -> Dict[str, bool]:
        """Get current component health status"""
        return self.component_health.copy()
    
    def get_performance_metrics(self) -> Dict:
        """Get comprehensive performance metrics"""
        if not self.performance_metrics:
            return {"enabled": False}
        
        base_metrics = self.performance_metrics.get_summary()
        
        # Add path-specific metrics
        path_metrics = {}
        for path, metrics_list in self.path_metrics.items():
            if metrics_list:
                latencies = [m.latency_ms for m in metrics_list]
                targets_met = sum(1 for m in metrics_list if m.target_met)
                
                path_metrics[path] = {
                    "total_queries": len(metrics_list),
                    "avg_latency_ms": sum(latencies) / len(latencies),
                    "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)],
                    "target_met_pct": (targets_met / len(metrics_list)) * 100,
                    "target_latency_ms": self.path_configs[path]['latency_target_ms']
                }
        
        base_metrics["path_performance"] = path_metrics
        base_metrics["component_health"] = self.component_health
        
        return base_metrics
    
    def close(self):
        """Close all connections and clean up resources"""
        logger.info("Closing UnifiedRetrieval resources...")
        
        # Close thread pool
        if self.executor:
            self.executor.shutdown(wait=True)
        
        # Close vector search
        if self.vector_search:
            self.vector_search.close()
        
        # Close graph search
        if self.graph_search:
            self.graph_search.close()
        
        # Close memory search
        if self.memory_search:
            self.memory_search.__del__()
        
        # Close graph provider
        if self.graph_provider:
            self.graph_provider.close()
        
        # Close cache
        if self.cache_client:
            self.cache_client.close()
        
        logger.info("UnifiedRetrieval resources closed")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


__all__ = ['UnifiedRetrieval', 'RetrievalPath', 'PathPerformanceMetrics']