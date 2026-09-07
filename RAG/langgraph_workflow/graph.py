"""
Main RAG Workflow Graph with LangGraph

Features:
- Parallel retrieval using ThreadPoolExecutor (graph-enhanced vector || memory)
- ReAct sub-graph for agentic path
- Memory integration with MultiSignalMemorySearch
- GraphRAG global search for broad/thematic queries
- RAGAS evaluation metrics
- Cognitive Twin integration (6-layer cognitive architecture)
"""
import logging
from typing import Literal, Dict, Callable, Any, Optional
from langgraph.graph import StateGraph, END

from .state import RAGState
from .nodes import create_nodes
from .react_subgraph import create_react_nodes, should_continue_react

# Cognitive Twin imports (optional - graceful fallback if not available)
try:
    from cognitive_twin.config import COGNITIVE_CONFIG, is_layer_enabled
    from cognitive_twin.langgraph_integration import (
        cognitive_route_node,
        cognitive_lens_node,
        cognitive_frame_node,
        situation_analysis_node,
        relationship_adaptation_node,
        cognitive_prompt_assembly_node,
        should_skip_retrieval,
        extend_state_with_cognitive,
    )
    COGNITIVE_TWIN_AVAILABLE = True
except ImportError:
    COGNITIVE_TWIN_AVAILABLE = False
    COGNITIVE_CONFIG = {"enabled": False}

logger = logging.getLogger(__name__)


def route_to_path(state: RAGState) -> Literal["fast", "standard", "agentic"]:
    """
    Conditional edge: Route based on path decision
    """
    path = state.get("selected_path", "standard")
    logger.info(f"Routing to {path} path")
    return path


def route_cognitive(state: RAGState) -> Literal["skip_retrieval", "continue_retrieval"]:
    """
    Conditional edge: Route based on cognitive routing decision.

    For conversational queries (greetings, small talk), skip retrieval
    and generate a personality-driven response directly.
    """
    if state.get("cognitive", {}).get("should_skip_retrieval", False):
        logger.info("Cognitive routing: skipping retrieval (conversational query)")
        return "skip_retrieval"
    return "continue_retrieval"


def create_rag_workflow(
    vector_engine: Any,
    graph_provider: Any,
    query_analyzer: Any,
    query_router: Any,
    result_fusion: Any,
    adaptive_reranker: Any,
    llm_orchestrator: Any,
    session_manager: Any,
    hybrid_retrieval_manager: Any = None,
    memory_search_engine: Any = None,
    checkpointer: Any = None,
    graphrag_provider: Any = None,
    ragas_evaluator: Any = None,
    conversation_engine: Any = None
) -> StateGraph:
    """
    Create complete RAG workflow graph with Cognitive Twin integration.

    Flow (with Cognitive Twin enabled):
    ────────────────────────────────────

    cognitive_route →
      [conversational] → generate_conversational → END (greetings/small talk skip retrieval)

      [retrieval] → analyze_query → route_query →

        [fast path] → retrieve → cognitive_lens → generate_fast → END

        [standard path] → GraphRAG → parallel_retrieval → fuse → rerank →
                         cognitive_lens → cognitive_frame → situation_analysis →
                         relationship_adaptation → prompt_assembly → generate → END

        [agentic path] → GraphRAG → parallel_retrieval → fuse → rerank →
                         react_think → react_act → react_observe → should_continue?
                             ↓ continue                           ↓ finalize
                             ← (loop back)                        → react_finalize → END

    Flow (without Cognitive Twin):
    ──────────────────────────────

    analyze_query → route_query →
      [fast] → retrieve → generate → END
      [standard] → GraphRAG → parallel_retrieval → fuse → rerank → generate → END
      [agentic] → GraphRAG → parallel_retrieval → fuse → rerank → ReAct loop → END

    Cognitive Twin Layers:
    ─────────────────────
    - Layer 0: Conversational Router (intent detection, personality-only responses)
    - Layer 1: Cognitive Lens (domain affinity reranking based on executive profile)
    - Layer 2: Cognitive Frame (reasoning patterns, red flags, decision cases)
    - Layer 4: Situation Analyzer (emotional tone, urgency, implicit needs)
    - Layer 5: Relationship Adapter (communication style based on user role)
    - Prompt Assembly: Combines all cognitive outputs into system/user prompts

    Args:
        vector_engine: VectorSearchEngine singleton
        graph_provider: GraphContextProvider singleton
        query_analyzer: QueryAnalyzer instance
        query_router: QueryRouter instance
        result_fusion: ResultFusion instance
        adaptive_reranker: AdaptiveReranker instance
        llm_orchestrator: LLMOrchestrator instance
        session_manager: SessionManager instance
        hybrid_retrieval_manager: For ReAct tool execution (optional)
        memory_search_engine: MultiSignalMemorySearch for episodic memory
        checkpointer: PostgresSaver for LangGraph threading/checkpointing
        graphrag_provider: GraphRAGProvider for global/thematic search
        ragas_evaluator: RAGASEvaluator for quality metrics
        conversation_engine: ConversationEngine for context-aware prompt generation

    Returns:
        Compiled StateGraph workflow
    """
    
    # Create nodes with dependency injection
    nodes = create_nodes(
        vector_engine=vector_engine,
        graph_provider=graph_provider,
        query_analyzer=query_analyzer,
        query_router=query_router,
        result_fusion=result_fusion,
        adaptive_reranker=adaptive_reranker,
        llm_orchestrator=llm_orchestrator,
        session_manager=session_manager,
        memory_search_engine=memory_search_engine,
        graphrag_provider=graphrag_provider,
        ragas_evaluator=ragas_evaluator,
        conversation_engine=conversation_engine
    )
    
    # Create ReAct nodes (Week 2, Day 4)
    # Create dedicated LLM client for ReAct using the factory
    from llm_integration.factory import LLMClientFactory
    from config.llm_config_loader import get_config
    
    config = get_config()
    provider = llm_orchestrator.provider
    provider_config = config.get_provider_config(provider)
    
    # Build client config for ReAct
    client_config = {
        'models': {},
        'temperature': {},
        'max_tokens': {},
        **provider_config
    }
    
    # Use agentic path settings for ReAct
    agentic_settings = config.get_path_settings('agentic')
    for path_name in ['fast', 'standard', 'agentic']:
        client_config['models'][path_name] = provider_config['models'].get(path_name, provider_config['models'].get('standard'))
        path_settings = config.get_path_settings(path_name)
        client_config['temperature'][path_name] = path_settings.get('temperature', 0.7)
        client_config['max_tokens'][path_name] = path_settings.get('max_tokens', 1000)
    
    react_llm_client = LLMClientFactory.create(
        provider=provider,
        config=client_config,
        path='agentic'  # Use agentic settings for ReAct
    )
    
    # ReAct nodes will get profile_id from state dynamically
    # No need to hardcode here - each request can use different profile
    # Pass conversation_engine and llm_orchestrator for prompt generation
    react_nodes = create_react_nodes(
        llm_client=react_llm_client,
        hybrid_retrieval_manager=hybrid_retrieval_manager,
        conversation_engine=conversation_engine,
        llm_orchestrator=llm_orchestrator
    )
    
    # Initialize workflow
    workflow = StateGraph(RAGState)

    # =========================================================================
    # COGNITIVE TWIN NODES (6-Layer Architecture)
    # =========================================================================
    # Add cognitive nodes if available and enabled
    cognitive_enabled = COGNITIVE_TWIN_AVAILABLE and COGNITIVE_CONFIG.get("enabled", False)

    logger.info(f"Cognitive Twin check: AVAILABLE={COGNITIVE_TWIN_AVAILABLE}, CONFIG_ENABLED={COGNITIVE_CONFIG.get('enabled', False)}, cognitive_enabled={cognitive_enabled}")

    if cognitive_enabled:
        logger.info("✅ Adding Cognitive Twin nodes to workflow (conversational routing enabled)")

        # Layer 0: Conversational Router (intent detection)
        workflow.add_node("cognitive_route", cognitive_route_node)

        # Conversational response node (for greetings/small talk)
        # Import router for prompt building
        from cognitive_twin.conversational_router import get_conversational_router

        def generate_conversational(state: RAGState) -> RAGState:
            """
            Generate response for conversational queries using LLM with personality.

            For non-streaming: Calls LLM directly and sets final_response
            For streaming: Builds prompts and stores in state for endpoint to stream
            """
            import time
            start_time = time.time()

            query = state.get("query", "")
            profile_id = state.get("profile_id", "exec_001_test")
            skip_generation = state.get("skip_generation", False)

            logger.info(f"Conversational node: query='{query[:50]}', profile={profile_id}, skip_gen={skip_generation}")

            # Get intent from routing
            cognitive_state = state.get("cognitive", {})
            routing = cognitive_state.get("routing")
            intent_value = routing.intent.value if routing and hasattr(routing, 'intent') else "greeting"

            # Build conversational prompt using personality
            router = get_conversational_router()
            system_prompt, user_prompt = router.build_conversational_prompt(
                query=query,
                profile_id=profile_id,
                intent=intent_value
            )

            logger.debug(f"Conversational prompts built: system={len(system_prompt)}, user={len(user_prompt)}")

            # Store prompts in state (needed for streaming endpoints)
            state["cognitive"]["conversational_system_prompt"] = system_prompt
            state["cognitive"]["conversational_user_prompt"] = user_prompt

            # Track whether LLM was called
            llm_status = "not_attempted"

            if skip_generation:
                # Streaming mode: endpoint will call LLM with streaming
                logger.info(f"Conversational: prompts built for streaming (intent={intent_value})")
                state["final_response"] = None  # Will be streamed by endpoint
                llm_status = "skipped_for_streaming"
            elif llm_orchestrator is None:
                # Orchestrator is None - this is a bug
                logger.error("llm_orchestrator is None in generate_conversational!")
                fallback = cognitive_state.get("personality_response", "Hey! What's up?")
                state["final_response"] = fallback
                state["error"] = "llm_orchestrator is None"
                llm_status = "orchestrator_none"
            else:
                # Non-streaming mode: call LLM directly for varied responses
                logger.info(f"Conversational: calling LLM for dynamic response (skip_generation={skip_generation})")
                try:
                    response = llm_orchestrator.generate_with_prompts(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        profile_id=profile_id,
                        path="fast"  # Use fast path for quick conversational responses
                    )
                    logger.info(f"Conversational: LLM response received, keys={list(response.keys())}")

                    # response is a dict with 'answer' and 'metadata' keys
                    llm_answer = response.get("answer", "")
                    if llm_answer:
                        state["final_response"] = llm_answer
                        state["llm_tokens"] = response.get("metadata", {}).get("llm_tokens", {})
                        logger.info(f"Conversational LLM SUCCESS: '{llm_answer[:100]}...'")
                        llm_status = "success"
                    else:
                        # Empty response - use personality response as fallback
                        logger.warning("LLM returned empty response, using personality fallback")
                        state["final_response"] = cognitive_state.get("personality_response", "Hey! What's up?")
                        llm_status = "empty_response"
                except Exception as e:
                    # Fallback on LLM failure - use personality response or generic
                    error_msg = str(e)
                    logger.error(f"Conversational LLM FAILED: {error_msg}", exc_info=True)
                    fallback = cognitive_state.get("personality_response")
                    if not fallback or fallback == "Hi! How can I help you?":
                        # Avoid the generic fallback - use something more natural
                        fallback = "Hey! What's on your mind?"
                    state["final_response"] = fallback
                    # Store error info for debugging
                    state["error"] = f"LLM call failed: {error_msg}"
                    llm_status = f"error: {error_msg[:50]}"
                    logger.warning(f"Using fallback response: '{fallback}'")

            # Set metadata with debug info
            elapsed_ms = (time.time() - start_time) * 1000
            state["selected_path"] = "conversational"
            # Note: llm_tokens expects integer values for token counts, stored via response metadata
            state["response_metadata"] = {
                "path": "conversational",
                "cognitive_layers_used": ["conversational_router", "llm_generation"],
                "retrieval_skipped": True,
                "intent": intent_value,
                "generation_time_ms": elapsed_ms,
                "llm_status": llm_status  # Debug: track if LLM was called
            }

            # Add LLM latency to component_latencies for proper tracking
            if "component_latencies" not in state:
                state["component_latencies"] = {}
            state["component_latencies"]["generate_conversational"] = elapsed_ms

            # Update conversation_history for multi-turn memory (checkpointer persists this)
            # CRITICAL: This must happen for follow-up queries to work!
            final_response = state.get("final_response", "")
            if final_response and not state.get("error"):
                from .state import safe_get
                history = safe_get(state, "conversation_history", [])
                history.append({"role": "user", "content": query})
                history.append({"role": "assistant", "content": final_response})
                state["conversation_history"] = history
                logger.info(f"Updated conversation_history (conversational): {len(history)} messages")

            return state

        workflow.add_node("generate_conversational", generate_conversational)

        # =====================================================================
        # FAST PATH cognitive nodes (just cognitive lens for speed)
        # =====================================================================
        workflow.add_node("cognitive_lens_fast", cognitive_lens_node)

        # =====================================================================
        # STANDARD PATH cognitive nodes (full cognitive enhancement)
        # =====================================================================
        # Layer 1: Cognitive Lens (domain affinity reranking)
        workflow.add_node("cognitive_lens_standard", cognitive_lens_node)

        # Layer 2: Cognitive Frame (reasoning injection)
        workflow.add_node("cognitive_frame_standard", cognitive_frame_node)

        # Layer 4: Situation Analysis
        workflow.add_node("situation_analysis_standard", situation_analysis_node)

        # Layer 5: Relationship Adaptation
        workflow.add_node("relationship_adaptation_standard", relationship_adaptation_node)

        # Prompt Assembly (combines all cognitive layers)
        workflow.add_node("cognitive_prompt_assembly_standard", cognitive_prompt_assembly_node)

    # =========================================================================
    # COMMON NODES (all paths)
    # =========================================================================
    workflow.add_node("analyze_query", nodes["analyze_query"])
    workflow.add_node("route_query", nodes["route_query"])

    # Fast path nodes
    workflow.add_node("retrieve_unified_fast", nodes["retrieve_graph_enhanced"])
    workflow.add_node("generate_fast", nodes["generate_fast"])

    # Standard path nodes (parallel retrieval with GraphRAG)
    workflow.add_node("retrieve_graphrag_standard", nodes["retrieve_graphrag_global"])
    workflow.add_node("retrieve_parallel_standard", nodes["retrieve_parallel"])
    workflow.add_node("fuse_results_standard", nodes["fuse_results"])
    workflow.add_node("rerank_results_standard", nodes["rerank_results"])
    workflow.add_node("generate_standard", nodes["generate_standard"])

    # Agentic path nodes (parallel retrieval + ReAct sub-graph)
    workflow.add_node("retrieve_graphrag_agentic", nodes["retrieve_graphrag_global"])
    workflow.add_node("retrieve_parallel_agentic", nodes["retrieve_parallel"])
    workflow.add_node("fuse_results_agentic", nodes["fuse_results"])
    workflow.add_node("rerank_results_agentic", nodes["rerank_results"])
    
    # ReAct sub-graph nodes
    workflow.add_node("react_think", react_nodes["react_think"])
    workflow.add_node("react_act", react_nodes["react_act"])
    workflow.add_node("react_observe", react_nodes["react_observe"])
    workflow.add_node("react_finalize", react_nodes["react_finalize"])

    # =========================================================================
    # WIRE WORKFLOW EDGES
    # =========================================================================

    if cognitive_enabled:
        # Entry point: cognitive_route first (checks for conversational queries)
        workflow.set_entry_point("cognitive_route")

        # Cognitive routing: skip retrieval for greetings/small talk
        workflow.add_conditional_edges(
            "cognitive_route",
            route_cognitive,
            {
                "skip_retrieval": "generate_conversational",
                "continue_retrieval": "analyze_query"
            }
        )

        # Conversational path ends directly
        workflow.add_edge("generate_conversational", END)
    else:
        # Without cognitive twin, start directly at analyze_query
        workflow.set_entry_point("analyze_query")

    # analyze_query → route_query (always)
    workflow.add_edge("analyze_query", "route_query")

    # Conditional routing (standard/agentic go through GraphRAG first)
    workflow.add_conditional_edges(
        "route_query",
        route_to_path,
        {
            "fast": "retrieve_unified_fast",
            "standard": "retrieve_graphrag_standard",
            "agentic": "retrieve_graphrag_agentic"
        }
    )

    # =========================================================================
    # FAST PATH (with optional cognitive enhancement)
    # =========================================================================
    if cognitive_enabled:
        # Fast path: retrieve → cognitive_lens_fast → generate_fast
        workflow.add_edge("retrieve_unified_fast", "cognitive_lens_fast")
        workflow.add_edge("cognitive_lens_fast", "generate_fast")
    else:
        # Fast path without cognitive: retrieve → generate_fast
        workflow.add_edge("retrieve_unified_fast", "generate_fast")

    workflow.add_edge("generate_fast", END)

    # =========================================================================
    # STANDARD PATH (with cognitive enhancement layers)
    # =========================================================================
    workflow.add_edge("retrieve_graphrag_standard", "retrieve_parallel_standard")
    workflow.add_edge("retrieve_parallel_standard", "fuse_results_standard")
    workflow.add_edge("fuse_results_standard", "rerank_results_standard")

    if cognitive_enabled:
        # Standard path with cognitive layers:
        # rerank → cognitive_lens → cognitive_frame → situation_analysis →
        # relationship_adaptation → cognitive_prompt_assembly → generate_standard
        workflow.add_edge("rerank_results_standard", "cognitive_lens_standard")
        workflow.add_edge("cognitive_lens_standard", "cognitive_frame_standard")
        workflow.add_edge("cognitive_frame_standard", "situation_analysis_standard")
        workflow.add_edge("situation_analysis_standard", "relationship_adaptation_standard")
        workflow.add_edge("relationship_adaptation_standard", "cognitive_prompt_assembly_standard")
        workflow.add_edge("cognitive_prompt_assembly_standard", "generate_standard")
    else:
        # Standard path without cognitive
        workflow.add_edge("rerank_results_standard", "generate_standard")

    workflow.add_edge("generate_standard", END)

    # =========================================================================
    # AGENTIC PATH (ReAct sub-graph with cognitive enhancement)
    # =========================================================================
    workflow.add_edge("retrieve_graphrag_agentic", "retrieve_parallel_agentic")
    workflow.add_edge("retrieve_parallel_agentic", "fuse_results_agentic")
    workflow.add_edge("fuse_results_agentic", "rerank_results_agentic")

    # Note: For agentic path, cognitive layers are integrated in ReAct nodes
    # via conversation_engine which already uses cognitive prompt assembly
    workflow.add_edge("rerank_results_agentic", "react_think")
    workflow.add_edge("react_think", "react_act")
    workflow.add_edge("react_act", "react_observe")

    # Conditional edge: continue loop or finalize
    workflow.add_conditional_edges(
        "react_observe",
        should_continue_react,
        {
            "continue": "react_think",      # Loop back for another iteration
            "finalize": "react_finalize"    # Exit loop and finalize
        }
    )

    # Final edge
    workflow.add_edge("react_finalize", END)

    # =========================================================================
    # LOG WORKFLOW CONFIGURATION
    # =========================================================================
    logger.info("RAG workflow created")
    logger.info("   - Graph-constrained vector search (0.6v + 0.4g hybrid scoring)")
    logger.info("   - Parallel retrieval (graph-enhanced || memory via ThreadPoolExecutor)")
    logger.info("   - GraphRAG global search for broad/thematic queries")
    logger.info("   - RAGAS evaluation (enable_evaluation=True to activate)")
    logger.info("   - 3 paths: fast, standard, agentic (with ReAct)")

    if cognitive_enabled:
        logger.info("Cognitive Twin ENABLED (6-layer architecture)")
        logger.info("   - Layer 0: Conversational Router (greetings skip retrieval)")
        logger.info("   - Layer 1: Cognitive Lens (domain affinity reranking)")
        logger.info("   - Layer 2: Cognitive Frame (reasoning injection)")
        logger.info("   - Layer 4: Situation Analyzer (context understanding)")
        logger.info("   - Layer 5: Relationship Adapter (communication style)")
        logger.info("   - Prompt Assembly: Combines all cognitive outputs")
    else:
        logger.info("Cognitive Twin DISABLED (using standard workflow)")

    # Compile with checkpointer for threading/conversation continuity
    if checkpointer:
        logger.info("✅ Compiling workflow WITH checkpointer (LangGraph threading enabled)")
        logger.info("   - Conversations will be linked in LangSmith")
        logger.info("   - State checkpointing enabled for recovery")
        return workflow.compile(checkpointer=checkpointer)
    else:
        logger.info("⚠️  Compiling workflow WITHOUT checkpointer (threading disabled)")
        return workflow.compile()


def visualize_workflow(workflow: StateGraph) -> str:
    """
    Generate Mermaid diagram for workflow visualization
    
    Returns:
        Mermaid diagram string
    """
    try:
        mermaid = workflow.get_graph().draw_mermaid()
        return mermaid
    except Exception as e:
        logger.error(f"Failed to generate Mermaid diagram: {e}")
        return "Error generating visualization"


# Export for easy import
__all__ = ["create_rag_workflow", "visualize_workflow"]
