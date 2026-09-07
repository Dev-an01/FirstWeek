"""
LangGraph Retrieval Node Wrapper
==================================

Wraps the original UnifiedRetrieval system with adaptive weighting by query type
for integration into LangGraph workflow.

This wrapper:
1. Preserves the original UnifiedRetrieval architecture (graph-enhanced, parallel)
2. Adds adaptive weighting by query type from retrieval_weights.yaml
3. Provides a LangGraph-compatible node interface

Author: AI Officer Implementation Team
Date: 2025-11-10
"""

import logging
import time
import yaml
from typing import Dict, Any, Optional, List
from pathlib import Path

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

# Import the original UnifiedRetrieval system
try:
    from hybrid_retrieval.unified_retrieval import UnifiedRetrieval, RetrievalPath
except ImportError:
    # Fallback for development
    UnifiedRetrieval = None
    RetrievalPath = None

logger = logging.getLogger(__name__)


# ============================================================================
# Adaptive Weights Configuration Loader
# ============================================================================

class AdaptiveWeightsConfig:
    """
    Manages adaptive weights configuration from YAML
    
    Loads and provides query-type specific weights for result fusion
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize adaptive weights configuration
        
        Args:
            config_path: Path to retrieval_weights.yaml (optional)
        """
        if config_path is None:
            # Default path
            config_path = Path(__file__).parent.parent / "checkpoint files" / "retrieval_weights.yaml"
        
        self.config_path = config_path
        self.config = self._load_config()
        
        logger.info(f"[AdaptiveWeights] Loaded configuration from {config_path}")
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file"""
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            return config
        except Exception as e:
            logger.error(f"[AdaptiveWeights] Failed to load config: {e}")
            # Return default configuration
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """Get default adaptive weights configuration"""
        return {
            "query_type_weights": {
                "factual_lookup": {"vector": 0.70, "graph": 0.20, "memory": 0.10},
                "relationship": {"vector": 0.30, "graph": 0.65, "memory": 0.05},
                "decision": {"vector": 0.40, "graph": 0.30, "memory": 0.30},
                "procedural": {"vector": 0.30, "graph": 0.20, "memory": 0.50},
                "comparison": {"vector": 0.40, "graph": 0.35, "memory": 0.25},
                "conversational_context": {"vector": 0.30, "graph": 0.10, "memory": 0.60}
            },
            "default_weights": {"vector": 0.50, "graph": 0.30, "memory": 0.20},
            "config": {
                "min_confidence_threshold": 0.6,
                "confidence_blending": True,
                "enabled": True,
                "log_classifications": True
            }
        }
    
    def get_weights(
        self,
        query_type: str,
        confidence: float = 1.0,
        fallback: bool = False
    ) -> Dict[str, float]:
        """
        Get adaptive weights for query type with confidence blending
        
        Args:
            query_type: Query type (factual_lookup, decision, etc.)
            confidence: Classification confidence (0.0-1.0)
            fallback: Whether this is a fallback classification
        
        Returns:
            {"vector": 0.40, "graph": 0.30, "memory": 0.30}
        """
        # Check if enabled
        if not self.config.get("config", {}).get("enabled", True):
            logger.info("[AdaptiveWeights] Adaptive weighting disabled, using defaults")
            return self.config["default_weights"]
        
        # Get configuration
        min_confidence = self.config.get("config", {}).get("min_confidence_threshold", 0.6)
        confidence_blending = self.config.get("config", {}).get("confidence_blending", True)
        
        # Use default weights if confidence too low or fallback classification
        if confidence < min_confidence or fallback:
            if fallback:
                logger.info(f"[AdaptiveWeights] Fallback classification, using default weights")
            else:
                logger.info(
                    f"[AdaptiveWeights] Confidence {confidence:.2f} < threshold {min_confidence:.2f}, "
                    f"using default weights"
                )
            return self.config["default_weights"]
        
        # Get type-specific weights
        weights_map = self.config["query_type_weights"]
        if query_type not in weights_map:
            logger.warning(f"[AdaptiveWeights] Unknown query type '{query_type}', using defaults")
            return self.config["default_weights"]
        
        type_weights = weights_map[query_type]
        
        # Apply confidence blending if enabled
        if confidence_blending and confidence < 1.0:
            default_weights = self.config["default_weights"]
            blended = {}
            for key in ["vector", "graph", "memory"]:
                blended[key] = (
                    confidence * type_weights[key] +
                    (1 - confidence) * default_weights[key]
                )
            
            logger.info(
                f"[AdaptiveWeights] Using blended weights for {query_type} "
                f"(confidence: {confidence:.2f}): V={blended['vector']:.2f}, "
                f"G={blended['graph']:.2f}, M={blended['memory']:.2f}"
            )
            return blended
        else:
            # Use type-specific weights directly
            weights = {
                "vector": type_weights["vector"],
                "graph": type_weights["graph"],
                "memory": type_weights["memory"]
            }
            logger.info(
                f"[AdaptiveWeights] Using {query_type} weights: "
                f"V={weights['vector']:.2f}, G={weights['graph']:.2f}, "
                f"M={weights['memory']:.2f}"
            )
            return weights
    
    def get_description(self, query_type: str) -> str:
        """Get description for query type"""
        weights_map = self.config.get("query_type_weights", {})
        if query_type in weights_map:
            return weights_map[query_type].get("description", "")
        return ""
    
    def get_reasoning(self, query_type: str) -> str:
        """Get reasoning for query type weights"""
        weights_map = self.config.get("query_type_weights", {})
        if query_type in weights_map:
            return weights_map[query_type].get("reasoning", "")
        return ""


# ============================================================================
# LangGraph Node Factory
# ============================================================================

def create_unified_retrieval_node(
    vector_engine: Any,
    graph_provider: Any,
    memory_search_engine: Optional[Any] = None,
    result_fusion: Optional[Any] = None,
    adaptive_reranker: Optional[Any] = None,
    unified_retrieval_manager: Optional[Any] = None,
    enable_adaptive_weights: bool = True,
    config_overrides: Optional[Dict] = None
):
    """
    Factory to create unified retrieval node for LangGraph workflow
    
    This function creates a node that wraps UnifiedRetrieval with adaptive weighting.
    
    Args:
        vector_engine: VectorSearchEngine instance
        graph_provider: GraphContextProvider instance
        memory_search_engine: MultiSignalMemorySearch instance (optional)
        result_fusion: ResultFusion instance (optional)
        adaptive_reranker: AdaptiveReranker instance (optional)
        unified_retrieval_manager: Pre-configured UnifiedRetrieval instance (optional)
        enable_adaptive_weights: Enable query-type adaptive weighting (default: True)
        config_overrides: Configuration overrides
    
    Returns:
        Callable node function for LangGraph workflow
    """
    
    # Initialize adaptive weights configuration
    adaptive_weights_config = AdaptiveWeightsConfig() if enable_adaptive_weights else None
    
    # Use provided UnifiedRetrieval or create new one
    if unified_retrieval_manager:
        unified_retrieval = unified_retrieval_manager
        logger.info("[UnifiedRetrievalNode] Using provided UnifiedRetrieval manager")
    else:
        # Create new UnifiedRetrieval instance
        if UnifiedRetrieval is None:
            raise ImportError(
                "UnifiedRetrieval not available. Please ensure hybrid_retrieval module is installed."
            )
        
        unified_retrieval = UnifiedRetrieval(
            enable_cache=True,
            enable_metrics=True,
            config_overrides=config_overrides,
            enable_parallel=True,
            max_workers=4
        )
        logger.info("[UnifiedRetrievalNode] Created new UnifiedRetrieval manager")
    
    @traceable(name="unified_retrieval_node")
    def unified_retrieval_node(state: Dict) -> Dict:
        """
        Unified retrieval node with adaptive weighting
        
        This node:
        1. Uses UnifiedRetrieval for graph-enhanced parallel retrieval
        2. Applies adaptive weighting by query type to result fusion
        3. Tracks performance metrics
        
        Input state:
            - query: str
            - query_type: str (optional, defaults to "factual_lookup")
            - query_classification: Dict (optional, contains confidence)
            - user_id: str
            - user_role: str
            - profile_id: str (executive ID)
            - session_id: str (optional)
            - top_k: int (default: 10)
            - force_path: str (optional, for testing)
        
        Output state:
            - retrieval_results: List[Dict]
            - adaptive_weights_used: Dict
            - retrieval_metadata: Dict
            - component_latencies: Dict
        """
        start_time = time.time()
        
        # Extract from state
        query = state["query"]
        query_type = state.get("query_type", "factual_lookup")
        query_classification = state.get("query_classification", {})
        user_id = state.get("user_id", "unknown")
        user_role = state.get("user_role", "employee")
        profile_id = state.get("profile_id", user_id)
        session_id = state.get("session_id")
        top_k = state.get("top_k", 10)
        force_path = state.get("force_path")
        
        # Build user context
        user_context = {
            "user_id": user_id,
            "role": user_role,
            "allowed_scopes": _get_allowed_scopes(user_role),
            "session_id": session_id,
            "company_id": state.get("company_id"),
        }
        
        logger.info(
            f"[UnifiedRetrievalNode] Starting retrieval for query: '{query[:50]}...'"
        )
        logger.info(
            f"[UnifiedRetrievalNode] Query type: {query_type}, Profile: {profile_id}, "
            f"Role: {user_role}, Top-K: {top_k}"
        )
        
        # Get adaptive weights if enabled
        adaptive_weights = None
        if adaptive_weights_config:
            confidence = query_classification.get("confidence", 1.0)
            fallback = query_classification.get("fallback", False)
            adaptive_weights = adaptive_weights_config.get_weights(
                query_type=query_type,
                confidence=confidence,
                fallback=fallback
            )
            
            logger.info(
                f"[UnifiedRetrievalNode] Adaptive weights: V={adaptive_weights['vector']:.2f}, "
                f"G={adaptive_weights['graph']:.2f}, M={adaptive_weights['memory']:.2f}"
            )
        
        # ================================================================
        # Call UnifiedRetrieval (Original System)
        # ================================================================
        
        retrieval_start = time.time()
        
        try:
            # CRITICAL: If adaptive weights are enabled, we need to temporarily
            # override the composite_weights in unified_retrieval config
            original_weights = None
            if adaptive_weights:
                # Save original weights
                original_weights = unified_retrieval.config.get("composite_weights", {}).copy()
                # Override with adaptive weights
                unified_retrieval.config["composite_weights"] = adaptive_weights
                logger.debug("[UnifiedRetrievalNode] Temporarily overriding composite_weights")
            
            # Call the original unified retrieval system
            response = unified_retrieval.retrieve(
                query=query,
                executive_id=profile_id,
                user_context=user_context,
                top_k=top_k,
                force_path=force_path
            )
            
            # Restore original weights if we overrode them
            if original_weights:
                unified_retrieval.config["composite_weights"] = original_weights
                logger.debug("[UnifiedRetrievalNode] Restored original composite_weights")
            
            retrieval_time = (time.time() - retrieval_start) * 1000
            
            # Extract results
            results = response.get("results", [])
            metadata = response.get("metadata", {})
            
            logger.info(
                f"[UnifiedRetrievalNode] Retrieval complete in {retrieval_time:.0f}ms, "
                f"returned {len(results)} results"
            )
            
        except Exception as e:
            retrieval_time = (time.time() - retrieval_start) * 1000
            logger.error(f"[UnifiedRetrievalNode] Retrieval failed: {e}", exc_info=True)
            
            # Restore original weights if error occurred
            if original_weights:
                unified_retrieval.config["composite_weights"] = original_weights
            
            # Return empty results with error metadata
            results = []
            metadata = {
                "error": str(e),
                "error_occurred": True,
                "retrieval_time_ms": retrieval_time
            }
        
        # ================================================================
        # Update State
        # ================================================================
        
        total_time = (time.time() - start_time) * 1000
        
        # Store results in state
        state["retrieval_results"] = results
        
        # Store adaptive weights used
        if adaptive_weights:
            state["adaptive_weights_used"] = adaptive_weights
        
        # Store retrieval metadata
        state["retrieval_metadata"] = {
            **metadata,
            "retrieval_node_time_ms": total_time,
            "adaptive_weighting_enabled": adaptive_weights is not None
        }
        
        # Track component latencies
        if "component_latencies" not in state:
            state["component_latencies"] = {}
        state["component_latencies"]["unified_retrieval"] = total_time
        state["component_latencies"]["retrieval_core"] = retrieval_time
        
        # Add query type information to metadata
        if adaptive_weights_config and query_type:
            state["retrieval_metadata"]["query_type_info"] = {
                "type": query_type,
                "description": adaptive_weights_config.get_description(query_type),
                "reasoning": adaptive_weights_config.get_reasoning(query_type)
            }
        
        logger.info(
            f"[UnifiedRetrievalNode] ✅ Complete in {total_time:.0f}ms, "
            f"returning {len(results)} documents"
        )
        
        return state
    
    return unified_retrieval_node


def _get_allowed_scopes(role: str) -> List[str]:
    """Delegate to shared RBAC module for role-to-scope mapping."""
    from shared.rbac import get_allowed_scopes
    return get_allowed_scopes(role)


# ============================================================================
# Standalone Retrieval Function (for Testing)
# ============================================================================

def execute_unified_retrieval(
    query: str,
    profile_id: str,
    query_type: str = "factual_lookup",
    user_role: str = "employee",
    top_k: int = 10,
    enable_adaptive_weights: bool = True,
    force_path: Optional[str] = None,
    unified_retrieval_manager: Optional[Any] = None
) -> Dict:
    """
    Standalone function to execute unified retrieval with adaptive weighting
    
    Useful for testing outside of LangGraph workflow.
    
    Args:
        query: User question
        profile_id: Executive profile ID
        query_type: Query classification type
        user_role: User's role (for RBAC)
        top_k: Number of results
        enable_adaptive_weights: Enable adaptive weighting
        force_path: Force specific retrieval path (testing)
        unified_retrieval_manager: Pre-configured manager (optional)
    
    Returns:
        Dict with results and metadata
    """
    # Create state
    state = {
        "query": query,
        "query_type": query_type,
        "query_classification": {"confidence": 1.0, "fallback": False},
        "user_id": "test_user",
        "user_role": user_role,
        "profile_id": profile_id,
        "top_k": top_k,
        "force_path": force_path
    }
    
    # Create node
    node = create_unified_retrieval_node(
        vector_engine=None,
        graph_provider=None,
        unified_retrieval_manager=unified_retrieval_manager,
        enable_adaptive_weights=enable_adaptive_weights
    )
    
    # Execute
    result_state = node(state)
    
    return {
        "results": result_state.get("retrieval_results", []),
        "metadata": result_state.get("retrieval_metadata", {}),
        "adaptive_weights": result_state.get("adaptive_weights_used", {})
    }


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "create_unified_retrieval_node",
    "AdaptiveWeightsConfig",
    "execute_unified_retrieval"
]
