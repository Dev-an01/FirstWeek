"""
LangGraph Nodes for RAG Workflow

Node functions that update state incrementally.

Key features:
- Parallel retrieval using ThreadPoolExecutor
- Closure pattern for dependency injection
- Null-safe state access with .get()
- GraphRAG global search + RAGAS evaluation integration
- Performance optimizations - cached YAML, module-level imports
"""
import re
import time
import logging
import yaml
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
# LangSmith tracing (optional)
try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]
        return decorator
import numpy as np

from .state import RAGState, safe_get


def _sanitize_state_for_serialization(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively convert all numpy types to Python native types for msgpack serialization.

    LangGraph uses msgpack for state checkpointing which cannot serialize numpy types.
    This function ensures all values in the state are serializable.
    """
    def _convert(obj):
        if obj is None:
            return None
        elif isinstance(obj, (str, bool)):
            return obj
        elif isinstance(obj, (int, float)):
            return obj
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: _convert(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [_convert(v) for v in obj]
        elif hasattr(obj, '__dict__'):
            # Handle objects with __dict__ (dataclasses, etc.)
            return {k: _convert(v) for k, v in obj.__dict__.items()}
        else:
            return obj

    return _convert(state)


def sanitize_node(func: Callable) -> Callable:
    """
    Decorator that sanitizes node state before returning to ensure msgpack serialization works.
    Accepts additional kwargs that LangGraph may pass (e.g., config).
    """
    from functools import wraps

    @wraps(func)
    def wrapper(state: RAGState, **kwargs) -> RAGState:
        result = func(state, **kwargs) if kwargs else func(state)
        return _sanitize_state_for_serialization(result)

    return wrapper

# Module-level imports (avoid runtime import overhead)
from profile_management.profile_id_mapper import normalize_profile_id
from hybrid_retrieval.config import HYBRID_RETRIEVAL_CONFIG

logger = logging.getLogger(__name__)

# AuthenticityChecker for post-generation validation
try:
    from conversation_engine.validation import AuthenticityChecker
    AUTHENTICITY_CHECKER = AuthenticityChecker()
    logger.info("✅ AuthenticityChecker loaded for response validation")
except ImportError:
    AUTHENTICITY_CHECKER = None
    logger.info("⚠️ AuthenticityChecker not available (optional)")


def create_nodes(
    vector_engine: Any,
    graph_provider: Any,
    query_analyzer: Any,
    query_router: Any,
    result_fusion: Any,
    adaptive_reranker: Any,
    llm_orchestrator: Any,
    session_manager: Any,
    memory_search_engine: Any = None,
    graphrag_provider: Any = None,
    ragas_evaluator: Any = None,
    conversation_engine: Any = None,  # ConversationEngine for context-aware prompts
) -> Dict[str, Callable]:
    """
    Create workflow nodes with dependency injection via closures

    Uses clean DI pattern with closures instead of functools.partial.

    Args:
        vector_engine: VectorSearchEngine singleton
        graph_provider: GraphContextProvider singleton
        query_analyzer: QueryAnalyzer instance
        query_router: QueryRouter instance
        result_fusion: ResultFusion instance
        adaptive_reranker: AdaptiveReranker instance
        llm_orchestrator: LLMOrchestrator instance
        session_manager: SessionManager instance
        memory_search_engine: MultiSignalMemorySearch for episodic memory
        graphrag_provider: GraphRAGProvider for global/thematic search
        ragas_evaluator: RAGASEvaluator for quality metrics
        conversation_engine: ConversationEngine for context-aware prompts

    Returns:
        Dictionary of node functions with dependencies injected
    """
    
    @traceable(name="analyze_query_node")
    def analyze_query(state: RAGState) -> RAGState:
        """
        Node 1: Analyze query features
        
        Input: state.query
        Output: state.query_features, state.entities, state.complexity
        """
        start_time = time.time()
        query = state["query"]
        
        logger.info(f"Analyzing query: {query[:50]}...")
        
        # Use existing QueryAnalyzer
        analysis = query_analyzer.analyze(query)
        
        # CRITICAL FIX #5: Safe state updates
        state["query_features"] = analysis
        state["query_type"] = analysis.get("query_type", "unknown")
        state["complexity"] = analysis.get("complexity", "medium")
        state["entities"] = analysis.get("entities", [])
        
        # Track latency
        if "component_latencies" not in state:
            state["component_latencies"] = {}
        state["component_latencies"]["analyze_query"] = (time.time() - start_time) * 1000
        
        logger.debug(f"Query analysis: type={state['query_type']}, complexity={state['complexity']}, entities={len(state['entities'])}")
        
        return state
    
    
    @traceable(name="route_query_node")
    def route_query(state: RAGState) -> RAGState:
        """
        Node 2: Route query to path
        
        Input: state.query, state.query_features
        Output: state.selected_path, state.routing_confidence
        """
        start_time = time.time()
        
        # Check for forced path
        if state.get("force_path"):
            state["selected_path"] = state["force_path"]
            state["routing_confidence"] = 1.0
            state["routing_reasoning"] = f"Forced to {state['force_path']} path"
            logger.info(f"Using forced path: {state['force_path']}")
            return state
        
        query = state["query"]
        query_features = safe_get(state, "query_features", {})
        
        # Use existing QueryRouter
        route_decision = query_router.route(query, query_features)
        
        # Update state (ensure Python float for msgpack serialization)
        state["selected_path"] = route_decision.path
        state["routing_confidence"] = float(route_decision.confidence)
        state["routing_reasoning"] = route_decision.reasoning
        
        # Track latency
        state["component_latencies"]["route_query"] = (time.time() - start_time) * 1000
        
        logger.info(f"Routed to {route_decision.path} path (confidence: {route_decision.confidence:.2f})")
        
        return state
    
    
    def _merge_and_dedup_results(doc_results: List[Dict], section_results: List[Dict], top_k: int) -> List[Dict]:
        """
        Merge document-level and section-level search results, deduplicating
        by parent document. Section results (more precise) take priority;
        full-doc results are skipped when sections from that same parent
        document are already present.

        Returns the top_k results sorted by similarity_score descending.
        """
        merged = []
        seen_parent_ids = set()

        # Add section results first (higher precision)
        for result in section_results:
            merged.append(result)
            parent_id = result.get("parent_document_id")
            if parent_id:
                seen_parent_ids.add(parent_id)

        # Add full-doc results, skipping those already covered by sections
        for result in doc_results:
            doc_id = result.get("id") or result.get("source_id")
            if doc_id in seen_parent_ids:
                continue
            merged.append(result)

        # Sort by similarity_score descending and trim to top_k
        merged.sort(key=lambda r: r.get("similarity_score", 0), reverse=True)
        return merged[:top_k]

    @traceable(name="retrieve_graph_enhanced_node")
    def retrieve_graph_enhanced(state: RAGState) -> RAGState:
        """
        UNIFIED RETRIEVAL NODE: Graph-Enhanced Vector Search
        
        This implements the CORRECT architecture from checkpoint:
        1. Extract entities (already done in analyze_query)
        2. Graph traversal → Get candidate IDs
        3. Vector search WITHIN candidates (graph-constrained!)
        4. Hybrid scoring: 0.6*vector + 0.4*graph_proximity
        
        Input: state.query, state.entities, state.top_k, state.user_role
        Output: state.vector_results (with hybrid scores), state.graph_context
        """
        start_time = time.time()
        
        query = state["query"]
        entities = safe_get(state, "entities", [])
        top_k = safe_get(state, "top_k", 20)
        role = safe_get(state, "user_role", "employee")
        min_score = safe_get(state, "min_score", 0.15)
        query_language = safe_get(state, "language", "en")
        company_id = safe_get(state, "company_id", None)
        profile_id = safe_get(state, "profile_id", None)
        user_context = {
            "role": role,
            "allowed_scopes": _get_allowed_scopes(role),
            "company_id": company_id,
        }

        # =====================================================================
        # CROSS-LINGUAL THRESHOLD ADJUSTMENT
        # BGE-M3 multilingual embeddings have lower similarity scores for
        # cross-lingual matches (Japanese query → English documents).
        # Lower the threshold to ensure relevant results aren't filtered out.
        # =====================================================================
        def _has_japanese(text: str) -> bool:
            """Check if text contains Japanese characters (Hiragana, Katakana, or Kanji)"""
            # Hiragana: \u3040-\u309F, Katakana: \u30A0-\u30FF, Kanji: \u4E00-\u9FFF
            return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))

        original_min_score = min_score
        is_cross_lingual = _has_japanese(query)  # Japanese query against mostly English docs

        if is_cross_lingual:
            # Lower threshold by 0.10 for cross-lingual queries (minimum 0.10)
            # Cross-lingual similarity scores are typically 0.1-0.2 lower than same-language
            min_score = max(0.10, min_score - 0.10)
            logger.info(f"🌐 Cross-lingual query detected (Japanese→English): lowering min_score {original_min_score:.2f} → {min_score:.2f}")

        logger.info(f"🔍 Graph-enhanced retrieval: query='{query[:50]}...', entities={len(entities)}, top_k={top_k}, min_score={min_score:.2f}")
        
        try:
            # Step 1: Graph traversal to get candidate IDs (if entities exist)
            graph_context = {"has_context": False}
            candidate_ids = None
            
            if entities and len(entities) > 0:
                graph_start = time.time()
                try:
                    graph_context = graph_provider.discover_context(
                        query=query,
                        entities=entities,
                        allowed_scopes=user_context.get("allowed_scopes"),
                        company_id=company_id,
                    )
                    
                    if graph_context.get("has_context"):
                        candidate_ids = graph_context.get("candidate_ids", [])
                        logger.info(f"✅ Graph context: {len(candidate_ids)} candidate docs from {len(entities)} entities")
                    else:
                        logger.debug("No graph context available - falling back to pure vector search")
                    
                    state["component_latencies"]["retrieve_graph"] = (time.time() - graph_start) * 1000
                    
                except Exception as e:
                    logger.warning(f"Graph traversal failed: {e}, falling back to pure vector")
                    graph_context = {"has_context": False, "error": str(e)}
            else:
                logger.debug("No entities found - using pure vector search")
            
            # Store graph context in state
            state["graph_context"] = graph_context
            
            # Step 2: Vector search (constrained by graph if available)
            vector_start = time.time()
            
            if candidate_ids and len(candidate_ids) > 0:
                # GRAPH-ENHANCED VECTOR SEARCH (CORRECT!)
                logger.info(f"🎯 Constrained vector search within {len(candidate_ids)} graph candidates")
                
                # Disable internal graph context — nodes.py already handles graph
                # discovery and applies candidate_ids via post-filter.
                all_results = vector_engine.search(
                    query=query,
                    top_k=top_k * 3,  # Get more results to filter down
                    role=role,
                    min_score=min_score,
                    use_graph_context=False,
                    executive_id=profile_id,
                    company_id=company_id,
                )
                # Filter results to only include graph candidate documents
                candidate_set = set(candidate_ids)
                filtered_results = [
                    r for r in all_results.get("results", [])
                    if r.get("id") in candidate_set or r.get("source_id") in candidate_set
                ]
                results = {"results": filtered_results[:top_k]}
                logger.info(f"Filtered {len(all_results.get('results', []))} → {len(filtered_results)} within {len(candidate_ids)} graph candidates")

                # Section-level search (more precise granularity)
                try:
                    section_response = vector_engine.search_sections(
                        query=query,
                        top_k=top_k,
                        role=role,
                        company_id=company_id,
                        executive_id=profile_id,
                        min_score=min_score,
                        candidate_doc_ids=candidate_ids,
                        group_by_document=False,
                    )
                    section_results = section_response.get("results", [])
                    logger.info(f"Section search returned {len(section_results)} results (graph-constrained)")
                except Exception as sec_err:
                    logger.warning(f"Section search failed (non-blocking): {sec_err}")
                    section_results = []

                if section_results:
                    merged = _merge_and_dedup_results(
                        doc_results=results.get("results", []),
                        section_results=section_results,
                        top_k=top_k,
                    )
                    results = {"results": merged}

                # Apply hybrid scoring: 0.6*vector + 0.4*graph_proximity
                # Ensure all scores are Python floats for msgpack serialization
                graph_distances = graph_context.get("graph_distances", {})
                for result in results.get("results", []):
                    doc_id = result.get("id") or result.get("source_id")
                    # For section results, use parent_document_id for graph distance lookup
                    if doc_id not in graph_distances and result.get("parent_document_id"):
                        doc_id = result["parent_document_id"]
                    vector_score = float(result.get("similarity_score", 0))

                    # Calculate graph score (inverse of distance)
                    graph_distance = graph_distances.get(doc_id, 999)
                    graph_score = float(1.0 / graph_distance) if graph_distance > 0 else 0.0

                    # Hybrid score
                    hybrid_score = float(0.6 * vector_score + 0.4 * graph_score)

                    # Store scores (all as Python floats)
                    result["vector_score"] = vector_score
                    result["graph_score"] = graph_score
                    result["hybrid_score"] = hybrid_score
                    result["similarity_score"] = hybrid_score  # Update primary score
                
                logger.info(f"✅ Graph-enhanced search: {len(results.get('results', []))} results with hybrid scoring")
                
            else:
                # PURE VECTOR SEARCH (fallback when no graph context)
                # Disable internal graph context to avoid redundant constraint
                logger.info("📊 Pure vector search (no graph constraint)")
                results = vector_engine.search(
                    query=query,
                    top_k=top_k,
                    role=role,
                    min_score=min_score,
                    use_graph_context=False,
                    executive_id=profile_id,
                    company_id=company_id,
                )

                # Section-level search (more precise granularity)
                try:
                    section_response = vector_engine.search_sections(
                        query=query,
                        top_k=top_k,
                        role=role,
                        company_id=company_id,
                        executive_id=profile_id,
                        min_score=min_score,
                        group_by_document=False,
                    )
                    section_results = section_response.get("results", [])
                    logger.info(f"Section search returned {len(section_results)} results (pure vector)")
                except Exception as sec_err:
                    logger.warning(f"Section search failed (non-blocking): {sec_err}")
                    section_results = []

                if section_results:
                    merged = _merge_and_dedup_results(
                        doc_results=results.get("results", []),
                        section_results=section_results,
                        top_k=top_k,
                    )
                    results = {"results": merged}

                # Mark as pure vector (no hybrid scoring)
                # Ensure all scores are Python floats for msgpack serialization
                for result in results.get("results", []):
                    result["vector_score"] = float(result.get("similarity_score", 0))
                    result["graph_score"] = 0.0
                    result["hybrid_score"] = float(result.get("similarity_score", 0))
            
            state["vector_results"] = results.get("results", [])
            state["component_latencies"]["retrieve_vector"] = (time.time() - vector_start) * 1000
            
            logger.info(f"✅ Unified retrieval complete: {len(state['vector_results'])} results")
            
        except Exception as e:
            logger.error(f"Graph-enhanced retrieval failed: {e}", exc_info=True)
            state["vector_results"] = []
            state["graph_context"] = {"has_context": False, "error": str(e)}
            state["error"] = str(e)
            state["error_node"] = "retrieve_graph_enhanced"
        
        # Track total latency
        state["component_latencies"]["retrieve_graph_enhanced"] = (time.time() - start_time) * 1000
        
        return state
    
    
    # Legacy nodes for backward compatibility (not used in new workflow)
    @traceable(name="retrieve_vector_node")
    def retrieve_vector(state: RAGState) -> RAGState:
        """Legacy: Pure vector search (NOT graph-enhanced)"""
        return retrieve_graph_enhanced(state)
    
    
    @traceable(name="retrieve_graph_node")
    def retrieve_graph(state: RAGState) -> RAGState:
        """Legacy: Graph context only (NOT recommended - use retrieve_graph_enhanced)"""
        # This is now a no-op since retrieve_graph_enhanced does both
        return state
    
    
    @traceable(name="retrieve_memory_node")
    def retrieve_memory(state: RAGState) -> RAGState:
        """
        Node 3c: Memory search

        Uses MultiSignalMemorySearch for executive-specific episodic memory retrieval.
        Implements 5-signal scoring:
        1. Semantic Similarity (40%)
        2. Temporal Decay (25%)
        3. Decision Importance (20%)
        4. Feedback Quality (multiplier)
        5. User Context Similarity (multiplier)

        Input: state.query, state.profile_id, state.user_id, state.user_role
        Output: state.memory_results (list of scored memory entries)
        """
        start_time = time.time()

        # Check if memory search engine is available
        if memory_search_engine is None:
            logger.warning("⚠️ Memory search engine not initialized - skipping memory retrieval")
            state["memory_results"] = []
            state["component_latencies"]["retrieve_memory"] = (time.time() - start_time) * 1000
            return state

        query = state["query"]
        profile_id = safe_get(state, "profile_id", "exec_001_test")
        user_id = safe_get(state, "user_id", None)
        user_role = safe_get(state, "user_role", "employee")

        logger.info(f"🧠 Memory search: query='{query[:50]}...', profile={profile_id}")

        try:
            # Use MultiSignalMemorySearch to retrieve episodic memory
            # This searches the executive's conversation history for relevant past interactions
            memory_result = memory_search_engine.search_executive_memory(
                query=query,
                executive_id=profile_id,
                current_user_id=user_id,
                current_user_role=user_role,
                top_k=5,  # Get top 5 most relevant memories
                min_similarity=0.4,  # Minimum semantic similarity threshold
                time_window_days=30  # Search within last 30 days
            )

            # Extract results from the search response
            memory_results = memory_result.get("results", [])

            # Format memory results for fusion compatibility
            # Each result contains: id, query, response, memory_score, signals, metadata
            # Ensure all scores are Python floats for msgpack serialization
            formatted_results = []
            for mem in memory_results:
                formatted_results.append({
                    "id": mem.get("id"),
                    "source": f"memory:{mem.get('id', 'unknown')}",
                    "content": f"Previous Q: {mem.get('query', '')}\nPrevious A: {mem.get('response', '')}",
                    "similarity_score": float(mem.get("memory_score", 0)),
                    "memory_score": float(mem.get("memory_score", 0)),
                    "signals": mem.get("signals", {}),
                    "metadata": mem.get("metadata", {}),
                    "source_type": "memory",
                    "days_ago": mem.get("metadata", {}).get("days_ago", 0)
                })

            state["memory_results"] = formatted_results

            # Log memory retrieval stats
            search_metadata = memory_result.get("metadata", {})
            logger.info(
                f"✅ Memory search complete: {len(formatted_results)} results "
                f"(total found: {search_metadata.get('total_found', 0)}, "
                f"query_time: {search_metadata.get('query_time_ms', 0):.1f}ms)"
            )

            # Store additional metadata for debugging
            state["memory_search_metadata"] = search_metadata

        except Exception as e:
            logger.error(f"❌ Memory search failed: {e}", exc_info=True)
            state["memory_results"] = []
            state["memory_search_error"] = str(e)

        # Track latency
        state["component_latencies"]["retrieve_memory"] = (time.time() - start_time) * 1000

        return state


    @traceable(name="retrieve_parallel_node")
    def retrieve_parallel(state: RAGState) -> RAGState:
        """
        Parallel Retrieval Node

        Runs graph-enhanced vector retrieval AND memory retrieval CONCURRENTLY
        using ThreadPoolExecutor for true parallelism.

        This preserves the original design concept:
        - Graph ENHANCES vector search (not parallel with it)
        - Graph-enhanced retrieval || Memory retrieval (parallel)
        - Results are then fused together

        Input: state.query, state.entities, state.top_k, state.profile_id
        Output: state.vector_results, state.graph_context, state.memory_results
        """
        start_time = time.time()
        logger.info("🚀 Starting PARALLEL retrieval (graph-enhanced + memory)")

        # Create copies of state for thread-safe execution
        # We'll merge the results back after parallel execution
        graph_state = dict(state)
        memory_state = dict(state)

        def run_graph_enhanced():
            """Execute graph-enhanced vector retrieval"""
            try:
                return retrieve_graph_enhanced(graph_state)
            except Exception as e:
                logger.error(f"Graph-enhanced retrieval failed in parallel: {e}")
                return {"vector_results": [], "graph_context": {"has_context": False, "error": str(e)}}

        def run_memory():
            """Execute memory retrieval"""
            try:
                return retrieve_memory(memory_state)
            except Exception as e:
                logger.error(f"Memory retrieval failed in parallel: {e}")
                return {"memory_results": []}

        # Execute both retrievals in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            graph_future = executor.submit(run_graph_enhanced)
            memory_future = executor.submit(run_memory)

            # Wait for both to complete
            graph_result = graph_future.result()
            memory_result = memory_future.result()

        # Merge results back into state
        # Graph-enhanced results
        state["vector_results"] = graph_result.get("vector_results", [])
        state["graph_context"] = graph_result.get("graph_context", {"has_context": False})

        # Memory results
        state["memory_results"] = memory_result.get("memory_results", [])
        if "memory_search_metadata" in memory_result:
            state["memory_search_metadata"] = memory_result["memory_search_metadata"]

        # Merge component latencies
        if "component_latencies" not in state:
            state["component_latencies"] = {}

        # Get latencies from both parallel executions
        graph_latencies = graph_result.get("component_latencies", {})
        memory_latencies = memory_result.get("component_latencies", {})

        state["component_latencies"].update(graph_latencies)
        state["component_latencies"].update(memory_latencies)

        # Track total parallel retrieval time
        total_time = (time.time() - start_time) * 1000
        state["component_latencies"]["retrieve_parallel"] = total_time

        # Calculate time saved by parallelization
        graph_time = graph_latencies.get("retrieve_graph_enhanced", 0)
        memory_time = memory_latencies.get("retrieve_memory", 0)
        sequential_time = graph_time + memory_time
        time_saved = sequential_time - total_time if sequential_time > 0 else 0

        logger.info(
            f"✅ Parallel retrieval complete: "
            f"vector={len(state['vector_results'])}, "
            f"memory={len(state['memory_results'])}, "
            f"total={total_time:.1f}ms "
            f"(saved ~{time_saved:.1f}ms vs sequential)"
        )

        return state


    @traceable(name="fuse_results_node")
    def fuse_results(state: RAGState) -> RAGState:
        """
        Node 4: Fuse multi-source results
        
        Input: state.vector_results, state.graph_context, state.memory_results
        Output: state.fused_results
        
        CRITICAL FIX #5: Null-safe access to state
        """
        start_time = time.time()
        
        # CRITICAL FIX #5: Use safe_get to avoid KeyError
        vector_results = safe_get(state, "vector_results", [])
        graph_context = safe_get(state, "graph_context", {"has_context": False})
        memory_results = safe_get(state, "memory_results", [])
        
        logger.info(f"Fusing results: vector={len(vector_results)}, graph={graph_context.get('has_context')}, memory={len(memory_results)}")
        
        retrieval_results = {
            "vector": {"results": vector_results},
            "graph": graph_context,
            "memory": {"results": memory_results}
        }
        
        # Get adaptive weights based on query type (RESTORED!)
        query_type = safe_get(state, "query_type", "factual_lookup")
        weights = get_adaptive_weights(query_type)
        
        # Store weights in state for debugging
        state["adaptive_weights"] = weights
        
        logger.info(f"Using adaptive weights for {query_type}: V={weights['vector']:.2f}, G={weights['graph']:.2f}, M={weights['memory']:.2f}")
        
        # Use existing ResultFusion
        fused = result_fusion.fuse(retrieval_results, weights)
        
        state["fused_results"] = fused
        
        logger.info(f"Fused {len(fused)} unique results")
        
        # Track latency
        state["component_latencies"]["fuse_results"] = (time.time() - start_time) * 1000
        
        return state
    
    
    @traceable(name="rerank_results_node")
    def rerank_results(state: RAGState) -> RAGState:
        """
        Node 5: Adaptive reranking

        Input: state.fused_results, state.query
        Output: state.reranked_results, state.reranking_strategy
        """
        start_time = time.time()

        fused = safe_get(state, "fused_results", [])
        query = state["query"]
        quality_assessment = safe_get(state, "query_features", {})

        # Build query classification from state (Priority 2: enable cross-encoder for complex queries)
        query_type = safe_get(state, "query_type", "unknown")
        query_classification = {
            "type": query_type,
            "confidence": safe_get(state, "routing_confidence", 0.5)
        } if query_type != "unknown" else None

        logger.info(f"Reranking {len(fused)} results (query_type={query_type})")

        # Use existing AdaptiveReranker (HYBRID_RETRIEVAL_CONFIG imported at module level)
        reranked = adaptive_reranker.rerank(
            results=fused,
            query=query,
            quality_assessment=quality_assessment,
            config=HYBRID_RETRIEVAL_CONFIG.get("reranking_thresholds", {}),
            query_classification=query_classification
        )
        
        state["reranked_results"] = reranked.get("results", [])
        state["reranking_strategy"] = reranked.get("strategy", "unknown")
        state["reranking_metadata"] = reranked.get("metadata", {})
        
        logger.info(f"Reranking complete: strategy={state['reranking_strategy']}")
        
        # Track latency
        state["component_latencies"]["rerank_results"] = (time.time() - start_time) * 1000
        
        return state
    
    
    # === GraphRAG Global Search Node ===

    @traceable(name="retrieve_graphrag_global_node")
    def retrieve_graphrag_global(state: RAGState) -> RAGState:
        """
        GraphRAG global search for broad/thematic queries.

        Uses community-based summarization for queries without clear entities.
        Complements entity-based local search with thematic context.

        Best for queries like:
        - "What are our main strategic risks?"
        - "Summarize our relationship with key partners"
        - "What themes emerge from recent decisions?"

        Input: state.query, state.entities
        Output: state.global_context
        """
        start_time = time.time()

        # Check if GraphRAG provider is available
        if graphrag_provider is None:
            logger.info("⚠️ GraphRAG provider not initialized - skipping global search")
            state["global_context"] = {"strategy": "skipped", "reason": "provider_not_initialized"}
            state["component_latencies"]["retrieve_graphrag_global"] = (time.time() - start_time) * 1000
            return state

        query = state["query"]
        entities = safe_get(state, "entities", [])

        # Only use global search if few/no entities found (broad/thematic query)
        if graphrag_provider.should_use_global_search(query, entities, threshold_entities=1):
            logger.info(f"🌐 Using GraphRAG global search for broad query: '{query[:50]}...'")

            try:
                # Import asyncio for sync-to-async bridge
                import asyncio

                # Check if we're in an event loop
                try:
                    loop = asyncio.get_running_loop()
                    # We're in an async context, need to run in executor
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run,
                            graphrag_provider.global_search(query=query, top_k=5)
                        )
                        result = future.result()
                except RuntimeError:
                    # No running loop, we can use asyncio.run directly
                    result = asyncio.run(
                        graphrag_provider.global_search(query=query, top_k=5)
                    )

                if result.success:
                    state["global_context"] = {
                        "strategy": result.strategy,
                        "communities_used": result.communities_used,
                        "context": result.context,
                        "summaries": result.summaries,
                        "has_context": True
                    }
                    logger.info(f"✅ GraphRAG global search: {result.communities_used} communities, context length: {len(result.context)}")
                else:
                    state["global_context"] = {
                        "strategy": "global",
                        "has_context": False,
                        "error": result.error
                    }
                    logger.warning(f"⚠️ GraphRAG global search returned no results: {result.error}")

            except Exception as e:
                logger.error(f"❌ GraphRAG global search failed: {e}", exc_info=True)
                state["global_context"] = {
                    "strategy": "global",
                    "has_context": False,
                    "error": str(e)
                }
        else:
            # Skip global search - entities found, use local search
            logger.info(f"📍 Skipping global search - {len(entities)} entities found, using local search")
            state["global_context"] = {
                "strategy": "skipped",
                "reason": "entities_found",
                "entity_count": len(entities)
            }

        state["component_latencies"]["retrieve_graphrag_global"] = (time.time() - start_time) * 1000
        return state

    # === Generation Nodes ===

    @traceable(name="generate_fast_node")
    def generate_fast(state: RAGState) -> RAGState:
        """
        Node 6a: Fast path generation
        Supports ConversationEngine for context-aware prompts.
        Input: state.query, state.reranked_results (top 3-5)
        Output: state.llm_response, state.citations
        """
        # CRITICAL: Skip generation if streaming endpoint will handle it
        if safe_get(state, "skip_generation", False):
            logger.info("⏭️  Skipping fast path generation (streaming mode)")
            return {
                "llm_response": "",  # Empty response, will be streamed later
                "citations": [],
                "sources": [],
                "llm_tokens": {},
                "llm_cost_usd": 0.0
            }

        start_time = time.time()

        query = state["query"]
        # Fast path uses vector_results directly (no reranking step)
        results = safe_get(state, "vector_results", [])[:5]  # Top 5 for fast path
        profile_id = normalize_profile_id(safe_get(state, "profile_id", "exec_001_test"))
        language = safe_get(state, "language", "en")
        memory_results = safe_get(state, "memory_results", [])
        session_id = safe_get(state, "session_id", None)
        user_id = safe_get(state, "user_id", None)
        use_conv_engine = safe_get(state, "use_conversation_engine", False)

        logger.info(f"Fast path generation: query='{query[:50]}...', results={len(results)}, use_conversation_engine={use_conv_engine}")

        try:
            # Use ConversationEngine if available and enabled
            if conversation_engine and use_conv_engine:
                logger.info("🧠 Using ConversationEngine for fast path generation")
                try:
                    import asyncio
                    from llm_integration.prompt_builder import RetrievalContext

                    # Create RetrievalContext for ConversationEngine
                    # CRITICAL: Include conversation_history for multi-turn context
                    conversation_history = safe_get(state, "conversation_history", [])
                    retrieval_context = RetrievalContext(
                        vector_results=results,
                        memory=memory_results,
                        conversation_history=conversation_history,  # Multi-turn context
                        query=query
                    )

                    # Generate prompts via ConversationEngine
                    try:
                        loop = asyncio.get_running_loop()
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(
                                asyncio.run,
                                conversation_engine.generate(
                                    query=query,
                                    profile_id=profile_id,
                                    retrieved_context=retrieval_context,
                                    path="fast",
                                    session_id=session_id,
                                    user_id=user_id,
                                    memory_enabled=safe_get(state, "memory_enabled", False),
                                    language=language,
                                )
                            )
                            system_prompt, user_prompt, conv_state = future.result()
                    except RuntimeError:
                        system_prompt, user_prompt, conv_state = asyncio.run(
                            conversation_engine.generate(
                                query=query,
                                profile_id=profile_id,
                                retrieved_context=retrieval_context,
                                path="fast",
                                session_id=session_id,
                                user_id=user_id,
                                memory_enabled=safe_get(state, "memory_enabled", False),
                                language=language,
                            )
                        )

                    # Store conversation state if returned
                    if conv_state:
                        state["conversation_state"] = {
                            "turn_count": conv_state.turn_count if hasattr(conv_state, 'turn_count') else 0,
                            "current_topic": conv_state.current_topic if hasattr(conv_state, 'current_topic') else None,
                        }

                    # Generate response using prompts from ConversationEngine
                    if system_prompt and user_prompt:
                        response = llm_orchestrator.generate_with_prompts(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            profile_id=profile_id,
                            path="fast",
                        )
                        logger.info("✅ Generated response using ConversationEngine prompts (fast path)")
                    else:
                        # Fallback if ConversationEngine returns empty prompts
                        logger.warning("ConversationEngine returned empty prompts, using legacy path")
                        conversation_history = safe_get(state, "conversation_history", [])
                        response = llm_orchestrator.generate(
                            query=query,
                            vector_results=results,
                            profile_id=profile_id,
                            memory=memory_results,
                            conversation_history=conversation_history,
                            force_path="fast",
                            language=language
                        )

                except Exception as conv_error:
                    logger.warning(f"ConversationEngine failed, falling back to legacy: {conv_error}")
                    # Fallback to legacy generation
                    conversation_history = safe_get(state, "conversation_history", [])
                    response = llm_orchestrator.generate(
                        query=query,
                        vector_results=results,
                        profile_id=profile_id,
                        memory=memory_results,
                        conversation_history=conversation_history,
                        force_path="fast",
                        language=language
                    )
            else:
                # Legacy path: Use LLM orchestrator's generate method
                conversation_history = safe_get(state, "conversation_history", [])
                response = llm_orchestrator.generate(
                    query=query,
                    vector_results=results,
                    profile_id=profile_id,
                    memory=memory_results,
                    conversation_history=conversation_history,
                    force_path="fast",
                    language=language
                )

            # Extract response data
            state["llm_response"] = response.get("answer", "")
            state["citations"] = response.get("citations", [])
            state["sources"] = response.get("sources", [])
            
            # Extract metadata
            metadata = response.get("metadata", {})
            state["llm_tokens"] = metadata.get("llm_tokens", {})
            state["llm_cost_usd"] = metadata.get("cost_usd", 0.0)
            state["langsmith_run_id"] = metadata.get("langsmith_run_id")
            
            logger.info(f"Fast generation complete: tokens={state['llm_tokens']}")

            # Optional RAGAS evaluation
            if ragas_evaluator is not None and safe_get(state, "enable_evaluation", False):
                try:
                    import asyncio

                    # Extract context texts for evaluation
                    context_texts = [
                        r.get("content", r.get("text", ""))
                        for r in results[:5]
                        if r.get("content") or r.get("text")
                    ]

                    # Run evaluation
                    try:
                        loop = asyncio.get_running_loop()
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(
                                asyncio.run,
                                ragas_evaluator.evaluate_response(
                                    question=query,
                                    answer=state["llm_response"],
                                    contexts=context_texts
                                )
                            )
                            evaluation = future.result()
                    except RuntimeError:
                        evaluation = asyncio.run(
                            ragas_evaluator.evaluate_response(
                                question=query,
                                answer=state["llm_response"],
                                contexts=context_texts
                            )
                        )

                    state["evaluation_metrics"] = evaluation.to_dict()
                    logger.info(
                        f"📊 RAGAS evaluation (fast): overall={evaluation.overall_score:.2f}, "
                        f"grade={evaluation.quality_grade}, method={evaluation.evaluation_method}"
                    )
                except Exception as eval_error:
                    logger.warning(f"⚠️ RAGAS evaluation failed (non-critical): {eval_error}")
                    state["evaluation_metrics"] = {"error": str(eval_error)}

        except Exception as e:
            logger.error(f"Fast generation failed: {e}")
            state["error"] = str(e)
            state["error_node"] = "generate_fast"
            state["llm_response"] = "I apologize, but I encountered an error generating the response."

        # Track latency
        state["component_latencies"]["generate_fast"] = (time.time() - start_time) * 1000

        # Update conversation_history for multi-turn memory (checkpointer persists this)
        if state.get("llm_response") and not state.get("error"):
            history = safe_get(state, "conversation_history", [])
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": state["llm_response"]})
            state["conversation_history"] = history
            logger.info(f"[MULTI-TURN] Updated conversation_history: {len(history)} messages (fast path)")

        return state


    @traceable(name="generate_standard_node")
    def generate_standard(state: RAGState) -> RAGState:
        """
        Node 6b: Standard path generation

        Supports ConversationEngine for context-aware prompts.

        Input: state.query, state.reranked_results (top 10-15)
        Output: state.llm_response, state.citations
        """
        # CRITICAL: Skip generation if streaming endpoint will handle it
        if safe_get(state, "skip_generation", False):
            logger.info("⏭️  Skipping standard path generation (streaming mode)")
            return {
                "llm_response": "",  # Empty response, will be streamed later
                "citations": [],
                "sources": [],
                "llm_tokens": {},
                "llm_cost_usd": 0.0
            }

        start_time = time.time()

        query = state["query"]
        results = safe_get(state, "reranked_results", [])[:10]  # Top 10 for standard
        profile_id = normalize_profile_id(safe_get(state, "profile_id", "exec_001_test"))
        language = safe_get(state, "language", "en")
        graph_context = safe_get(state, "graph_context", {})
        memory_results = safe_get(state, "memory_results", [])
        session_id = safe_get(state, "session_id", None)
        user_id = safe_get(state, "user_id", None)
        use_conv_engine = safe_get(state, "use_conversation_engine", False)

        logger.info(f"Standard path generation: query='{query[:50]}...', results={len(results)}, use_conversation_engine={use_conv_engine}")

        try:
            # Convert graph_context to list format if needed
            graph_results = None
            if graph_context and graph_context.get("has_context"):
                graph_results = graph_context.get("results", [])

            # Use ConversationEngine if available and enabled
            if conversation_engine and use_conv_engine:
                logger.info("🧠 Using ConversationEngine for standard path generation")
                try:
                    import asyncio
                    from llm_integration.prompt_builder import RetrievalContext

                    # Create RetrievalContext for ConversationEngine
                    # CRITICAL: Include conversation_history for multi-turn context
                    conversation_history = safe_get(state, "conversation_history", [])
                    retrieval_context = RetrievalContext(
                        vector_results=results,
                        graph_results=graph_results,
                        memory=memory_results,
                        conversation_history=conversation_history,  # Multi-turn context
                        query=query
                    )

                    # Generate prompts via ConversationEngine
                    try:
                        loop = asyncio.get_running_loop()
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(
                                asyncio.run,
                                conversation_engine.generate(
                                    query=query,
                                    profile_id=profile_id,
                                    retrieved_context=retrieval_context,
                                    path="standard",
                                    session_id=session_id,
                                    user_id=user_id,
                                    memory_enabled=safe_get(state, "memory_enabled", False),
                                    language=language,
                                )
                            )
                            system_prompt, user_prompt, conv_state = future.result()
                    except RuntimeError:
                        system_prompt, user_prompt, conv_state = asyncio.run(
                            conversation_engine.generate(
                                query=query,
                                profile_id=profile_id,
                                retrieved_context=retrieval_context,
                                path="standard",
                                session_id=session_id,
                                user_id=user_id,
                                memory_enabled=safe_get(state, "memory_enabled", False),
                                language=language,
                            )
                        )

                    # Store conversation state if returned
                    if conv_state:
                        state["conversation_state"] = {
                            "turn_count": conv_state.turn_count if hasattr(conv_state, 'turn_count') else 0,
                            "current_topic": conv_state.current_topic if hasattr(conv_state, 'current_topic') else None,
                        }

                    # Generate response using prompts from ConversationEngine
                    if system_prompt and user_prompt:
                        response = llm_orchestrator.generate_with_prompts(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            profile_id=profile_id,
                        )
                        logger.info("✅ Generated response using ConversationEngine prompts")
                    else:
                        # Fallback if ConversationEngine returns empty prompts
                        logger.warning("ConversationEngine returned empty prompts, using legacy path")
                        conversation_history = safe_get(state, "conversation_history", [])
                        response = llm_orchestrator.generate(
                            query=query,
                            vector_results=results,
                            profile_id=profile_id,
                            graph_results=graph_results,
                            memory=memory_results,
                            conversation_history=conversation_history,
                            force_path="standard",
                            language=language
                        )

                except Exception as conv_error:
                    logger.warning(f"ConversationEngine failed, falling back to legacy: {conv_error}")
                    # Fallback to legacy generation
                    conversation_history = safe_get(state, "conversation_history", [])
                    response = llm_orchestrator.generate(
                        query=query,
                        vector_results=results,
                        profile_id=profile_id,
                        graph_results=graph_results,
                        memory=memory_results,
                        conversation_history=conversation_history,
                        force_path="standard",
                        language=language
                    )
            else:
                # Legacy path: Use LLM orchestrator's generate method
                conversation_history = safe_get(state, "conversation_history", [])
                response = llm_orchestrator.generate(
                    query=query,
                    vector_results=results,
                    profile_id=profile_id,
                    graph_results=graph_results,
                    memory=memory_results,
                    conversation_history=conversation_history,
                    force_path="standard",
                    language=language
                )

            # Extract response data
            state["llm_response"] = response.get("answer", "")
            state["citations"] = response.get("citations", [])
            state["sources"] = response.get("sources", [])
            
            # Extract metadata
            metadata = response.get("metadata", {})
            state["llm_tokens"] = metadata.get("llm_tokens", {})
            state["llm_cost_usd"] = metadata.get("cost_usd", 0.0)
            state["langsmith_run_id"] = metadata.get("langsmith_run_id")
            
            logger.info(f"Standard generation complete: tokens={state['llm_tokens']}")

            # Optional RAGAS evaluation
            if ragas_evaluator is not None and safe_get(state, "enable_evaluation", False):
                try:
                    import asyncio

                    # Extract context texts for evaluation
                    context_texts = [
                        r.get("content", r.get("text", ""))
                        for r in results[:5]
                        if r.get("content") or r.get("text")
                    ]

                    # Run evaluation
                    try:
                        loop = asyncio.get_running_loop()
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            future = pool.submit(
                                asyncio.run,
                                ragas_evaluator.evaluate_response(
                                    question=query,
                                    answer=state["llm_response"],
                                    contexts=context_texts
                                )
                            )
                            evaluation = future.result()
                    except RuntimeError:
                        evaluation = asyncio.run(
                            ragas_evaluator.evaluate_response(
                                question=query,
                                answer=state["llm_response"],
                                contexts=context_texts
                            )
                        )

                    state["evaluation_metrics"] = evaluation.to_dict()
                    logger.info(
                        f"📊 RAGAS evaluation: overall={evaluation.overall_score:.2f}, "
                        f"grade={evaluation.quality_grade}, method={evaluation.evaluation_method}"
                    )
                except Exception as eval_error:
                    logger.warning(f"⚠️ RAGAS evaluation failed (non-critical): {eval_error}")
                    state["evaluation_metrics"] = {"error": str(eval_error)}

        except Exception as e:
            logger.error(f"Standard generation failed: {e}")
            state["error"] = str(e)
            state["error_node"] = "generate_standard"
            state["llm_response"] = "I apologize, but I encountered an error generating the response."

        # Track latency
        state["component_latencies"]["generate_standard"] = (time.time() - start_time) * 1000

        # Update conversation_history for multi-turn memory (checkpointer persists this)
        if state.get("llm_response") and not state.get("error"):
            history = safe_get(state, "conversation_history", [])
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": state["llm_response"]})
            state["conversation_history"] = history
            logger.info(f"[MULTI-TURN] Updated conversation_history: {len(history)} messages (standard path)")

        return state


    # === Validation Node ===

    @traceable(name="validate_response_node")
    def validate_response(state: RAGState) -> RAGState:
        """
        Post-generation authenticity validation.

        Validates AI-generated responses to ensure they:
        1. Contain required voiceprint elements (lexicon, signature)
        2. Avoid forbidden AI patterns ("I'd be happy to", numbered lists)
        3. Match expected tone for context
        4. Can auto-fix minor issues

        Input: state.llm_response, state.voiceprint, state.profile_id
        Output: state.authenticity_score, state.validation_issues, state.llm_response (potentially fixed)
        """
        start_time = time.time()

        # Skip if no response or checker not available
        llm_response = safe_get(state, "llm_response", "")
        if not llm_response or AUTHENTICITY_CHECKER is None:
            state["authenticity_score"] = 1.0  # Already a Python float
            state["validation_issues"] = []
            state["component_latencies"]["validate_response"] = float((time.time() - start_time) * 1000)
            return state

        # Get voiceprint and executive info
        voiceprint = safe_get(state, "voiceprint", None)
        profile_id = safe_get(state, "profile_id", "")
        executive_name = safe_get(state, "executive_name", "")

        # Determine context flags from state
        context_flags = []
        if safe_get(state, "is_crisis", False):
            context_flags.append("crisis")
        if safe_get(state, "is_data_heavy", False):
            context_flags.append("data_heavy")
        if safe_get(state, "query_type", "") == "analytical":
            context_flags.append("data_heavy")

        logger.info(f"🔍 Validating response authenticity for {profile_id}")

        try:
            # Run validation
            result = AUTHENTICITY_CHECKER.validate(
                response=llm_response,
                voiceprint=voiceprint,
                executive_name=executive_name,
                context_flags=context_flags,
            )

            # Store results in state (ensure Python float for msgpack serialization)
            state["authenticity_score"] = float(result.authenticity_score)
            state["validation_issues"] = [
                {
                    "category": issue.category,
                    "description": issue.description,
                    "severity": issue.severity.value,
                    "suggestion": issue.suggestion,
                }
                for issue in result.issues
            ]

            # Log validation result
            if result.is_valid:
                logger.info(
                    f"✅ Response validation passed: score={result.authenticity_score:.2f}"
                )
            else:
                logger.warning(
                    f"⚠️ Response validation issues: score={result.authenticity_score:.2f}, "
                    f"issues={len(result.issues)}"
                )

                # Attempt auto-fix for minor issues (if enabled)
                enable_auto_fix = safe_get(state, "enable_auto_fix", True)
                if enable_auto_fix and result.authenticity_score >= 0.5:
                    fixed_response, fixes_applied = AUTHENTICITY_CHECKER.fix_response(
                        response=llm_response,
                        issues=result.issues,
                        voiceprint=voiceprint,
                        executive_name=executive_name,
                    )

                    if fixes_applied:
                        logger.info(f"🔧 Auto-fixed response: {fixes_applied}")
                        state["llm_response"] = fixed_response
                        state["auto_fixes_applied"] = fixes_applied

                        # Re-validate after fixes
                        revalidation = AUTHENTICITY_CHECKER.validate(
                            response=fixed_response,
                            voiceprint=voiceprint,
                            executive_name=executive_name,
                            context_flags=context_flags,
                        )
                        state["authenticity_score"] = float(revalidation.authenticity_score)
                        logger.info(
                            f"📈 Post-fix score: {revalidation.authenticity_score:.2f}"
                        )

        except Exception as e:
            logger.error(f"❌ Response validation failed: {e}", exc_info=True)
            state["authenticity_score"] = 0.0  # Already a Python float
            state["validation_error"] = str(e)

        # Track latency
        state["component_latencies"]["validate_response"] = (time.time() - start_time) * 1000

        return state

    # Return all nodes in a dict
    # Wrap each node with sanitize_node to ensure state is serializable for msgpack
    return {
        "analyze_query": sanitize_node(analyze_query),
        "route_query": sanitize_node(route_query),
        "retrieve_vector": sanitize_node(retrieve_vector),
        "retrieve_graph": sanitize_node(retrieve_graph),
        "retrieve_graph_enhanced": sanitize_node(retrieve_graph_enhanced),
        "retrieve_memory": sanitize_node(retrieve_memory),
        "retrieve_parallel": sanitize_node(retrieve_parallel),
        "retrieve_graphrag_global": sanitize_node(retrieve_graphrag_global),
        "fuse_results": sanitize_node(fuse_results),
        "rerank_results": sanitize_node(rerank_results),
        "generate_fast": sanitize_node(generate_fast),
        "generate_standard": sanitize_node(generate_standard),
        "validate_response": sanitize_node(validate_response),
    }


@lru_cache(maxsize=1)
def _load_retrieval_weights() -> Dict:
    """
    Load and cache retrieval weights from YAML (called once).

    Uses functools.lru_cache to ensure the YAML file is only read once
    per process lifetime, avoiding repeated disk I/O on every query.
    """
    weights_path = Path(__file__).parent.parent / "config" / "retrieval_weights.yaml"

    try:
        with open(weights_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            logger.info(f"✅ Loaded retrieval weights from {weights_path}")
            return config
    except Exception as e:
        logger.warning(f"Failed to load retrieval weights: {e}, using defaults")
        return {
            "default_weights": {"vector": 0.50, "graph": 0.30, "memory": 0.20},
            "query_type_weights": {}
        }


def get_adaptive_weights(query_type: str) -> Dict[str, float]:
    """
    Get adaptive weights based on query type.

    Uses cached YAML loading for better performance.

    Maps query analyzer types to retrieval_weights.yaml types:
    - factual → factual_lookup
    - decision → decision
    - analysis → comparison
    - navigation → relationship
    """
    try:
        # Use cached config
        weights_config = _load_retrieval_weights()

        query_type_weights = weights_config.get("query_type_weights", {})
        default_weights = weights_config.get("default_weights", {
            "vector": 0.50, "graph": 0.30, "memory": 0.20
        })

        # Map query analyzer types to YAML types
        type_mapping = {
            "factual": "factual_lookup",
            "decision": "decision",
            "analysis": "comparison",
            "navigation": "relationship",
            "default": "default_weights"
        }

        yaml_type = type_mapping.get(query_type, "default_weights")

        if yaml_type == "default_weights":
            weights = default_weights
        else:
            type_config = query_type_weights.get(yaml_type, {})
            weights = {
                "vector": type_config.get("vector", default_weights["vector"]),
                "graph": type_config.get("graph", default_weights["graph"]),
                "memory": type_config.get("memory", default_weights["memory"])
            }

        return weights

    except Exception as e:
        logger.warning(f"Failed to get adaptive weights: {e}, using defaults")
        # Fallback to hardcoded weights
        weights_map = {
            "factual": {"vector": 0.80, "graph": 0.15, "memory": 0.05},
            "decision": {"vector": 0.35, "graph": 0.25, "memory": 0.40},
            "analysis": {"vector": 0.40, "graph": 0.35, "memory": 0.25},
            "navigation": {"vector": 0.30, "graph": 0.65, "memory": 0.05},
            "default": {"vector": 0.50, "graph": 0.30, "memory": 0.20}
        }
        return weights_map.get(query_type, weights_map["default"])


def _get_allowed_scopes(user_role: str) -> list:
    """Delegate to shared RBAC module for role-to-scope mapping."""
    from shared.rbac import get_allowed_scopes
    return get_allowed_scopes(user_role)
