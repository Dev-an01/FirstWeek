"""
LLM Integration Orchestrator

Coordinates the complete LLM integration flow:
1. Profile loading
2. Query routing
3. LLM client creation
4. Path handler selection
5. Response generation
"""

from typing import Dict, Any, List, Optional
import logging
import time

from config.llm_config_loader import get_config
from profile_management.profile_manager import get_profile_manager
from query_routing.router import QueryRouter
from .factory import LLMClientFactory
from .fast_path_handler import FastPathHandler
from .standard_path_handler import StandardPathHandler
from .agentic_path_handler import AgenticPathHandler
from .response_formatter import FormattedResponse
from conversation_engine.prompt.sections import InstructionsSection
from conversation_engine.prompt.rules import get_word_limit

# Observability imports
from observability.decorators import trace_function
from observability.logging import StructuredLogger
from observability.context import RequestContext
from observability.metrics import (
    llm_requests_counter,
    request_latency,
    routing_decisions_counter,
    handler_cache_hits_counter,
)
from observability.quality_evaluator import QualityEvaluator
from observability.db_persistence import store_quality_metrics, track_user_activity

logger = logging.getLogger(__name__)
obs_logger = StructuredLogger('llm_orchestrator')


class LLMOrchestrator:
    """
    Main orchestrator for LLM integration.
    
    Provides a simple interface for generating responses:
    orchestrator.generate(query, retrieval_results, profile_id)
    """
    
    def __init__(self, provider: Optional[str] = None, hybrid_retrieval_manager: Optional[Any] = None):
        """
        Initialize LLM orchestrator.
        
        Args:
            provider: LLM provider name (openai, glm, etc.)
                     If None, uses default from config
            hybrid_retrieval_manager: Optional hybrid retrieval manager for ReAct tool integration
        """
        # Load configuration
        self.config = get_config()
        self.provider = provider or self.config.active_provider
        
        # Initialize query router
        self.query_router = QueryRouter()
        
        # Initialize profile manager
        self.profile_manager = get_profile_manager()
        self.profile_manager.initialize()  # Load all profiles into memory
        
        # Cache for handlers (reuse across requests)
        self._handler_cache: Dict[str, Any] = {}
        
        # Store hybrid retrieval manager for ReAct integration
        self.hybrid_retrieval_manager = hybrid_retrieval_manager
        
        logger.info(f"Initialized LLMOrchestrator with provider={self.provider}")
        obs_logger.info(
            "LLMOrchestrator initialized",
            provider=self.provider,
            component="llm_orchestrator"
        )
    
    @trace_function("llm_orchestrator", "generate_response")
    def generate(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        profile_id: str = "akiko_tanaka",
        graph_results: Optional[List[Dict[str, Any]]] = None,
        precedents: Optional[List[Dict[str, Any]]] = None,
        memory: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        force_path: Optional[str] = None,
        query_analysis: Optional[Dict[str, Any]] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Generate a response using LLM integration.

        Args:
            query: User's question
            vector_results: Vector search results
            profile_id: Executive profile ID
            graph_results: Optional graph context
            precedents: Optional historical precedents
            memory: Optional episodic memory from past sessions
            conversation_history: Optional current session conversation turns
            force_path: Optional path override (fast/standard/agentic)
            query_analysis: Optional pre-analyzed query data
            language: Response language preference (en or ja)

        Returns:
            Dict with response, citations, metadata
        """
        start_time = time.time()
        
        # Set context for observability
        RequestContext.set('executive_id', profile_id)
        RequestContext.set('query_length', len(query))
        
        logger.info(f"Generating response for query: {query[:50]}...")
        obs_logger.info(
            "Response generation started",
            query_length=len(query),
            profile_id=profile_id,
            has_graph_results=graph_results is not None,
            has_precedents=precedents is not None,
            has_memory=memory is not None,
            forced_path=force_path
        )
        
        # 1. Route query (unless path is forced)
        if force_path:
            path = force_path
            routing_metadata = {"path": force_path, "forced": True}
            logger.info(f"Using forced path: {force_path}")
            obs_logger.info(
                "Using forced path",
                path=force_path,
                forced=True
            )
            # Track routing decision
            routing_decisions_counter.labels(path=force_path, forced="true").inc()
        else:
            route_decision = self.query_router.route(query, query_analysis)
            path = route_decision.path
            routing_metadata = {
                "path": route_decision.path,
                "confidence": route_decision.confidence,
                "reasoning": route_decision.reasoning,
                "features": route_decision.features
            }
            logger.info(f"Routed to {path} path: {route_decision.reasoning}")
            obs_logger.info(
                "Query routed",
                path=path,
                confidence=route_decision.confidence,
                reasoning=route_decision.reasoning
            )
            # Track routing decision
            routing_decisions_counter.labels(path=path, forced="false").inc()
        
        # 2. Get path handler
        handler, cache_hit = self._get_handler(path, profile_id)
        
        # Track cache hit
        if cache_hit:
            handler_cache_hits_counter.labels(path=path).inc()
            obs_logger.info("Handler retrieved from cache", path=path, cache_hit=True)
        
        # 3. Generate response using appropriate handler
        try:
            handler_start = time.time()
            
            if path == "fast":
                formatted_response = handler.handle(
                    query=query,
                    vector_results=vector_results,
                    memory=memory,
                    conversation_history=conversation_history,
                    language=language
                )
            elif path == "standard":
                formatted_response = handler.handle(
                    query=query,
                    vector_results=vector_results,
                    graph_results=graph_results,
                    precedents=precedents,
                    memory=memory,
                    conversation_history=conversation_history,
                    language=language
                )
            elif path == "agentic":
                formatted_response = handler.handle(
                    query=query,
                    vector_results=vector_results,
                    graph_results=graph_results,
                    precedents=precedents,
                    memory=memory,
                    conversation_history=conversation_history,
                    language=language
                )
            else:
                raise ValueError(f"Unknown path: {path}")
            
            handler_latency = (time.time() - handler_start) * 1000
            obs_logger.info(
                "Handler execution completed",
                path=path,
                handler_latency_ms=handler_latency
            )
            
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            obs_logger.error(
                "Handler execution failed",
                path=path,
                error=str(e),
                error_type=type(e).__name__
            )
            # Track error in metrics
            llm_requests_counter.labels(
                model=self.provider,
                path=path,
                status="error"
            ).inc()
            raise
        
        # 4. Build final response
        total_latency = (time.time() - start_time) * 1000
        
        # 4.1 Validate response word count (P1 fix)
        response_text = formatted_response.content
        word_count = len(response_text.split())
        max_words = get_word_limit(path)
        word_count_exceeded = word_count > max_words

        if word_count_exceeded:
            overage = word_count - max_words
            overage_pct = (overage / max_words) * 100
            logger.warning(
                f"Response exceeds word limit: {word_count} words "
                f"(limit: {max_words}, over by {overage} words / {overage_pct:.1f}%)"
            )
            obs_logger.warning(
                "Response word count exceeded",
                path=path,
                word_count=word_count,
                max_words=max_words,
                overage=overage,
                overage_pct=overage_pct
            )
        else:
            obs_logger.info(
                "Response word count within limit",
                path=path,
                word_count=word_count,
                max_words=max_words
            )

        response = {
            "answer": formatted_response.content,
            "citations": formatted_response.citations,
            "sources": formatted_response.sources,
            "metadata": {
                **formatted_response.metadata,
                "routing": routing_metadata,
                "profile_id": profile_id,
                "provider": self.provider,
                "total_latency_ms": total_latency,
                "word_count": word_count,
                "max_words": max_words,
                "word_count_exceeded": word_count_exceeded
            }
        }

        # Capture LangSmith run_id at orchestrator level
        try:
            from langsmith import get_current_run_tree
            run_tree = get_current_run_tree()
            if run_tree:
                response['metadata']['langsmith_run_id'] = str(run_tree.id)
                obs_logger.info(
                    "Captured LangSmith run_id in orchestrator",
                    run_id=str(run_tree.id),
                    path=path
                )
        except Exception as e:
            obs_logger.debug(f"Could not capture LangSmith run_id: {e}")
        
        # Track successful completion
        llm_requests_counter.labels(
            model=self.provider,
            path=path,
            status="success"
        ).inc()
        
        # Track overall latency
        request_latency.labels(
            endpoint="generate_response",
            path=path
        ).observe(total_latency / 1000)  # Convert to seconds
        
        logger.info(
            f"Response generated: {len(formatted_response.content)} chars, "
            f"{len(formatted_response.citations)} citations"
        )
        
        obs_logger.info(
            "Response generation completed",
            path=path,
            response_length=len(formatted_response.content),
            citations_count=len(formatted_response.citations),
            sources_count=len(formatted_response.sources),
            total_latency_ms=total_latency,
            profile_id=profile_id,
            provider=self.provider
        )

        # 5. Evaluate quality metrics (sampling-based, async-friendly)
        try:
            quality_metrics = QualityEvaluator.evaluate_response(
                response=formatted_response.content,
                sources=formatted_response.sources,
                executive_id=profile_id,
                query=query
            )

            # Store quality metrics in database (if evaluation was performed)
            if quality_metrics:
                request_id = RequestContext.get_request_id()
                user_id = RequestContext.get('user_id')

                # Extract citations for storage
                quality_metrics['citations'] = formatted_response.citations

                store_quality_metrics(
                    request_id=request_id or "unknown",
                    executive_id=profile_id,
                    user_id=user_id,
                    query_text=query,
                    response_text=formatted_response.content,
                    quality_metrics=quality_metrics,
                    path=path,
                    model=self.provider,
                    sources_count=len(formatted_response.sources)
                )

                # Track user activity for DAU
                if user_id:
                    track_user_activity(
                        user_id=user_id,
                        activity_type="query",
                        executive_id=profile_id,
                        session_id=request_id,
                        path=path,
                        success=True
                    )

                # Add quality metrics to response metadata
                response['metadata']['quality'] = {
                    'citation_coverage': quality_metrics.get('citation_coverage'),
                    'factual_grounding_rate': quality_metrics.get('grounding_rate'),
                    'evaluated': True
                }
        except Exception as e:
            obs_logger.error(
                "Quality evaluation failed",
                error=str(e),
                request_id=RequestContext.get_request_id()
            )
            # Don't fail the request if quality evaluation fails
            response['metadata']['quality'] = {'evaluated': False, 'error': str(e)}

        return response
    
    def _get_handler(self, path: str, profile_id: str):
        """
        Get or create path handler.
        
        Args:
            path: Path name (fast/standard/agentic)
            profile_id: Executive profile ID
            
        Returns:
            Tuple of (handler instance, cache_hit boolean)
        """
        # Cache key
        cache_key = f"{path}_{profile_id}_{self.provider}"
        
        # Check cache
        if cache_key in self._handler_cache:
            return self._handler_cache[cache_key], True  # Cache hit
        
        # Create LLM client
        provider_config = self.config.get_provider_config(self.provider)
        
        # Transform config for client (needs models/temperature/max_tokens per path)
        # Build client config with all paths
        client_config = {
            'models': {},
            'temperature': {},
            'max_tokens': {},
            **provider_config  # Include other fields like api_key_env, enabled, etc.
        }
        
        for path_name in ['fast', 'standard', 'agentic']:
            # Get model for this path from provider config
            client_config['models'][path_name] = provider_config['models'].get(path_name, provider_config['models'].get('standard'))
            
            # Get settings for this path from global path_settings
            path_settings = self.config.get_path_settings(path_name)
            client_config['temperature'][path_name] = path_settings.get('temperature', 0.7)
            client_config['max_tokens'][path_name] = path_settings.get('max_tokens', 1000)
        
        llm_client = LLMClientFactory.create(
            provider=self.provider,
            config=client_config,
            path=path
        )
        
        # Get path configuration
        path_config = self.config.get_path_settings(path)
        
        # Create appropriate handler
        handler_classes = {
            "fast": FastPathHandler,
            "standard": StandardPathHandler,
            "agentic": AgenticPathHandler
        }
        
        if path not in handler_classes:
            raise ValueError(f"Unknown path: {path}")
        
        handler_class = handler_classes[path]

        # Only AgenticPathHandler accepts hybrid_retrieval_manager
        if path == "agentic":
            handler = handler_class(
                llm_client=llm_client,
                profile_id=profile_id,
                config=path_config,
                hybrid_retrieval_manager=self.hybrid_retrieval_manager
            )
        else:
            handler = handler_class(
                llm_client=llm_client,
                profile_id=profile_id,
                config=path_config
            )
        
        # Cache handler
        self._handler_cache[cache_key] = handler
        
        logger.debug(f"Created and cached handler for {cache_key}")
        obs_logger.info(
            "Handler created and cached",
            path=path,
            profile_id=profile_id,
            provider=self.provider,
            cache_key=cache_key
        )
        
        return handler, False  # Cache miss
    
    def clear_cache(self):
        """Clear handler cache (useful when config changes)"""
        self._handler_cache.clear()
        logger.info("Cleared handler cache")
    
    def reload_config(self):
        """Reload configuration and clear cache"""
        self.config.reload()
        self.clear_cache()
        logger.info("Reloaded configuration")

    async def generate_stream(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        profile_id: str = "akiko_tanaka",
        graph_results: Optional[List[Dict[str, Any]]] = None,
        precedents: Optional[List[Dict[str, Any]]] = None,
        memory: Optional[List[Dict[str, Any]]] = None,
        force_path: Optional[str] = None,
        query_analysis: Optional[Dict[str, Any]] = None,
        language: str = "en"
    ):
        """
        Generate a streaming response using LLM integration.

        Args:
            query: User's question
            vector_results: Vector search results
            profile_id: Executive profile ID
            graph_results: Optional graph context
            precedents: Optional historical precedents
            memory: Optional conversation history
            force_path: Optional path override (fast/standard/agentic)
            query_analysis: Optional pre-analyzed query data
            language: Response language preference (en or ja)

        Yields:
            Dict with streaming chunks:
            - {'type': 'token', 'content': '...'} - Text tokens
            - {'type': 'citations', 'citations': [...]} - Citations
            - {'type': 'complete', 'metadata': {...}} - Final metadata
        """
        logger.info(f"Generating streaming response for query: {query[:50]}...")

        # 1. Route query (unless path is forced)
        if force_path:
            path = force_path
            routing_metadata = {"path": force_path, "forced": True}
            logger.info(f"Using forced path: {force_path}")
        else:
            route_decision = self.query_router.route(query, query_analysis)
            path = route_decision.path
            routing_metadata = {
                "path": route_decision.path,
                "confidence": route_decision.confidence,
                "reasoning": route_decision.reasoning,
                "features": route_decision.features
            }
            logger.info(f"Routed to {path} path: {route_decision.reasoning}")

        # 2. Get path handler
        handler, _ = self._get_handler(path, profile_id)  # Unpack tuple (handler, cache_hit)

        # 3. Build context and prompts (similar to regular generate)
        from .prompt_builder import PromptBuilder, RetrievalContext

        prompt_builder = PromptBuilder(profile_id, path=path)

        # Prepare context based on path
        if path == "fast":
            max_results = 5
            context = RetrievalContext(
                vector_results=vector_results[:max_results],
                memory=memory or [],
                query=query
            )
        else:
            max_results = 10
            context = RetrievalContext(
                vector_results=vector_results[:max_results],
                graph_results=graph_results[:5] if graph_results else None,
                precedents=precedents[:3] if precedents else None,
                memory=memory or [],
                query=query
            )

        # Build prompts with language preference
        system_prompt, user_prompt = prompt_builder.build_full_prompt(query, context, language=language)

        # Create messages
        from .base_client import LLMMessage
        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=user_prompt)
        ]

        # 4. Stream LLM response
        full_response = ""
        llm_metadata = {}

        try:
            # Use native streaming if available (Gemini supports both Live API and REST streaming)
            has_streaming = hasattr(handler.llm_client, 'generate_stream')

            if has_streaming:
                async for chunk in handler.llm_client.generate_stream(messages):
                    if chunk['type'] == 'token':
                        full_response += chunk['content']
                        # Forward token to caller
                        yield chunk
                    elif chunk['type'] == 'complete':
                        llm_metadata = chunk.get('metadata', {})
                    elif chunk['type'] == 'langsmith_metadata':
                        # Forward LangSmith metadata but don't include in response
                        yield chunk
            else:
                # Fallback: non-streaming (simulate streaming)
                llm_response = handler.llm_client.generate(messages)
                full_response = llm_response.content

                # Emit in word chunks (FAKE STREAMING)
                words = full_response.split()
                accumulated = ""
                for word in words:
                    accumulated += word + " "
                    yield {
                        'type': 'token',
                        'content': word + " "
                    }

                llm_metadata = {
                    'model': llm_response.model,
                    'latency_ms': llm_response.latency_ms,
                    'total_tokens': llm_response.usage.get('total_tokens', 0)
                }

        except Exception as e:
            logger.error(f"Error streaming response: {e}", exc_info=True)
            raise

        # 5. Extract citations from full response
        from .response_formatter import ResponseFormatter
        response_formatter = ResponseFormatter()
        formatted = response_formatter.format_response(
            full_response,
            retrieval_context={
                "vector_results": vector_results,
                "graph_results": graph_results,
                "precedents": precedents
            }
        )

        # 6. Yield citations
        if formatted.citations:
            yield {
                'type': 'citations',
                'citations': formatted.citations
            }

        # 7. Yield completion metadata
        yield {
            'type': 'complete',
            'metadata': {
                **llm_metadata,
                "routing": routing_metadata,
                "profile_id": profile_id,
                "provider": self.provider,
                "path": path,
                "results_used": len(vector_results),
                "citation_count": len(formatted.citations)
            }
        }

        logger.info(
            f"Streaming response complete: {len(full_response)} chars, "
            f"{len(formatted.citations)} citations"
        )

    def generate_with_prompts(
        self,
        system_prompt: str,
        user_prompt: str,
        profile_id: str = "akiko_tanaka",
        path: str = "standard",
    ) -> Dict[str, Any]:
        """
        Generate a response using pre-built prompts from ConversationEngine.

        Supports ConversationEngine integration.

        Args:
            system_prompt: Complete system prompt from ConversationEngine
            user_prompt: Complete user prompt from ConversationEngine
            profile_id: Executive profile ID
            path: Path hint for handler selection

        Returns:
            Dict with response, citations, metadata
        """
        start_time = time.time()

        logger.info(f"Generating response with pre-built prompts (profile={profile_id}, path={path})")
        obs_logger.info(
            "Response generation with prompts started",
            profile_id=profile_id,
            path=path,
            system_prompt_length=len(system_prompt),
            user_prompt_length=len(user_prompt)
        )

        try:
            # Build LLM client config (same pattern as graph.py and integration.py)
            provider_config = self.config.get_provider_config(self.provider)
            path_settings = self.config.get_path_settings(path)

            client_config = {
                'models': {},
                'temperature': {},
                'max_tokens': {},
                **provider_config
            }

            # Set model and settings for requested path
            client_config['models'][path] = provider_config['models'].get(
                path, provider_config['models'].get('standard')
            )
            client_config['temperature'][path] = path_settings.get('temperature', 0.7)
            client_config['max_tokens'][path] = path_settings.get('max_tokens', 1000)

            llm_client = LLMClientFactory.create(
                provider=self.provider,
                config=client_config,
                path=path
            )

            # Build messages
            from .base_client import LLMMessage
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt)
            ]

            # Generate response
            llm_response = llm_client.generate(messages)

            # Validate response word count (P1 fix)
            response_text = llm_response.content
            word_count = len(response_text.split())
            max_words = get_word_limit(path)
            word_count_exceeded = word_count > max_words

            if word_count_exceeded:
                overage = word_count - max_words
                overage_pct = (overage / max_words) * 100
                logger.warning(
                    f"Response exceeds word limit: {word_count} words "
                    f"(limit: {max_words}, over by {overage} words / {overage_pct:.1f}%)"
                )
                obs_logger.warning(
                    "Response word count exceeded (generate_with_prompts)",
                    path=path,
                    word_count=word_count,
                    max_words=max_words,
                    overage=overage,
                    overage_pct=overage_pct
                )

            # Extract response data
            response = {
                "answer": llm_response.content,
                "citations": [],  # Citations should be extracted from response
                "sources": [],
                "metadata": {
                    "profile_id": profile_id,
                    "provider": self.provider,
                    "path": path,
                    "total_latency_ms": (time.time() - start_time) * 1000,
                    "llm_tokens": {
                        "prompt": llm_response.usage.get("prompt_tokens", 0),
                        "completion": llm_response.usage.get("completion_tokens", 0),
                        "total": llm_response.usage.get("total_tokens", 0)
                    },
                    "cost_usd": getattr(llm_response, 'cost_usd', 0.0),
                    "conversation_engine": True,  # Mark as generated via ConversationEngine
                    "word_count": word_count,
                    "max_words": max_words,
                    "word_count_exceeded": word_count_exceeded
                }
            }

            # Extract citations from response
            try:
                from .response_formatter import ResponseFormatter
                response_formatter = ResponseFormatter()
                # Extract citations from the response text
                import re
                citation_pattern = r'\[Source:\s*([^\]]+)\]'
                citations = re.findall(citation_pattern, llm_response.content)
                response["citations"] = [{"source": c, "type": "inline"} for c in citations]
                response["sources"] = list(set(citations))
            except Exception as e:
                logger.warning(f"Citation extraction failed: {e}")

            logger.info(
                f"Response generated with prompts: {len(llm_response.content)} chars, "
                f"latency={(time.time() - start_time) * 1000:.1f}ms"
            )

            return response

        except Exception as e:
            logger.error(f"Error generating response with prompts: {e}", exc_info=True)
            raise

    async def generate_stream_with_prompts(
        self,
        system_prompt: str,
        user_prompt: str,
        profile_id: str = "akiko_tanaka",
        path: str = "standard",
        retrieval_context: Optional[Dict[str, Any]] = None,
    ):
        """
        Stream a response using pre-built prompts from ConversationEngine.

        This method enables streaming while using the full ConversationEngine
        5-stage pipeline for prompt generation. It accepts pre-built prompts
        (system_prompt, user_prompt) from ConversationEngine.generate() and
        streams the LLM response token-by-token.

        Enables streaming with full voiceprint/calibration pipeline.

        Args:
            system_prompt: Complete system prompt from ConversationEngine
            user_prompt: Complete user prompt from ConversationEngine
            profile_id: Executive profile ID
            path: Path hint for handler selection (fast/standard/agentic)
            retrieval_context: Optional retrieval results for citation extraction
                              Format: {"vector_results": [...], "graph_results": [...], "precedents": [...]}

        Yields:
            Dict with streaming chunks:
            - {'type': 'token', 'content': '...'} - Text tokens as they arrive
            - {'type': 'citations', 'citations': [...]} - Extracted citations
            - {'type': 'complete', 'metadata': {...}} - Final metadata

        Example:
            ```python
            # First, get prompts from ConversationEngine
            system_prompt, user_prompt, conv_state = await conversation_engine.generate(
                query=query,
                profile_id=profile_id,
                retrieved_context=retrieval_context,
                path=path,
            )

            # Then stream using those prompts
            async for chunk in orchestrator.generate_stream_with_prompts(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                profile_id=profile_id,
                path=path,
            ):
                if chunk['type'] == 'token':
                    print(chunk['content'], end='', flush=True)
            ```
        """
        start_time = time.time()

        logger.info(
            f"🔄 Streaming with ConversationEngine prompts "
            f"(profile={profile_id}, path={path}, "
            f"system_prompt={len(system_prompt)} chars, user_prompt={len(user_prompt)} chars)"
        )
        obs_logger.info(
            "Streaming with ConversationEngine prompts started",
            profile_id=profile_id,
            path=path,
            system_prompt_length=len(system_prompt),
            user_prompt_length=len(user_prompt),
            conversation_engine=True
        )

        try:
            # Build LLM client config (same pattern as generate_with_prompts)
            provider_config = self.config.get_provider_config(self.provider)
            path_settings = self.config.get_path_settings(path)

            client_config = {
                'models': {},
                'temperature': {},
                'max_tokens': {},
                **provider_config
            }

            # Set model and settings for requested path
            client_config['models'][path] = provider_config['models'].get(
                path, provider_config['models'].get('standard')
            )
            client_config['temperature'][path] = path_settings.get('temperature', 0.7)
            client_config['max_tokens'][path] = path_settings.get('max_tokens', 1000)

            llm_client = LLMClientFactory.create(
                provider=self.provider,
                config=client_config,
                path=path
            )

            # Build messages from pre-built prompts
            from .base_client import LLMMessage
            messages = [
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=user_prompt)
            ]

            # Stream LLM response
            full_response = ""
            llm_metadata = {}
            token_count = 0

            # Check if LLM client supports native streaming
            has_streaming = hasattr(llm_client, 'generate_stream')

            if has_streaming:
                logger.debug(f"Using native streaming for {self.provider}")
                async for chunk in llm_client.generate_stream(messages):
                    if chunk['type'] == 'token':
                        full_response += chunk['content']
                        token_count += 1
                        # Forward token to caller
                        yield chunk
                    elif chunk['type'] == 'complete':
                        llm_metadata = chunk.get('metadata', {})
                    elif chunk['type'] == 'langsmith_metadata':
                        # Forward LangSmith metadata
                        yield chunk
            else:
                # Fallback: non-streaming (simulate streaming by word chunks)
                logger.debug(f"Simulating streaming for {self.provider} (no native streaming)")
                llm_response = llm_client.generate(messages)
                full_response = llm_response.content

                # Emit in word chunks (simulated streaming)
                words = full_response.split()
                for word in words:
                    token_count += 1
                    yield {
                        'type': 'token',
                        'content': word + " "
                    }

                llm_metadata = {
                    'model': getattr(llm_response, 'model', 'unknown'),
                    'latency_ms': getattr(llm_response, 'latency_ms', 0),
                    'total_tokens': llm_response.usage.get('total_tokens', 0) if hasattr(llm_response, 'usage') else 0
                }

            # Extract citations from full response
            citations = []
            sources = []
            try:
                import re
                citation_pattern = r'\[Source:\s*([^\]]+)\]'
                found_citations = re.findall(citation_pattern, full_response)
                citations = [{"source": c, "type": "inline"} for c in found_citations]
                sources = list(set(found_citations))

                # Also try to match against retrieval context if provided
                if retrieval_context:
                    from .response_formatter import ResponseFormatter
                    response_formatter = ResponseFormatter()
                    formatted = response_formatter.format_response(
                        full_response,
                        retrieval_context=retrieval_context
                    )
                    if formatted.citations:
                        citations = formatted.citations
                    if formatted.sources:
                        sources = formatted.sources

            except Exception as e:
                logger.warning(f"Citation extraction failed: {e}")

            # Yield citations if found
            if citations:
                yield {
                    'type': 'citations',
                    'citations': citations
                }

            # Calculate final metrics
            total_latency_ms = (time.time() - start_time) * 1000

            # Validate response word count (P1 fix)
            word_count = len(full_response.split())
            max_words = get_word_limit(path)
            word_count_exceeded = word_count > max_words

            if word_count_exceeded:
                overage = word_count - max_words
                overage_pct = (overage / max_words) * 100
                logger.warning(
                    f"Response exceeds word limit: {word_count} words "
                    f"(limit: {max_words}, over by {overage} words / {overage_pct:.1f}%)"
                )
                obs_logger.warning(
                    "Response word count exceeded (streaming)",
                    path=path,
                    word_count=word_count,
                    max_words=max_words,
                    overage=overage,
                    overage_pct=overage_pct
                )

            # Yield completion metadata
            yield {
                'type': 'complete',
                'metadata': {
                    **llm_metadata,
                    "profile_id": profile_id,
                    "provider": self.provider,
                    "path": path,
                    "total_latency_ms": total_latency_ms,
                    "response_length": len(full_response),
                    "token_count": token_count,
                    "citation_count": len(citations),
                    "source_count": len(sources),
                    "conversation_engine": True,  # Mark as using ConversationEngine pipeline
                    "streaming_method": "generate_stream_with_prompts",
                    "word_count": word_count,
                    "max_words": max_words,
                    "word_count_exceeded": word_count_exceeded
                }
            }

            logger.info(
                f"✅ Streaming with ConversationEngine complete: "
                f"{len(full_response)} chars, {token_count} tokens, "
                f"{len(citations)} citations, latency={total_latency_ms:.1f}ms"
            )
            obs_logger.info(
                "Streaming with ConversationEngine completed",
                profile_id=profile_id,
                path=path,
                response_length=len(full_response),
                token_count=token_count,
                citations_count=len(citations),
                total_latency_ms=total_latency_ms,
                conversation_engine=True
            )

        except Exception as e:
            logger.error(f"Error streaming with ConversationEngine prompts: {e}", exc_info=True)
            obs_logger.error(
                "Streaming with ConversationEngine failed",
                error=str(e),
                error_type=type(e).__name__,
                profile_id=profile_id,
                path=path
            )
            # Yield error event
            yield {
                'type': 'error',
                'error': str(e),
                'error_type': type(e).__name__
            }
            raise
