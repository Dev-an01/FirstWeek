"""
Hybrid Retrieval Manager
=========================

Master orchestrator for multi-source retrieval.

Flow:
1. Analyze query (type, complexity, entities)
2. Select strategy (vector_only / vector_graph / full_hybrid)
3. Execute parallel retrieval (vector, graph, memory)
4. Fuse results (deduplicate, normalize scores)
5. Adaptive reranking (lightweight/medium/full)
6. Build response (format, add provenance)

This is the SINGLE entry point for all retrieval operations.
"""

import logging
import time
import concurrent.futures
from typing import Dict, List, Optional

from .query_analyzer import QueryAnalyzer
from .memory_search import MultiSignalMemorySearch
from .result_fusion import ResultFusion
from .adaptive_reranker import AdaptiveReranker
from .response_builder import ResponseBuilder
from .query_decomposer import QueryDecomposer
from .query_type_classifier import QueryTypeClassifier  # NEW: Query-type weighting
from llm_integration.decomposition_handler import DecompositionHandler
from llm_integration.sub_query_processor import SubQueryProcessor, ProcessingConfig
from .config import HYBRID_RETRIEVAL_CONFIG
from .utils import get_logger
import yaml
from pathlib import Path

# Observability imports
from observability.decorators import trace_function
from observability.logging import StructuredLogger
from observability.metrics import (
    retrieval_strategy_counter,
    retrieval_latency,
    retrieval_results_counter,
    vector_search_latency,
    graph_query_latency,
    memory_search_latency,
    fusion_latency,
)

# WEEK 1, DAY 3: LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_AVAILABLE = True
except ImportError:
    # Fallback: no-op decorator that accepts keyword arguments
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator
    LANGSMITH_AVAILABLE = False

logger = get_logger(__name__)
obs_logger = StructuredLogger('hybrid_retrieval_manager')


class HybridRetrievalManager:
    """
    Unified retrieval interface combining vector, graph, and memory
    
    This is the main orchestrator that coordinates all retrieval components.
    """
    
    def __init__(
        self,
        vector_search_engine,  # VectorSearchEngine from Blueprint #2
        graph_context_provider,  # GraphContextProvider from Blueprint #3.5
        memory_search_engine: Optional[MultiSignalMemorySearch] = None,
        config: Optional[Dict] = None,
        enable_cache: bool = True,  # NEW: Enable result caching
        enable_metrics: bool = True,  # NEW: Enable performance metrics
        enable_decomposition: bool = True,  # NEW: Enable query decomposition
        llm_provider: str = "openai",  # NEW: LLM provider for decomposition
        llm_config: Optional[Dict] = None  # NEW: LLM configuration
    ):
        """
        Initialize hybrid retrieval manager
        
        Args:
            vector_search_engine: From Blueprint #2
            graph_context_provider: From Blueprint #3.5 (enhanced NER)
            memory_search_engine: NEW component (this blueprint)
            config: Configuration overrides
            enable_cache: Enable LRU cache with TTL (default: True)
            enable_metrics: Enable performance tracking (default: True)
            enable_decomposition: Enable query decomposition (default: True)
            llm_provider: LLM provider for decomposition (default: openai)
            llm_config: LLM configuration for decomposition
        """
        self.vector = vector_search_engine
        self.graph = graph_context_provider
        self.memory = memory_search_engine
        
        # Initialize sub-components
        self.query_analyzer = QueryAnalyzer()
        self.result_fusion = ResultFusion()
        self.adaptive_reranker = AdaptiveReranker()
        self.response_builder = ResponseBuilder()

        # NEW: Query-type adaptive weighting
        self.query_type_classifier = QueryTypeClassifier()
        self.retrieval_weights = self._load_retrieval_weights()
        logger.info("[HybridRetrieval] Query-type adaptive weighting enabled")

        # Merge configuration
        self.config = {**HYBRID_RETRIEVAL_CONFIG, **(config or {})}
        
        # NEW: Result cache
        self.cache = None
        if enable_cache:
            from .result_cache import ResultCache
            self.cache = ResultCache(
                max_size=self.config.get("cache_max_size", 100),
                ttl_seconds=self.config.get("cache_ttl_seconds", 300)
            )
            logger.info("[HybridRetrieval] Result caching enabled")
        
        # NEW: Performance metrics
        self.metrics = None
        if enable_metrics:
            from .metrics import PerformanceMetrics
            self.metrics = PerformanceMetrics()
            logger.info("[HybridRetrieval] Performance metrics enabled")
        
        # NEW: Query decomposer
        self.query_decomposer = None
        self.decomposition_handler = None
        if enable_decomposition:
            # Create processing config
            decomp_config = self.config.get("query_decomposition", {})
            processing_config = ProcessingConfig(
                mode=decomp_config.get("processing_mode", "dependency_aware"),
                max_workers=decomp_config.get("max_workers", 3),
                timeout_seconds=decomp_config.get("timeout_seconds", 30),
                min_confidence_threshold=decomp_config.get("min_confidence_threshold", 0.3),
                min_result_count=decomp_config.get("min_result_count", 1),
                enable_caching=decomp_config.get("enable_caching", True),
                enable_validation=decomp_config.get("enable_validation", True),
                retry_failed_queries=decomp_config.get("retry_failed_queries", True),
                max_retries=decomp_config.get("max_retries", 2),
                cache_ttl_seconds=decomp_config.get("cache_ttl_seconds", 300)
            )
            
            # Initialize sub-query processor
            sub_query_processor = SubQueryProcessor(
                retrieval_manager=self,
                config=processing_config
            )
            
            # Initialize decomposition handler
            self.decomposition_handler = DecompositionHandler(
                retrieval_manager=self,
                llm_provider=llm_provider,
                llm_config=llm_config or {},
                config=decomp_config
            )
            
            # Keep legacy decomposer for backward compatibility
            self.query_decomposer = self.decomposition_handler
            
            logger.info("[HybridRetrieval] Enhanced query decomposition enabled")
        
        logger.info("[HybridRetrievalManager] Initialized with all components")
    
    @trace_function("hybrid_retrieval_manager", "retrieve")
    @traceable(name="hybrid_retrieval", tags=["retrieval", "orchestration"])
    def retrieve(
        self,
        query: str,
        executive_id: str,
        user_context: Optional[Dict] = None,
        top_k: int = 10,
        strategy: str = "auto",
        use_section_search: bool = False
    ) -> Dict:
        """
        Unified retrieval interface - MAIN METHOD

        This is the single entry point for all retrieval operations.

        Args:
            query: User's natural language question
            executive_id: Which executive context (exec_001, exec_002, etc.)
            user_context: User info for RBAC {
                "user_id": "U123",
                "role": "employee",
                "allowed_scopes": ["public", "internal"]
            }
            top_k: Number of results to return (default: 10)
            strategy: "auto" | "vector_only" | "vector_graph" | "full_hybrid"
            use_section_search: Enable section-level retrieval (default: False)
        
        Returns:
            {
                "results": [
                    {
                        "rank": 1,
                        "id": "DC_AKIKO_001",
                        "type": "decision_case",
                        "title": "MegaCorp Discount Approval",
                        "content": "...",
                        "final_score": 0.94,
                        "source_scores": {
                            "vector": 0.89,
                            "graph": 1.0,
                            "memory": 0.85
                        },
                        "provenance": {
                            "found_in": ["vector", "graph", "memory"],
                            "graph_context": "Akiko MADE_DECISION...",
                            "memory_context": "Similar to query 3 days ago",
                            "why_relevant": "Multi-source agreement..."
                        }
                    },
                    ...
                ],
                "metadata": {
                    "query": "...",
                    "query_analysis": {...},
                    "retrieval_strategy": {...},
                    "performance": {...}
                }
            }
        
        Flow:
        1. Query Analysis → Determine complexity, extract entities
        2. Strategy Selection → Choose retrieval sources
        3. Parallel Retrieval → Execute vector, graph, memory
        4. Result Fusion → Merge, deduplicate, composite scoring
        5. Adaptive Reranking → Apply quality-based reranking
        6. Response Building → Format final output
        """
        start_time = time.time()
        
        # Log retrieval started
        obs_logger.info(
            "Hybrid retrieval started",
            query_length=len(query),
            executive_id=executive_id,
            top_k=top_k,
            strategy=strategy
        )
        
        # Default user context
        if user_context is None:
            user_context = {
                "user_id": "unknown",
                "role": "employee",
                "allowed_scopes": ["public", "internal"]
            }
        
        # NEW: Check cache first
        if self.cache:
            cached_result = self.cache.get(query, strategy, executive_id, company_id=user_context.get("company_id", ""))
            if cached_result:
                # Add cache metadata
                cached_result["metadata"]["cache_hit"] = True
                cached_result["metadata"]["cache_age_seconds"] = int(
                    time.time() - start_time
                )
                logger.info(f"[HybridRetrieval] ✅ Cache hit for: {query[:50]}...")
                
                # NEW: Record cache hit metrics
                if self.metrics:
                    # Extract sources from cached response
                    sources = []
                    if "metadata" in cached_result and "retrieval" in cached_result["metadata"]:
                        ret_meta = cached_result["metadata"]["retrieval"]
                        if ret_meta.get("vector_count", 0) > 0:
                            sources.append("vector")
                        if ret_meta.get("graph_count", 0) > 0:
                            sources.append("graph")
                        if ret_meta.get("memory_count", 0) > 0:
                            sources.append("memory")
                    
                    self.metrics.record_query(
                        latency_ms=(time.time() - start_time) * 1000,  # Near-zero latency
                        strategy=strategy if strategy != "auto" else cached_result["metadata"].get("strategy", "unknown"),
                        sources=sources,
                        cache_hit=True,
                        error=False
                    )
                
                return cached_result
        
        # Query analysis
        logger.info(f"[HybridRetrieval] Analyzing query: {query[:50]}...")
        query_analysis = self.query_analyzer.analyze(query)
        
        # NEW: Check if query needs decomposition
        if self.decomposition_handler and strategy != "vector_only":
            decomposition_result = self.decomposition_handler.process_query(
                query=query,
                executive_id=executive_id,
                user_context=user_context,
                entities=query_analysis.get("entities", []),
                query_analysis=query_analysis
            )
            
            if decomposition_result.needs_decomposition:
                logger.info(f"[HybridRetrieval] Query decomposed into {len(decomposition_result.sub_queries)} sub-queries")
                
                # Build response from decomposition result
                decomposition_response = self._build_enhanced_decomposition_response(
                    decomposition_result,
                    query,
                    query_analysis,
                    time.time() - start_time
                )
                
                # Store in cache
                if self.cache:
                    self.cache.set(query, strategy, executive_id, decomposition_response, company_id=user_context.get("company_id", ""))
                
                # Mark as cache miss
                decomposition_response["metadata"]["cache_hit"] = False
                
                # Record metrics
                if self.metrics:
                    self.metrics.record_query(
                        latency_ms=decomposition_result.total_processing_time_ms,
                        strategy="decomposition",
                        sources=["vector", "graph", "memory"],  # Decomposition uses all sources
                        cache_hit=False,
                        error=False
                    )
                
                return decomposition_response
        
        # Strategy selection
        if strategy == "auto":
            strategy = self._select_strategy(query_analysis)
        logger.info(f"[HybridRetrieval] Strategy: {strategy}")
        
        # Track strategy selection
        retrieval_strategy_counter.labels(strategy=strategy).inc()
        obs_logger.info(
            "Retrieval strategy selected",
            strategy=strategy,
            query_type=query_analysis.get("query_type"),
            complexity=query_analysis.get("complexity_score")
        )
        
        # Multi-source parallel retrieval
        retrieval_results = self._parallel_retrieve(
            query=query,
            executive_id=executive_id,
            strategy=strategy,
            user_context=user_context,
            query_analysis=query_analysis,
            use_section_search=use_section_search
        )
        
        # Result fusion with adaptive weighting
        query_classification = self.query_type_classifier.classify(query)

        # NEW: Get query-type adaptive weights instead of fixed weights
        adaptive_weights = self._get_adaptive_weights(query, query_analysis, query_classification)

        fused_results = self.result_fusion.fuse(
            retrieval_results,
            weights=adaptive_weights  # NEW: Use adaptive weights
        )
        logger.info(
            f"[HybridRetrieval] Fused {len(fused_results)} unique results "
            f"with adaptive weights (V={adaptive_weights['vector']:.2f}, "
            f"G={adaptive_weights['graph']:.2f}, M={adaptive_weights['memory']:.2f})"
        )

        # Adaptive reranking (Priority 2: pass query_classification for smarter strategy selection)
        reranked_results = self.adaptive_reranker.rerank(
            results=fused_results,
            query=query,
            quality_assessment=query_analysis,
            config=self.config["reranking_thresholds"],
            query_classification={
                "type": query_classification.query_type,
                "confidence": query_classification.confidence
            }
        )
        logger.info(f"[HybridRetrieval] Reranking strategy: {reranked_results.get('strategy')}")
        
        # Build response
        response = self.response_builder.build(
            results=reranked_results['results'][:top_k],
            query=query,
            query_analysis=query_analysis,
            retrieval_metadata=retrieval_results.get("metadata", {}),
            reranking_info=reranked_results.get("metadata", {}),
            total_time=time.time() - start_time
        )

        # Add query type classification to metadata
        response["metadata"]["query_classification"] = {
            "type": query_classification.query_type,
            "confidence": query_classification.confidence,
            "fallback": query_classification.fallback,
            "description": query_classification.description
        }
        response["metadata"]["adaptive_weights"] = adaptive_weights

        # NEW: Store in cache
        if self.cache:
            self.cache.set(query, strategy, executive_id, response, company_id=user_context.get("company_id", ""))

        # Mark as cache miss
        response["metadata"]["cache_hit"] = False
        
        # NEW: Record metrics
        if self.metrics:
            # Extract sources from response
            sources = []
            if "metadata" in response and "retrieval" in response["metadata"]:
                ret_meta = response["metadata"]["retrieval"]
                if ret_meta.get("vector_count", 0) > 0:
                    sources.append("vector")
                if ret_meta.get("graph_count", 0) > 0:
                    sources.append("graph")
                if ret_meta.get("memory_count", 0) > 0:
                    sources.append("memory")
            
            self.metrics.record_query(
                latency_ms=response["metadata"]["performance"]["total_time_ms"],
                strategy=strategy,
                sources=sources,
                cache_hit=False,
                error=False
            )
        
        logger.info(f"[HybridRetrieval] Complete in {response['metadata']['performance']['total_time_ms']:.1f}ms")
        
        # Track overall retrieval latency
        total_latency_s = (time.time() - start_time)
        retrieval_latency.labels(component='total').observe(total_latency_s)
        
        # Log completion with details
        obs_logger.info(
            "Hybrid retrieval completed",
            strategy=strategy,
            total_latency_ms=total_latency_s * 1000,
            results_count=len(response.get('results', [])),
            vector_results=response.get('metadata', {}).get('retrieval', {}).get('vector_count', 0),
            graph_results=response.get('metadata', {}).get('retrieval', {}).get('graph_count', 0),
            memory_results=response.get('metadata', {}).get('retrieval', {}).get('memory_count', 0),
            cache_hit=False
        )
        
        return response
    
    def _select_strategy(self, query_analysis: Dict) -> str:
        """
        Intelligent strategy selection based on query characteristics
        
        Strategies:
        - "vector_only": Simple factual queries, no entities
        - "vector_graph": Entity queries, graph context helpful
        - "full_hybrid": Complex queries, need memory + precedents
        
        Args:
            query_analysis: Output from QueryAnalyzer
        
        Returns:
            Strategy name
        """
        complexity = query_analysis.get("complexity", "medium")
        has_entities = query_analysis.get("has_entities", False)
        query_type = query_analysis.get("query_type", "factual")
        
        # Simple factual queries → vector only
        if complexity == "simple" and not has_entities:
            return "vector_only"
        
        # Entity-based non-decision queries → vector + graph
        elif has_entities and query_type != "decision":
            return "vector_graph"
        
        # Decision/analysis queries → full hybrid (vector + graph + memory)
        else:
            return "full_hybrid"
    
    def _parallel_retrieve(
        self,
        query: str,
        executive_id: str,
        strategy: str,
        user_context: Dict,
        query_analysis: Dict,
        use_section_search: bool = False
    ) -> Dict:
        """
        Execute retrieval from multiple sources in parallel

        Uses threading to run vector/graph/memory simultaneously.
        Significantly faster than sequential execution.

        Args:
            query: User question
            executive_id: Executive context
            strategy: Selected strategy
            user_context: User info for RBAC
            query_analysis: Query analysis results
            use_section_search: Enable section-level retrieval (default: False)

        Returns:
            {
                "vector": {"results": [...], "metadata": {...}},
                "graph": {"candidate_ids": [...], "graph_distances": {...}},
                "memory": {"results": [...], "metadata": {...}},
                "metadata": {
                    "strategy": "full_hybrid",
                    "execution_mode": "parallel",
                    "timing": {...}
                }
            }
        """
        results = {}
        timing = {}
        
        if self.config.get("parallel_execution", True):
            # Parallel execution (recommended)
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                futures = {}

                # Vector search (always)
                futures["vector"] = executor.submit(
                    self._execute_vector_search,
                    query, user_context, use_section_search, executive_id
                )
                
                # Graph context (if strategy includes it)
                if strategy in ["vector_graph", "full_hybrid"]:
                    futures["graph"] = executor.submit(
                        self._execute_graph_context,
                        query, query_analysis, user_context
                    )
                
                # Memory search (if full hybrid)
                if strategy == "full_hybrid" and self.memory:
                    futures["memory"] = executor.submit(
                        self._execute_memory_search,
                        query, executive_id
                    )
                
                # Collect results
                for source, future in futures.items():
                    try:
                        start = time.time()
                        results[source] = future.result()
                        latency_ms = (time.time() - start) * 1000
                        timing[source] = latency_ms
                        
                        # Track component latency
                        retrieval_latency.labels(component=source).observe(latency_ms / 1000)
                        
                        # Track results count
                        result_count = len(results[source].get('results', [])) if isinstance(results[source], dict) else 0
                        if result_count > 0:
                            retrieval_results_counter.labels(source=source).observe(result_count)
                        
                        obs_logger.info(
                            f"{source} retrieval completed",
                            component=source,
                            latency_ms=latency_ms,
                            results_count=result_count
                        )
                    except Exception as e:
                        logger.error(f"[HybridRetrieval] Error in {source} retrieval: {e}")
                        obs_logger.error(
                            f"{source} retrieval failed",
                            component=source,
                            error=str(e)
                        )
                        results[source] = {"results": [], "error": str(e)}
                        timing[source] = 0
        else:
            # Sequential execution (fallback)
            # Vector
            start = time.time()
            results["vector"] = self._execute_vector_search(query, user_context, use_section_search, executive_id)
            timing["vector"] = (time.time() - start) * 1000
            
            # Graph
            if strategy in ["vector_graph", "full_hybrid"]:
                start = time.time()
                results["graph"] = self._execute_graph_context(query, query_analysis, user_context)
                timing["graph"] = (time.time() - start) * 1000
            
            # Memory
            if strategy == "full_hybrid" and self.memory:
                start = time.time()
                results["memory"] = self._execute_memory_search(query, executive_id)
                timing["memory"] = (time.time() - start) * 1000
        
        results["metadata"] = {
            "strategy": strategy,
            "execution_mode": "parallel" if self.config.get("parallel_execution") else "sequential",
            "timing": timing
        }
        
        return results
    
    def _execute_vector_search(
        self,
        query: str,
        user_context: Dict,
        use_section_search: bool = False,
        executive_id: Optional[str] = None
    ) -> Dict:
        """
        Execute vector search at document or section level

        Args:
            query: User question
            user_context: RBAC context
            use_section_search: If True, search document sections instead of full documents
            executive_id: Executive profile ID for isolation filtering

        Returns:
            Vector search results with metadata
        """
        try:
            if use_section_search:
                # NEW: Section-level search (semantic chunking)
                # NOTE: Use flat results (group_by_document=False) for compatibility
                # with result fusion. Sections will be treated as individual results
                # that can be fused with graph and memory results.
                result = self.vector.search_sections(
                    query=query,
                    top_k=self.config["max_candidates"]["vector"],
                    role=user_context.get("role", "employee"),
                    company_id=user_context.get("company_id"),
                    executive_id=executive_id,
                    group_by_document=False  # Flat list for result fusion
                )
                # Add search type metadata
                if "metadata" not in result:
                    result["metadata"] = {}
                result["metadata"]["search_level"] = "section"
                return result
            else:
                # Legacy: Document-level search
                result = self.vector.search(
                    query=query,
                    use_graph_context=False,  # Graph done separately
                    top_k=self.config["max_candidates"]["vector"],
                    role=user_context.get("role", "employee"),
                    company_id=user_context.get("company_id"),
                    executive_id=executive_id,
                )
                if "metadata" not in result:
                    result["metadata"] = {}
                result["metadata"]["search_level"] = "document"
                return result
        except Exception as e:
            logger.error(f"[HybridRetrieval] Vector search failed: {e}")
            return {"results": [], "error": str(e)}
    
    def _execute_graph_context(self, query: str, query_analysis: Dict, user_context: Dict) -> Dict:
        """Execute graph context discovery"""
        try:
            return self.graph.discover_context(
                query=query,
                entities=query_analysis.get("entities"),
                allowed_scopes=user_context.get("allowed_scopes"),
                company_id=user_context.get("company_id")
            )
        except Exception as e:
            logger.error(f"[HybridRetrieval] Graph context failed: {e}")
            return {"candidate_ids": [], "graph_distances": {}, "error": str(e)}
    
    def _execute_memory_search(self, query: str, executive_id: str) -> Dict:
        """Execute memory search"""
        try:
            return self.memory.search_executive_memory(
                query=query,
                executive_id=executive_id,
                top_k=self.config["memory_config"]["max_results"],
                min_similarity=self.config["memory_config"]["min_similarity"],
                time_window_days=self.config["memory_config"]["time_window_days"]
            )
        except Exception as e:
            logger.error(f"[HybridRetrieval] Memory search failed: {e}")
            return {"results": [], "error": str(e)}
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        if not self.cache:
            return {"enabled": False}
        
        stats = self.cache.get_stats()
        stats["enabled"] = True
        return stats
    
    def get_performance_metrics(self) -> Dict:
        """Get performance metrics summary"""
        if not self.metrics:
            return {"enabled": False}
        
        return self.metrics.get_summary()
    
    def print_performance_report(self):
        """Print formatted performance report"""
        if not self.metrics:
            print("Performance metrics not enabled")
            return
        
        self.metrics.print_report()
    
    def reset_metrics(self):
        """Reset performance metrics"""
        if self.metrics:
            self.metrics.reset()
    
    def _build_decomposition_response(
        self,
        decomposition_result,
        original_query: str,
        query_analysis: Dict,
        total_time: float
    ) -> Dict:
        """
        Build response format for decomposed queries (legacy method).
        
        Args:
            decomposition_result: Result from QueryDecomposer
            original_query: Original query string
            query_analysis: Query analysis results
            total_time: Total processing time
            
        Returns:
            Formatted response dict
        """
        # Delegate to enhanced method
        return self._build_enhanced_decomposition_response(
            decomposition_result, original_query, query_analysis, total_time
        )
    
    def _build_enhanced_decomposition_response(
        self,
        decomposition_result,
        original_query: str,
        query_analysis: Dict,
        total_time: float
    ) -> Dict:
        """
        Build enhanced response format for decomposed queries.
        
        Args:
            decomposition_result: Result from DecompositionHandler
            original_query: Original query string
            query_analysis: Query analysis results
            total_time: Total processing time
            
        Returns:
            Formatted response dict
        """
        # Convert sub-query results to standard format
        results = []
        for sub_result in decomposition_result.sub_query_results:
            for i, doc in enumerate(sub_result.results):
                result = {
                    "rank": len(results) + 1,
                    "id": doc.get("id", f"subquery_{sub_result.sub_query.id}_{i}"),
                    "type": doc.get("type", "document"),
                    "title": doc.get("title", sub_result.sub_query.text),
                    "content": doc.get("content", ""),
                    "final_score": doc.get("final_score", sub_result.confidence),
                    "source_scores": {
                        "vector": doc.get("vector_score", 0),
                        "graph": doc.get("graph_score", 0),
                        "memory": doc.get("memory_score", 0)
                    },
                    "provenance": {
                        "found_in": doc.get("found_in", ["decomposition"]),
                        "sub_query": sub_result.sub_query.text,
                        "sub_query_id": sub_result.sub_query.id,
                        "sub_query_type": sub_result.sub_query.query_type.value,
                        "why_relevant": f"Result for sub-query: {sub_result.sub_query.text}"
                    }
                }
                results.append(result)
        
        # Build enhanced metadata
        metadata = {
            "query": original_query,
            "query_analysis": query_analysis,
            "retrieval_strategy": {
                "name": "decomposition",
                "reasoning": "Query was decomposed into multiple sub-queries",
                "strategy_used": decomposition_result.strategy_used.value if decomposition_result.strategy_used else None,
                "sub_queries": [
                    {
                        "id": sq.id,
                        "text": sq.text,
                        "order": sq.order,
                        "query_type": sq.query_type.value,
                        "entities": sq.entities,
                        "dependencies": sq.dependencies,
                        "confidence": sq.confidence
                    }
                    for sq in decomposition_result.sub_queries
                ]
            },
            "performance": {
                "total_time_ms": total_time * 1000,
                "decomposition_time_ms": decomposition_result.total_processing_time_ms,
                "sub_query_count": len(decomposition_result.sub_queries),
                "source_count": len(decomposition_result.all_sources),
                "decomposition_confidence": decomposition_result.decomposition_confidence,
                "synthesis_confidence": decomposition_result.synthesis_confidence
            },
            "decomposition": {
                "enabled": True,
                "confidence": decomposition_result.decomposition_confidence,
                "synthesis_confidence": decomposition_result.synthesis_confidence,
                "strategy_used": decomposition_result.strategy_used.value if decomposition_result.strategy_used else None,
                "processing_metrics": decomposition_result.metadata.get("processing_metrics", {}),
                "sub_query_results": [
                    {
                        "sub_query_id": result.sub_query.id,
                        "sub_query_text": result.sub_query.text,
                        "sub_query_type": result.sub_query.query_type.value,
                        "confidence": result.confidence,
                        "processing_time_ms": result.processing_time_ms,
                        "source_count": len(result.sources),
                        "validation": result.metadata.get("validation", {}),
                        "warnings": result.metadata.get("warnings", [])
                    }
                    for result in decomposition_result.sub_query_results
                ]
            }
        }
        
        return {
            "results": results,
            "synthesized_answer": decomposition_result.synthesized_answer,
            "metadata": metadata
        }

    def _load_retrieval_weights(self) -> Dict:
        """
        Load retrieval weights configuration from YAML file.

        Returns:
            Dict with query type weights and configuration
        """
        weights_path = Path(__file__).parent.parent / "config" / "retrieval_weights.yaml"

        try:
            with open(weights_path, 'r', encoding='utf-8') as f:
                weights_config = yaml.safe_load(f)

            logger.info(
                f"[HybridRetrieval] Loaded retrieval weights for "
                f"{len(weights_config.get('query_type_weights', {}))} query types"
            )

            return weights_config

        except FileNotFoundError:
            logger.warning(
                f"[HybridRetrieval] Weights file not found at {weights_path} - "
                "using default balanced weights"
            )
            return {
                "query_type_weights": {},
                "default_weights": {"vector": 0.50, "graph": 0.30, "memory": 0.20},
                "config": {"enabled": False}
            }
        except Exception as e:
            logger.error(f"[HybridRetrieval] Failed to load weights: {e}")
            return {
                "query_type_weights": {},
                "default_weights": {"vector": 0.50, "graph": 0.30, "memory": 0.20},
                "config": {"enabled": False}
            }

    def _get_adaptive_weights(
        self,
        query: str,
        query_analysis: Dict,
        query_classification=None  # Optional: reuse existing classification
    ) -> Dict[str, float]:
        """
        Get adaptive retrieval weights based on query type classification.

        Args:
            query: User's natural language question
            query_analysis: Query analysis results from QueryAnalyzer
            query_classification: Optional pre-computed classification (to avoid double-classification)

        Returns:
            Dict with vector/graph/memory weights
        """
        # Check if adaptive weighting is enabled
        if not self.retrieval_weights.get("config", {}).get("enabled", True):
            logger.debug("[HybridRetrieval] Adaptive weighting disabled - using defaults")
            return self.retrieval_weights.get("default_weights", {
                "vector": 0.50,
                "graph": 0.30,
                "memory": 0.20
            })

        # Classify query type (or reuse existing classification)
        classification = query_classification or self.query_type_classifier.classify(query)

        # Get configuration
        config = self.retrieval_weights.get("config", {})
        min_confidence = config.get("min_confidence_threshold", 0.6)
        confidence_blending = config.get("confidence_blending", True)
        log_classifications = config.get("log_classifications", True)

        # Get default weights
        default_weights = self.retrieval_weights.get("default_weights", {
            "vector": 0.50,
            "graph": 0.30,
            "memory": 0.20
        })

        # If confidence is too low, use default weights
        if classification.confidence < min_confidence:
            if log_classifications:
                logger.info(
                    f"[HybridRetrieval] Low confidence classification "
                    f"(type={classification.query_type}, "
                    f"conf={classification.confidence:.2f} < {min_confidence}) - "
                    f"using default weights"
                )
            return default_weights

        # Get type-specific weights
        type_weights_config = self.retrieval_weights.get("query_type_weights", {})
        type_config = type_weights_config.get(classification.query_type, {})

        if not type_config:
            logger.warning(
                f"[HybridRetrieval] No weights found for type '{classification.query_type}' - "
                f"using defaults"
            )
            return default_weights

        # Extract weights (remove non-weight keys)
        type_weights = {
            "vector": type_config.get("vector", default_weights["vector"]),
            "graph": type_config.get("graph", default_weights["graph"]),
            "memory": type_config.get("memory", default_weights["memory"])
        }

        # Apply confidence blending if enabled
        if confidence_blending:
            # Blend type-specific weights with defaults based on confidence
            # Higher confidence = more type-specific, lower = more default
            confidence = classification.confidence
            blended_weights = {
                "vector": confidence * type_weights["vector"] + (1 - confidence) * default_weights["vector"],
                "graph": confidence * type_weights["graph"] + (1 - confidence) * default_weights["graph"],
                "memory": confidence * type_weights["memory"] + (1 - confidence) * default_weights["memory"]
            }

            if log_classifications:
                logger.info(
                    f"[HybridRetrieval] Query type: {classification.query_type} "
                    f"(conf={classification.confidence:.2f}) | "
                    f"Blended weights: V={blended_weights['vector']:.2f}, "
                    f"G={blended_weights['graph']:.2f}, M={blended_weights['memory']:.2f}"
                )

            return blended_weights
        else:
            # Use type-specific weights directly (no blending)
            if log_classifications:
                logger.info(
                    f"[HybridRetrieval] Query type: {classification.query_type} "
                    f"(conf={classification.confidence:.2f}) | "
                    f"Type weights: V={type_weights['vector']:.2f}, "
                    f"G={type_weights['graph']:.2f}, M={type_weights['memory']:.2f}"
                )

            return type_weights


__all__ = ['HybridRetrievalManager']
