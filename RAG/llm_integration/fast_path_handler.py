"""
Fast Path Handler for LLM Integration

Optimized for speed: <1.5s response time
- Uses top 5 vector results only
- No precedents or graph context
- Includes memory for continuity
- Concise responses
"""

from typing import Dict, Any, List
import logging
import time

from .base_client import BaseLLMClient, LLMMessage
from .prompt_builder_two_stage import TwoStagePromptBuilder, RetrievalContext
from .prompt_builder_dual_stream import DualStreamPromptBuilder
from .response_formatter import ResponseFormatter, FormattedResponse
from api.config import settings

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
obs_logger = StructuredLogger('fast_path_handler')


class FastPathHandler:
    """
    Fast path handler for quick factual queries.
    
    Target latency: 0.8-1.5 seconds
    Use cases: "What is...", "Who is...", "Define..."
    """
    
    def __init__(
        self,
        llm_client: BaseLLMClient,
        profile_id: str,
        config: Dict[str, Any]
    ):
        """
        Initialize fast path handler.
        
        Args:
            llm_client: LLM client instance
            profile_id: Executive profile ID
            config: Path-specific configuration
        """
        self.llm_client = llm_client
        self.profile_id = profile_id
        self.config = config

        # Initialize prompt builder (dual-stream or two-stage)
        use_dual_stream = settings.DUAL_STREAM_ENABLED

        if use_dual_stream:
            logger.info(f"[FastPathHandler] Using DualStreamPromptBuilder for {profile_id}")
            self.prompt_builder = DualStreamPromptBuilder(
                profile_id=profile_id,
                path="fast"
            )
        else:
            logger.info(f"[FastPathHandler] Using TwoStagePromptBuilder for {profile_id}")
            self.prompt_builder = TwoStagePromptBuilder(
                profile_id=profile_id,
                path="fast",
                enable_compression=True,        # Stage 1.5A: 77% token reduction
                enable_fact_extraction=False    # Stage 1.5B disabled (experimental)
            )

        self.response_formatter = ResponseFormatter(
            citation_style=config.get("citation_style", "inline")
        )
        
        logger.debug(f"Initialized FastPathHandler for {profile_id}")
        obs_logger.info(
            "FastPathHandler initialized",
            profile_id=profile_id,
            path="fast"
        )
    
    @trace_function("fast_path_handler", "handle_query")
    @traceable(name="fast_path_handler", tags=["llm", "path", "fast"])
    def handle(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        memory: List[Dict[str, Any]] = None,
        conversation_history: List[Dict[str, Any]] = None,
        language: str = "en"
    ) -> FormattedResponse:
        """
        Handle query using fast path.

        Args:
            query: User's question
            vector_results: Vector search results
            memory: Episodic memory from past sessions
            conversation_history: Current session conversation turns
            language: Response language preference (en or ja)

        Returns:
            FormattedResponse with answer
        """
        start_time = time.time()
        
        logger.info(f"Fast path handling query: {query[:50]}... (language={language})")
        obs_logger.info(
            "Fast path query started",
            query_length=len(query),
            vector_results_count=len(vector_results),
            has_memory=memory is not None and len(memory) > 0
        )
        
        # 1. Prepare context (top 5 results only)
        max_results = self.config.get("max_results", 5)
        context = RetrievalContext(
            vector_results=vector_results[:max_results],
            memory=memory or [],
            conversation_history=conversation_history or [],
            query=query
        )

        # 2. Build prompts with language preference
        system_prompt, user_prompt = self.prompt_builder.build_full_prompt(
            query, context, language=language
        )
        
        # 3. Create messages
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]
        
        # 4. Generate response
        llm_start = time.time()
        llm_response = self.llm_client.generate(messages)
        llm_latency_ms = (time.time() - llm_start) * 1000
        
        # Track LLM usage and cost
        if llm_response.usage:
            cost = CostTracker.track_llm_usage(
                model=llm_response.model,
                prompt_tokens=llm_response.usage.get('prompt_tokens', 0),
                completion_tokens=llm_response.usage.get('completion_tokens', 0),
                path="fast",
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
                path='fast'
            ).inc(cost)
            
            llm_latency.labels(model=llm_response.model).observe(llm_latency_ms / 1000)
            
            obs_logger.info(
                "LLM generation completed",
                model=llm_response.model,
                prompt_tokens=llm_response.usage.get('prompt_tokens', 0),
                completion_tokens=llm_response.usage.get('completion_tokens', 0),
                total_tokens=llm_response.usage.get('total_tokens', 0),
                cost_usd=cost,
                llm_latency_ms=llm_latency_ms
            )
        
        # 5. Format response
        formatted = self.response_formatter.format_response(
            llm_response.content,
            retrieval_context={"vector_results": vector_results}
        )
        
        # 6. Add metadata
        total_time = (time.time() - start_time) * 1000
        formatted.metadata.update({
            "path": "fast",
            "total_latency_ms": total_time,
            "llm_latency_ms": llm_response.latency_ms,
            "llm_tokens": llm_response.usage,
            "llm_model": llm_response.model,
            "results_used": len(context.vector_results),
            "target_latency_ms": self.config.get("target_latency_ms", 1500)
        })
        
        # Check latency target
        target = self.config.get("target_latency_ms", 1500)
        exceeded_target = total_time > target
        
        if exceeded_target:
            logger.warning(
                f"Fast path exceeded target latency: {total_time:.0f}ms > {target}ms"
            )
            obs_logger.warning(
                "Fast path exceeded target latency",
                total_latency_ms=total_time,
                target_latency_ms=target,
                exceeded_by_ms=total_time - target
            )
        else:
            logger.info(
                f"Fast path completed in {total_time:.0f}ms "
                f"(target: {target}ms)"
            )
        
        # Log completion
        obs_logger.info(
            "Fast path query completed",
            total_latency_ms=total_time,
            llm_latency_ms=llm_latency_ms,
            target_latency_ms=target,
            exceeded_target=exceeded_target,
            response_length=len(formatted.content),
            citations_count=len(formatted.citations),
            results_used=len(context.vector_results)
        )
        
        # Track request completion
        llm_requests_counter.labels(
            model=llm_response.model,
            path='fast',
            status='success'
        ).inc()
        
        return formatted
