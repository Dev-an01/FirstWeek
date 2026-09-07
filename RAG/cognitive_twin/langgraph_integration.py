"""
LangGraph Integration - Integrates cognitive twin layers into the LangGraph workflow.

This module provides:
1. New LangGraph nodes for cognitive layers
2. Integration points with existing workflow
3. State management for cognitive context
4. Parallelized cognitive layers for ~40% speedup (Priority 3 optimization)

Usage:
    # In your LangGraph graph definition:
    from cognitive_twin.langgraph_integration import (
        cognitive_route_node,
        cognitive_lens_node,
        cognitive_frame_node,
        situation_analysis_node,
        relationship_adaptation_node,
        cognitive_prompt_assembly_node,
        parallel_cognitive_analysis_node,  # Parallelized version
    )

    # Add nodes to your graph
    graph.add_node("cognitive_route", cognitive_route_node)
    graph.add_node("cognitive_lens", cognitive_lens_node)
    ...
"""

import logging
import time
from dataclasses import asdict, is_dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import COGNITIVE_CONFIG, is_layer_enabled
from .profile_loader import get_cognitive_profile_loader
from .conversational_router import get_conversational_router
from .cognitive_lens import get_cognitive_lens
from .cognitive_frame import get_cognitive_frame_builder
from .situation_analyzer import get_situation_analyzer
from .relationship_adapter import get_relationship_adapter
from .prompt_assembler import (
    get_cognitive_prompt_assembler,
    CognitivePromptContext,
)
from .inference_engine import (
    get_inference_engine,
    QueryNature,
    QueryClassification,
    InferenceResult,
)

logger = logging.getLogger(__name__)


def _make_serializable(obj: Any) -> Any:
    """
    Convert dataclasses, enums, and numpy types to serializable Python types.

    LangGraph uses msgpack for state serialization, which requires:
    - No dataclass instances
    - No enum instances
    - No numpy types (float64, etc.)
    """
    import numpy as np
    from enum import Enum

    if obj is None:
        return None
    elif isinstance(obj, (str, int, bool)):
        return obj
    elif isinstance(obj, float):
        return float(obj)  # Ensure Python float, not numpy
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, Enum):
        return obj.value
    elif is_dataclass(obj) and not isinstance(obj, type):
        # Convert dataclass to dict, recursively processing values
        return {k: _make_serializable(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_make_serializable(v) for v in obj]
    else:
        # Return as-is (might fail serialization, but let's see)
        return obj


def _sanitize_full_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize the entire state dictionary to ensure msgpack serialization works.

    This is a final safety net applied before returning state from any node.
    """
    return _make_serializable(state)


# ============================================================================
# State Extension
# ============================================================================

def extend_state_with_cognitive(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extend RAGState with cognitive twin fields.

    This adds the necessary fields for cognitive layer outputs
    without breaking existing state structure.

    Note: Always ensures all required keys exist, even if "cognitive"
    already exists but is missing some keys.
    """
    # Initialize cognitive dict if missing
    if "cognitive" not in state:
        state["cognitive"] = {}

    # Define default values for all cognitive fields
    defaults = {
        "routing": None,          # ConversationalContext
        "lens_result": None,      # CognitiveLensResult
        "frame_result": None,     # CognitiveFrameResult
        "situation": None,        # SituationContext
        "relationship": None,     # RelationshipContext
        "assembled_prompt": None, # AssembledPrompt
        "should_skip_retrieval": False,
        "personality_response": None,
        "layer_timings_ms": {},
        # Inference engine fields
        "query_classification": None,  # QueryClassification
        "inference_result": None,      # InferenceResult
        "use_inference_mode": False,   # True when using inference for response
    }

    # Ensure all required keys exist (don't overwrite existing values)
    for key, default_value in defaults.items():
        if key not in state["cognitive"]:
            state["cognitive"][key] = default_value

    return state


# ============================================================================
# LangGraph Nodes
# ============================================================================

def cognitive_route_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Route query through conversational router.

    Determines if query should skip retrieval (greetings, small talk)
    and generates personality-driven response if so.

    Input state:
        - query: str
        - profile_id: str

    Output state additions:
        - cognitive.routing: ConversationalContext
        - cognitive.should_skip_retrieval: bool
        - cognitive.personality_response: Optional[str]
    """
    state = extend_state_with_cognitive(state)
    start_time = time.time()

    if not is_layer_enabled("enhancement.conversational_router"):
        logger.debug("Conversational router disabled, skipping")
        return state

    query = state.get("query", "")
    profile_id = state.get("profile_id", "")

    if not query or not profile_id:
        logger.warning("Missing query or profile_id for cognitive routing")
        return state

    # =========================================================================
    # FORCE_PATH OVERRIDE: If user specifies force_path, ALWAYS proceed to
    # retrieval and skip conversational routing entirely.
    # This ensures explicit path routing takes precedence over auto-detection.
    # =========================================================================
    force_path = state.get("force_path")
    if force_path:
        logger.info(f"Force path specified ({force_path}), bypassing conversational router - proceeding to retrieval")
        state["cognitive"]["should_skip_retrieval"] = False
        state["cognitive"]["routing"] = None
        state["cognitive"]["force_path_override"] = True
        return _sanitize_full_state(state)

    try:
        router = get_conversational_router()
        conversation_history = state.get("conversation_history", [])

        routing = router.route(
            query=query,
            profile_id=profile_id,
            conversation_history=conversation_history,
        )

        # Store as serializable dict
        state["cognitive"]["routing"] = _make_serializable(routing)
        state["cognitive"]["should_skip_retrieval"] = routing.should_skip_retrieval

        if routing.personality_response:
            state["cognitive"]["personality_response"] = routing.personality_response

        elapsed_ms = (time.time() - start_time) * 1000
        state["cognitive"]["layer_timings_ms"]["routing"] = elapsed_ms

        logger.info(
            f"Cognitive routing: intent={routing.intent.value}, "
            f"skip_retrieval={routing.should_skip_retrieval}, "
            f"latency={elapsed_ms:.1f}ms"
        )

    except Exception as e:
        logger.error(f"Cognitive routing failed: {e}")
        state["cognitive"]["should_skip_retrieval"] = False

    return _sanitize_full_state(state)


def inference_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Classify query nature and prepare inference reasoning.

    This node runs early in the workflow to:
    1. Classify query as factual/opinion/decision/etc.
    2. Prepare inference reasoning for non-factual queries

    The inference result is used later IF retrieval yields no useful results.

    Input state:
        - query: str
        - profile_id: str

    Output state additions:
        - cognitive.query_classification: QueryClassification
        - cognitive.inference_result: InferenceResult (if needs_inference)
    """
    state = extend_state_with_cognitive(state)
    start_time = time.time()

    # Skip if conversational query (already handled by conversational router)
    if state.get("cognitive", {}).get("should_skip_retrieval", False):
        logger.debug("Skipping inference analysis - conversational query")
        return state

    if not is_layer_enabled("enhancement.inference_engine"):
        logger.debug("Inference engine disabled, skipping")
        return state

    query = state.get("query", "")
    profile_id = state.get("profile_id", "")

    if not query or not profile_id:
        logger.warning("Missing query or profile_id for inference analysis")
        return state

    try:
        engine = get_inference_engine()

        # Step 1: Classify the query
        classification = engine.classify_query(query)
        # Store as serializable dict
        state["cognitive"]["query_classification"] = _make_serializable(classification)

        logger.info(
            f"Query classified: nature={classification.nature.value}, "
            f"needs_retrieval={classification.needs_retrieval}, "
            f"needs_inference={classification.needs_inference}"
        )

        # Step 2: If needs inference, prepare reasoning
        if classification.needs_inference:
            inference_result = engine.reason(
                query=query,
                profile_id=profile_id,
                classification=classification,
            )
            # Store as serializable dict
            state["cognitive"]["inference_result"] = _make_serializable(inference_result)

            logger.info(
                f"Inference prepared: values={inference_result.applied_values}, "
                f"red_flags={len(inference_result.red_flags_triggered)}, "
                f"escalate={inference_result.should_escalate}"
            )

        elapsed_ms = (time.time() - start_time) * 1000
        state["cognitive"]["layer_timings_ms"]["inference_analysis"] = elapsed_ms

    except Exception as e:
        logger.error(f"Inference analysis failed: {e}")
        # Continue without inference - retrieval may still work

    return _sanitize_full_state(state)


def cognitive_lens_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Apply cognitive lens to retrieval results.

    Reranks documents based on executive's domain affinity.

    Input state:
        - reranked_results or vector_results: List[Dict]
        - profile_id: str

    Output state additions:
        - cognitive.lens_result: CognitiveLensResult
        - reranked_results: Updated with cognitive lens scores
    """
    state = extend_state_with_cognitive(state)
    start_time = time.time()

    # Skip if retrieval should be skipped
    if state.get("cognitive", {}).get("should_skip_retrieval", False):
        logger.debug("Skipping cognitive lens - retrieval skipped")
        return state

    if not is_layer_enabled("foundation.cognitive_lens"):
        logger.debug("Cognitive lens disabled, skipping")
        return state

    profile_id = state.get("profile_id", "")
    if not profile_id:
        return state

    # Get results to rerank
    results = state.get("reranked_results", []) or state.get("vector_results", [])
    if not results:
        logger.debug("No results to apply cognitive lens to")
        return state

    try:
        lens = get_cognitive_lens()
        lens_result = lens.apply(results, profile_id)

        # Store as serializable dict
        state["cognitive"]["lens_result"] = _make_serializable(lens_result)

        # Update reranked results
        if lens_result.reranked_results:
            state["reranked_results"] = lens_result.reranked_results

        elapsed_ms = (time.time() - start_time) * 1000
        state["cognitive"]["layer_timings_ms"]["lens"] = elapsed_ms

        logger.info(
            f"Cognitive lens applied: domain={lens_result.domain_used}, "
            f"boosted={lens_result.documents_boosted}/{len(results)}, "
            f"latency={elapsed_ms:.1f}ms"
        )

    except Exception as e:
        logger.error(f"Cognitive lens failed: {e}")

    return _sanitize_full_state(state)


def cognitive_frame_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Build cognitive frame for reasoning injection.

    Extracts thinking patterns, red flags, and similar decision cases.

    Input state:
        - query: str
        - profile_id: str

    Output state additions:
        - cognitive.frame_result: CognitiveFrameResult
    """
    state = extend_state_with_cognitive(state)
    start_time = time.time()

    if state.get("cognitive", {}).get("should_skip_retrieval", False):
        logger.debug("Skipping cognitive frame - retrieval skipped")
        return state

    if not is_layer_enabled("foundation.cognitive_frame"):
        logger.debug("Cognitive frame disabled, skipping")
        return state

    query = state.get("query", "")
    profile_id = state.get("profile_id", "")

    if not query or not profile_id:
        return state

    try:
        frame_builder = get_cognitive_frame_builder()
        frame_result = frame_builder.build(query, profile_id)

        # Store as serializable dict
        state["cognitive"]["frame_result"] = _make_serializable(frame_result)

        elapsed_ms = (time.time() - start_time) * 1000
        state["cognitive"]["layer_timings_ms"]["frame"] = elapsed_ms

        logger.info(
            f"Cognitive frame built: cases_matched={frame_result.cases_matched}, "
            f"latency={elapsed_ms:.1f}ms"
        )

    except Exception as e:
        logger.error(f"Cognitive frame failed: {e}")

    return _sanitize_full_state(state)


def situation_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Analyze situational context.

    Detects emotional tone, urgency, implicit needs.

    Input state:
        - query: str
        - conversation_history: Optional[List]
        - user_metadata: Optional[Dict]

    Output state additions:
        - cognitive.situation: SituationContext
    """
    state = extend_state_with_cognitive(state)
    start_time = time.time()

    if not is_layer_enabled("enhancement.situation_analyzer"):
        logger.debug("Situation analyzer disabled, skipping")
        return state

    query = state.get("query", "")
    if not query:
        return state

    try:
        analyzer = get_situation_analyzer()

        situation = analyzer.analyze(
            query=query,
            timestamp=datetime.now(),
            conversation_history=state.get("conversation_history", []),
            user_metadata=state.get("user_metadata"),
        )

        # Store as serializable dict
        state["cognitive"]["situation"] = _make_serializable(situation)

        elapsed_ms = (time.time() - start_time) * 1000
        state["cognitive"]["layer_timings_ms"]["situation"] = elapsed_ms

        logger.info(
            f"Situation analyzed: tone={situation.emotional_tone.value}, "
            f"urgency={situation.urgency_level.value}, "
            f"latency={elapsed_ms:.1f}ms"
        )

    except Exception as e:
        logger.error(f"Situation analysis failed: {e}")

    return _sanitize_full_state(state)


def relationship_adaptation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Adapt communication based on relationship.

    Determines how to communicate based on user's role.

    Input state:
        - profile_id: str
        - user_id: Optional[str]
        - user_metadata: Optional[Dict]

    Output state additions:
        - cognitive.relationship: RelationshipContext
    """
    state = extend_state_with_cognitive(state)
    start_time = time.time()

    if not is_layer_enabled("enhancement.relationship_dynamics"):
        logger.debug("Relationship dynamics disabled, skipping")
        return state

    profile_id = state.get("profile_id", "")
    if not profile_id:
        return state

    try:
        adapter = get_relationship_adapter()

        relationship = adapter.adapt(
            executive_profile_id=profile_id,
            user_id=state.get("user_id"),
            user_metadata=state.get("user_metadata"),
        )

        # Store as serializable dict
        state["cognitive"]["relationship"] = _make_serializable(relationship)

        elapsed_ms = (time.time() - start_time) * 1000
        state["cognitive"]["layer_timings_ms"]["relationship"] = elapsed_ms

        logger.info(
            f"Relationship adapted: type={relationship.relationship_type.value}, "
            f"user_role={relationship.user_role.value}, "
            f"latency={elapsed_ms:.1f}ms"
        )

    except Exception as e:
        logger.error(f"Relationship adaptation failed: {e}")

    return _sanitize_full_state(state)


def cognitive_prompt_assembly_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Assemble final cognitive prompt.

    Combines all layer outputs into system and user prompts.
    Uses INFERENCE MODE when:
    - Query is opinion/decision/concern type (needs_inference=True)
    - AND no retrieval results are available

    Input state:
        - query: str
        - profile_id: str
        - cognitive.*: All cognitive layer outputs
        - reranked_results: Retrieved sources

    Output state additions:
        - cognitive.assembled_prompt: AssembledPrompt
        - cognitive.use_inference_mode: bool
        - system_prompt: str (for generation)
        - user_prompt: str (for generation)
    """
    state = extend_state_with_cognitive(state)
    start_time = time.time()

    # Check if we should use personality response
    if state.get("cognitive", {}).get("should_skip_retrieval", False):
        personality_response = state.get("cognitive", {}).get("personality_response")
        if personality_response:
            # For conversational queries, we already have the response
            state["final_response"] = personality_response
            logger.info("Using personality response for conversational query")
            return state

    query = state.get("query", "")
    profile_id = state.get("profile_id", "")

    if not query or not profile_id:
        return state

    cognitive_state = state.get("cognitive", {})
    retrieval_results = state.get("reranked_results", []) or state.get("vector_results", [])

    # Check if we should use inference mode
    # query_classification and inference_result are stored as dicts for serialization
    query_classification_dict = cognitive_state.get("query_classification")
    inference_result_dict = cognitive_state.get("inference_result")

    use_inference_mode = False

    # Use inference mode when:
    # 1. Query needs inference (opinion/decision/concern/values)
    # 2. AND (no retrieval results OR query is purely opinion-based)
    if query_classification_dict and inference_result_dict:
        needs_inference = query_classification_dict.get("needs_inference", False)
        query_nature = query_classification_dict.get("nature", "")
        no_retrieval_data = len(retrieval_results) == 0

        # For opinion/decision queries with no data, ALWAYS use inference
        if needs_inference and no_retrieval_data:
            use_inference_mode = True
            logger.info(
                f"INFERENCE MODE: No retrieval data for {query_nature} query, "
                f"using inference framework"
            )
        # For factual queries with no data, inference is NOT used (OK to say "don't know")
        elif query_nature == "factual" and no_retrieval_data:
            use_inference_mode = False
            logger.info("FACTUAL query with no data - standard mode (may say 'don't know')")

    state["cognitive"]["use_inference_mode"] = use_inference_mode

    try:
        if use_inference_mode and inference_result_dict:
            # Reconstruct InferenceResult from dict for prompt building
            inference_result = InferenceResult(
                reasoning_steps=inference_result_dict.get("reasoning_steps", []),
                applied_values=inference_result_dict.get("applied_values", []),
                risk_assessment=inference_result_dict.get("risk_assessment"),
                red_flags_triggered=inference_result_dict.get("red_flags_triggered", []),
                suggested_response_pattern=inference_result_dict.get("suggested_response_pattern", ""),
                confidence=inference_result_dict.get("confidence", 0.5),
                should_escalate=inference_result_dict.get("should_escalate", False),
                escalation_reason=inference_result_dict.get("escalation_reason"),
            )

            # Use inference engine to build prompts
            engine = get_inference_engine()
            system_prompt, user_prompt = engine.build_inference_prompt(
                query=query,
                profile_id=profile_id,
                inference_result=inference_result,
                retrieval_context=retrieval_results,  # Pass any available context
            )

            state["system_prompt"] = system_prompt
            state["user_prompt"] = user_prompt

            logger.info(
                f"Inference prompt built: "
                f"values={inference_result.applied_values}, "
                f"pattern={inference_result.suggested_response_pattern}"
            )
        else:
            # Standard cognitive prompt assembly (with retrieval data)
            assembler = get_cognitive_prompt_assembler()

            context = CognitivePromptContext(
                query=query,
                profile_id=profile_id,
                cognitive_frame=cognitive_state.get("frame_result"),
                situation_context=cognitive_state.get("situation"),
                relationship_context=cognitive_state.get("relationship"),
                retrieved_sources=retrieval_results,
                conversation_history=state.get("conversation_history", []),
                user_metadata=state.get("user_metadata"),
            )

            assembled = assembler.assemble(context)

            # Store as serializable dict
            state["cognitive"]["assembled_prompt"] = _make_serializable(assembled)
            state["system_prompt"] = assembled.system_prompt
            state["user_prompt"] = assembled.user_prompt

            logger.info(
                f"Cognitive prompt assembled: "
                f"system={len(assembled.system_prompt)} chars, "
                f"user={len(assembled.user_prompt)} chars"
            )

        elapsed_ms = (time.time() - start_time) * 1000
        state["cognitive"]["layer_timings_ms"]["assembly"] = elapsed_ms

    except Exception as e:
        logger.error(f"Prompt assembly failed: {e}")

    return _sanitize_full_state(state)


# ============================================================================
# Conditional Edge Functions
# ============================================================================

def should_skip_retrieval(state: Dict[str, Any]) -> str:
    """
    Conditional edge: Determine if retrieval should be skipped.

    Returns:
        "skip_retrieval" if conversational query
        "continue_retrieval" otherwise
    """
    if state.get("cognitive", {}).get("should_skip_retrieval", False):
        return "skip_retrieval"
    return "continue_retrieval"


def get_cognitive_layer_timings(state: Dict[str, Any]) -> Dict[str, float]:
    """
    Get timing information for all cognitive layers.

    Useful for monitoring and optimization.
    """
    return state.get("cognitive", {}).get("layer_timings_ms", {})


# ============================================================================
# Integration Helper
# ============================================================================

def create_cognitive_workflow_nodes(use_parallel: bool = None) -> Dict[str, callable]:
    """
    Get all cognitive workflow nodes as a dict.

    Useful for adding to existing LangGraph graphs.

    Args:
        use_parallel: If True, uses parallelized node for frame/situation/relationship.
                      If None, reads from COGNITIVE_CONFIG["performance"]["parallel_cognitive_layers"]

    Returns:
        Dict mapping node names to node functions

    Node order:
        1. cognitive_route - Determine if conversational (skip retrieval)
        2. inference_analysis - Classify query nature, prepare inference reasoning
        3. cognitive_lens - Apply domain affinity reranking (after retrieval)
        4. parallel_cognitive_analysis OR frame/situation/relationship
        5. cognitive_prompt_assembly - Build final prompt (uses inference if needed)
    """
    # Check if parallelization is enabled
    if use_parallel is None:
        use_parallel = COGNITIVE_CONFIG.get("performance", {}).get("parallel_cognitive_layers", True)

    if use_parallel:
        # Use single parallelized node instead of three sequential nodes
        return {
            "cognitive_route": cognitive_route_node,
            "inference_analysis": inference_analysis_node,  # NEW: Query classification + inference prep
            "cognitive_lens": cognitive_lens_node,
            "parallel_cognitive_analysis": parallel_cognitive_analysis_node,  # Replaces frame/situation/relationship
            "cognitive_prompt_assembly": cognitive_prompt_assembly_node,
        }
    else:
        # Original sequential nodes
        return {
            "cognitive_route": cognitive_route_node,
            "inference_analysis": inference_analysis_node,  # NEW: Query classification + inference prep
            "cognitive_lens": cognitive_lens_node,
            "cognitive_frame": cognitive_frame_node,
            "situation_analysis": situation_analysis_node,
            "relationship_adaptation": relationship_adaptation_node,
            "cognitive_prompt_assembly": cognitive_prompt_assembly_node,
        }


def add_cognitive_nodes_to_graph(graph: Any) -> Any:
    """
    Add all cognitive nodes to a LangGraph StateGraph.

    Args:
        graph: LangGraph StateGraph instance

    Returns:
        Updated graph with cognitive nodes added
    """
    nodes = create_cognitive_workflow_nodes()

    for name, node_fn in nodes.items():
        graph.add_node(name, node_fn)

    logger.info(f"Added {len(nodes)} cognitive nodes to graph")
    return graph


# ============================================================================
# Parallelized Cognitive Analysis (Priority 3 Optimization)
# ============================================================================

def parallel_cognitive_analysis_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Run frame, situation, and relationship analysis in PARALLEL.

    These three layers are independent and can run concurrently:
    - cognitive_frame: Needs query + profile_id
    - situation_analysis: Needs query + conversation_history
    - relationship_adaptation: Needs profile_id + user_metadata

    Expected speedup: ~200ms (40% of cognitive layer time)

    Input state:
        - query: str
        - profile_id: str
        - conversation_history: Optional[List]
        - user_metadata: Optional[Dict]

    Output state additions:
        - cognitive.frame_result: CognitiveFrameResult
        - cognitive.situation: SituationContext
        - cognitive.relationship: RelationshipContext
    """
    state = extend_state_with_cognitive(state)
    start_time = time.time()

    # Skip if retrieval should be skipped (conversational query)
    if state.get("cognitive", {}).get("should_skip_retrieval", False):
        logger.debug("Skipping parallel cognitive analysis - retrieval skipped")
        return state

    query = state.get("query", "")
    profile_id = state.get("profile_id", "")

    if not query or not profile_id:
        logger.warning("Missing query or profile_id for parallel cognitive analysis")
        return state

    def run_frame_analysis():
        """Run cognitive frame analysis."""
        if not is_layer_enabled("foundation.cognitive_frame"):
            return None, "frame", 0
        layer_start = time.time()
        try:
            frame_builder = get_cognitive_frame_builder()
            result = frame_builder.build(query, profile_id)
            elapsed = (time.time() - layer_start) * 1000
            return result, "frame", elapsed
        except Exception as e:
            logger.error(f"Cognitive frame failed in parallel: {e}")
            return None, "frame", 0

    def run_situation_analysis():
        """Run situation analysis."""
        if not is_layer_enabled("enhancement.situation_analyzer"):
            return None, "situation", 0
        layer_start = time.time()
        try:
            analyzer = get_situation_analyzer()
            result = analyzer.analyze(
                query=query,
                timestamp=datetime.now(),
                conversation_history=state.get("conversation_history", []),
                user_metadata=state.get("user_metadata"),
            )
            elapsed = (time.time() - layer_start) * 1000
            return result, "situation", elapsed
        except Exception as e:
            logger.error(f"Situation analysis failed in parallel: {e}")
            return None, "situation", 0

    def run_relationship_adaptation():
        """Run relationship adaptation."""
        if not is_layer_enabled("enhancement.relationship_dynamics"):
            return None, "relationship", 0
        layer_start = time.time()
        try:
            adapter = get_relationship_adapter()
            result = adapter.adapt(
                executive_profile_id=profile_id,
                user_id=state.get("user_id"),
                user_metadata=state.get("user_metadata"),
            )
            elapsed = (time.time() - layer_start) * 1000
            return result, "relationship", elapsed
        except Exception as e:
            logger.error(f"Relationship adaptation failed in parallel: {e}")
            return None, "relationship", 0

    # Run all three in parallel
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(run_frame_analysis),
            executor.submit(run_situation_analysis),
            executor.submit(run_relationship_adaptation),
        ]

        for future in as_completed(futures):
            result, layer_name, elapsed_ms = future.result()
            if result is not None:
                if layer_name == "frame":
                    # Store as serializable dict
                    state["cognitive"]["frame_result"] = _make_serializable(result)
                    state["cognitive"]["layer_timings_ms"]["frame"] = elapsed_ms
                    logger.info(f"[Parallel] Frame: cases_matched={result.cases_matched}, {elapsed_ms:.1f}ms")
                elif layer_name == "situation":
                    # Store as serializable dict
                    state["cognitive"]["situation"] = _make_serializable(result)
                    state["cognitive"]["layer_timings_ms"]["situation"] = elapsed_ms
                    logger.info(f"[Parallel] Situation: tone={result.emotional_tone.value}, {elapsed_ms:.1f}ms")
                elif layer_name == "relationship":
                    # Store as serializable dict
                    state["cognitive"]["relationship"] = _make_serializable(result)
                    state["cognitive"]["layer_timings_ms"]["relationship"] = elapsed_ms
                    logger.info(f"[Parallel] Relationship: type={result.relationship_type.value}, {elapsed_ms:.1f}ms")

    total_elapsed = (time.time() - start_time) * 1000
    state["cognitive"]["layer_timings_ms"]["parallel_total"] = total_elapsed

    logger.info(f"Parallel cognitive analysis completed in {total_elapsed:.1f}ms")

    return _sanitize_full_state(state)
