"""
ReAct Sub-Graph for Agentic Path - Week 2, Day 4

Implements the ReAct (Reasoning and Acting) pattern as a LangGraph sub-graph
with explicit iteration nodes.

Flow:
    react_think → react_act → react_observe → should_continue_react?
        ↓ continue                              ↓ finalize
        ← (back to react_think)                 → react_finalize → END

Key Features:
- Explicit thought-action-observe loop
- Confidence-based continuation logic
- Tool integration for multi-hop reasoning
- Context accumulation across iterations
- LangSmith tracing for each node
"""

import logging
import time
import re
import threading
from typing import Literal, Dict, Any, List, Callable, TypeVar
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
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

from .state import RAGState, safe_get
from .nodes import sanitize_node, _sanitize_state_for_serialization

# Type variable for generic timeout wrapper
T = TypeVar('T')

# Tool execution timeout in seconds
TOOL_EXECUTION_TIMEOUT = 30  # 30 seconds max per tool


def _execute_with_timeout(func: Callable[[], T], timeout_seconds: int = TOOL_EXECUTION_TIMEOUT) -> T:
    """
    Execute a function with a timeout.

    Uses ThreadPoolExecutor for cross-platform compatibility (Windows doesn't support SIGALRM).

    Args:
        func: Zero-argument callable to execute
        timeout_seconds: Maximum execution time in seconds

    Returns:
        Result of the function

    Raises:
        TimeoutError: If execution exceeds timeout
    """
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            raise TimeoutError(f"Tool execution timed out after {timeout_seconds} seconds")


def _strip_bold_formatting(text: str) -> str:
    """
    Strip bold markdown formatting from LLM responses.
    Converts **bold text** to plain text.
    """
    if not text:
        return text
    # Remove bold formatting: **text** → text
    return re.sub(r'\*\*([^*]+)\*\*', r'\1', text)

logger = logging.getLogger(__name__)

# ============================================================================
# MODULE-LEVEL CACHES (avoid expensive re-initialization)
# Thread-safe with locks to prevent race conditions in multi-threaded scenarios
# ============================================================================
_cached_embedding_model = None
_cached_db_config = None
_cached_graph_provider = None
_cache_lock = threading.Lock()  # FIX: Thread lock for cache operations


def _get_cached_embedding_model():
    """
    Get cached embedding model to avoid expensive re-initialization.
    The embedding model takes 2-5 seconds to load, so we cache it.
    Thread-safe with double-checked locking pattern.
    """
    global _cached_embedding_model
    if _cached_embedding_model is None:
        with _cache_lock:
            # Double-check inside lock to prevent race condition
            if _cached_embedding_model is None:
                logger.info("Initializing embedding model (first use - will be cached)")
                from embedding_generation.model_manager import EmbeddingModel
                _cached_embedding_model = EmbeddingModel()
    return _cached_embedding_model


def _get_cached_graph_provider():
    """
    Get cached GraphContextProvider to avoid re-initialization.
    Neo4j driver connection is expensive to create.
    Thread-safe with double-checked locking pattern.
    """
    global _cached_graph_provider
    if _cached_graph_provider is None:
        with _cache_lock:
            # Double-check inside lock to prevent race condition
            if _cached_graph_provider is None:
                logger.info("Initializing GraphContextProvider (first use - will be cached)")
                from graph_context.provider import GraphContextProvider
                _cached_graph_provider = GraphContextProvider()
    return _cached_graph_provider


def _get_db_connection():
    """
    Get a fresh database connection using cached config.
    Connections are closed after each use to avoid stale connections.
    Config caching is thread-safe.
    """
    import psycopg2
    import os
    from dotenv import load_dotenv

    global _cached_db_config
    if _cached_db_config is None:
        with _cache_lock:
            # Double-check inside lock to prevent race condition
            if _cached_db_config is None:
                load_dotenv()
                _cached_db_config = {
                    'dbname': os.getenv('POSTGRES_DB'),
                    'user': os.getenv('POSTGRES_USER'),
                    'password': os.getenv('POSTGRES_PASSWORD'),
                    'host': os.getenv('POSTGRES_HOST'),
                    'port': os.getenv('POSTGRES_PORT')
                }

    return psycopg2.connect(**_cached_db_config)


def create_react_nodes(
    llm_client: Any,
    hybrid_retrieval_manager: Any,
    conversation_engine: Any = None,
    llm_orchestrator: Any = None
) -> Dict[str, Any]:
    """
    Create ReAct sub-graph nodes with dependency injection.

    Args:
        llm_client: LLM client for generating thoughts and actions
        hybrid_retrieval_manager: For tool execution (search, retrieval)
        conversation_engine: ConversationEngine instance for Phase 6 integration
        llm_orchestrator: LLMOrchestrator for generate_with_prompts method

    Returns:
        Dictionary of ReAct node functions

    Note:
        profile_id is obtained from state dynamically, not hardcoded at creation time.
        This allows different requests to use different executive profiles.

    Phase 6: When conversation_engine is provided and use_conversation_engine=True
             in state, uses ConversationEngine for persona-aware prompt generation.
    """
    
    @traceable(name="react_think_node")
    def react_think(state: RAGState) -> RAGState:
        """
        ReAct Node 1: Generate thought (reasoning step)
        
        Input: state.query, state.react_steps, state.reranked_results
        Output: state.react_steps (append thought)
        
        This node uses LLM to reason about:
        - What information is still needed?
        - What action should be taken next?
        - Is current information sufficient?
        """
        start_time = time.time()
        
        query = state["query"]
        react_steps = safe_get(state, "react_steps", [])
        react_iteration = safe_get(state, "react_iteration", 0)
        reranked_results = safe_get(state, "reranked_results", [])
        
        logger.info(f"ReAct Think - Iteration {react_iteration + 1}")
        
        # Build thought prompt
        thought_prompt = _build_thought_prompt(
            query=query,
            previous_steps=react_steps,
            current_context=reranked_results
        )
        
        # Generate thought using LLM
        from llm_integration.base_client import LLMMessage
        
        messages = [
            LLMMessage(role="system", content=_get_react_system_prompt()),
            LLMMessage(role="user", content=thought_prompt)
        ]
        
        try:
            response = llm_client.generate(messages)
            thought = response.content
            
            logger.debug(f"Generated thought: {thought[:100]}...")
            
            # Create new step
            new_step = {
                "step": len(react_steps) + 1,
                "thought": thought,
                "action": None,
                "observation": None,
                "confidence": 0.0,
                "processing_time_ms": 0.0
            }
            
            # Append to state
            react_steps.append(new_step)
            state["react_steps"] = react_steps
            state["react_iteration"] = react_iteration + 1
            
            logger.info(f"ReAct Think complete: step {new_step['step']}")
            
        except Exception as e:
            logger.error(f"ReAct Think failed: {e}")
            state["error"] = f"ReAct Think failed: {str(e)}"
            state["error_node"] = "react_think"
            state["react_force_finalize"] = True  # Force finalization on error
        
        # Track latency
        if "component_latencies" not in state:
            state["component_latencies"] = {}
        state["component_latencies"][f"react_think_{react_iteration + 1}"] = (time.time() - start_time) * 1000
        
        return state
    
    
    @traceable(name="react_act_node")
    def react_act(state: RAGState) -> RAGState:
        """
        ReAct Node 2: Select and parse action from thought
        
        Input: state.react_steps[-1].thought
        Output: state.react_steps[-1].action
        
        Parses the thought to extract:
        - Action type (search, analyze, compare, finalize)
        - Action parameters (query, entities, etc.)
        """
        start_time = time.time()
        
        react_steps = state["react_steps"]
        current_step = react_steps[-1]
        thought = current_step["thought"]
        
        logger.info(f"ReAct Act - Parsing action from thought")
        
        # Parse action from thought
        action = _parse_action_from_thought(thought)
        
        current_step["action"] = action
        state["react_steps"] = react_steps
        
        logger.info(f"Parsed action: type={action.get('type')}, query={action.get('query', '')[:50]}")
        
        # Track latency
        react_iteration = safe_get(state, "react_iteration", 0)
        state["component_latencies"][f"react_act_{react_iteration}"] = (time.time() - start_time) * 1000
        
        return state
    
    
    @traceable(name="react_observe_node")
    def react_observe(state: RAGState) -> RAGState:
        """
        ReAct Node 3: Execute action and observe results
        
        Input: state.react_steps[-1].action
        Output: state.react_steps[-1].observation, state.react_confidence
        
        Executes the tool/action and captures results:
        - Search: Execute hybrid retrieval
        - Analyze: Analyze documents
        - Compare: Compare entities/items
        - Finalize: Skip (handled by should_continue)
        """
        start_time = time.time()
        
        react_steps = state["react_steps"]
        current_step = react_steps[-1]
        action = current_step["action"]
        
        # Get profile_id from state
        profile_id = safe_get(state, "profile_id", "exec_001_test")
        
        logger.info(f"ReAct Observe - Executing action: {action.get('type')}")
        
        try:
            # Execute tool based on action type
            observation, sources = _execute_tool(
                action=action,
                state=state,
                hybrid_retrieval_manager=hybrid_retrieval_manager,
                profile_id=profile_id
            )
            
            current_step["observation"] = observation
            current_step["sources_used"] = sources
            
            # Calculate confidence based on observation quality
            confidence = _calculate_confidence(
                action=action,
                observation=observation,
                total_steps=len(react_steps)
            )
            
            # Ensure Python float for msgpack serialization
            current_step["confidence"] = float(confidence)
            state["react_confidence"] = float(confidence)

            logger.info(f"Observation captured: {observation[:100]}... (confidence={confidence:.2f})")

        except Exception as e:
            logger.error(f"ReAct Observe failed: {e}")
            current_step["observation"] = f"Error executing action: {str(e)}"
            current_step["confidence"] = 0.0
            state["react_confidence"] = 0.0
            state["error"] = f"ReAct Observe failed: {str(e)}"
            state["react_force_finalize"] = True  # Force finalization on error
        
        # Update step timing
        current_step["processing_time_ms"] = (time.time() - start_time) * 1000
        state["react_steps"] = react_steps
        
        # Track latency
        react_iteration = safe_get(state, "react_iteration", 0)
        state["component_latencies"][f"react_observe_{react_iteration}"] = current_step["processing_time_ms"]
        
        return state
    
    
    @traceable(name="react_finalize_node")
    def react_finalize(state: RAGState) -> RAGState:
        """
        ReAct Node 4: Finalize with comprehensive answer

        Phase 6: Supports ConversationEngine for context-aware prompts.

        Input: state.react_steps (all thoughts, actions, observations)
        Output: state.llm_response, state.citations

        Synthesizes all ReAct steps into a final comprehensive answer.
        """
        # CRITICAL: Skip generation if streaming endpoint will handle it
        if safe_get(state, "skip_generation", False):
            logger.info("⏭️  Skipping ReAct finalize generation (streaming mode)")
            # FIX: Update state fields and return full state (not partial dict)
            state["llm_response"] = ""  # Empty response, will be streamed later
            state["citations"] = []
            state["sources"] = []
            state["llm_tokens"] = {}
            state["llm_cost_usd"] = 0.0
            state["react_confidence"] = safe_get(state, "react_confidence", 0.0)
            return state

        start_time = time.time()

        query = state["query"]
        react_steps = safe_get(state, "react_steps", [])
        profile_id = safe_get(state, "profile_id", "exec_001_test")
        language = safe_get(state, "language", "en")
        use_conv_engine = safe_get(state, "use_conversation_engine", False)
        session_id = safe_get(state, "session_id", None)
        user_id = safe_get(state, "user_id", None)
        reranked_results = safe_get(state, "reranked_results", [])
        graph_context = safe_get(state, "graph_context", {})
        memory_results = safe_get(state, "memory_results", [])

        logger.info(f"ReAct Finalize - Synthesizing answer from {len(react_steps)} steps, use_conversation_engine={use_conv_engine}")
        
        # Build finalization prompt with all observations
        finalization_prompt = _build_finalization_prompt(
            query=query,
            react_steps=react_steps,
            language=language
        )
        
        # Generate final answer
        from llm_integration.base_client import LLMMessage
        
        messages = [
            LLMMessage(role="system", content=_get_finalization_system_prompt(profile_id, language)),
            LLMMessage(role="user", content=finalization_prompt)
        ]

        try:
            # Phase 6: Use ConversationEngine if available and enabled
            if conversation_engine and llm_orchestrator and use_conv_engine:
                logger.info("🧠 Using ConversationEngine for agentic path finalization")
                try:
                    import asyncio
                    from llm_integration.prompt_builder import RetrievalContext

                    # Convert graph_context to list format if needed
                    graph_results = None
                    if graph_context and graph_context.get("has_context"):
                        graph_results = graph_context.get("results", [])

                    # Build observation context from ReAct steps
                    react_observations = []
                    for step in react_steps:
                        if step.get("observation"):
                            react_observations.append({
                                "step": step.get("step", 0),
                                "thought": step.get("thought", ""),
                                "observation": step.get("observation", ""),
                                "sources": step.get("sources_used", [])
                            })

                    # Create RetrievalContext for ConversationEngine
                    retrieval_context = RetrievalContext(
                        vector_results=reranked_results[:10],
                        graph_results=graph_results,
                        memory=memory_results,
                        query=query
                    )
                    # Attach ReAct observations to context
                    retrieval_context.react_observations = react_observations

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
                                    path="agentic",
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
                                path="agentic",
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
                            path="agentic",
                        )
                        final_answer = response.get("answer", "")
                        final_answer = _strip_bold_formatting(final_answer)

                        # Extract citations from all steps
                        all_sources = []
                        for step in react_steps:
                            if step.get("sources_used"):
                                all_sources.extend(step["sources_used"])
                        unique_sources = list(set(all_sources))

                        # Update state
                        state["llm_response"] = final_answer
                        state["sources"] = unique_sources
                        state["citations"] = _extract_citations(final_answer, unique_sources)

                        # Track LLM usage from response metadata
                        metadata = response.get("metadata", {})
                        state["llm_tokens"] = metadata.get("llm_tokens", {})
                        state["llm_cost_usd"] = metadata.get("cost_usd", 0.0)

                        logger.info(f"✅ ReAct Finalize complete (ConversationEngine): {len(final_answer)} chars, {len(unique_sources)} sources")

                        # Track latency
                        state["component_latencies"]["react_finalize"] = (time.time() - start_time) * 1000
                        return state
                    else:
                        logger.warning("ConversationEngine returned empty prompts, falling back to legacy path")

                except Exception as conv_error:
                    logger.warning(f"ConversationEngine failed for agentic path, falling back to legacy: {conv_error}")

            # LEGACY PATH: Use direct LLM client
            # Build finalization prompt with all observations
            finalization_prompt = _build_finalization_prompt(
                query=query,
                react_steps=react_steps,
                language=language
            )

            # Generate final answer
            from llm_integration.base_client import LLMMessage

            messages = [
                LLMMessage(role="system", content=_get_finalization_system_prompt(profile_id, language)),
                LLMMessage(role="user", content=finalization_prompt)
            ]

            # Generate comprehensive response based on ReAct reasoning
            # Target aligned with centralized rules: 60-150 words (agentic path)
            # Using max_tokens=300 to allow for ~150 words with buffer
            response = llm_client.generate(messages, max_tokens=300)
            final_answer = response.content

            # Strip excessive markdown formatting (bold headers, etc.)
            final_answer = _strip_bold_formatting(final_answer)

            # Extract citations from all steps
            all_sources = []
            for step in react_steps:
                if step.get("sources_used"):
                    all_sources.extend(step["sources_used"])
            
            # Deduplicate sources
            unique_sources = list(set(all_sources))
            
            # Update state
            state["llm_response"] = final_answer
            state["sources"] = unique_sources
            state["citations"] = _extract_citations(final_answer, unique_sources)
            
            # Track LLM usage
            if response.usage:
                state["llm_tokens"] = response.usage
                
                # Calculate cost
                from observability.cost_tracker import CostTracker
                cost = CostTracker.track_llm_usage(
                    model=response.model,
                    prompt_tokens=response.usage.get('prompt_tokens', 0),
                    completion_tokens=response.usage.get('completion_tokens', 0),
                    path="agentic",
                    executive_id=state.get("profile_id")
                )
                state["llm_cost_usd"] = cost
            
            logger.info(f"ReAct Finalize complete: {len(final_answer)} chars, {len(unique_sources)} sources")
            
        except Exception as e:
            logger.error(f"ReAct Finalize failed: {e}")
            state["error"] = f"ReAct Finalize failed: {str(e)}"
            state["error_node"] = "react_finalize"
            state["llm_response"] = "I apologize, but I encountered an error generating the final response."
        
        # Track latency
        state["component_latencies"]["react_finalize"] = (time.time() - start_time) * 1000

        # Update conversation_history for multi-turn memory (checkpointer persists this)
        query = safe_get(state, "query", "")
        if state.get("llm_response") and not state.get("error"):
            history = safe_get(state, "conversation_history", [])
            history.append({"role": "user", "content": query})
            history.append({"role": "assistant", "content": state["llm_response"]})
            state["conversation_history"] = history
            logger.debug(f"Updated conversation_history (agentic): {len(history)} messages")

        return state


    # Wrap each node with sanitize_node to ensure state is serializable for msgpack
    return {
        "react_think": sanitize_node(react_think),
        "react_act": sanitize_node(react_act),
        "react_observe": sanitize_node(react_observe),
        "react_finalize": sanitize_node(react_finalize)
    }


def should_continue_react(state: RAGState) -> Literal["continue", "finalize"]:
    """
    Conditional edge: Determine if ReAct should continue or finalize
    
    Continue if:
    - Confidence < threshold (0.7)
    - Iterations < max_steps (5)
    - No forced finalization
    - Last action was not "finalize"
    
    Finalize if:
    - Confidence >= threshold
    - Iterations >= max_steps
    - Forced finalization (error)
    - Last action was "finalize"
    
    Args:
        state: Current RAGState
        
    Returns:
        "continue" or "finalize"
    """
    confidence = safe_get(state, "react_confidence", 0.0)
    react_steps = safe_get(state, "react_steps", [])
    iterations = len(react_steps)
    force_finalize = safe_get(state, "react_force_finalize", False)
    
    # Configuration - Updated for thorough multi-step reasoning
    max_steps = 6  # Allow more steps for complex analysis
    confidence_threshold = 0.85  # Higher threshold to encourage more steps
    min_iterations = 4  # Require at least 4 steps before allowing finalization

    # Check last action
    last_action_type = None
    if react_steps:
        last_step = react_steps[-1]
        if last_step.get("action"):
            last_action_type = last_step["action"].get("type")

    # Decision logic
    should_finalize = (
        confidence >= confidence_threshold or
        iterations >= max_steps or
        force_finalize or
        last_action_type == "finalize"
    )

    # NEW: Minimum iteration enforcement
    # Don't allow finalization on step 1 (need at least 2 iterations for proper reasoning)
    # UNLESS we've hit max_steps or force_finalize (error handling)
    if should_finalize and iterations < min_iterations:
        # Override finalization if we haven't met minimum iterations
        # Exception: Still finalize if max_steps reached or forced
        if iterations >= max_steps or force_finalize:
            decision = "finalize"
            logger.info(
                f"ReAct: Finalizing despite min_iterations due to "
                f"{'max_steps' if iterations >= max_steps else 'force_finalize'}"
            )
        else:
            decision = "continue"
            logger.info(
                f"ReAct: Preventing premature finalization "
                f"(iterations={iterations} < min_iterations={min_iterations})"
            )
    else:
        decision = "finalize" if should_finalize else "continue"

    logger.info(
        f"ReAct continuation decision: {decision} "
        f"(confidence={confidence:.2f}, iterations={iterations}/{max_steps}, "
        f"min_iterations={min_iterations}, last_action={last_action_type}, force={force_finalize})"
    )

    return decision


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_react_system_prompt() -> str:
    """
    Get system prompt for ReAct thinking WITH STRICT FORMAT ENFORCEMENT

    This prompt enforces:
    1. Exact two-line format (Thought + Action)
    2. Multi-step reasoning (minimum 3-4 steps before finalize)
    3. No premature finalization
    4. Use of diverse tools (not just SEARCH)
    """
    return """You are an expert analytical assistant using the ReAct (Reasoning and Acting) pattern.

Your task is to think step-by-step about what information you need to answer the user's query.

═══════════════════════════════════════════════════════════
⚠️ CRITICAL RESTRICTION - READ CAREFULLY ⚠️
═══════════════════════════════════════════════════════════

You can ONLY use the actions listed below. NO OTHER ACTIONS EXIST.
- There is NO web search, NO Google search, NO internet access
- There is NO external API access, NO browsing capability
- You MUST use ONLY these 6 actions from the INTERNAL knowledge base:

═══════════════════════════════════════════════════════════
AVAILABLE ACTIONS (USE THESE ONLY)
═══════════════════════════════════════════════════════════

1. SEARCH: Search the INTERNAL knowledge base (NOT the internet!)
   Format: Action: SEARCH: [specific query terms]
   Example: Action: SEARCH: product launch decisions timeline management

2. ANALYZE: Deeply analyze documents already retrieved
   Format: Action: ANALYZE: [what aspect to analyze]
   Example: Action: ANALYZE: risk factors and mitigation strategies

3. RELATIONSHIP: Find how two entities are connected in the knowledge graph
   Format: Action: RELATIONSHIP: [Entity A] and [Entity B]
   Example: Action: RELATIONSHIP: Tanaka and Project Alpha

4. PRECEDENT: Find similar past decisions for comparison
   Format: Action: PRECEDENT: [scenario description]
   Example: Action: PRECEDENT: 15% discount approval for strategic client

5. PATTERN: Analyze the executive's decision-making patterns
   Format: Action: PATTERN: [domain or behavior to analyze]
   Example: Action: PATTERN: pricing decisions and risk tolerance

6. FINALIZE: Generate final answer (ONLY after 3-4 thorough steps!)
   Format: Action: FINALIZE:
   Use ONLY when you have gathered comprehensive information

═══════════════════════════════════════════════════════════
FORMAT REQUIREMENT
═══════════════════════════════════════════════════════════

For EVERY reasoning step, output EXACTLY these two lines:

Line 1: "Thought: [Your detailed reasoning about what information is needed and why]"
Line 2: "Action: [ACTION_TYPE]: [specific parameters]"

DO NOT add extra text. DO NOT skip lines. DO NOT deviate from this format.

═══════════════════════════════════════════════════════════
MULTI-STEP REASONING EXAMPLE (Using Different Tools)
═══════════════════════════════════════════════════════════

Query: "How would this executive handle a 20% discount request?"

Step 1:
Thought: I need to find similar past decisions about discounts to understand the executive's approach.
Action: PRECEDENT: discount approval for strategic client negotiation

Step 2:
Thought: Now I should understand the executive's overall decision-making pattern around pricing.
Action: PATTERN: pricing decisions and risk tolerance

Step 3:
Thought: Let me search for any policies or guidelines about discount approvals.
Action: SEARCH: discount approval policy guidelines strategic clients

Step 4:
Thought: I should analyze the retrieved information to identify key decision factors.
Action: ANALYZE: key decision factors and conditions for discount approval

Step 5:
Thought: I now have precedents, patterns, policies, and analysis. This is sufficient.
Action: FINALIZE:

═══════════════════════════════════════════════════════════
TOOL SELECTION GUIDE
═══════════════════════════════════════════════════════════

Choose the RIGHT tool for each step:
- "Have we done this before?" → PRECEDENT
- "How does the executive typically decide?" → PATTERN
- "How are X and Y connected?" → RELATIONSHIP
- "What do the documents say about X?" → SEARCH
- "Let me examine the details more closely" → ANALYZE
- "I have enough information now" → FINALIZE (only after 4+ steps!)

═══════════════════════════════════════════════════════════
CRITICAL RULES
═══════════════════════════════════════════════════════════

1. ✅ DO: Use AT LEAST 4 different actions before FINALIZE
2. ✅ DO: Use DIVERSE tools (PRECEDENT, PATTERN, SEARCH, ANALYZE) not just SEARCH
3. ✅ DO: Make each query specific and focused
4. ✅ DO: Build on previous observations to guide next steps

5. ❌ DON'T: Jump to FINALIZE before step 4 (you need more information!)
6. ❌ DON'T: Use only SEARCH - use PRECEDENT and PATTERN for richer analysis
7. ❌ DON'T: Try web search, Google, or internet - they DO NOT EXIST!
8. ❌ DON'T: Repeat the same action multiple times

═══════════════════════════════════════════════════════════
FORBIDDEN ACTIONS (These DO NOT EXIST - Will cause errors!)
═══════════════════════════════════════════════════════════

❌ WEB_SEARCH, GOOGLE, BROWSE, INTERNET, API_CALL - None of these exist!
If you try these, you will get an error. Use SEARCH, PRECEDENT, PATTERN instead.

Remember: Build knowledge using DIVERSE tools before finalizing."""


def _get_finalization_system_prompt(profile_id: str, language: str = "en") -> str:
    """
    Get system prompt for finalization WITH FULL PERSONA.

    This is CRITICAL - must include executive persona to maintain authentic voice.

    REFACTORED (2025-01-15): Now uses centralized rules from rules.py
    - Uses build_system_prompt_from_rules() instead of deprecated ProfileManager.generate_system_prompt()
    - Word limits and anti-AI rules come from the single source of truth
    - Agentic-path-specific additions for ReAct synthesis remain here

    Args:
        profile_id: Executive profile ID
        language: Response language (en/ja)

    Returns:
        Complete system prompt for ReAct finalization
    """
    # Import from centralized rules - SINGLE SOURCE OF TRUTH
    from conversation_engine.prompt.rules import build_system_prompt_from_rules

    try:
        # Build base system prompt using centralized rules
        # This replaces the deprecated ProfileManager.generate_system_prompt()
        system_prompt = build_system_prompt_from_rules(
            profile_id=profile_id,
            path="agentic",
            language=language,
            include_examples=True,
        )

        # Add ReAct-specific synthesis instructions
        # These are unique to the agentic finalization step
        react_synthesis_instructions = """
REACT SYNTHESIS REQUIREMENTS (AGENTIC PATH):

You are synthesizing insights from a multi-step reasoning process.

1. INTEGRATE OBSERVATIONS:
   - Review ALL observations from the ReAct steps above
   - Weave findings from each step into a coherent narrative
   - Don't just list findings - synthesize them into YOUR perspective

2. MAINTAIN YOUR VOICE:
   - You ARE this executive, speaking from your experience
   - Reference YOUR past decisions: "When I faced X in DC_XXX_###..."
   - Use YOUR phrases and emojis naturally
   - Be conversational, not formal or report-like

3. COMPLETE YOUR THOUGHT:
   - Aim for 60-100 words (thorough but focused)
   - Don't truncate mid-analysis
   - End with a clear recommendation or perspective
"""

        # CRITICAL: Anti-formatting rules - MUST be at the END for LLM recency bias
        formatting_rules = """
⚠️ STRUCTURE REQUIREMENT (EXECUTIVES DON'T USE HEADERS):

FORBIDDEN:
- Section headers like "Customer impact" or "Financial projection"
- Report-style structure (1. Topic 2. Topic)
- "In conclusion..." or "To summarize..."

REQUIRED:
- Flowing conversational paragraphs
- Weave topics naturally: "On the customer side..." "From a financial angle..."
- Your authentic voice throughout

CORRECT EXAMPLE:
"Here's how I see this. On the customer side, AI adds intelligence they can't get elsewhere.
When I approved the ¥12M pilot [DC_sample_002], we saw a 12-point NPS lift. That's the kind
of ROI that makes the investment obvious. 🎯"

Write like you're talking to a trusted colleague, not writing a board report.
"""

        # Combine all parts - formatting rules LAST for recency bias
        full_prompt = f"""{system_prompt}

{react_synthesis_instructions}

{formatting_rules}"""

        return full_prompt

    except Exception as e:
        logger.error(f"Failed to build finalization prompt with persona: {e}")
        # Fallback to minimal prompt if profile loading fails
        return f"""You are an expert executive assistant for {profile_id}.
Synthesize the information gathered through multi-step reasoning into a comprehensive answer.
Speak in first person as the executive. Be analytical but maintain their authentic voice."""


def _build_thought_prompt(
    query: str,
    previous_steps: List[Dict],
    current_context: List[Dict]
) -> str:
    """
    Build prompt for thought generation.

    IMPORTANT: This prompt shows the LLM what tools have been used and their results,
    so it can decide what to do next. Observations are now shown in full (up to 1000 chars)
    to give the LLM enough context for good decisions.
    """

    prompt = f"Original Query: {query}\n\n"

    if previous_steps:
        prompt += "═══════════════════════════════════════════════════════════\n"
        prompt += "PREVIOUS STEPS (Tools already used - do NOT repeat these!):\n"
        prompt += "═══════════════════════════════════════════════════════════\n"

        tools_used = []
        for step in previous_steps:
            prompt += f"\n--- Step {step['step']} ---\n"
            prompt += f"Thought: {step['thought']}\n"

            # Show what action was taken (CRITICAL for avoiding repetition)
            if step.get('action'):
                action_type = step['action'].get('type', 'unknown').upper()
                action_query = step['action'].get('query', '')[:100]
                prompt += f"Action Used: {action_type}: {action_query}\n"
                tools_used.append(action_type)

            # Show observation with MORE context (1000 chars instead of 200)
            if step.get('observation'):
                obs = step['observation']
                if len(obs) > 1000:
                    prompt += f"Result: {obs[:1000]}...[truncated]\n"
                else:
                    prompt += f"Result: {obs}\n"

        prompt += "\n"
        prompt += f"Tools already used: {', '.join(tools_used)}\n"
        prompt += "Do NOT repeat these tools with the same query.\n\n"

    if current_context:
        prompt += "═══════════════════════════════════════════════════════════\n"
        prompt += f"INITIAL CONTEXT ({len(current_context)} documents retrieved):\n"
        prompt += "═══════════════════════════════════════════════════════════\n"
        # Show brief summary of initial context so LLM knows what's available
        for i, doc in enumerate(current_context[:3], 1):
            source = doc.get("source", doc.get("title", f"Document_{i}"))
            content_preview = doc.get("content", "")[:150]
            prompt += f"{i}. [{source}]: {content_preview}...\n"
        if len(current_context) > 3:
            prompt += f"... and {len(current_context) - 3} more documents\n"
        prompt += "\nUse ANALYZE to examine these documents in detail, or use other tools.\n\n"

    prompt += "═══════════════════════════════════════════════════════════\n"
    prompt += "DECIDE YOUR NEXT STEP:\n"
    prompt += "═══════════════════════════════════════════════════════════\n"
    prompt += "Based on what you've learned, what should be the next step?\n"
    if previous_steps:
        prompt += "Use a DIFFERENT tool than the ones already used above.\n"
    else:
        prompt += "Choose from: PRECEDENT, PATTERN, SEARCH, ANALYZE, RELATIONSHIP\n"
    prompt += "Remember: You need at least 4 steps before FINALIZE.\n"

    return prompt


def _build_finalization_prompt(
    query: str,
    react_steps: List[Dict],
    language: str
) -> str:
    """
    Build prompt for final answer generation.

    Includes the full context from all ReAct steps:
    - Which tool was used (SEARCH, PRECEDENT, PATTERN, etc.)
    - What the observation/finding was
    - Sources used

    This gives the LLM full context to synthesize a comprehensive answer.
    """

    prompt = f"Original Query: {query}\n\n"
    prompt += "═══════════════════════════════════════════════════════════\n"
    prompt += "INFORMATION GATHERED THROUGH MULTI-STEP ANALYSIS:\n"
    prompt += "═══════════════════════════════════════════════════════════\n\n"

    all_sources = []
    for step in react_steps:
        prompt += f"--- Step {step['step']} ---\n"

        # Show what tool was used (important for context)
        if step.get('action'):
            action_type = step['action'].get('type', 'unknown').upper()
            action_query = step['action'].get('query', '')[:100]
            prompt += f"Tool Used: {action_type}\n"
            prompt += f"Query: {action_query}\n"

        # Show the observation/finding
        observation = step.get('observation', 'N/A')
        prompt += f"Finding:\n{observation}\n"

        # Collect sources
        if step.get('sources_used'):
            all_sources.extend(step['sources_used'])
            prompt += f"Sources: {', '.join(step['sources_used'][:3])}\n"

        prompt += "\n"

    # Summary of all sources
    unique_sources = list(set(all_sources))
    if unique_sources:
        prompt += f"═══════════════════════════════════════════════════════════\n"
        prompt += f"All Sources Used: {', '.join(unique_sources[:10])}\n"
        prompt += f"═══════════════════════════════════════════════════════════\n\n"

    # Final instructions
    prompt += f"Based on the above analysis, provide a comprehensive answer to the original query.\n"
    prompt += f"Language: {language.upper()}\n"
    prompt += f"- Synthesize insights from ALL tools used (PRECEDENT, PATTERN, SEARCH, etc.)\n"
    prompt += f"- Include specific details and cite sources where appropriate\n"
    prompt += f"- Write in a natural, conversational tone as the executive\n"

    return prompt


def _parse_action_from_thought(thought: str) -> Dict[str, Any]:
    """
    Parse action from thought with natural language intent detection

    Tries (in order):
    1. Explicit format: "Action: SEARCH: query"
    2. Natural language intent: "I need to search for..."
    3. Only then: finalize

    Expected format:
        Thought: ...
        Action: SEARCH: vacation policy

    Returns:
        {"type": "search", "query": "vacation policy"}
    """
    # Try to extract explicit Action line first
    # Handle FINALIZE separately since it has no query after the colon
    finalize_match = re.search(r'Action:\s*FINALIZE\s*:?\s*$', thought, re.IGNORECASE | re.MULTILINE)
    if finalize_match:
        return {"type": "finalize", "query": ""}

    # Match other actions with query content
    action_match = re.search(r'Action:\s*(\w+):\s*(.+)', thought, re.IGNORECASE)

    if action_match:
        action_type = action_match.group(1).lower()
        action_query = action_match.group(2).strip()

        return {
            "type": action_type,
            "query": action_query
        }

    # NEW: Try to detect intent from natural language
    thought_lower = thought.lower()

    # Search intent patterns
    search_patterns = [
        "need to find", "need to search", "need to locate",
        "should search", "let me search", "i should find",
        "need to retrieve", "should look for", "need to look",
        "want to find", "looking for", "search for"
    ]

    if any(phrase in thought_lower for phrase in search_patterns):
        # Try to extract potential search query
        for pattern in [
            r"(?:need to|should|want to|let me) (?:find|search for|locate|look for) (.+?)(?:\.|$|to |in order)",
            r"(?:i should|looking for) (.+?)(?:\.|$|to |in order)",
            r"information about (.+?)(?:\.|$|to |in order)"
        ]:
            match = re.search(pattern, thought_lower)
            if match:
                query = match.group(1).strip()
                # Clean up the query
                query = query.replace("yuki's", "yuki").replace("the ", "")
                logger.info(f"Detected SEARCH intent from natural language: {query}")
                return {
                    "type": "search",
                    "query": query
                }

        # Generic fallback - use first 100 chars of thought as query
        logger.info("Detected search intent but couldn't extract query, using thought")
        return {
            "type": "search",
            "query": thought[:100]
        }

    # Analyze intent patterns
    if any(phrase in thought_lower for phrase in [
        "need to analyze", "should analyze", "let me analyze",
        "need to examine", "should examine", "analyze the"
    ]):
        logger.info("Detected ANALYZE intent from natural language")
        return {
            "type": "analyze",
            "query": thought[:100]
        }

    # Relationship/Compare intent patterns
    if any(phrase in thought_lower for phrase in [
        "need to compare", "should compare", "compare the",
        "comparison", "comparing", "how are", "how is",
        "relationship between", "connected to", "related to",
        "connection between", "link between", "ties to"
    ]):
        logger.info("Detected RELATIONSHIP intent from natural language")
        return {
            "type": "relationship",
            "query": thought[:150]  # Longer to capture both entity names
        }

    # Temporal intent patterns - REDIRECT TO SEARCH (TEMPORAL is disabled)
    if any(phrase in thought_lower for phrase in [
        "last week", "last month", "last quarter", "this year",
        "yesterday", "last few days", "recently discussed",
        "previous conversations", "earlier this", "in q1", "in q2", "in q3", "in q4",
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
        "what did we discuss", "historical", "time range"
    ]):
        # TEMPORAL is temporarily disabled, redirect to SEARCH
        logger.info("Detected TEMPORAL intent but redirecting to SEARCH (TEMPORAL disabled)")
        return {
            "type": "search",
            "query": thought[:150]  # Include time context in search
        }

    # Precedent intent patterns
    if any(phrase in thought_lower for phrase in [
        "precedent", "similar decision", "past decision", "done this before",
        "approved before", "similar situation", "like this before",
        "have we", "did we", "similar case", "past experience",
        "historical decision", "previous decision", "track record"
    ]):
        logger.info("Detected PRECEDENT intent from natural language")
        return {
            "type": "precedent",
            "query": thought[:200]  # Include full scenario context
        }

    # Pattern/style intent patterns
    if any(phrase in thought_lower for phrase in [
        "decision pattern", "decision style", "decision-making style",
        "how do they decide", "how does he decide", "how does she decide",
        "approach to", "typical approach", "usually decide",
        "risk tolerance", "risk appetite", "decision behavior",
        "leadership style", "management style", "their style",
        "pattern of", "tendency to", "typically handle"
    ]):
        logger.info("Detected PATTERN intent from natural language")
        return {
            "type": "pattern",
            "query": thought[:150]  # Include domain context
        }

    # Finalize intent patterns (explicit only)
    if any(phrase in thought_lower for phrase in [
        "have enough", "sufficient information", "ready to answer",
        "can now answer", "have everything", "ready to finalize",
        "enough context", "gathered all"
    ]):
        logger.info("Detected explicit FINALIZE intent from natural language")
        return {
            "type": "finalize",
            "query": ""
        }

    # IMPROVED FALLBACK: Only finalize if thought is very short or clearly final
    if len(thought) < 50:
        logger.warning(f"Thought too short ({len(thought)} chars), assuming finalize")
        return {"type": "finalize", "query": ""}

    # Otherwise, default to SEARCH (not finalize!)
    # If we can't determine intent, it's safer to search than to finalize prematurely
    logger.warning(f"Could not parse action format or detect clear intent, defaulting to SEARCH")
    return {
        "type": "search",
        "query": thought[:100]  # Use first 100 chars as search query
    }


def _execute_tool(
    action: Dict[str, Any],
    state: RAGState,
    hybrid_retrieval_manager: Any,
    profile_id: str
) -> tuple:
    """
    Execute tool based on action type
    
    Returns:
        (observation_text, sources_list)
    """
    action_type = action.get("type", "finalize")
    action_query = action.get("query", "")
    
    if action_type == "search":
        # Execute hybrid retrieval with timeout protection
        logger.info(f"Executing SEARCH: {action_query}")

        try:
            # FIX: Wrap retrieval in timeout to prevent hanging
            def _do_search():
                return hybrid_retrieval_manager.retrieve(
                    query=action_query,
                    executive_id=profile_id,
                    user_context={
                        "company_id": state.get("company_id"),
                    },
                    top_k=5,
                    strategy="auto"
                )

            results = _execute_with_timeout(_do_search, timeout_seconds=TOOL_EXECUTION_TIMEOUT)

            # Format observation - INCREASED from 200 to 500 chars per doc for better context
            docs = results.get("results", [])
            if docs:
                observation = f"Found {len(docs)} relevant documents:\n"
                for i, doc in enumerate(docs[:5], 1):  # Show all 5 docs, not just 3
                    source = doc.get("source", doc.get("title", f"Document_{i}"))
                    content = doc.get("content", "")[:500]  # Increased from 200 to 500
                    observation += f"\n{i}. [{source}]\n{content}...\n"

                sources = [doc.get("source", f"doc_{i}") for i, doc in enumerate(docs)]
            else:
                observation = "No relevant documents found. Try a different search query or use PRECEDENT/PATTERN for decision-related information."
                sources = []

            return observation, sources

        except TimeoutError as e:
            logger.error(f"Search timed out: {e}")
            return f"Search timed out. Try a simpler query or use ANALYZE on existing results.", []
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return f"Search failed: {str(e)}. Try a different query.", []
    
    elif action_type == "analyze":
        # Analyze current context
        # FIXED: Increased from 150 to 1500 chars per doc, 3 to 5 docs
        logger.info(f"Executing ANALYZE: {action_query}")

        reranked_results = safe_get(state, "reranked_results", [])
        if reranked_results:
            observation = f"Analyzed {len(reranked_results)} documents. Key findings:\n"
            for i, doc in enumerate(reranked_results[:5], 1):
                source = doc.get("source", doc.get("title", f"Document_{i}"))
                content = doc.get("content", "")[:1500]
                score = doc.get("score", 0.0)
                observation += f"\n[{source}] (relevance: {score:.2f})\n{content}\n"

            sources = [doc.get("source", f"doc_{i}") for i, doc in enumerate(reranked_results)]
        else:
            observation = "No documents available to analyze."
            sources = []

        return observation, sources
    
    elif action_type in ["compare", "relationship"]:
        # Entity relationship analysis using Neo4j graph
        logger.info(f"Executing RELATIONSHIP: {action_query}")

        try:
            # Parse entities from query
            entities = _parse_entities_from_query(action_query)

            if len(entities) >= 2:
                # Import and use the relationship analyzer
                from .react_tools import analyze_entity_relationship, EntityRelationshipInput
                from .react_tools.relationship_analyzer import format_for_observation

                # Get Neo4j driver (use cached provider for performance)
                graph_provider = _get_cached_graph_provider()

                # Create input params
                params = EntityRelationshipInput(
                    entity_a=entities[0],
                    entity_b=entities[1],
                    include_indirect=True,
                    max_paths=5
                )

                # Execute relationship analysis
                result = analyze_entity_relationship(
                    params=params,
                    graph_driver=graph_provider.driver
                )

                # Format observation
                observation = format_for_observation(result)

                # Extract source references
                sources = []
                for rel in result.direct_relationships:
                    sources.append(f"Graph: {rel.get('from', 'unknown')} -> {rel.get('to', 'unknown')}")

                logger.info(f"Relationship analysis complete: {len(result.direct_relationships)} direct, {len(result.indirect_relationships)} indirect")

            else:
                # Fallback: not enough entities detected
                observation = f"Could not identify two entities to compare in query: '{action_query}'. Please rephrase as 'How are X and Y related?'"
                sources = []
                logger.warning(f"Entity parsing failed: found {len(entities)} entities in '{action_query}'")

        except ImportError as e:
            logger.error(f"Relationship tool import failed: {e}")
            observation = f"Relationship analysis tool not available. Falling back to context search."
            sources = []
        except Exception as e:
            logger.error(f"Relationship analysis failed: {e}")
            observation = f"Relationship analysis error: {str(e)}. Try using SEARCH instead."
            sources = []

        return observation, sources

    elif action_type == "temporal":
        # TEMPORARILY DISABLED: episodic_memory table is empty
        # TODO: Re-enable when episodic_memory is populated with conversation data
        logger.warning(f"TEMPORAL action requested but temporarily disabled (no data)")
        observation = (
            "TEMPORAL search is temporarily unavailable (episodic memory not populated). "
            "Please use SEARCH to find information in the knowledge base, "
            "or PRECEDENT to find similar past decisions."
        )
        return observation, []

    elif action_type == "precedent":
        # Precedent finder - search for similar past decisions
        logger.info(f"Executing PRECEDENT: {action_query}")

        db_conn = None  # FIX: Initialize for try/finally pattern
        try:
            from .react_tools import find_precedents, PrecedentFinderInput, extract_decision_type_from_query
            from .react_tools.precedent_finder import format_for_observation

            # Extract decision type if present in query
            decision_type = extract_decision_type_from_query(action_query)

            # Use cached database connection and embedding model (PERFORMANCE FIX)
            db_conn = _get_db_connection()
            embedding_model = _get_cached_embedding_model()

            # Create input params
            params = PrecedentFinderInput(
                scenario=action_query,
                decision_type=decision_type,
                similarity_threshold=0.60,  # Lower threshold for broader results
                include_outcomes=True,
                top_k=5
            )

            # Execute precedent search
            result = find_precedents(params, db_conn, embedding_model, company_id=state.get("company_id"))

            # Format observation
            observation = format_for_observation(result)

            # Extract source references
            sources = [f"Precedent:{p.get('case_id', 'unknown')}" for p in result.precedents[:5]]

            logger.info(f"Precedent search complete: {result.count} results")

        except ImportError as e:
            logger.error(f"Precedent finder import failed: {e}")
            observation = f"Precedent finder tool not available: {str(e)}"
            sources = []
        except Exception as e:
            logger.error(f"Precedent search failed: {e}")
            observation = f"Precedent search error: {str(e)}. Try using SEARCH instead."
            sources = []
        finally:
            # FIX: Always close database connection to prevent leaks
            if db_conn:
                try:
                    db_conn.close()
                except Exception:
                    pass  # Ignore close errors

        return observation, sources

    elif action_type == "pattern":
        # Decision pattern analyzer - analyze executive decision-making patterns
        logger.info(f"Executing PATTERN: {action_query}")

        db_conn = None  # FIX: Initialize for try/finally pattern
        try:
            from .react_tools import analyze_decision_pattern, DecisionPatternInput, extract_domain_from_query
            from .react_tools.decision_pattern import format_for_observation

            # Extract domain from query if present
            decision_domain = extract_domain_from_query(action_query)

            # Use cached database connection (PERFORMANCE FIX)
            db_conn = _get_db_connection()

            # Create input params - use profile_id from state
            params = DecisionPatternInput(
                executive_id=profile_id,
                decision_domain=decision_domain,
                include_examples=True
            )

            # Execute pattern analysis
            result = analyze_decision_pattern(params, db_conn, company_id=state.get("company_id"))

            # Format observation
            observation = format_for_observation(result)

            # Extract source references
            sources = [f"Pattern:{profile_id}"]
            if result.examples:
                sources.extend([f"Decision:{ex.get('id', 'unknown')}" for ex in result.examples])

            logger.info(f"Pattern analysis complete: {result.total_decisions_analyzed} decisions analyzed")

        except ImportError as e:
            logger.error(f"Decision pattern analyzer import failed: {e}")
            observation = f"Decision pattern analyzer tool not available: {str(e)}"
            sources = []
        except Exception as e:
            logger.error(f"Decision pattern analysis failed: {e}")
            observation = f"Decision pattern analysis error: {str(e)}. Try using SEARCH instead."
            sources = []
        finally:
            # FIX: Always close database connection to prevent leaks
            if db_conn:
                try:
                    db_conn.close()
                except Exception:
                    pass  # Ignore close errors

        return observation, sources

    elif action_type in ["finalize", "ready", ""]:
        # Finalize action - but check if we have enough steps
        # Get current step count from state to provide appropriate feedback
        react_steps = safe_get(state, "react_steps", [])
        current_iteration = len(react_steps)
        min_iterations = 4  # Must match the value in should_continue_react

        if current_iteration < min_iterations:
            # Too early to finalize - provide clear feedback to continue
            logger.warning(f"FINALIZE attempted at step {current_iteration}, but need {min_iterations} steps")
            observation = (
                f"⚠️ Cannot finalize yet - you've only completed {current_iteration} step(s), "
                f"but need at least {min_iterations} steps for thorough analysis.\n\n"
                f"Please continue gathering information using DIFFERENT tools:\n"
                f"- PRECEDENT: Find similar past decisions\n"
                f"- PATTERN: Analyze decision-making patterns\n"
                f"- SEARCH: Find more information in knowledge base\n"
                f"- ANALYZE: Examine retrieved documents in detail\n\n"
                f"DO NOT use FINALIZE again until you have {min_iterations}+ steps."
            )
            return observation, []
        else:
            # Enough steps - ready to finalize
            logger.info(f"Action type '{action_type}' - ready to finalize (step {current_iteration})")
            return "Ready to finalize answer. Sufficient information gathered.", []

    else:
        # Unknown action type - provide clear error feedback
        logger.warning(f"Unknown action type '{action_type}' - this tool does not exist!")
        available_tools = "SEARCH, ANALYZE, RELATIONSHIP, PRECEDENT, PATTERN, FINALIZE"
        observation = (
            f"ERROR: Action '{action_type}' does not exist. "
            f"Available actions are: {available_tools}. "
            f"Please use one of these actions instead. "
            f"Remember: There is NO web search, NO Google, NO internet access."
        )
        return observation, []


def _calculate_confidence(
    action: Dict[str, Any],
    observation: str,
    total_steps: int
) -> float:
    """
    Calculate confidence score based on CONTENT QUALITY and STEP PROGRESSION.

    Updated to encourage thorough multi-step reasoning:
    - Lower individual factor scores
    - Higher weight on step progression
    - Cap at 0.70 to require min_iterations=4 before finalization

    Returns:
        Confidence score (0.0 to 1.0)
    """
    action_type = action.get("type", "")

    # Finalize action always returns 1.0
    if action_type == "finalize":
        return 1.0

    # Start with base score
    confidence = 0.0

    # =========================================================================
    # Factor 1: Result Count (0.0 - 0.15) - Supports SEARCH, PRECEDENT, PATTERN
    # =========================================================================
    result_count = 0

    # Pattern for SEARCH: "Found N relevant documents"
    doc_count_match = re.search(r'Found (\d+) relevant documents', observation)
    if doc_count_match:
        result_count = int(doc_count_match.group(1))

    # Pattern for PRECEDENT: "Found N similar precedent(s)"
    precedent_count_match = re.search(r'Found (\d+) similar precedent', observation)
    if precedent_count_match:
        result_count = max(result_count, int(precedent_count_match.group(1)))

    # Pattern for PATTERN: "Based on N historical decision(s)"
    pattern_count_match = re.search(r'Based on (\d+) historical decision', observation)
    if pattern_count_match:
        result_count = max(result_count, int(pattern_count_match.group(1)))

    # Pattern for RELATIONSHIP: direct/indirect connections
    relationship_match = re.search(r'(\d+) direct.*?(\d+) indirect', observation)
    if relationship_match:
        direct = int(relationship_match.group(1))
        indirect = int(relationship_match.group(2))
        result_count = max(result_count, direct + indirect)

    if result_count >= 5:
        confidence += 0.15
    elif result_count >= 3:
        confidence += 0.12
    elif result_count >= 1:
        confidence += 0.08
    elif "No relevant documents" in observation or "No similar precedents" in observation or "No historical decisions" in observation:
        confidence += 0.0  # No results found
    else:
        confidence += 0.05  # Unknown format or ANALYZE tool

    # =========================================================================
    # Factor 2: Specific Data Presence (0.0 - 0.15) - Reduced from 0.25
    # =========================================================================
    specific_data_score = 0.0

    # Check for numbers/metrics (¥, %, dates, quantities)
    number_patterns = [
        r'¥[\d,]+',           # Yen amounts
        r'\d+%',              # Percentages
        r'\d{4}[-/]\d{1,2}',  # Dates
        r'DC_\w+_\d+',        # Decision IDs
        r'\d+\s*(?:months?|weeks?|days?|years?)',  # Time durations
        r'Q[1-4]\s*\d{4}',    # Quarterly references
    ]

    matches_found = 0
    for pattern in number_patterns:
        if re.search(pattern, observation):
            matches_found += 1

    if matches_found >= 4:
        specific_data_score = 0.15
    elif matches_found >= 2:
        specific_data_score = 0.10
    elif matches_found >= 1:
        specific_data_score = 0.07
    else:
        specific_data_score = 0.03

    confidence += specific_data_score

    # =========================================================================
    # Factor 3: Content Diversity (0.0 - 0.10) - Reduced from 0.20
    # =========================================================================
    diversity_score = 0.0

    # Check for different types of content
    content_indicators = [
        ('decision', r'(?:decision|decided|chose|selected)'),
        ('reasoning', r'(?:because|reason|rationale|why)'),
        ('outcome', r'(?:result|outcome|impact|effect)'),
        ('context', r'(?:context|situation|scenario|case)'),
        ('precedent', r'(?:precedent|previous|past|history)'),
    ]

    types_found = 0
    for name, pattern in content_indicators:
        if re.search(pattern, observation, re.IGNORECASE):
            types_found += 1

    if types_found >= 4:
        diversity_score = 0.10
    elif types_found >= 2:
        diversity_score = 0.07
    elif types_found >= 1:
        diversity_score = 0.05
    else:
        diversity_score = 0.02

    confidence += diversity_score

    # =========================================================================
    # Factor 4: Step Progression (0.0 - 0.30) - Increased from 0.20
    # This is now the most important factor to encourage multi-step reasoning
    # =========================================================================
    if total_steps >= 5:
        step_score = 0.30
    elif total_steps >= 4:
        step_score = 0.22
    elif total_steps >= 3:
        step_score = 0.15
    elif total_steps >= 2:
        step_score = 0.08
    else:
        step_score = 0.03  # First step gets minimal boost

    confidence += step_score

    # =========================================================================
    # Factor 5: Error Detection (Penalty)
    # =========================================================================
    error_patterns = [
        r'(?:error|failed|exception)',
        r'No (?:relevant |)documents found',
        r'Search failed',
        r'does not exist',
    ]

    for pattern in error_patterns:
        if re.search(pattern, observation, re.IGNORECASE):
            confidence -= 0.10
            break

    # =========================================================================
    # Cap confidence at 0.70 to ensure min_iterations=4 is respected
    # Only finalize action can reach 1.0
    # With max 0.70, LLM must do 4+ steps to reach confidence_threshold=0.85
    # =========================================================================
    confidence = max(0.0, min(0.70, confidence))

    logger.debug(
        f"Confidence calculated: {confidence:.2f} "
        f"(docs={doc_count_match.group(1) if doc_count_match else 'N/A'}, "
        f"specific_data={specific_data_score:.2f}, diversity={diversity_score:.2f}, "
        f"steps={total_steps}, step_score={step_score:.2f})"
    )

    return confidence


def _extract_citations(text: str, sources: List[str]) -> List[Dict]:
    """
    Extract citations from text
    
    Returns:
        List of citation dictionaries
    """
    citations = []
    
    for i, source in enumerate(sources, 1):
        citations.append({
            "number": i,
            "source": source,
            "type": "document"
        })
    
    return citations


def _extract_search_keywords(query: str) -> str:
    """
    Extract search keywords from a temporal query by removing time indicators.

    Examples:
    - "what did we discuss last week about discounts" -> "discounts"
    - "conversations about remote work in November" -> "remote work"
    - "Q3 decisions on pricing" -> "decisions pricing"
    """
    # Words to remove (time-related)
    time_words = [
        'last', 'week', 'month', 'quarter', 'year', 'yesterday', 'today',
        'january', 'february', 'march', 'april', 'may', 'june', 'july',
        'august', 'september', 'october', 'november', 'december',
        'jan', 'feb', 'mar', 'apr', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec',
        'q1', 'q2', 'q3', 'q4', 'days', 'this',
    ]

    # Common filler words
    filler_words = [
        'what', 'did', 'we', 'discuss', 'about', 'in', 'from', 'during',
        'conversations', 'discussion', 'discussed', 'talked', 'the', 'a', 'an',
        'regarding', 'concerning', 'related', 'to',
    ]

    words = query.lower().split()
    keywords = [w for w in words if w not in time_words and w not in filler_words]

    result = ' '.join(keywords).strip()

    # If nothing left, use original query
    if not result:
        return query

    return result


def _parse_entities_from_query(query: str) -> List[str]:
    """
    Parse entity names from a relationship query.

    Handles patterns like:
    - "How are X and Y related?"
    - "relationship between X and Y"
    - "X and Y connection"
    - "compare X with Y"
    - Just "X Y" (fallback: split on common delimiters)

    Returns:
        List of entity names (typically 2)
    """
    entities = []
    query_lower = query.lower()

    # Pattern 1: "between X and Y"
    match = re.search(r'between\s+(.+?)\s+and\s+(.+?)(?:\s*\?|$|\.)', query, re.IGNORECASE)
    if match:
        entities = [match.group(1).strip(), match.group(2).strip()]
        logger.debug(f"Entity pattern 'between X and Y': {entities}")
        return entities

    # Pattern 2: "How are X and Y related"
    match = re.search(r'how\s+(?:are|is)\s+(.+?)\s+and\s+(.+?)\s+(?:related|connected)', query, re.IGNORECASE)
    if match:
        entities = [match.group(1).strip(), match.group(2).strip()]
        logger.debug(f"Entity pattern 'How are X and Y': {entities}")
        return entities

    # Pattern 3: "X and Y" (simple) - FIX: Allow numbers, hyphens, slashes in entity names
    # Handles: "Project 2025 and Alpha Corp", "AC/DC and Beta-Test"
    match = re.search(r'([A-Z][a-zA-Z0-9\s/\-]+)\s+and\s+([A-Z][a-zA-Z0-9\s/\-]+)', query)
    if match:
        entities = [match.group(1).strip(), match.group(2).strip()]
        logger.debug(f"Entity pattern 'X and Y': {entities}")
        return entities

    # Pattern 4: "compare X with Y"
    match = re.search(r'compare\s+(.+?)\s+(?:with|to|and)\s+(.+?)(?:\s*\?|$|\.)', query, re.IGNORECASE)
    if match:
        entities = [match.group(1).strip(), match.group(2).strip()]
        logger.debug(f"Entity pattern 'compare X with Y': {entities}")
        return entities

    # Pattern 5: "X vs Y" or "X versus Y"
    match = re.search(r'(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:\s*\?|$|\.)', query, re.IGNORECASE)
    if match:
        entities = [match.group(1).strip(), match.group(2).strip()]
        logger.debug(f"Entity pattern 'X vs Y': {entities}")
        return entities

    # Fallback: Try to find capitalized words/phrases (proper nouns)
    # FIX: Allow numbers, hyphens, slashes in entity names
    # Handles: "Project 2025", "Alpha-Beta", "AC/DC Corp"
    capitalized_matches = re.findall(r'[A-Z][a-zA-Z0-9/\-]*(?:\s+[A-Z]?[a-zA-Z0-9/\-]+)*', query)
    if len(capitalized_matches) >= 2:
        # Take the two longest matches as likely entity names
        sorted_matches = sorted(capitalized_matches, key=len, reverse=True)
        entities = sorted_matches[:2]
        logger.debug(f"Entity pattern 'capitalized words': {entities}")
        return entities

    # Last resort: split on common delimiters
    for delimiter in [' and ', ' with ', ' to ', ', ']:
        if delimiter in query_lower:
            parts = query.split(delimiter if delimiter != query_lower else delimiter.upper())
            if len(parts) >= 2:
                entities = [parts[0].strip()[:50], parts[1].strip()[:50]]  # Limit length
                logger.debug(f"Entity pattern 'delimiter split': {entities}")
                return entities

    logger.warning(f"Could not parse entities from query: {query}")
    return entities


# Import required at module level
import re
