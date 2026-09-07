"""
Query Routing Integration

Integrates the enhanced query routing system with existing RAG components.
Provides a unified interface that maintains compatibility with existing code
while adding the new adaptive routing capabilities.
"""

import logging
from typing import Dict, Any, List, Optional

from .router import QueryRouter, RouteDecision
from .path_handlers import FastPathHandler, StandardPathHandler, AgenticPathHandler

# Import existing components
from vector_search.search_engine import VectorSearchEngine
from graph_context.provider import GraphContextProvider
from llm_integration.factory import LLMClientFactory
from profile_management.profile_manager import get_profile_manager

logger = logging.getLogger(__name__)


class QueryRoutingIntegration:
    """
    Integration layer for enhanced query routing system.
    
    Bridges the new query routing components with existing RAG system
    while maintaining backward compatibility.
    """
    
    def __init__(self, vector_engine: VectorSearchEngine = None, 
                 graph_provider: GraphContextProvider = None):
        """
        Initialize query routing integration.
        
        Args:
            vector_engine: Vector search engine instance
            graph_provider: Graph context provider instance
        """
        # Initialize components
        self.query_router = QueryRouter()
        self.profile_manager = get_profile_manager()
        
        # Use provided instances or create new ones
        self.vector_engine = vector_engine or VectorSearchEngine()
        self.graph_provider = graph_provider or GraphContextProvider()
        
        # Cache for path handlers (reuse across requests)
        self._handler_cache: Dict[str, Any] = {}
        
        logger.info("QueryRoutingIntegration initialized")
    
    def process_query(
        self,
        query: str,
        user_id: str,
        user_role: str = "employee",
        executive_id: str = "akiko_tanaka",
        session_id: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.4,
        force_path: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process a query using the enhanced routing system.
        
        Args:
            query: User's question
            user_id: User making the request
            user_role: User's role for RBAC
            executive_id: Executive profile ID to use
            session_id: Conversation session ID for multi-turn chat
            top_k: Number of retrieval results to use
            min_score: Minimum similarity score for retrieval
            force_path: Override automatic routing (fast/standard/agentic)
            **kwargs: Additional parameters
            
        Returns:
            Dict with response, citations, metadata
        """
        logger.info(f"Processing query: {query[:50]}...")
        
        try:
            # Step 1: Route query (unless path is forced)
            if force_path:
                path = force_path
                routing_metadata = {"path": force_path, "forced": True}
                logger.info(f"Using forced path: {force_path}")
            else:
                route_decision = self.query_router.route(query)
                path = route_decision.path
                routing_metadata = {
                    "path": path,
                    "complexity": route_decision.complexity,
                    "confidence": route_decision.confidence,
                    "reasoning": route_decision.reasoning,
                    "features": route_decision.features
                }
                logger.info(f"Routed to {path} path: {route_decision.reasoning}")
            
            # Step 2: Get path handler
            handler = self._get_handler(path, executive_id)
            
            # Step 3: Retrieve relevant knowledge
            vector_results, graph_results, precedents, memory = self._retrieve_knowledge(
                query, user_role, executive_id, session_id, top_k, min_score, path
            )
            
            # Step 4: Generate response using appropriate handler
            if path == "fast":
                response = handler.handle(
                    query=query,
                    vector_results=vector_results,
                    memory=memory
                )
            elif path == "standard":
                response = handler.handle(
                    query=query,
                    vector_results=vector_results,
                    graph_results=graph_results,
                    precedents=precedents,
                    memory=memory
                )
            elif path == "agentic":
                response = handler.handle(
                    query=query,
                    vector_results=vector_results,
                    graph_results=graph_results,
                    precedents=precedents,
                    memory=memory
                )
            else:
                raise ValueError(f"Unknown path: {path}")
            
            # Step 5: Add routing metadata
            response["metadata"]["routing"] = routing_metadata
            response["metadata"]["executive_id"] = executive_id
            response["metadata"]["user_id"] = user_id
            response["metadata"]["session_id"] = session_id
            
            # Step 6: Store interaction in memory (if applicable)
            self._store_interaction(
                query, response, user_id, user_role, executive_id, session_id
            )
            
            logger.info(
                f"Response generated: {len(response['answer'])} chars, "
                f"{len(response.get('citations', []))} citations"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}", exc_info=True)
            return self._build_error_response(query, str(e))
    
    def _get_handler(self, path: str, executive_id: str):
        """
        Get or create path handler.
        
        Args:
            path: Path name (fast/standard/agentic)
            executive_id: Executive profile ID
            
        Returns:
            Path handler instance
        """
        # Cache key
        cache_key = f"{path}_{executive_id}"
        
        # Check cache
        if cache_key in self._handler_cache:
            return self._handler_cache[cache_key]
        
        # Get executive profile
        profile = self.profile_manager.get_profile(executive_id)
        
        # Get path configuration
        config = self.query_router.path_expectations.get(path, {})
        
        # Create LLM client
        provider_config = self.profile_manager.config.get_provider_config(
            self.profile_manager.config.active_provider
        )
        
        # Transform config for client (needs models/temperature/max_tokens per path)
        client_config = {
            'models': {},
            'temperature': {},
            'max_tokens': {},
            **provider_config  # Include other fields like api_key_env, enabled, etc.
        }
        
        for path_name in ['fast', 'standard', 'agentic']:
            # Get model for this path from provider config
            client_config['models'][path_name] = provider_config['models'].get(
                path_name, provider_config['models'].get('standard')
            )
            
            # Get settings for this path from global path_settings
            path_settings = self.profile_manager.config.get_path_settings(path_name)
            client_config['temperature'][path_name] = path_settings.get('temperature', 0.7)
            client_config['max_tokens'][path_name] = path_settings.get('max_tokens', 1000)
        
        llm_client = LLMClientFactory.create(
            provider=self.profile_manager.config.active_provider,
            config=client_config,
            path=path
        )
        
        # Create appropriate handler
        handler_classes = {
            "fast": FastPathHandler,
            "standard": StandardPathHandler,
            "agentic": AgenticPathHandler
        }
        
        if path not in handler_classes:
            raise ValueError(f"Unknown path: {path}")
        
        handler_class = handler_classes[path]
        handler = handler_class(
            llm_client=llm_client,
            profile_id=executive_id,
            config=config
        )
        
        # Cache handler
        self._handler_cache[cache_key] = handler
        
        logger.debug(f"Created and cached handler for {cache_key}")
        
        return handler
    
    def _retrieve_knowledge(
        self,
        query: str,
        user_role: str,
        executive_id: str,
        session_id: Optional[str],
        top_k: int,
        min_score: float,
        path: str
    ) -> tuple:
        """
        Retrieve relevant knowledge from all sources.
        
        Args:
            query: User's question
            user_role: User's role for RBAC
            executive_id: Executive profile ID
            session_id: Conversation session ID
            top_k: Number of results to retrieve
            min_score: Minimum similarity score
            path: Processing path (affects retrieval strategy)
            
        Returns:
            Tuple of (vector_results, graph_results, precedents, memory)
        """
        # Adjust top_k based on path
        if path == "fast":
            retrieval_top_k = min(top_k, 10)
        elif path == "standard":
            retrieval_top_k = min(top_k, 20)
        elif path == "agentic":
            retrieval_top_k = min(top_k, 30)
        else:
            retrieval_top_k = top_k
        
        # 1. Vector search
        vector_response = self.vector_engine.search(
            query=query,
            top_k=retrieval_top_k,
            min_score=min_score,
            role=user_role,
            include_metadata=True,
            include_citations=True,
            use_graph_context=True
        )
        vector_results = vector_response.get('results', [])
        
        # 2. Graph context (already included in vector_results if available)
        graph_results = None
        if vector_response.get('metadata', {}).get('graph_enhanced', False):
            # Extract graph results from vector response metadata
            graph_results = vector_response.get('metadata', {}).get('graph_context', {})
        
        # 3. Personal memory (executive-specific)
        memory = self._retrieve_executive_memory(
            query, executive_id, session_id, top_k
        )
        
        # 4. Precedents (for standard and agentic paths)
        precedents = None
        if path in ["standard", "agentic"]:
            precedents = self._retrieve_precedents(query, executive_id, top_k)
        
        return vector_results, graph_results, precedents, memory
    
    def _retrieve_executive_memory(
        self,
        query: str,
        executive_id: str,
        session_id: Optional[str],
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve executive's personal memory.
        
        Args:
            query: User's question
            executive_id: Executive profile ID
            session_id: Conversation session ID
            top_k: Number of results to retrieve
            
        Returns:
            List of memory entries
        """
        # This would query the episodic_memory table for this executive
        # For now, returning empty list as placeholder
        # In a real implementation, this would use multi-signal scoring
        return []
    
    def _retrieve_precedents(
        self,
        query: str,
        executive_id: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant precedents for the executive.
        
        Args:
            query: User's question
            executive_id: Executive profile ID
            top_k: Number of results to retrieve
            
        Returns:
            List of precedent entries
        """
        # This would query historical decisions for this executive
        # For now, returning empty list as placeholder
        # In a real implementation, this would use semantic similarity
        return []
    
    def _store_interaction(
        self,
        query: str,
        response: Dict[str, Any],
        user_id: str,
        user_role: str,
        executive_id: str,
        session_id: Optional[str]
    ):
        """
        Store interaction in executive's personal memory.
        
        Args:
            query: User's question
            response: Generated response
            user_id: User making the request
            user_role: User's role
            executive_id: Executive profile ID
            session_id: Conversation session ID
        """
        # This would store the interaction in the episodic_memory table
        # For now, just logging as placeholder
        logger.debug(
            f"Storing interaction for {executive_id}: "
            f"query={query[:50]}..., response_length={len(response.get('answer', ''))}"
        )
    
    def _build_error_response(self, query: str, error_message: str) -> Dict[str, Any]:
        """
        Build error response.
        
        Args:
            query: Original query
            error_message: Error message
            
        Returns:
            Error response dictionary
        """
        return {
            "success": False,
            "error": "ProcessingError",
            "message": f"Failed to process query: {error_message}",
            "query": query,
            "metadata": {
                "error_type": "ProcessingError",
                "timestamp": self._get_timestamp()
            }
        }
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.utcnow().isoformat()
    
    def clear_cache(self):
        """Clear handler cache."""
        self._handler_cache.clear()
        logger.info("Handler cache cleared")
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get routing statistics.
        
        Returns:
            Dictionary with routing statistics
        """
        # This would return statistics about query routing
        # For now, returning basic info as placeholder
        return {
            "handler_cache_size": len(self._handler_cache),
            "available_paths": ["fast", "standard", "agentic"],
            "path_expectations": self.query_router.path_expectations
        }