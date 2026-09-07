"""
Orchestrator Wrapper

Wraps the existing LLM orchestrator to use the enhanced query routing system.
Maintains backward compatibility while adding new adaptive routing capabilities.
"""

import logging
from typing import Dict, Any, List, Optional

from .integration import QueryRoutingIntegration
from llm_integration.orchestrator import LLMOrchestrator

logger = logging.getLogger(__name__)


class EnhancedLLMOrchestrator:
    """
    Enhanced LLM Orchestrator that uses the new query routing system.
    
    Wraps the existing LLMOrchestrator to maintain backward compatibility
    while adding the new adaptive routing capabilities from the Solution Manual.
    """
    
    def __init__(self, provider: Optional[str] = None, hybrid_retrieval_manager: Optional[Any] = None):
        """
        Initialize enhanced LLM orchestrator.
        
        Args:
            provider: LLM provider name (openai, glm, etc.)
                     If None, uses default from config
            hybrid_retrieval_manager: Optional hybrid retrieval manager for ReAct tool integration
        """
        logger.info("Initializing EnhancedLLMOrchestrator...")
        
        # Initialize new query routing integration
        self.query_routing = QueryRoutingIntegration()
        
        # Initialize the original orchestrator for backward compatibility
        self.original_orchestrator = LLMOrchestrator(provider, hybrid_retrieval_manager)
        
        logger.info("EnhancedLLMOrchestrator initialized successfully")
    
    def generate(
        self,
        query: str,
        vector_results: List[Dict[str, Any]],
        profile_id: str = "akiko_tanaka",
        graph_results: Optional[List[Dict[str, Any]]] = None,
        precedents: Optional[List[Dict[str, Any]]] = None,
        memory: Optional[List[Dict[str, Any]]] = None,
        force_path: Optional[str] = None,
        query_analysis: Optional[Dict[str, Any]] = None,
        user_id: str = "default_user",
        user_role: str = "employee",
        session_id: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.4,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a response using the enhanced query routing system.
        
        Args:
            query: User's question
            vector_results: Vector search results
            profile_id: Executive profile ID
            graph_results: Optional graph context
            precedents: Optional historical precedents
            memory: Optional conversation history
            force_path: Optional path override (fast/standard/agentic)
            query_analysis: Optional pre-analyzed query data
            user_id: User making the request
            user_role: User's role for RBAC
            session_id: Conversation session ID
            top_k: Number of retrieval results to use
            min_score: Minimum similarity score
            **kwargs: Additional parameters
            
        Returns:
            Dict with response, citations, metadata
        """
        logger.info(f"Generating response for query: {query[:50]}...")
        
        # Use the new query routing system
        response = self.query_routing.process_query(
            query=query,
            user_id=user_id,
            user_role=user_role,
            executive_id=profile_id,
            session_id=session_id,
            top_k=top_k,
            min_score=min_score,
            force_path=force_path,
            vector_results=vector_results,
            graph_results=graph_results,
            precedents=precedents,
            memory=memory,
            **kwargs
        )
        
        # Ensure response has expected fields for backward compatibility
        if "success" not in response:
            response["success"] = True
        
        return response
    
    def clear_cache(self):
        """Clear all caches."""
        self.query_routing.clear_cache()
        self.original_orchestrator.clear_cache()
        logger.info("All caches cleared")
    
    def reload_config(self):
        """Reload configuration and clear cache."""
        self.original_orchestrator.reload_config()
        logger.info("Configuration reloaded")
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        return self.query_routing.get_routing_stats()
    
    def get_react_metrics(self) -> Dict[str, Any]:
        """Get ReAct performance metrics."""
        # This would be available from the agentic path handler
        # For now, returning empty dict as placeholder
        return {}
    
    def __getattr__(self, name):
        """
        Delegate attribute access to the original orchestrator for backward compatibility.
        
        This ensures that any method or property not explicitly defined
        in this class is delegated to the original orchestrator.
        """
        return getattr(self.original_orchestrator, name)


# Factory function to create the appropriate orchestrator
def create_orchestrator(use_enhanced_routing: bool = True, **kwargs) -> LLMOrchestrator:
    """
    Factory function to create the appropriate orchestrator.
    
    Args:
        use_enhanced_routing: Whether to use the enhanced routing system
        **kwargs: Additional arguments for orchestrator initialization
        
    Returns:
        LLMOrchestrator instance (either enhanced or original)
    """
    if use_enhanced_routing:
        logger.info("Creating EnhancedLLMOrchestrator with adaptive routing")
        return EnhancedLLMOrchestrator(**kwargs)
    else:
        logger.info("Creating original LLMOrchestrator")
        return LLMOrchestrator(**kwargs)