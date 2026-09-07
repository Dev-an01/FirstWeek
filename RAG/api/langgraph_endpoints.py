"""
LangGraph Workflow Endpoints
FastAPI integration endpoints for LangGraph workflow

Provides:
1. Visualization endpoint for workflow DAG
2. LangGraph-powered chat endpoint (alternative to orchestrator)
3. Workflow state inspection endpoint
"""

import logging
import time
import os
from typing import Dict, Any, Optional, AsyncGenerator
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
import json
import asyncio

from api.models import ChatRequest, ChatResponse, Citation, ChatMetadata
from api.dependencies import retrieval_system, resolve_company_id
from langgraph_workflow import create_rag_workflow, visualize_workflow, get_default_state
from api.config import should_use_conversation_engine
from conversation_engine.prompt.sections import InstructionsSection
from conversation_engine.prompt.rules import get_word_limit

logger = logging.getLogger(__name__)

# Router for LangGraph endpoints
router = APIRouter(prefix="/api/v1/langgraph", tags=["LangGraph"])


@router.post("/chat", response_model=ChatResponse)
async def langgraph_chat(
    request: Request,
    chat_request: ChatRequest
):
    """
    LangGraph-powered chat endpoint (Week 2, Day 5)
    
    Alternative to /api/v1/chat that uses LangGraph StateGraph instead of
    the legacy orchestrator. Provides identical functionality with explicit
    DAG execution and complete LangSmith tracing.
    
    **Flow:**
    1. Initialize RAGState with query and user context
    2. Execute LangGraph workflow
    3. Extract response from final state
    4. Format and return response
    
    **Benefits over legacy orchestrator:**
    - Visual DAG representation
    - Explicit state tracking
    - Complete node-level tracing
    - Easier debugging and testing
    - Checkpointing support (future)
    
    **Usage:**
    Same as /api/v1/chat but routes through LangGraph
    """
    request_id = request.state.request_id
    start_time = time.time()

    # ============================================================
    # UTF-8 ENCODING DEBUG (Windows Japanese Fix)
    # ============================================================
    # Log query encoding details to help diagnose Japanese character issues
    query_text = chat_request.query

    # Check for encoding issues (question marks replacing Japanese chars)
    has_cjk = any('\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u30ff' for c in query_text)
    has_suspicious_qmarks = query_text.count('?') > 3 and not query_text.endswith('?')

    if has_suspicious_qmarks and not has_cjk:
        logger.warning(
            f"[{request_id}] [UTF8-DEBUG] Possible encoding corruption detected! "
            f"Query has {query_text.count('?')} question marks but no CJK characters. "
            f"Raw bytes: {query_text.encode('utf-8', errors='replace')[:100]}"
        )
    elif has_cjk:
        logger.info(f"[{request_id}] [UTF8-DEBUG] Japanese/CJK text detected - encoding OK")

    logger.info(f"[{request_id}] LangGraph chat query: '{query_text[:50]}...'")
    
    try:
        # Get workflow from app state (initialized at startup)
        if not hasattr(request.app.state, 'langgraph_workflow'):
            raise HTTPException(
                status_code=503,
                detail="LangGraph workflow not initialized. Check startup logs."
            )
        
        workflow = request.app.state.langgraph_workflow
        
        # Create initial state (use database ID format like sample_profile)
        use_conv_engine = should_use_conversation_engine(request_id)

        initial_state = get_default_state(
            query=chat_request.query,
            user_id=chat_request.user_id,
            user_role=chat_request.user_role,
            profile_id=chat_request.profile_id or "sample_profile",
            session_id=chat_request.session_id,
            company_id=resolve_company_id(chat_request.company_id, chat_request.user_role),
            top_k=chat_request.top_k or 20,
            min_score=chat_request.min_score or 0.15,
            language=chat_request.language or "en",
            enable_evaluation=getattr(chat_request, 'enable_evaluation', False),
            use_conversation_engine=use_conv_engine
        )

        # Override force_path if specified
        if chat_request.force_path:
            initial_state["force_path"] = chat_request.force_path
        
        # Get or create session_id for threading
        session_id = chat_request.session_id
        if not session_id and hasattr(request.app.state, 'session_manager'):
            from profile_management.profile_id_mapper import normalize_profile_id
            normalized_profile_id = normalize_profile_id(chat_request.profile_id or "sample_profile")
            session_id = await request.app.state.session_manager.get_or_create_session(
                user_id=chat_request.user_id,
                executive_id=normalized_profile_id
            )

        # Build config with thread_id for LangGraph threading and state checkpointing
        thread_id = session_id or request_id
        config = {
            "configurable": {
                "thread_id": thread_id,
                "user_id": chat_request.user_id,
                "profile_id": chat_request.profile_id
            },
            # FIX: Increase recursion limit for agentic path
            # Agentic path: 3 nodes per iteration (think, act, observe) * 6 max_steps = 18
            # Add buffer for cognitive nodes and routing = 50 total
            "recursion_limit": 50
        }

        # Preserve conversation_history from checkpointer for multi-turn continuity
        # The checkpointer stores previous state including conversation_history
        # =====================================================================
        # FIX: Handle both sync (MemorySaver) and async (AsyncPostgresSaver) checkpointers
        # AsyncPostgresSaver requires awaiting aget_tuple(), MemorySaver uses sync get_tuple()
        # =====================================================================
        if hasattr(request.app.state, 'langgraph_checkpointer') and request.app.state.langgraph_checkpointer:
            checkpointer = request.app.state.langgraph_checkpointer
            try:
                checkpoint_config = {"configurable": {"thread_id": thread_id}}

                # Check if checkpointer is async (has aget_tuple method)
                if hasattr(checkpointer, 'aget_tuple'):
                    # Async checkpointer (AsyncPostgresSaver)
                    checkpoint_tuple = await checkpointer.aget_tuple(checkpoint_config)
                else:
                    # Sync checkpointer (MemorySaver)
                    checkpoint_tuple = checkpointer.get_tuple(checkpoint_config)

                if checkpoint_tuple:
                    logger.info(f"[{request_id}] ✅ Checkpoint found for thread_id={thread_id}")

                    # Try to extract channel_values from checkpoint
                    checkpoint_data = checkpoint_tuple.checkpoint
                    if checkpoint_data:
                        # Log checkpoint structure for debugging (WARNING level to ensure visibility)
                        checkpoint_keys = list(checkpoint_data.keys()) if isinstance(checkpoint_data, dict) else 'not a dict'
                        logger.warning(f"[{request_id}] [CHECKPOINT-DEBUG] Checkpoint keys: {checkpoint_keys}")

                        # Try multiple paths to find conversation_history
                        # LangGraph may store data in different structures depending on version
                        prev_history = None

                        # Path 1: Standard LangGraph structure (channel_values.conversation_history)
                        channel_values = checkpoint_data.get("channel_values", {})
                        if isinstance(channel_values, dict):
                            logger.warning(f"[{request_id}] [CHECKPOINT-DEBUG] channel_values keys: {list(channel_values.keys())}")
                            prev_history = channel_values.get("conversation_history", None)
                            if prev_history:
                                logger.warning(f"[{request_id}] [CHECKPOINT-DEBUG] Found history via channel_values: {len(prev_history)} messages")

                        # Path 2: Direct access (some LangGraph versions store directly)
                        if not prev_history:
                            prev_history = checkpoint_data.get("conversation_history", None)
                            if prev_history:
                                logger.warning(f"[{request_id}] [CHECKPOINT-DEBUG] Found history via direct access: {len(prev_history)} messages")

                        # Path 3: Check if entire state is stored in a 'values' key
                        if not prev_history and "values" in checkpoint_data:
                            values = checkpoint_data.get("values", {})
                            if isinstance(values, dict):
                                prev_history = values.get("conversation_history", None)
                                if prev_history:
                                    logger.warning(f"[{request_id}] [CHECKPOINT-DEBUG] Found history via values: {len(prev_history)} messages")

                        if prev_history and isinstance(prev_history, list) and len(prev_history) > 0:
                            initial_state["conversation_history"] = prev_history
                            logger.info(f"[{request_id}] ✅ Restored conversation_history: {len(prev_history)} messages")
                            # Log last exchange for verification
                            if len(prev_history) >= 2:
                                last_user = next((m for m in reversed(prev_history) if m.get("role") == "user"), None)
                                if last_user:
                                    logger.info(f"[{request_id}] Last user message: '{last_user.get('content', '')[:80]}...'")
                        else:
                            logger.warning(f"[{request_id}] [CHECKPOINT-DEBUG] No conversation_history found in any path")
                            # Log a sample of what's in channel_values for debugging
                            if isinstance(channel_values, dict) and channel_values:
                                sample_keys = list(channel_values.keys())[:10]
                                logger.warning(f"[{request_id}] [CHECKPOINT-DEBUG] Sample channel_values keys: {sample_keys}")
                    else:
                        logger.warning(f"[{request_id}] [CHECKPOINT-DEBUG] Checkpoint tuple found but checkpoint data is empty")
                else:
                    logger.info(f"[{request_id}] No checkpoint found for thread_id={thread_id} (first request in session)")
            except Exception as e:
                logger.warning(f"[{request_id}] Error restoring checkpoint: {e}")

        logger.info(f"[{request_id}] Executing LangGraph workflow with thread_id={thread_id}...")

        # Execute workflow with threading config
        # =====================================================================
        # FIX: Use ainvoke() for async checkpointer (AsyncPostgresSaver)
        # LangGraph requires async interface when using async checkpointers
        # =====================================================================
        workflow_start = time.time()
        raw_final_state = await workflow.ainvoke(initial_state, config=config)
        workflow_time = (time.time() - workflow_start) * 1000

        logger.info(f"[{request_id}] LangGraph workflow complete in {workflow_time:.1f}ms")
        logger.info(f"[{request_id}] Raw final state keys: {list(raw_final_state.keys())}")

        # Extract the actual state from node-keyed dict if needed
        # workflow.ainvoke() returns the full accumulated state directly (not node-keyed)
        final_state = raw_final_state

        # Extract response from final state
        # Check final_response first (used by conversational path), then llm_response
        llm_response = final_state.get("final_response") or final_state.get("llm_response", "")
        logger.info(f"[{request_id}] Extracted response length: {len(llm_response)} chars")

        citations_data = final_state.get("citations", [])
        sources = final_state.get("sources", [])
        
        # Build citations
        api_citations = []
        for i, citation in enumerate(citations_data, 1):
            if isinstance(citation, dict):
                api_citations.append(Citation(
                    source=citation.get("source", f"source_{i}"),
                    raw_text=citation.get("raw_text", citation.get("text", "")),
                    position=citation.get("position", i),
                    context=citation.get("context", "")
                ))
        
        # Build metadata
        total_time = (time.time() - start_time) * 1000
        component_latencies = final_state.get("component_latencies", {})
        
        # Calculate results_used based on path
        selected_path = final_state.get("selected_path", "unknown")
        if selected_path == "fast":
            # Fast path uses vector_results directly (no reranking)
            results_used = len(final_state.get("vector_results", []))
        else:
            # Standard/agentic paths use reranked_results
            results_used = len(final_state.get("reranked_results", []))
        
        metadata = ChatMetadata(
            total_latency_ms=total_time,
            llm_latency_ms=component_latencies.get("generate_fast", 0) +
                           component_latencies.get("generate_standard", 0) +
                           component_latencies.get("react_finalize", 0) +
                           component_latencies.get("generate_conversational", 0),
            retrieval_latency_ms=component_latencies.get("retrieve_vector", 0) +
                                component_latencies.get("retrieve_graph", 0) +
                                component_latencies.get("retrieve_memory", 0),
            path=final_state.get("selected_path", "unknown"),
            routing_confidence=final_state.get("routing_confidence", 0.0),
            routing_reasoning=final_state.get("routing_reasoning", ""),
            llm_model=final_state.get("llm_tokens", {}).get("model", "unknown"),
            llm_provider="groq",
            llm_tokens=final_state.get("llm_tokens", {}),
            profile_id=chat_request.profile_id,
            results_used=results_used,
            citation_count=len(api_citations),
            unique_sources=len(set(sources)),
            reranking_strategy=final_state.get("reranking_strategy"),
            trace_id=request_id,
            langsmith_run_id=final_state.get("langsmith_run_id"),
            evaluation_metrics=final_state.get("evaluation_metrics")
        )
        
        # Add ReAct metadata if agentic path
        if final_state.get("selected_path") == "agentic":
            react_steps = final_state.get("react_steps", [])
            metadata.react_steps = len(react_steps)
            metadata.context_quality = final_state.get("react_confidence", 0.0)

        # Add conversational path debug info
        if final_state.get("selected_path") == "conversational":
            response_metadata = final_state.get("response_metadata", {})
            # Include debug info in evaluation_metrics for visibility
            if not metadata.evaluation_metrics:
                metadata.evaluation_metrics = {}
            metadata.evaluation_metrics["conversational_debug"] = {
                "llm_status": response_metadata.get("llm_status", "unknown"),
                "intent": response_metadata.get("intent", "unknown"),
                "generation_time_ms": response_metadata.get("generation_time_ms", 0)
            }
            # Add any error from state
            if final_state.get("error"):
                metadata.evaluation_metrics["error"] = final_state.get("error")
        
        # session_id was already resolved above for threading

        # Store conversation turn
        if session_id and hasattr(request.app.state, 'session_manager'):
            try:
                await request.app.state.session_manager.store_conversation_turn(
                    session_id=session_id,
                    query=chat_request.query,
                    response=llm_response,
                    sources_used=sources,
                    reasoning_trace=final_state.get("react_steps"),
                    importance_score=0.5,
                    embedding=None
                )
            except Exception as e:
                logger.warning(f"[{request_id}] Failed to store conversation: {e}")
        
        logger.info(
            f"[{request_id}] ✅ LangGraph chat complete: {len(llm_response)} chars, "
            f"{len(api_citations)} citations, {metadata.path} path"
        )
        
        return ChatResponse(
            success=True,
            answer=llm_response,
            citations=api_citations,
            sources=sources,
            metadata=metadata,
            session_id=session_id,
            request_id=request_id
        )
        
    except Exception as e:
        logger.error(f"[{request_id}] ❌ LangGraph chat failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"LangGraph chat processing failed: {str(e)}"
        )


@router.post("/chat/stream")
async def langgraph_chat_stream(
    request: Request,
    chat_request: ChatRequest
):
    """
    LangGraph-powered streaming chat endpoint

    Streams the response as it's being generated using Server-Sent Events (SSE).
    Provides real-time updates as the workflow executes and LLM generates tokens.

    **Flow:**
    1. Initialize RAGState with query and user context
    2. Execute LangGraph workflow with streaming
    3. Yield state updates as they happen
    4. Stream LLM response tokens in real-time
    5. Send final metadata

    **Benefits:**
    - Better UX - users see response immediately
    - Lower perceived latency
    - Can show progress (routing, retrieval, generation)
    - Real-time feedback

    **Response Format (SSE):**
    ```
    event: routing
    data: {"path": "standard", "confidence": 0.85}

    event: retrieval
    data: {"results": 15, "sources": 8}

    event: token
    data: {"token": "Here's", "index": 0}

    event: token
    data: {"token": " my", "index": 1}

    event: complete
    data: {"answer": "full response", "citations": [...], "metadata": {...}}
    ```

    **Usage:**
    Frontend should use EventSource API to consume SSE stream.
    """
    request_id = request.state.request_id
    start_time = time.time()

    logger.info(f"[{request_id}] LangGraph streaming chat query: '{chat_request.query[:50]}...'")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for streaming response"""
        try:
            # Get workflow from app state
            if not hasattr(request.app.state, 'langgraph_workflow'):
                yield f"event: error\ndata: {json.dumps({'error': 'Workflow not initialized'})}\n\n"
                return

            workflow = request.app.state.langgraph_workflow

            # Get or create session_id for threading
            session_id = chat_request.session_id
            if not session_id and hasattr(request.app.state, 'session_manager'):
                from profile_management.profile_id_mapper import normalize_profile_id
                normalized_profile_id = normalize_profile_id(chat_request.profile_id or "sample_profile")
                session_id = await request.app.state.session_manager.get_or_create_session(
                    user_id=chat_request.user_id,
                    executive_id=normalized_profile_id
                )

            # Create initial state
            # Determine if ConversationEngine should be used
            use_conv_engine = should_use_conversation_engine(request_id)

            initial_state = get_default_state(
                query=chat_request.query,
                user_id=chat_request.user_id,
                user_role=chat_request.user_role,
                profile_id=chat_request.profile_id or "sample_profile",
                session_id=session_id,  # Use resolved session_id
                company_id=resolve_company_id(chat_request.company_id, chat_request.user_role),
                top_k=chat_request.top_k or 20,
                min_score=chat_request.min_score or 0.15,
                language=chat_request.language or "en",
                enable_evaluation=getattr(chat_request, 'enable_evaluation', False),
                use_conversation_engine=use_conv_engine
            )

            # Override force_path if specified
            if chat_request.force_path:
                initial_state["force_path"] = chat_request.force_path

            # CRITICAL: Skip LLM generation in workflow nodes (we'll stream it separately)
            initial_state["skip_generation"] = True

            # Build config with thread_id for LangGraph threading
            thread_id = session_id or request_id
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": chat_request.user_id,
                    "profile_id": chat_request.profile_id
                }
            }

            # Preserve conversation_history from checkpointer for multi-turn continuity
            # =====================================================================
            # FIX: Handle both sync (MemorySaver) and async (AsyncPostgresSaver) checkpointers
            # =====================================================================
            if hasattr(request.app.state, 'langgraph_checkpointer') and request.app.state.langgraph_checkpointer:
                checkpointer = request.app.state.langgraph_checkpointer
                try:
                    checkpoint_config = {"configurable": {"thread_id": thread_id}}

                    # Check if checkpointer is async (has aget_tuple method)
                    if hasattr(checkpointer, 'aget_tuple'):
                        # Async checkpointer (AsyncPostgresSaver)
                        checkpoint_tuple = await checkpointer.aget_tuple(checkpoint_config)
                    else:
                        # Sync checkpointer (MemorySaver)
                        checkpoint_tuple = checkpointer.get_tuple(checkpoint_config)

                    if checkpoint_tuple:
                        checkpoint_data = checkpoint_tuple.checkpoint
                        if checkpoint_data:
                            # Try multiple paths to find conversation_history
                            prev_history = None
                            channel_values = checkpoint_data.get("channel_values", {})
                            if isinstance(channel_values, dict):
                                prev_history = channel_values.get("conversation_history", None)
                            if not prev_history:
                                prev_history = checkpoint_data.get("conversation_history", None)
                            if not prev_history and "values" in checkpoint_data:
                                values = checkpoint_data.get("values", {})
                                if isinstance(values, dict):
                                    prev_history = values.get("conversation_history", None)

                            if prev_history and isinstance(prev_history, list) and len(prev_history) > 0:
                                initial_state["conversation_history"] = prev_history
                                logger.info(f"[{request_id}] ✅ Restored conversation_history (stream): {len(prev_history)} messages")
                except Exception as e:
                    logger.warning(f"[{request_id}] Error restoring checkpoint (stream): {e}")

            # Send start event
            start_event = f"event: start\ndata: {json.dumps({'query': chat_request.query, 'request_id': request_id, 'thread_id': thread_id})}\n\n"
            yield start_event

            logger.info(f"[{request_id}] Starting workflow.astream() - workflow type: {type(workflow)}")

            # Stream workflow execution
            # Accumulate state from node-keyed updates
            final_state = None
            accumulated_state = {}
            state_count = 0
            sent_routing = False  # Track if we've already sent routing event
            sent_retrieval = False  # Track if we've already sent retrieval event
            last_react_step_count = 0  # Track react steps to avoid duplicates

            # Stream with config for threading
            async for state_update in workflow.astream(initial_state, config=config):
                state_count += 1
                logger.info(f"[{request_id}] astream iteration {state_count}: keys={list(state_update.keys()) if state_update else 'None'}")

                # state_update is node-keyed: {"node_name": {...state...}}
                # Extract the state from the node key
                if state_update:
                    # Get the first (and only) value from the dict
                    node_state = next(iter(state_update.values())) if state_update else {}

                    # Merge into accumulated state
                    if isinstance(node_state, dict):
                        accumulated_state.update(node_state)

                current_state = accumulated_state

                # Send routing update (ONCE only, when routing is actually complete)
                # Check for actual values, not just key existence (initial state has None values)
                selected_path = current_state.get("selected_path")
                routing_confidence = current_state.get("routing_confidence")
                if not sent_routing and selected_path is not None and routing_confidence is not None:
                    routing_data = {
                        "path": selected_path,
                        "confidence": routing_confidence,
                        "reasoning": current_state.get("routing_reasoning", "")
                    }
                    yield f"event: routing\ndata: {json.dumps(routing_data)}\n\n"
                    sent_routing = True

                # Send retrieval update (ONCE only, when retrieval has actual results)
                # Only send when vector_results has been populated with actual data
                if not sent_retrieval:
                    vector_results = current_state.get("vector_results", [])
                    reranked_results = current_state.get("reranked_results", [])
                    fused_results = current_state.get("fused_results", [])

                    # Only send when we have actual retrieval results
                    if len(vector_results) > 0 or len(reranked_results) > 0 or len(fused_results) > 0:
                        retrieval_data = {
                            "vector_results": len(vector_results),
                            "graph_results": len(current_state.get("graph_results", [])),
                            "memory_results": len(current_state.get("memory_results", [])),
                            "fused_results": len(fused_results),
                            "reranked_results": len(reranked_results)
                        }
                        yield f"event: retrieval\ndata: {json.dumps(retrieval_data)}\n\n"
                        sent_retrieval = True

                # Send ReAct step updates (only when new steps are added)
                if "react_steps" in current_state:
                    react_steps = current_state["react_steps"]
                    if react_steps and len(react_steps) > last_react_step_count:
                        latest_step = react_steps[-1]
                        # Handle None values - ReAct steps may have None for fields not yet populated
                        thought = latest_step.get("thought") or ""
                        action = latest_step.get("action") or ""
                        observation = latest_step.get("observation") or ""

                        react_data = {
                            "step": len(react_steps),
                            "thought": thought,
                            "action": action,
                            "observation_preview": observation[:200]
                        }
                        yield f"event: react_step\ndata: {json.dumps(react_data)}\n\n"
                        last_react_step_count = len(react_steps)

                # Keep track of final state
                final_state = accumulated_state

                # Small delay to prevent overwhelming client
                await asyncio.sleep(0.01)

            # Check if we have a valid final state
            if not final_state:
                logger.error(f"[{request_id}] ❌ No final state from workflow!")
                raise Exception("Workflow did not produce a final state")

            # ================================================================
            # CHECK FOR CONVERSATIONAL PATH (greetings, small talk, etc.)
            # Use LLM with TRUE STREAMING for dynamic personality responses
            # ================================================================
            selected_path = final_state.get("selected_path", "standard")
            cognitive_state = final_state.get("cognitive", {})

            if selected_path == "conversational":
                logger.info(f"[{request_id}] 🗣️ Conversational path - using LLM with true streaming")

                # Get prompts built by generate_conversational node
                system_prompt = cognitive_state.get("conversational_system_prompt")
                user_prompt = cognitive_state.get("conversational_user_prompt")

                if system_prompt and user_prompt:
                    # TRUE LLM STREAMING - tokens arrive as they're generated
                    orchestrator = request.app.state.base_llm_orchestrator
                    token_count = 0
                    full_response = ""
                    llm_start = time.time()

                    try:
                        async for chunk in orchestrator.generate_stream_with_prompts(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            profile_id=chat_request.profile_id or "sample_profile",
                            path="fast"
                        ):
                            if chunk['type'] == 'token':
                                token_count += 1
                                full_response += chunk['content']
                                token_data = {"token": chunk['content'], "index": token_count - 1}
                                yield f"event: token\ndata: {json.dumps(token_data)}\n\n"

                            elif chunk['type'] == 'complete':
                                # LLM streaming complete
                                pass

                        llm_latency = (time.time() - llm_start) * 1000
                        logger.info(f"[{request_id}] Conversational LLM streaming: {token_count} tokens, {llm_latency:.1f}ms")

                    except Exception as e:
                        logger.error(f"[{request_id}] Conversational LLM streaming failed: {e}")
                        # Fallback to hardcoded response
                        full_response = cognitive_state.get("personality_response", "Hi! How can I help?")
                        for i, word in enumerate(full_response.split()):
                            token = word + " " if i < len(full_response.split()) - 1 else word
                            yield f"event: token\ndata: {json.dumps({'token': token, 'index': i})}\n\n"
                        llm_latency = 0.0

                else:
                    # Fallback: no prompts available, use pre-generated response
                    full_response = final_state.get("final_response", "Hi! How can I help?")
                    for i, word in enumerate(full_response.split()):
                        token = word + " " if i < len(full_response.split()) - 1 else word
                        yield f"event: token\ndata: {json.dumps({'token': token, 'index': i})}\n\n"
                        await asyncio.sleep(0.02)
                    llm_latency = 0.0

                # Build and send complete event
                total_time = (time.time() - start_time) * 1000
                metadata = {
                    "total_latency_ms": total_time,
                    "llm_latency_ms": llm_latency if 'llm_latency' in dir() else 0.0,
                    "retrieval_latency_ms": 0.0,
                    "path": "conversational",
                    "routing_confidence": final_state.get("routing_confidence"),
                    "llm_model": orchestrator.provider if 'orchestrator' in dir() else "unknown",
                    "llm_provider": "groq",
                    "llm_tokens": {},
                    "profile_id": chat_request.profile_id,
                    "results_used": 0,
                    "citation_count": 0,
                    "unique_sources": 0,
                    "trace_id": request_id,
                    "conversation_engine": False,
                    "streaming_method": "conversational_llm_streaming"
                }

                complete_data = {
                    "success": True,
                    "answer": full_response,
                    "citations": [],
                    "sources": [],
                    "metadata": metadata,
                    "request_id": request_id
                }
                yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"

                # Update conversation_history for conversational path (multi-turn continuity)
                if full_response and hasattr(request.app.state, 'langgraph_workflow'):
                    try:
                        updated_history = initial_state.get("conversation_history", []).copy()
                        updated_history.append({"role": "user", "content": chat_request.query})
                        updated_history.append({"role": "assistant", "content": full_response})

                        workflow.update_state(
                            config,
                            {"conversation_history": updated_history}
                        )
                        logger.info(f"[{request_id}] ✅ Updated conversation_history (conversational stream): {len(updated_history)} messages")
                    except Exception as hist_e:
                        logger.warning(f"[{request_id}] Failed to update conversation_history: {hist_e}")

                logger.info(f"[{request_id}] ✅ Conversational streaming complete: {len(full_response)} chars, {total_time:.1f}ms")
                return  # Exit early - conversational path complete

            # ================================================================
            # STANDARD LLM STREAMING (for non-conversational queries)
            # ================================================================

            # Stream LLM response in real-time using orchestrator
            # Get orchestrator from app state for real streaming
            orchestrator = request.app.state.base_llm_orchestrator

            # Extract retrieval data from final state
            vector_results = final_state.get("reranked_results", final_state.get("fused_results", final_state.get("vector_results", [])))
            graph_results = final_state.get("graph_results", [])
            memory_results = final_state.get("memory_results", [])

            token_count = 0
            full_response = ""

            # ================================================================
            # Use ConversationEngine for streaming (same as /chat)
            # This ensures streaming responses have the same voiceprint quality
            # as non-streaming responses by using the full 5-stage pipeline.
            # ================================================================
            conversation_engine = getattr(request.app.state, 'conversation_engine', None)

            if conversation_engine and use_conv_engine:
                logger.info(f"[{request_id}] 🧠 Using ConversationEngine for streaming (same pipeline as /chat)")

                # Build RetrievalContext for ConversationEngine
                from llm_integration.prompt_builder import RetrievalContext
                retrieval_context = RetrievalContext(
                    vector_results=vector_results,
                    graph_results=graph_results if graph_results else None,
                    precedents=memory_results if memory_results else None,
                    memory=[],
                    query=chat_request.query
                )

                # Generate prompts using ConversationEngine (SAME as /chat endpoint!)
                # This runs the full 5-stage pipeline:
                # 1. ContextAnalyzer → theme, urgency, emotion
                # 2. ResponseCalibrator → attention weights, tone calibration
                # 3. ExampleSelector → best matching communication example
                # 4. PrecedentSelector → relevant decision cases
                # 5. PromptAssembler → IdentitySection, ValuesSection, etc.
                system_prompt, user_prompt, conv_state = await conversation_engine.generate(
                    query=chat_request.query,
                    profile_id=chat_request.profile_id or "sample_profile",
                    retrieved_context=retrieval_context,
                    path=selected_path,
                    session_id=session_id,
                    user_id=chat_request.user_id,
                    memory_enabled=False,
                    language=chat_request.language or "en",
                )

                logger.info(
                    f"[{request_id}] ConversationEngine prompts built: "
                    f"system={len(system_prompt)} chars, user={len(user_prompt)} chars"
                )

                # Stream using pre-built prompts from ConversationEngine
                async for chunk in orchestrator.generate_stream_with_prompts(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    profile_id=chat_request.profile_id or "sample_profile",
                    path=selected_path,
                    retrieval_context={
                        "vector_results": vector_results,
                        "graph_results": graph_results,
                        "precedents": memory_results
                    }
                ):
                    if chunk['type'] == 'token':
                        token_count += 1
                        full_response += chunk['content']

                        # Send token immediately in LangGraph SSE format
                        token_data = {
                            "token": chunk['content'],
                            "index": token_count - 1
                        }
                        yield f"event: token\ndata: {json.dumps(token_data)}\n\n"

                    elif chunk['type'] == 'langsmith_metadata':
                        # Forward LangSmith metadata
                        final_state['langsmith_run_id'] = chunk.get('run_id')

                    elif chunk['type'] == 'error':
                        # Handle errors from streaming
                        logger.error(f"[{request_id}] Streaming error: {chunk.get('error')}")
                        yield f"event: error\ndata: {json.dumps({'error': chunk.get('error')})}\n\n"

            else:
                # Fallback: Use original PromptBuilder path (legacy behavior)
                logger.info(f"[{request_id}] Using PromptBuilder fallback for streaming")

                # Stream tokens as they arrive from LLM
                async for chunk in orchestrator.generate_stream(
                    query=chat_request.query,
                    vector_results=vector_results,
                    profile_id=chat_request.profile_id or "sample_profile",
                    graph_results=graph_results,
                    precedents=memory_results,
                    memory=[],
                    force_path=selected_path,
                    query_analysis=final_state.get("query_analysis", {}),
                    language=chat_request.language or "en"
                ):
                    if chunk['type'] == 'token':
                        token_count += 1
                        full_response += chunk['content']

                        # Send token immediately in LangGraph SSE format
                        token_data = {
                            "token": chunk['content'],
                            "index": token_count - 1
                        }
                        yield f"event: token\ndata: {json.dumps(token_data)}\n\n"

                    elif chunk['type'] == 'langsmith_metadata':
                        # Forward LangSmith metadata
                        final_state['langsmith_run_id'] = chunk.get('run_id')

            # Update final state with streamed response
            llm_response = full_response

            # Validate response word count (P1 fix)
            word_count = len(llm_response.split())
            max_words = get_word_limit(selected_path)
            word_count_exceeded = word_count > max_words

            if word_count_exceeded:
                overage = word_count - max_words
                overage_pct = (overage / max_words) * 100
                logger.warning(
                    f"[{request_id}] Response exceeds word limit: {word_count} words "
                    f"(limit: {max_words}, over by {overage} words / {overage_pct:.1f}%)"
                )

            # Build final response
            citations_data = final_state.get("citations", [])
            sources = final_state.get("sources", [])

            # Build citations
            api_citations = []
            for i, citation in enumerate(citations_data, 1):
                if isinstance(citation, dict):
                    api_citations.append({
                        "source": citation.get("source", f"source_{i}"),
                        "raw_text": citation.get("raw_text", citation.get("text", "")),
                        "position": citation.get("position", i),
                        "context": citation.get("context", "")
                    })

            # Build metadata
            total_time = (time.time() - start_time) * 1000
            component_latencies = final_state.get("component_latencies", {})

            selected_path = final_state.get("selected_path", "unknown")
            if selected_path == "fast":
                results_used = len(final_state.get("vector_results", []))
            else:
                results_used = len(final_state.get("reranked_results", []))

            # Track if ConversationEngine was used for this request
            used_conversation_engine = conversation_engine is not None and use_conv_engine

            metadata = {
                "total_latency_ms": total_time,
                "llm_latency_ms": component_latencies.get("generate_fast", 0) +
                                 component_latencies.get("generate_standard", 0) +
                                 component_latencies.get("react_finalize", 0),
                "retrieval_latency_ms": component_latencies.get("retrieve_vector", 0) +
                                      component_latencies.get("retrieve_graph", 0) +
                                      component_latencies.get("retrieve_memory", 0),
                "path": selected_path,
                "routing_confidence": final_state.get("routing_confidence", 0.0),
                "routing_reasoning": final_state.get("routing_reasoning", ""),
                "llm_model": final_state.get("llm_tokens", {}).get("model", "unknown"),
                "llm_provider": "groq",
                "llm_tokens": final_state.get("llm_tokens", {}),
                "profile_id": chat_request.profile_id,
                "results_used": results_used,
                "citation_count": len(api_citations),
                "unique_sources": len(set(sources)),
                "reranking_strategy": final_state.get("reranking_strategy"),
                "trace_id": request_id,
                "langsmith_run_id": final_state.get("langsmith_run_id"),
                "conversation_engine": used_conversation_engine,
                "streaming_method": "generate_stream_with_prompts" if used_conversation_engine else "generate_stream",
                "word_count": word_count,
                "max_words": max_words,
                "word_count_exceeded": word_count_exceeded
            }

            # Add ReAct metadata if agentic path
            if selected_path == "agentic":
                react_steps = final_state.get("react_steps", [])
                metadata["react_steps"] = len(react_steps)
                metadata["context_quality"] = final_state.get("react_confidence", 0.0)

            # Send complete event with full response
            complete_data = {
                "success": True,
                "answer": llm_response,
                "citations": api_citations,
                "sources": sources,
                "metadata": metadata,
                "request_id": request_id
            }
            yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"

            # Update conversation_history after streaming (for multi-turn continuity)
            # This is necessary because skip_generation=True bypasses the normal history update
            if llm_response and hasattr(request.app.state, 'langgraph_workflow'):
                try:
                    # Update workflow state with conversation history
                    updated_history = initial_state.get("conversation_history", []).copy()
                    updated_history.append({"role": "user", "content": chat_request.query})
                    updated_history.append({"role": "assistant", "content": llm_response})

                    # Use workflow.update_state to persist conversation history
                    workflow.update_state(
                        config,
                        {"conversation_history": updated_history}
                    )
                    logger.info(f"[{request_id}] ✅ Updated conversation_history after streaming: {len(updated_history)} messages")
                except Exception as hist_e:
                    logger.warning(f"[{request_id}] Failed to update conversation_history: {hist_e}")

            logger.info(
                f"[{request_id}] ✅ Streaming complete: {len(llm_response)} chars, "
                f"{len(api_citations)} citations, {metadata['path']} path"
            )

        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            error_msg = str(e) if str(e) else f"{type(e).__name__}: {repr(e)}"
            logger.error(f"[{request_id}] ❌ Streaming failed: {error_msg}\n{tb_str}")
            error_data = {
                "error": error_msg,
                "error_type": type(e).__name__,
                "request_id": request_id
            }
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


# ============================================================================
# LANGGRAPH STREAMING CHAT WITH AUDIO
# ============================================================================

@router.post("/chat/stream-audio")
async def langgraph_chat_stream_audio(
    request: Request,
    chat_request: ChatRequest
):
    """
    LangGraph-powered streaming chat with AUDIO + text

    Combines LangGraph workflow execution (with LangSmith tracking) with
    real-time audio generation using Kokoro TTS. Returns Server-Sent Events
    with both text tokens AND audio frames.

    **Flow:**
    1. Execute LangGraph workflow (tracked in LangSmith)
    2. Stream routing/retrieval updates
    3. Stream LLM response tokens in real-time
    4. Generate audio sentence-by-sentence with Kokoro TTS
    5. Stream audio frames as they're generated
    6. Send final metadata

    **Benefits:**
    - ✅ Full LangSmith observability
    - ✅ Real-time text AND audio streaming
    - ✅ Sentence-by-sentence audio generation
    - ✅ Compatible with existing LangGraph infrastructure

    **Stream format (newline-delimited JSON):**
    - `event: routing` - Path selection (fast/standard/agentic)
    - `event: retrieval` - Vector/graph/memory retrieval counts
    - `event: token` - Text token from LLM
    - `event: audio_frame` - Base64-encoded PCM audio frame (24kHz, 16-bit, mono)
    - `event: complete` - Final metadata with citations

    **Audio format:**
    - Sample rate: 24kHz
    - Format: 16-bit PCM (LINEAR16), mono
    - Frame size: 480 samples (20ms @ 24kHz)
    - Encoding: Base64 for JSON transmission
    - TTS Engine: Kokoro TTS (af_bella voice for English, jf_alpha for Japanese)
    """
    request_id = request.state.request_id
    start_time = time.time()

    logger.info(f"[{request_id}] LangGraph audio streaming: '{chat_request.query[:50]}...'")
    logger.info(f"[{request_id}] Request Payload: {chat_request.model_dump()}")

    # Resolve session ID accurately before anything else
    session_id = chat_request.session_id
    
    # Check if we need to create a new session
    if not session_id and hasattr(request.app.state, 'session_manager'):
        from profile_management.profile_id_mapper import normalize_profile_id
        normalized_profile_id = normalize_profile_id(chat_request.profile_id or "sample_profile")
        session_id = await request.app.state.session_manager.get_or_create_session(
            user_id=chat_request.user_id,
            executive_id=normalized_profile_id
        )
        logger.info(f"[{request_id}] Created new session for audio stream: {session_id}")
    
    # Fallback only if still None (and assume stateless or request_id tracking if backend permits, though DB will fail if used there)
    # Ideally should be a UUID if engaging with DB.
    final_session_id = session_id or request_id

    # Initialize connection manager for this session
    from audio_services.connection_manager import ConnectionManager
    manager = ConnectionManager(final_session_id)
    await manager.connect()
    await manager.start_streaming()

    # Store in app state for interruption access
    request.app.state.active_sessions[final_session_id] = manager

    async def audio_event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for streaming text + audio"""
        try:
            # Get workflow and TTS manager from app state
            if not hasattr(request.app.state, 'langgraph_workflow'):
                yield f"event: error\ndata: {json.dumps({'error': 'Workflow not initialized'})}\n\n"
                return

            workflow = request.app.state.langgraph_workflow

            # Get singleton TTS manager (with GPU semaphore)
            from audio_services.tts_manager import get_tts_manager
            tts_manager = await get_tts_manager()

            # Audio metrics
            audio_metrics = {'frames_generated': 0, 'audio_segments': 0}
            
            # Use the resolved session_id
            resolved_session_id = final_session_id

            # Video Service Client (Persistent)
            video_client = None
            if chat_request.enable_video_push:
                try:
                    from audio_services.video_client import VideoServiceClient
                    
                    # Initialize persistence storage if needed
                    if not hasattr(request.app.state, 'video_clients'):
                        request.app.state.video_clients = {}
                    
                    # Reuse existing client if connected
                    existing_client = request.app.state.video_clients.get(resolved_session_id)

                    if existing_client and existing_client.is_connected:
                        video_client = existing_client
                        logger.info(f"[{request_id}] ♻️ Reusing existing Video Service connection (session_id: {resolved_session_id})")
                        # await video_client.start_speaking()
                    else:
                        # Create new connection
                        if existing_client:
                            logger.warning(f"[{request_id}] ⚠️ Existing video client found but not connected. Creating new connection.")

                        video_client = VideoServiceClient()
                        # Use 'anand_idle_v2' or map from chat_request.profile_id
                        await video_client.connect(
                            session_id=resolved_session_id
                        )

                        # Store in global state
                        request.app.state.video_clients[resolved_session_id] = video_client
                        logger.info(f"[{request_id}] 🆕 Created new Video Service connection (session_id: {resolved_session_id})")
                        # await video_client.start_speaking()
                        
                except Exception as e:
                    logger.error(f"[{request_id}] ❌ Failed to connect to Video Service: {e}")
                    video_client = None

            # Create initial state
            # Determine if ConversationEngine should be used
            use_conv_engine = should_use_conversation_engine(request_id)

            initial_state = get_default_state(
                query=chat_request.query,
                user_id=chat_request.user_id,
                user_role=chat_request.user_role,
                profile_id=chat_request.profile_id or "sample_profile",
                session_id=resolved_session_id,  # Use resolved session_id
                company_id=resolve_company_id(chat_request.company_id, chat_request.user_role),
                top_k=chat_request.top_k or 20,
                min_score=chat_request.min_score or 0.15,
                language=chat_request.language or "en",
                enable_evaluation=getattr(chat_request, 'enable_evaluation', False),
                use_conversation_engine=use_conv_engine
            )

            # Override force_path if specified
            if chat_request.force_path:
                initial_state["force_path"] = chat_request.force_path

            # CRITICAL: Skip LLM generation in workflow nodes (we'll stream it separately with audio)
            initial_state["skip_generation"] = True

            # Build config with thread_id for LangGraph threading
            thread_id = resolved_session_id or request_id
            config = {
                "configurable": {
                    "thread_id": thread_id,
                    "user_id": chat_request.user_id,
                    "profile_id": chat_request.profile_id
                }
            }

            # Preserve conversation_history from checkpointer for multi-turn continuity
            # =====================================================================
            # FIX: Handle both sync (MemorySaver) and async (AsyncPostgresSaver) checkpointers
            # =====================================================================
            if hasattr(request.app.state, 'langgraph_checkpointer') and request.app.state.langgraph_checkpointer:
                checkpointer = request.app.state.langgraph_checkpointer
                try:
                    checkpoint_config = {"configurable": {"thread_id": thread_id}}

                    # Check if checkpointer is async (has aget_tuple method)
                    if hasattr(checkpointer, 'aget_tuple'):
                        # Async checkpointer (AsyncPostgresSaver)
                        checkpoint_tuple = await checkpointer.aget_tuple(checkpoint_config)
                    else:
                        # Sync checkpointer (MemorySaver)
                        checkpoint_tuple = checkpointer.get_tuple(checkpoint_config)

                    if checkpoint_tuple:
                        checkpoint_data = checkpoint_tuple.checkpoint
                        if checkpoint_data:
                            # Try multiple paths to find conversation_history
                            prev_history = None
                            channel_values = checkpoint_data.get("channel_values", {})
                            if isinstance(channel_values, dict):
                                prev_history = channel_values.get("conversation_history", None)
                            if not prev_history:
                                prev_history = checkpoint_data.get("conversation_history", None)
                            if not prev_history and "values" in checkpoint_data:
                                values = checkpoint_data.get("values", {})
                                if isinstance(values, dict):
                                    prev_history = values.get("conversation_history", None)

                            if prev_history and isinstance(prev_history, list) and len(prev_history) > 0:
                                initial_state["conversation_history"] = prev_history
                                logger.info(f"[{request_id}] ✅ Restored conversation_history (audio): {len(prev_history)} messages")
                except Exception as e:
                    logger.warning(f"[{request_id}] Error restoring checkpoint (audio): {e}")

            # Send start event
            start_event = f"event: start\ndata: {json.dumps({'query': chat_request.query, 'request_id': request_id, 'thread_id': thread_id})}\n\n"
            yield start_event

            # Stream workflow execution
            final_state = None
            accumulated_state = {}
            state_count = 0
            sent_routing = False
            sent_retrieval = False
            last_react_step_count = 0

            # Stream with config for threading
            async for state_update in workflow.astream(initial_state, config=config):
                state_count += 1

                # Check for interruption
                if manager.is_interrupted():
                    logger.warning(f"[{request_id}] Audio stream interrupted")
                    yield f"event: interrupted\ndata: {json.dumps({'message': 'Stream interrupted'})}\n\n"
                    break

                # Extract state from node-keyed update
                if state_update:
                    node_state = next(iter(state_update.values())) if state_update else {}
                    if isinstance(node_state, dict):
                        accumulated_state.update(node_state)

                current_state = accumulated_state

                # Send routing update (ONCE only, when routing is actually complete)
                # Check for actual values, not just key existence (initial state has None values)
                selected_path = current_state.get("selected_path")
                routing_confidence = current_state.get("routing_confidence")
                if not sent_routing and selected_path is not None and routing_confidence is not None:
                    routing_data = {
                        "path": selected_path,
                        "confidence": routing_confidence,
                        "reasoning": current_state.get("routing_reasoning", "")
                    }
                    yield f"event: routing\ndata: {json.dumps(routing_data)}\n\n"
                    sent_routing = True

                # Send retrieval update (ONCE only, when retrieval has actual results)
                # Only send when vector_results has been populated with actual data
                if not sent_retrieval:
                    vector_results = current_state.get("vector_results", [])
                    reranked_results = current_state.get("reranked_results", [])
                    fused_results = current_state.get("fused_results", [])

                    # Only send when we have actual retrieval results
                    if len(vector_results) > 0 or len(reranked_results) > 0 or len(fused_results) > 0:
                        retrieval_data = {
                            "vector_results": len(vector_results),
                            "graph_results": len(current_state.get("graph_results", [])),
                            "memory_results": len(current_state.get("memory_results", [])),
                            "fused_results": len(fused_results),
                            "reranked_results": len(reranked_results)
                        }
                        yield f"event: retrieval\ndata: {json.dumps(retrieval_data)}\n\n"
                        sent_retrieval = True

                # Send ReAct step updates (only new steps)
                if "react_steps" in current_state:
                    react_steps = current_state["react_steps"]
                    if react_steps and len(react_steps) > last_react_step_count:
                        latest_step = react_steps[-1]
                        react_data = {
                            "step": len(react_steps),
                            "thought": latest_step.get("thought") or "",
                            "action": latest_step.get("action") or "",
                            "observation_preview": (latest_step.get("observation") or "")[:200]
                        }
                        yield f"event: react_step\ndata: {json.dumps(react_data)}\n\n"
                        last_react_step_count = len(react_steps)

                final_state = accumulated_state
                await asyncio.sleep(0.01)

            # Check for valid final state
            if not final_state:
                logger.error(f"[{request_id}] ❌ No final state from workflow")
                raise Exception("Workflow did not produce final state")

            # ================================================================
            # CHECK FOR CONVERSATIONAL PATH (greetings, small talk, etc.)
            # Use LLM with TRUE STREAMING + audio for dynamic personality responses
            # ================================================================
            selected_path = final_state.get("selected_path", "standard")
            cognitive_state = final_state.get("cognitive", {})

            if selected_path == "conversational":
                logger.info(f"[{request_id}] 🗣️ Conversational path - using LLM streaming + audio")

                # Import TTS and audio utilities
                from audio_services.tts_manager import get_tts_manager
                from audio_services.streaming_utils import clean_text_for_tts, has_complete_sentence, extract_first_sentence
                import base64

                tts_manager = await get_tts_manager()
                audio_metrics = {'frames_generated': 0, 'audio_segments': 0}

                # Get prompts built by generate_conversational node
                system_prompt = cognitive_state.get("conversational_system_prompt")
                user_prompt = cognitive_state.get("conversational_user_prompt")

                full_response = ""
                sentence_buffer = ""
                token_count = 0
                frame_index = 0
                sentence_id = 0
                llm_latency = 0.0

                if system_prompt and user_prompt:
                    # TRUE LLM STREAMING with audio generation
                    orchestrator = request.app.state.base_llm_orchestrator
                    llm_start = time.time()

                    try:
                        async for chunk in orchestrator.generate_stream_with_prompts(
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            profile_id=chat_request.profile_id or "sample_profile",
                            path="fast"
                        ):
                            if manager.is_interrupted():
                                break

                            if chunk['type'] == 'token':
                                token_content = chunk['content']
                                full_response += token_content
                                sentence_buffer += token_content

                                # Stream token immediately
                                token_data = {"token": token_content, "index": token_count}
                                yield f"event: token\ndata: {json.dumps(token_data)}\n\n"
                                await manager.add_text_token(token_content)
                                token_count += 1

                                # Check for complete sentence and generate audio
                                if has_complete_sentence(sentence_buffer):
                                    sentence, sentence_buffer = extract_first_sentence(sentence_buffer)
                                    if sentence.strip():
                                        sentence_id += 1
                                        clean_sentence = clean_text_for_tts(sentence)

                                        try:
                                            async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                                                clean_sentence,
                                                voice_config={'language': chat_request.language or 'en', 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                                                is_last_sentence=False
                                            ):
                                                if manager.is_interrupted():
                                                    break

                                                if video_client:
                                                    await video_client.send_audio(audio_frame)

                                                audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                                                frame_msg = {
                                                    'type': 'audio_frame',
                                                    'data': audio_b64,
                                                    'index': frame_index,
                                                    'sentence_id': sentence_id
                                                }
                                                yield f"event: audio_frame\ndata: {json.dumps(frame_msg)}\n\n"
                                                await manager.add_audio_frame(audio_frame)
                                                frame_index += 1
                                                audio_metrics['frames_generated'] += 1
                                            audio_metrics['audio_segments'] += 1
                                        except Exception as e:
                                            logger.error(f"[{request_id}] Audio generation failed for sentence: {e}")

                        llm_latency = (time.time() - llm_start) * 1000

                        # Generate audio for remaining buffer
                        if sentence_buffer.strip():
                            sentence_id += 1
                            clean_sentence = clean_text_for_tts(sentence_buffer)
                            try:
                                async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                                    clean_sentence,
                                    voice_config={'language': chat_request.language or 'en', 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                                    is_last_sentence=True
                                ):
                                    if manager.is_interrupted():
                                        break

                                    if video_client:
                                        await video_client.send_audio(audio_frame)

                                    audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                                    frame_msg = {
                                        'type': 'audio_frame',
                                        'data': audio_b64,
                                        'index': frame_index,
                                        'sentence_id': sentence_id
                                    }
                                    yield f"event: audio_frame\ndata: {json.dumps(frame_msg)}\n\n"
                                    await manager.add_audio_frame(audio_frame)
                                    frame_index += 1
                                    audio_metrics['frames_generated'] += 1
                                audio_metrics['audio_segments'] += 1
                            except Exception as e:
                                logger.error(f"[{request_id}] Final audio generation failed: {e}")

                        logger.info(f"[{request_id}] Conversational LLM+audio streaming: {token_count} tokens, {llm_latency:.1f}ms")

                    except Exception as e:
                        logger.error(f"[{request_id}] Conversational LLM streaming failed: {e}")
                        # Fallback to hardcoded response
                        full_response = cognitive_state.get("personality_response", "Hi! How can I help?")
                        for i, word in enumerate(full_response.split()):
                            token = word + " " if i < len(full_response.split()) - 1 else word
                            yield f"event: token\ndata: {json.dumps({'token': token, 'index': i})}\n\n"

                else:
                    # Fallback: no prompts, use pre-generated response
                    full_response = final_state.get("final_response", "Hi! How can I help?")
                    for i, word in enumerate(full_response.split()):
                        token = word + " " if i < len(full_response.split()) - 1 else word
                        yield f"event: token\ndata: {json.dumps({'token': token, 'index': i})}\n\n"
                        await manager.add_text_token(token)
                        await asyncio.sleep(0.02)

                    # Generate audio for fallback
                    clean_text = clean_text_for_tts(full_response)
                    try:
                        async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                            clean_text,
                            voice_config={'language': chat_request.language or 'en', 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                            is_last_sentence=True
                        ):
                            if video_client:
                                await video_client.send_audio(audio_frame)

                            audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                            yield f"event: audio_frame\ndata: {json.dumps({'type': 'audio_frame', 'data': audio_b64, 'index': frame_index})}\n\n"
                            frame_index += 1
                            audio_metrics['frames_generated'] += 1
                        audio_metrics['audio_segments'] += 1
                    except Exception as e:
                        logger.error(f"[{request_id}] Fallback audio failed: {e}")

                await manager.end_streaming()

                # Build and send complete event
                total_time = (time.time() - start_time) * 1000
                metadata = {
                    "total_latency_ms": total_time,
                    "llm_latency_ms": llm_latency,
                    "retrieval_latency_ms": 0.0,
                    "path": "conversational",
                    "routing_confidence": final_state.get("routing_confidence"),
                    "llm_model": "groq",
                    "llm_provider": "groq",
                    "llm_tokens": {},
                    "profile_id": chat_request.profile_id,
                    "results_used": 0,
                    "citation_count": 0,
                    "unique_sources": 0,
                    "trace_id": request_id,
                    "audio_frames": audio_metrics['frames_generated'],
                    "audio_segments": audio_metrics['audio_segments'],
                    "conversation_engine": False,
                    "streaming_method": "conversational_llm_audio_streaming"
                }

                complete_data = {
                    "success": True,
                    "answer": full_response,
                    "citations": [],
                    "sources": [],
                    "metadata": metadata,
                    "request_id": request_id
                }
                yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"

                # Update conversation_history for conversational audio path
                if full_response and hasattr(request.app.state, 'langgraph_workflow'):
                    try:
                        updated_history = initial_state.get("conversation_history", []).copy()
                        updated_history.append({"role": "user", "content": chat_request.query})
                        updated_history.append({"role": "assistant", "content": full_response})

                        workflow.update_state(
                            config,
                            {"conversation_history": updated_history}
                        )
                        logger.info(f"[{request_id}] ✅ Updated conversation_history (conversational audio): {len(updated_history)} messages")
                    except Exception as hist_e:
                        logger.warning(f"[{request_id}] Failed to update conversation_history: {hist_e}")

                logger.info(f"[{request_id}] ✅ Conversational audio streaming complete: {len(full_response)} chars, {audio_metrics['frames_generated']} frames, {total_time:.1f}ms")
                logger.info(f"[{request_id}] 🗣️ Complete response text: {full_response}")
                return  # Exit early - no LLM needed

            # ================================================================
            # STANDARD LLM + AUDIO STREAMING (for non-conversational queries)
            # ================================================================

            # Stream LLM response + audio in REAL-TIME using orchestrator
            # Get orchestrator from app state for real streaming
            orchestrator = request.app.state.base_llm_orchestrator

            # Extract retrieval data from final state
            vector_results = final_state.get("reranked_results", final_state.get("fused_results", final_state.get("vector_results", [])))
            graph_results = final_state.get("graph_results", [])
            memory_results = final_state.get("memory_results", [])

            # Import streaming utilities
            from audio_services.streaming_utils import (
                has_complete_sentence,
                extract_first_sentence,
                clean_text_for_tts
            )

            # Stream tokens and generate audio
            import base64
            sentence_buffer = ""
            full_response = ""
            frame_index = 0
            sentence_id = 0
            token_index = 0

            # ================================================================
            # Use ConversationEngine for audio streaming (same as /chat/stream)
            # This ensures audio responses have the same voiceprint quality
            # as text streaming responses by using the full 5-stage pipeline.
            # ================================================================
            conversation_engine = getattr(request.app.state, 'conversation_engine', None)
            used_conversation_engine = False

            if conversation_engine and use_conv_engine:
                logger.info(f"[{request_id}] 🧠 Using ConversationEngine for audio streaming (same pipeline as /chat/stream)")
                used_conversation_engine = True

                # Build RetrievalContext for ConversationEngine
                from llm_integration.prompt_builder import RetrievalContext
                retrieval_context = RetrievalContext(
                    vector_results=vector_results,
                    graph_results=graph_results if graph_results else None,
                    precedents=memory_results if memory_results else None,
                    memory=[],
                    query=chat_request.query
                )

                # Generate prompts using ConversationEngine (SAME as /chat/stream endpoint!)
                # This runs the full 5-stage pipeline:
                # 1. ContextAnalyzer → theme, urgency, emotion
                # 2. ResponseCalibrator → attention weights, tone calibration
                # 3. ExampleSelector → best matching communication example
                # 4. PrecedentSelector → relevant decision cases
                # 5. PromptAssembler → IdentitySection, ValuesSection, etc.
                #
                # Check for audio_mode flag (set by /chat/stream-audio-natural endpoint)
                # When audio_mode=True, includes natural speaking patterns from YouTube
                audio_mode = getattr(request.state, 'audio_mode', False)

                system_prompt, user_prompt, conv_state = await conversation_engine.generate(
                    query=chat_request.query,
                    profile_id=chat_request.profile_id or "sample_profile",
                    retrieved_context=retrieval_context,
                    path=selected_path,
                    session_id=resolved_session_id,
                    user_id=chat_request.user_id,
                    memory_enabled=False,
                    language=chat_request.language or "en",
                    audio_mode=audio_mode,
                )

                logger.info(
                    f"[{request_id}] ConversationEngine prompts built for audio: "
                    f"system={len(system_prompt)} chars, user={len(user_prompt)} chars, "
                    f"audio_mode={audio_mode}"
                )

                # Stream using pre-built prompts from ConversationEngine
                async for chunk in orchestrator.generate_stream_with_prompts(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    profile_id=chat_request.profile_id or "sample_profile",
                    path=selected_path,
                    retrieval_context={
                        "vector_results": vector_results,
                        "graph_results": graph_results,
                        "precedents": memory_results
                    }
                ):
                    if chunk['type'] == 'token':
                        if manager.is_interrupted():
                            break

                        # Process token and generate audio
                        token_content = chunk['content']
                        full_response += token_content
                        token_data = {"token": token_content, "index": token_index}
                        yield f"event: token\ndata: {json.dumps(token_data)}\n\n"
                        await manager.add_text_token(token_content)

                        sentence_buffer += token_content
                        token_index += 1

                        # Check for complete sentence
                        while has_complete_sentence(sentence_buffer):
                            sentence, sentence_buffer = extract_first_sentence(sentence_buffer)

                            if sentence.strip():
                                clean_sentence = clean_text_for_tts(sentence)
                                sentence_id += 1

                                # Generate and stream audio for sentence
                                try:
                                    async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                                        clean_sentence,
                                        voice_config={'language': chat_request.language, 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                                        is_last_sentence=False
                                    ):
                                        if manager.is_interrupted():
                                            break

                                        if video_client:
                                            await video_client.send_audio(audio_frame)

                                        audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                                        frame_msg = {
                                            'type': 'audio_frame',
                                            'data': audio_b64,
                                            'index': frame_index,
                                            'sentence_id': sentence_id
                                        }
                                        yield f"event: audio_frame\ndata: {json.dumps(frame_msg)}\n\n"
                                        await manager.add_audio_frame(audio_frame)
                                        frame_index += 1
                                        audio_metrics['frames_generated'] += 1

                                    audio_metrics['audio_segments'] += 1

                                except Exception as e:
                                    logger.error(f"[{request_id}] Audio generation failed: {e}", exc_info=True)
                                    yield f"event: audio_error\ndata: {json.dumps({'message': str(e), 'sentence_id': sentence_id})}\n\n"

                    elif chunk['type'] == 'langsmith_metadata':
                        # Forward LangSmith metadata
                        final_state['langsmith_run_id'] = chunk.get('run_id')

                    elif chunk['type'] == 'error':
                        # Handle errors from streaming
                        logger.error(f"[{request_id}] Audio streaming error: {chunk.get('error')}")
                        yield f"event: error\ndata: {json.dumps({'error': chunk.get('error')})}\n\n"

            else:
                # Fallback: Use original PromptBuilder path (legacy behavior)
                logger.info(f"[{request_id}] Using PromptBuilder fallback for audio streaming")

                # Stream tokens as they arrive from LLM (legacy path)
                async for chunk in orchestrator.generate_stream(
                    query=chat_request.query,
                    vector_results=vector_results,
                    profile_id=chat_request.profile_id or "sample_profile",
                    graph_results=graph_results,
                    precedents=memory_results,
                    memory=[],
                    force_path=selected_path,
                    query_analysis=final_state.get("query_analysis", {}),
                    language=chat_request.language or "en"
                ):
                    if chunk['type'] == 'token':
                        if manager.is_interrupted():
                            break

                        # Get token content from chunk
                        token_content = chunk['content']
                        full_response += token_content
                        token_data = {"token": token_content, "index": token_index}
                        yield f"event: token\ndata: {json.dumps(token_data)}\n\n"
                        await manager.add_text_token(token_content)

                        sentence_buffer += token_content
                        token_index += 1

                        # Check for complete sentence
                        while has_complete_sentence(sentence_buffer):
                            sentence, sentence_buffer = extract_first_sentence(sentence_buffer)

                            if sentence.strip():
                                clean_sentence = clean_text_for_tts(sentence)
                                sentence_id += 1

                                # Generate and stream audio for sentence
                                try:
                                    async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                                        clean_sentence,
                                        voice_config={'language': chat_request.language, 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                                        is_last_sentence=False
                                    ):
                                        if manager.is_interrupted():
                                            break

                                        if video_client:
                                            await video_client.send_audio(audio_frame)

                                        audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                                        frame_msg = {
                                            'type': 'audio_frame',
                                            'data': audio_b64,
                                            'index': frame_index,
                                            'sentence_id': sentence_id
                                        }
                                        yield f"event: audio_frame\ndata: {json.dumps(frame_msg)}\n\n"
                                        await manager.add_audio_frame(audio_frame)
                                        frame_index += 1
                                        audio_metrics['frames_generated'] += 1

                                    audio_metrics['audio_segments'] += 1

                                except Exception as e:
                                    logger.error(f"[{request_id}] Audio generation failed: {e}", exc_info=True)
                                    yield f"event: audio_error\ndata: {json.dumps({'message': str(e), 'sentence_id': sentence_id})}\n\n"

                    elif chunk['type'] == 'langsmith_metadata':
                        # Forward LangSmith metadata
                        final_state['langsmith_run_id'] = chunk.get('run_id')

            # Process remaining text in buffer
            if sentence_buffer.strip() and not manager.is_interrupted():
                clean_sentence = clean_text_for_tts(sentence_buffer)
                sentence_id += 1

                try:
                    async for audio_frame in tts_manager.synthesize_with_gpu_lock(
                        clean_sentence,
                        voice_config={'language': chat_request.language, 'executive_id': chat_request.voice_profile_id or chat_request.profile_id},
                        is_last_sentence=True
                    ):
                        if manager.is_interrupted():
                            break

                        if video_client:
                            await video_client.send_audio(audio_frame)

                        audio_b64 = base64.b64encode(audio_frame).decode('ascii')
                        frame_msg = {
                            'type': 'audio_frame',
                            'data': audio_b64,
                            'index': frame_index,
                            'sentence_id': sentence_id
                        }
                        yield f"event: audio_frame\ndata: {json.dumps(frame_msg)}\n\n"
                        await manager.add_audio_frame(audio_frame)
                        frame_index += 1
                        audio_metrics['frames_generated'] += 1
                except Exception as e:
                    logger.error(f"[{request_id}] Final sentence audio failed: {e}", exc_info=True)

            await manager.end_streaming()

            # Build final response with citations and metadata
            citations_data = final_state.get("citations", [])
            sources = final_state.get("sources", [])

            api_citations = []
            for i, citation in enumerate(citations_data, 1):
                if isinstance(citation, dict):
                    api_citations.append({
                        "source": citation.get("source", f"source_{i}"),
                        "raw_text": citation.get("raw_text", citation.get("text", "")),
                        "position": citation.get("position", i),
                        "context": citation.get("context", "")
                    })

            # Build metadata
            total_time = (time.time() - start_time) * 1000
            component_latencies = final_state.get("component_latencies", {})
            selected_path = final_state.get("selected_path", "unknown")

            if selected_path == "fast":
                results_used = len(final_state.get("vector_results", []))
            else:
                results_used = len(final_state.get("reranked_results", []))

            metadata = {
                "total_latency_ms": total_time,
                "llm_latency_ms": component_latencies.get("generate_fast", 0) +
                                 component_latencies.get("generate_standard", 0) +
                                 component_latencies.get("react_finalize", 0),
                "retrieval_latency_ms": component_latencies.get("retrieve_vector", 0) +
                                      component_latencies.get("retrieve_graph", 0) +
                                      component_latencies.get("retrieve_memory", 0),
                "path": selected_path,
                "routing_confidence": final_state.get("routing_confidence", 0.0),
                "routing_reasoning": final_state.get("routing_reasoning", ""),
                "llm_model": final_state.get("llm_tokens", {}).get("model", "unknown"),
                "llm_provider": "groq",
                "llm_tokens": final_state.get("llm_tokens", {}),
                "profile_id": chat_request.profile_id,
                "results_used": results_used,
                "citation_count": len(api_citations),
                "unique_sources": len(set(sources)),
                "reranking_strategy": final_state.get("reranking_strategy"),
                "trace_id": request_id,
                "langsmith_run_id": final_state.get("langsmith_run_id"),
                "audio_frames": audio_metrics['frames_generated'],
                "audio_segments": audio_metrics['audio_segments'],
                "conversation_engine": used_conversation_engine,
                "streaming_method": "generate_stream_with_prompts" if used_conversation_engine else "generate_stream"
            }

            # Add ReAct metadata if agentic path
            if selected_path == "agentic":
                react_steps = final_state.get("react_steps", [])
                metadata["react_steps"] = len(react_steps)
                metadata["context_quality"] = final_state.get("react_confidence", 0.0)

            # Send complete event
            logger.info(f"[{request_id}] 🗣️ Complete response text: {full_response}")
            complete_data = {
                "success": True,
                "answer": full_response,
                "citations": api_citations,
                "sources": sources,
                "metadata": metadata,
                "request_id": request_id
            }
            yield f"event: complete\ndata: {json.dumps(complete_data)}\n\n"

            # Update conversation_history after audio streaming (multi-turn continuity)
            if full_response and hasattr(request.app.state, 'langgraph_workflow'):
                try:
                    updated_history = initial_state.get("conversation_history", []).copy()
                    updated_history.append({"role": "user", "content": chat_request.query})
                    updated_history.append({"role": "assistant", "content": full_response})

                    workflow.update_state(
                        config,
                        {"conversation_history": updated_history}
                    )
                    logger.info(f"[{request_id}] ✅ Updated conversation_history after audio streaming: {len(updated_history)} messages")
                except Exception as hist_e:
                    logger.warning(f"[{request_id}] Failed to update conversation_history: {hist_e}")

        except asyncio.CancelledError:
            logger.warning(f"[{request_id}] Audio stream cancelled")
            
            # If interrupted by user cancellation, force stop speaking immediately
            if video_client:
                logger.info(f"[{request_id}] Stream cancelled - forcing stop speaking")
                await video_client.stop_speaking()
                
            await manager.clear_buffers()
            yield f"event: cancelled\ndata: {json.dumps({'message': 'Stream cancelled'})}\n\n"
        except Exception as e:
            logger.error(f"[{request_id}] ❌ Audio streaming failed: {e}", exc_info=True)
            await manager.handle_error(e)
            error_data = {"error": str(e), "request_id": request_id}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"
        finally:
            # Cleanup
            if session_id in request.app.state.active_sessions:
                del request.app.state.active_sessions[session_id]
            
            if video_client:
                # Only force stop calling if explicitly interrupted via manager
                if manager.is_interrupted():
                    logger.info(f"[{request_id}] Interrupted logic triggered - forcing stop speaking")
                    await video_client.stop_speaking()
                
                # PERSISTENCE CHANGE: Do NOT disconnect here.
                # Keep the connection open for the next request.
                # await video_client.disconnect()
                
            await manager.disconnect()

    return StreamingResponse(
        audio_event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ============================================================================
# NATURAL SPEECH AUDIO ENDPOINT (with speaking patterns from YouTube)
# ============================================================================

@router.post("/chat/stream-audio-natural")
async def langgraph_chat_stream_audio_natural(
    request: Request,
    chat_request: ChatRequest
):
    """
    LangGraph-powered streaming chat with NATURAL speaking style + audio.

    Same as /chat/stream-audio but uses natural speaking patterns from YouTube
    transcripts (fillers, verbal tics, conversational expressions).

    **Use cases:**
    - Video avatar conversations
    - Meeting avatar (Recall.ai bot)
    - Any audio interface where natural speech is preferred

    **Speaking patterns included (Japanese primary):**
    - Fillers: あの, ま, まあ, なんか
    - Connectors: っていう風に, っていうのは
    - Intensifiers: むちゃくちゃ, 本当に
    - Enthusiasm: ワクワク, いいですね！
    - Humility: まだまだ, 正直に言うと

    **Audio format:** Same as /chat/stream-audio (24kHz, 16-bit PCM, mono)
    """
    # Set audio_mode flag on request state for downstream use
    request.state.audio_mode = True

    # Forward to the main stream-audio endpoint
    # The endpoint will check request.state.audio_mode
    return await langgraph_chat_stream_audio(request, chat_request)


# ============================================================================
# WORKFLOW VISUALIZATION ENDPOINT
# ============================================================================

@router.get("/workflow/visualization")
async def get_workflow_visualization(request: Request):
    """
    Get Mermaid diagram of LangGraph workflow
    
    Returns a Mermaid diagram that can be rendered in tools like:
    - Mermaid Live Editor (https://mermaid.live)
    - GitHub markdown (rendered automatically)
    - Obsidian (with Mermaid plugin)
    - VS Code (with Mermaid extension)
    
    **Response:**
    ```json
    {
        "format": "mermaid",
        "diagram": "graph TD\n  start --> analyze_query\n  ..."
    }
    ```
    
    **Usage:**
    1. Copy diagram text
    2. Paste into Mermaid Live Editor
    3. View visual workflow DAG
    """
    try:
        # Get workflow from app state
        if not hasattr(request.app.state, 'langgraph_workflow'):
            raise HTTPException(
                status_code=503,
                detail="LangGraph workflow not initialized"
            )
        
        workflow = request.app.state.langgraph_workflow
        
        # Generate Mermaid diagram
        mermaid_diagram = visualize_workflow(workflow)
        
        return JSONResponse({
            "success": True,
            "format": "mermaid",
            "diagram": mermaid_diagram,
            "viewer_urls": {
                "mermaid_live": "https://mermaid.live",
                "github": "Paste in GitHub markdown file",
                "obsidian": "Use Mermaid plugin"
            }
        })
        
    except Exception as e:
        logger.error(f"Workflow visualization failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Visualization generation failed: {str(e)}"
        )


@router.get("/workflow/structure")
async def get_workflow_structure(request: Request):
    """
    Get structured workflow information
    
    Returns detailed information about workflow nodes, edges, and paths.
    Useful for debugging and documentation.
    
    **Response:**
    ```json
    {
        "nodes": ["analyze_query", "route_query", ...],
        "edges": [
            {"from": "analyze_query", "to": "route_query"},
            ...
        ],
        "paths": {
            "fast": ["analyze_query", "route_query", "retrieve_vector_fast", ...],
            "standard": [...],
            "agentic": [...]
        },
        "entry_point": "analyze_query"
    }
    ```
    """
    try:
        if not hasattr(request.app.state, 'langgraph_workflow'):
            raise HTTPException(
                status_code=503,
                detail="LangGraph workflow not initialized"
            )
        
        # Get workflow graph structure
        workflow = request.app.state.langgraph_workflow
        graph = workflow.get_graph()
        
        # Extract nodes
        nodes = list(graph.nodes.keys())
        
        # Extract edges
        edges = []
        for node_name, node_data in graph.nodes.items():
            # Get outgoing edges
            if hasattr(node_data, 'edges'):
                for target in node_data.edges:
                    edges.append({
                        "from": node_name,
                        "to": target,
                        "type": "direct"
                    })
        
        # Define paths (manual for clarity)
        paths = {
            "fast": [
                "analyze_query",
                "route_query",
                "retrieve_vector_fast",
                "generate_fast",
                "END"
            ],
            "standard": [
                "analyze_query",
                "route_query",
                "retrieve_vector_standard",
                "retrieve_graph_standard",
                "retrieve_memory_standard",
                "fuse_results_standard",
                "rerank_results_standard",
                "generate_standard",
                "END"
            ],
            "agentic": [
                "analyze_query",
                "route_query",
                "retrieve_vector_agentic",
                "retrieve_graph_agentic",
                "retrieve_memory_agentic",
                "fuse_results_agentic",
                "rerank_results_agentic",
                "react_think",
                "react_act",
                "react_observe",
                "[conditional: continue → react_think OR finalize → react_finalize]",
                "react_finalize",
                "END"
            ]
        }
        
        return JSONResponse({
            "success": True,
            "nodes": nodes,
            "node_count": len(nodes),
            "edges": edges,
            "edge_count": len(edges),
            "paths": paths,
            "entry_point": "analyze_query",
            "workflow_type": "StateGraph",
            "state_schema": "RAGState"
        })
        
    except Exception as e:
        logger.error(f"Workflow structure retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Structure retrieval failed: {str(e)}"
        )


# ============================================================================
# WORKFLOW STATE INSPECTION (Debug Endpoint)
# ============================================================================

@router.post("/workflow/inspect-state")
async def inspect_workflow_state(
    request: Request,
    chat_request: ChatRequest
):
    """
    Inspect workflow state at each node (DEBUG ENDPOINT)
    
    Executes workflow and returns state after each node for debugging.
    **WARNING:** This is expensive and should only be used for debugging.
    
    **Response:**
    ```json
    {
        "states": {
            "after_analyze_query": {...},
            "after_route_query": {...},
            ...
        },
        "final_state": {...},
        "execution_path": ["analyze_query", "route_query", ...]
    }
    ```
    """
    # Only enable in development/debug mode
    if not os.getenv("DEBUG", "false").lower() == "true":
        raise HTTPException(
            status_code=403,
            detail="State inspection only available in DEBUG mode"
        )
    
    try:
        workflow = request.app.state.langgraph_workflow

        # Normalize profile ID to database format
        from profile_management.profile_id_mapper import normalize_profile_id
        profile_id = normalize_profile_id(chat_request.profile_id or "sample_profile")

        # Determine if ConversationEngine should be used
        request_id = getattr(request.state, 'request_id', 'inspect')
        use_conv_engine = should_use_conversation_engine(request_id)

        # Create initial state with normalized profile_id
        initial_state = get_default_state(
            query=chat_request.query,
            user_id=chat_request.user_id,
            user_role=chat_request.user_role,
            profile_id=profile_id,  # Use normalized database ID
            company_id=resolve_company_id(chat_request.company_id, chat_request.user_role),
            enable_evaluation=getattr(chat_request, 'enable_evaluation', False),
            use_conversation_engine=use_conv_engine
        )
        
        # Execute with state tracking
        states_history = {}
        execution_path = []
        
        # Note: This is a simplified version - real implementation would need
        # to hook into LangGraph's execution to capture intermediate states
        # FIX: Use ainvoke() for async checkpointer compatibility
        final_state = await workflow.ainvoke(initial_state)
        
        return JSONResponse({
            "success": True,
            "warning": "State inspection is expensive - use sparingly",
            "final_state_keys": list(final_state.keys()),
            "selected_path": final_state.get("selected_path"),
            "execution_summary": {
                "query": chat_request.query,
                "path": final_state.get("selected_path"),
                "routing_confidence": final_state.get("routing_confidence"),
                "vector_results_count": len(final_state.get("vector_results", [])),
                "fused_results_count": len(final_state.get("fused_results", [])),
                "reranked_results_count": len(final_state.get("reranked_results", [])),
                "react_iterations": len(final_state.get("react_steps", [])),
                "llm_response_length": len(final_state.get("llm_response", "")),
                "citations_count": len(final_state.get("citations", []))
            }
        })
        
    except Exception as e:
        logger.error(f"State inspection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"State inspection failed: {str(e)}"
        )
