"""
Agentic Path Handler for LLM Integration

Comprehensive analysis: <5s response time
- Uses up to 15 vector results
- Full graph context and precedents
- Deep analytical reasoning
- ReAct loop for multi-hop reasoning
"""

from typing import Dict, Any, List, Optional, Tuple
import logging
import time
import json
import re
from dataclasses import dataclass
from enum import Enum

from .base_client import BaseLLMClient, LLMMessage
from .prompt_builder_two_stage import TwoStagePromptBuilder, RetrievalContext
from .prompt_builder_dual_stream import DualStreamPromptBuilder
from .response_formatter import ResponseFormatter, FormattedResponse
from .react_reasoning import ReActReasoner, ReActState, ReActStep
from .tools import get_tool_registry, create_tool_context
from .document_summarizer import DocumentSummarizer
from api.config import settings
# Import from centralized rules - SINGLE SOURCE OF TRUTH
from conversation_engine.prompt.rules import get_word_limit_instruction

# Observability imports
from observability.decorators import trace_function
from observability.logging import StructuredLogger
from observability.cost_tracker import CostTracker
from observability.metrics import (
    llm_tokens_counter,
    llm_cost_counter,
    llm_latency,
    llm_requests_counter,
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

logger = logging.getLogger(__name__)
obs_logger = StructuredLogger('agentic_path_handler')


class AgenticPathHandler:
    """
    Agentic path handler for complex analytical queries.
    
    Target latency: 3-5 seconds
    Use cases: "Compare...", "Analyze...", "Evaluate trade-offs..."
    Implements ReAct loop for iterative reasoning
    """
    
    def __init__(
        self,
        llm_client: BaseLLMClient,
        profile_id: str,
        config: Dict[str, Any],
        hybrid_retrieval_manager: Optional[Any] = None
    ):
        """
        Initialize agentic path handler.
        
        Args:
            llm_client: LLM client instance
            profile_id: Executive profile ID
            config: Path-specific configuration
            hybrid_retrieval_manager: Optional hybrid retrieval manager for tool actions
        """
        self.llm_client = llm_client
        self.profile_id = profile_id
        self.config = config
        self.hybrid_retrieval_manager = hybrid_retrieval_manager

        # Initialize prompt builder (dual-stream or two-stage)
        use_dual_stream = settings.DUAL_STREAM_ENABLED

        if use_dual_stream:
            logger.info(f"[AgenticPathHandler] Using DualStreamPromptBuilder for {profile_id}")
            self.prompt_builder = DualStreamPromptBuilder(
                profile_id=profile_id,
                path="agentic"
            )
        else:
            logger.info(f"[AgenticPathHandler] Using TwoStagePromptBuilder for {profile_id}")
            self.prompt_builder = TwoStagePromptBuilder(
                profile_id=profile_id,
                path="agentic",
                enable_compression=True,        # Stage 1.5A: 77% token reduction
                enable_fact_extraction=False    # Stage 1.5B disabled (experimental)
            )

        self.response_formatter = ResponseFormatter(
            citation_style=config.get("citation_style", "inline")
        )

        # Initialize document summarizer for token budget management
        self.summarizer = DocumentSummarizer(
            max_summary_tokens=config.get("max_summary_tokens", 150)
        )

        # ReAct loop configuration
        self.multi_hop_enabled = config.get("multi_hop_enabled", True)
        self.max_react_steps = config.get("max_react_steps", 5)
        self.react_confidence_threshold = config.get("react_confidence_threshold", 0.7)
        self.enable_tool_integration = config.get("enable_tool_integration", True)
        
        # Performance tracking
        self.react_metrics = {
            "total_queries": 0,
            "react_loops_executed": 0,
            "average_steps_per_query": 0,
            "average_confidence": 0
        }
        
        logger.debug(f"Initialized AgenticPathHandler for {profile_id} with ReAct enabled: {self.multi_hop_enabled}")
        obs_logger.info(
            "AgenticPathHandler initialized",
            profile_id=profile_id,
            path="agentic",
            multi_hop_enabled=self.multi_hop_enabled,
            max_react_steps=self.max_react_steps
        )
    
    @trace_function("agentic_path_handler", "handle_query")
    @traceable(name="agentic_path_handler", tags=["llm", "path", "agentic", "react"])
    def handle(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        graph_results: Optional[List[Dict[str, Any]]] = None,
        precedents: Optional[List[Dict[str, Any]]] = None,
        memory: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        language: str = "en"
    ) -> FormattedResponse:
        """
        Handle query using agentic path.

        Args:
            query: User's question
            vector_results: Vector search results
            graph_results: Knowledge graph context
            precedents: Historical similar queries
            memory: Episodic memory from past sessions
            conversation_history: Current session conversation turns
            language: Response language preference (en or ja)

        Returns:
            FormattedResponse with comprehensive analytical answer
        """
        start_time = time.time()

        logger.info(f"Agentic path handling query: {query[:50]}... (language={language})")
        obs_logger.info(
            "Agentic path query started",
            query_length=len(query),
            vector_results_count=len(vector_results),
            has_graph=graph_results is not None and len(graph_results) > 0,
            has_precedents=precedents is not None and len(precedents) > 0,
            has_memory=memory is not None and len(memory) > 0,
            multi_hop_enabled=self.multi_hop_enabled
        )

        # 1. Summarize documents to fit token budget (prevents 413 errors)
        logger.info("Applying document summarization for token budget management")

        # Summarize vector results (main source of large context)
        if vector_results:
            logger.debug(f"Summarizing {len(vector_results)} vector results")
            vector_results = self.summarizer.summarize_documents(
                docs=vector_results,
                query=query,
                target_tokens_per_doc=300,  # Increased from 120 to preserve key details (¥amounts, metrics)
                max_docs=5  # Limit to top 5 docs
            )
            logger.info(f"Vector results summarized: {len(vector_results)} docs")

        # Summarize graph results if present
        if graph_results:
            logger.debug(f"Summarizing {len(graph_results)} graph results")
            graph_results = self.summarizer.summarize_documents(
                docs=graph_results,
                query=query,
                target_tokens_per_doc=200,  # Increased from 80 to preserve details
                max_docs=3
            )

        # 2. Prepare comprehensive context with summarized docs
        max_results = self.config.get("max_results", 15)
        context = RetrievalContext(
            vector_results=vector_results[:max_results],
            graph_results=graph_results[:10] if graph_results else None,
            precedents=precedents[:5] if precedents else None,
            memory=memory or [],
            conversation_history=conversation_history or [],
            query=query
        )

        # 2. Build prompts with analytical instructions and language preference
        system_prompt, user_prompt = self.prompt_builder.build_full_prompt(
            query, context, language=language
        )
        
        # Add extra analytical instructions
        user_prompt = self._enhance_prompt_for_analysis(user_prompt, query)
        
        # 3. Create messages
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        # 4. Generate response (potentially with ReAct loop in future)
        if self.multi_hop_enabled:
            # Create tool context with hybrid retrieval manager
            from .tools import create_tool_context
            from .react_reasoning import ReActReasoner
            from .tools import get_tool_registry
            
            # Get tool registry
            tool_registry = get_tool_registry()
            tools = tool_registry.get_all_tools()
            
            # Create ReAct reasoner with tools
            react_reasoner = ReActReasoner(
                llm_client=self.llm_client,
                tools=tools,
                config={
                    "max_steps": self.max_react_steps,
                    "confidence_threshold": self.react_confidence_threshold,
                    "context_window_limit": 16000,  # Increased from 8000 to allow more ReAct steps
                    "enable_tracing": True
                }
            )
            
            # Create tool context
            tool_context = create_tool_context(
                query=context.query,
                state=None,  # Will be created by ReActReasoner
                hybrid_retrieval_manager=self.hybrid_retrieval_manager,
                graph_context_provider=getattr(self.hybrid_retrieval_manager, 'graph', None),
                executive_id=self.profile_id
            )
            
            # Execute ReAct reasoning with initial context
            initial_context = {
                "vector_results": context.vector_results,
                "graph_results": context.graph_results,
                "precedents": context.precedents,
                "memory": context.memory
            }
            
            final_answer, metadata = react_reasoner.reason(
                query=context.query,
                initial_context=initial_context,
                system_prompt=system_prompt  # Pass executive persona for final answer
            )
            
            # Create LLM response from ReAct result
            from .base_client import LLMResponse
            llm_response = LLMResponse(
                content=final_answer,
                model=self.llm_client.get_model_name(),
                finish_reason="stop",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                latency_ms=metadata.get("react_processing_time_ms", 0),
                provider=self.llm_client.provider_name
            )
            
            # Add ReAct metadata to response
            if not hasattr(llm_response, 'metadata'):
                llm_response.metadata = {}
            llm_response.metadata.update(metadata)
        else:
            llm_start = time.time()
            llm_response = self.llm_client.generate(messages)
            llm_latency_ms = (time.time() - llm_start) * 1000
            
            # Track LLM usage and cost
            if llm_response.usage:
                cost = CostTracker.track_llm_usage(
                    model=llm_response.model,
                    prompt_tokens=llm_response.usage.get('prompt_tokens', 0),
                    completion_tokens=llm_response.usage.get('completion_tokens', 0),
                    path="agentic",
                    executive_id=self.profile_id
                )
                
                # Track metrics
                llm_tokens_counter.labels(
                    model=llm_response.model,
                    token_type='prompt'
                ).inc(llm_response.usage.get('prompt_tokens', 0))
                
                llm_tokens_counter.labels(
                    model=llm_response.model,
                    token_type='completion'
                ).inc(llm_response.usage.get('completion_tokens', 0))
                
                llm_cost_counter.labels(
                    model=llm_response.model,
                    path='agentic'
                ).inc(cost)
                
                llm_latency.labels(model=llm_response.model).observe(llm_latency_ms / 1000)
                
                obs_logger.info(
                    "LLM generation completed",
                    model=llm_response.model,
                    prompt_tokens=llm_response.usage.get('prompt_tokens', 0),
                    completion_tokens=llm_response.usage.get('completion_tokens', 0),
                    total_tokens=llm_response.usage.get('total_tokens', 0),
                    cost_usd=cost,
                    llm_latency_ms=llm_latency_ms,
                    multi_hop_used=False
                )
        
        # 5. Format response
        formatted = self.response_formatter.format_response(
            llm_response.content,
            retrieval_context={
                "vector_results": vector_results,
                "graph_results": graph_results,
                "precedents": precedents
            }
        )
        
        # 6. Add metadata
        total_time = (time.time() - start_time) * 1000
        formatted.metadata.update({
            "path": "agentic",
            "total_latency_ms": total_time,
            "llm_latency_ms": llm_response.latency_ms,
            "llm_tokens": llm_response.usage,
            "llm_model": llm_response.model,
            "results_used": len(context.vector_results),
            "graph_context_used": len(context.graph_results) if context.graph_results else 0,
            "precedents_used": len(context.precedents) if context.precedents else 0,
            "multi_hop_used": self.multi_hop_enabled,
            "target_latency_ms": self.config.get("target_latency_ms", 5000)
        })
        
        # Preserve ReAct metadata if available (Fix: Add ReAct steps to response)
        if hasattr(llm_response, 'metadata') and llm_response.metadata:
            if 'react_steps' in llm_response.metadata:
                formatted.metadata['react_steps'] = llm_response.metadata['react_steps']
            if 'react_processing_time_ms' in llm_response.metadata:
                formatted.metadata['react_processing_time_ms'] = llm_response.metadata['react_processing_time_ms']
            if 'react_step_count' in llm_response.metadata:
                formatted.metadata['react_step_count'] = llm_response.metadata['react_step_count']
        
        # Check latency target
        target = self.config.get("target_latency_ms", 5000)
        exceeded_target = total_time > target
        
        if exceeded_target:
            logger.warning(
                f"Agentic path exceeded target latency: {total_time:.0f}ms > {target}ms"
            )
            obs_logger.warning(
                "Agentic path exceeded target latency",
                total_latency_ms=total_time,
                target_latency_ms=target,
                exceeded_by_ms=total_time - target
            )
        else:
            logger.info(
                f"Agentic path completed in {total_time:.0f}ms "
                f"(target: {target}ms)"
            )
        
        # Log completion
        obs_logger.info(
            "Agentic path query completed",
            total_latency_ms=total_time,
            llm_latency_ms=llm_response.latency_ms,
            target_latency_ms=target,
            exceeded_target=exceeded_target,
            response_length=len(formatted.content),
            citations_count=len(formatted.citations),
            results_used=len(context.vector_results),
            graph_results_used=len(context.graph_results) if context.graph_results else 0,
            precedents_used=len(context.precedents) if context.precedents else 0,
            multi_hop_used=self.multi_hop_enabled
        )
        
        # Track request completion
        llm_requests_counter.labels(
            model=llm_response.model,
            path='agentic',
            status='success'
        ).inc()
        
        return formatted
    
    def _enhance_prompt_for_analysis(self, base_prompt: str, query: str) -> str:
        """
        Enhance prompt with analytical instructions.

        Args:
            base_prompt: Base user prompt
            query: Original query

        Returns:
            Enhanced prompt with analytical guidance
        """
        # Use centralized word limits from rules.py
        word_limit = get_word_limit_instruction("agentic")

        analytical_instructions = f"""

ANALYTICAL APPROACH:
For complex queries, think through the problem conversationally:
- Start with your main insight or recommendation
- Walk through the key factors that shaped your thinking
- Reference specific past decisions or precedents naturally
- If recommending action, explain the trade-offs you considered

{word_limit}
Write like you're talking to a colleague, NOT writing a formal report.
DO NOT use bold headers, numbered sections, or emoji markers. Just natural conversational paragraphs."""

        return base_prompt + analytical_instructions
    
    def _react_loop(
        self,
        initial_messages: List[LLMMessage],
        context: RetrievalContext
    ):
        """
        ReAct loop for iterative reasoning using the ReActReasoner.
        
        Implements the Thought-Act-Observe pattern for multi-hop reasoning:
        1. Generate initial thought about the query
        2. Determine action type (search/analyze/compare/finalize)
        3. Execute action using hybrid search tools
        4. Observe results and build context
        5. Reason about next step based on observations
        6. Continue until sufficient information gathered or max steps reached
        7. Generate final comprehensive answer
        
        Args:
            initial_messages: Initial conversation messages
            context: Retrieval context with initial search results
            
        Returns:
            LLM response with comprehensive multi-hop reasoning
        """
        start_time = time.time()
        
        logger.info(f"Starting ReAct loop for query: {context.query[:50]}...")
        
        # Prepare initial context for ReAct reasoner
        initial_context = {
            "vector_results": context.vector_results.copy(),
            "graph_results": context.graph_results.copy() if context.graph_results else [],
            "precedents": context.precedents.copy() if context.precedents else [],
            "memory": context.memory.copy() if context.memory else []
        }
        
        # Initialize ReAct reasoner with tools
        tool_registry = get_tool_registry()
        tools = tool_registry.get_all_tools()
        
        # Create ReAct reasoner with configuration
        react_reasoner = ReActReasoner(
            llm_client=self.llm_client,
            tools=tools,
            config={
                "max_steps": self.max_react_steps,
                "confidence_threshold": self.react_confidence_threshold,
                "context_window_limit": 8000,
                "enable_tracing": True
            }
        )
        
        # Execute ReAct reasoning
        final_answer, metadata = react_reasoner.reason(
            query=context.query,
            initial_context=initial_context
        )
        
        # Create LLM response with ReAct metadata
        from .base_client import LLMResponse
        final_response = LLMResponse(
            content=final_answer,
            model=self.llm_client.get_model_name(),
            finish_reason="stop",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},  # Would be populated by actual LLM call
            latency_ms=(time.time() - start_time) * 1000,
            provider=self.llm_client.provider_name
        )
        
        # Add ReAct metadata to response
        if not hasattr(final_response, 'metadata'):
            final_response.metadata = {}
        
        final_response.metadata.update({
            "react_steps": metadata.get("react_steps", 0),
            "react_processing_time_ms": metadata.get("react_processing_time_ms", 0),
            "react_confidence": metadata.get("react_confidence", 0),
            "react_actions": metadata.get("react_actions", []),
            "accumulated_findings": metadata.get("accumulated_findings", []),
            "sources_used": metadata.get("sources_used", [])
        })
        
        # Update metrics
        self._update_react_metrics_from_metadata(metadata)
        
        logger.info(
            f"ReAct loop completed in {metadata.get('react_steps', 0)} steps, "
            f"{metadata.get('react_processing_time_ms', 0):.0f}ms total"
        )
        
        return final_response

    
    def _generate_thought_and_action(
        self,
        react_state: ReActState,
        original_query: str
    ) -> Tuple[str, Any, str, float]:
        """
        Generate thought and determine next action using LLM.
        
        This method is now handled by the ReActReasoner class.
        
        Args:
            react_state: Current ReAct state
            original_query: Original user query
            
        Returns:
            Tuple of (thought, action_type, action_query, confidence)
        """
        # This method is now handled by ReActReasoner
        # Keeping for backward compatibility but not used
        return "Thought generated by ReActReasoner", None, "", 0.5
    
    def _execute_react_action(
        self,
        action_type: Any,
        action_query: str,
        react_state: ReActState
    ) -> Tuple[str, List[str]]:
        """
        Execute the determined action using appropriate tools.
        
        This method is now handled by the ReActReasoner class.
        
        Args:
            action_type: Type of action to execute
            action_query: Query for the action
            react_state: Current ReAct state
            
        Returns:
            Tuple of (observation, sources_used)
        """
        # This method is now handled by ReActReasoner
        # Keeping for backward compatibility but not used
        return "Action executed by ReActReasoner", []
    
    def _parse_react_response(self, response: str) -> Tuple[str, Any, str, float]:
        """
        Parse LLM response to extract thought, action, action_query, and confidence.
        
        This method is now handled by the ReActReasoner class.
        
        Args:
            response: LLM response text
            
        Returns:
            Tuple of (thought, action_type, action_query, confidence)
        """
        # This method is now handled by ReActReasoner
        # Keeping for backward compatibility but not used
        return "Response parsed by ReActReasoner", None, "", 0.5
    
    def _build_react_context_summary(self, react_state: ReActState) -> str:
        """Build a summary of ReAct context for the LLM"""
        if not react_state.steps:
            return "No previous steps. This is the initial analysis."
        
        summary_lines = []
        for step in react_state.steps[-3:]:  # Show last 3 steps
            summary_lines.append(
                f"Step {step.step_number}: {step.thought}\n"
                f"Action: {step.action_type.value} - {step.action_query}\n"
                f"Observation: {step.observation[:200]}...\n"
                f"Confidence: {step.confidence:.2f}\n"
            )
        
        return "\n".join(summary_lines)
    
    def _format_search_results(self, search_results: Dict) -> str:
        """Format search results for observation"""
        results = search_results.get("results", [])
        if not results:
            return "No additional information found."
        
        formatted = []
        for i, result in enumerate(results[:3], 1):
            title = result.get("title", "Untitled")
            content = result.get("content", "")[:200]
            score = result.get("final_score", 0.0)
            formatted.append(f"{i}. {title} (relevance: {score:.2f})\n{content}...")
        
        return f"Found {len(results)} relevant results:\n" + "\n".join(formatted)
    
    def _analyze_existing_context(self, action_query: str, react_state: ReActState) -> str:
        """Analyze existing context based on action query"""
        vector_results = react_state.accumulated_context["vector_results"]
        if not vector_results:
            return "No context available for analysis."
        
        # Simple analysis based on available documents
        relevant_docs = []
        for doc in vector_results[:5]:
            title = doc.get("title", "")
            content = doc.get("content", "")[:150]
            relevant_docs.append(f"- {title}: {content}...")
        
        return f"Analysis of '{action_query}' based on {len(vector_results)} available documents:\n" + "\n".join(relevant_docs)
    
    def _compare_options(self, action_query: str, react_state: ReActState) -> str:
        """Compare options based on action query"""
        vector_results = react_state.accumulated_context["vector_results"]
        if len(vector_results) < 2:
            return "Insufficient information for comparison. Need at least 2 relevant documents."
        
        # Extract key points from top documents for comparison
        comparison_points = []
        for i, doc in enumerate(vector_results[:3], 1):
            title = doc.get("title", f"Document {i}")
            content = doc.get("content", "")[:150]
            comparison_points.append(f"Option {i} ({title}): {content}...")
        
        return f"Comparison for '{action_query}':\n" + "\n\n".join(comparison_points)
    
    def _update_accumulated_context(self, react_state: ReActState, step: ReActStep):
        """Update accumulated context with new step information"""
        # Add to intermediate findings
        finding = {
            "step": step.step_number,
            "action": step.action_type.value,
            "query": step.action_query,
            "observation": step.observation,
            "sources": step.sources_used
        }
        react_state.accumulated_context["intermediate_findings"].append(finding)
        
        # If search action, we would add new results to vector_results
        # For now, we just track the findings
        logger.debug(f"Updated accumulated context with step {step.step_number}")
    
    def _should_continue_react(self, react_state: ReActState, confidence: float) -> bool:
        """Determine if ReAct loop should continue"""
        # Stop if we reached max steps
        if react_state.current_step >= react_state.max_steps:
            return False
        
        # Stop if last action was finalize
        if react_state.steps and react_state.steps[-1].action_type == ReActActionType.FINALIZE:
            return False
        
        # Stop if confidence is high enough
        if confidence >= self.react_confidence_threshold:
            return False
        
        # Continue otherwise
        return True
    
    def _generate_final_answer(self, react_state: ReActState, initial_messages: List[LLMMessage]):
        """Generate final comprehensive answer based on all ReAct steps"""
        # This method is now handled by the ReActReasoner class
        # Keeping for backward compatibility but not used
        from .base_client import LLMResponse
        return LLMResponse(
            content="Final answer generated by ReActReasoner",
            model=self.llm_client.get_model_name(),
            finish_reason="stop",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            latency_ms=0,
            provider=self.llm_client.provider_name
        )
    
    def _update_react_metrics(self, react_state: ReActState):
        """Update ReAct performance metrics"""
        self.react_metrics["total_queries"] += 1
        self.react_metrics["react_loops_executed"] += 1
        
        if react_state.steps:
            avg_steps = self.react_metrics["average_steps_per_query"]
            total_queries = self.react_metrics["total_queries"]
            self.react_metrics["average_steps_per_query"] = (
                (avg_steps * (total_queries - 1) + len(react_state.steps)) / total_queries
            )
            
            avg_confidence = self.react_metrics["average_confidence"]
            step_confidence = sum(s.confidence for s in react_state.steps) / len(react_state.steps)
            self.react_metrics["average_confidence"] = (
                (avg_confidence * (total_queries - 1) + step_confidence) / total_queries
            )
    
    def _update_react_metrics_from_metadata(self, metadata: Dict[str, Any]):
        """Update ReAct performance metrics from ReActReasoner metadata"""
        self.react_metrics["total_queries"] += 1
        self.react_metrics["react_loops_executed"] += 1
        
        # Update metrics from metadata
        if "react_steps" in metadata:
            avg_steps = self.react_metrics["average_steps_per_query"]
            total_queries = self.react_metrics["total_queries"]
            self.react_metrics["average_steps_per_query"] = (
                (avg_steps * (total_queries - 1) + metadata["react_steps"]) / total_queries
            )
        
        if "react_confidence" in metadata:
            avg_confidence = self.react_metrics["average_confidence"]
            total_queries = self.react_metrics["total_queries"]
            self.react_metrics["average_confidence"] = (
                (avg_confidence * (total_queries - 1) + metadata["react_confidence"]) / total_queries
            )
    
    def get_react_metrics(self) -> Dict[str, Any]:
        """Get ReAct performance metrics"""
        return self.react_metrics.copy()
