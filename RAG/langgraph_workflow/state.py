"""
LangGraph State Schema for RAG Workflow

Complete state definition with proper typing for type-safe workflow orchestration.
"""
from typing import TypedDict, List, Dict, Any, Optional, Literal


class RAGState(TypedDict, total=False):
    """
    Complete state for RAG workflow
    
    This state is passed through all nodes and updated incrementally.
    Using total=False allows optional fields.
    
    CRITICAL FIX #5: All fields have defaults to avoid KeyError
    """
    
    # ===================================================================
    # INPUT (Required)
    # ===================================================================
    query: str
    user_id: str
    user_role: str
    profile_id: str
    session_id: Optional[str]
    company_id: Optional[str]  # Tenant isolation
    top_k: int
    min_score: float
    language: str  # "en" or "ja"
    
    # ===================================================================
    # QUERY ANALYSIS
    # ===================================================================
    query_features: Optional[Dict[str, Any]]  # From QueryAnalyzer
    query_type: Optional[str]  # factual/decision/analysis/navigation
    complexity: Optional[str]  # simple/medium/complex
    entities: Optional[List[Dict]]  # Extracted entities (spaCy NER)
    
    # ===================================================================
    # ROUTING DECISION
    # ===================================================================
    selected_path: Optional[Literal["fast", "standard", "agentic"]]
    routing_confidence: Optional[float]
    routing_reasoning: Optional[str]
    force_path: Optional[str]  # Override routing
    skip_generation: Optional[bool]  # Skip LLM generation in nodes (for streaming mode)

    # ===================================================================
    # RETRIEVAL RESULTS
    # ===================================================================
    vector_results: Optional[List[Dict]]
    graph_context: Optional[Dict]
    memory_results: Optional[List[Dict]]
    fused_results: Optional[List[Dict]]
    reranked_results: Optional[List[Dict]]
    
    # ===================================================================
    # RERANKING
    # ===================================================================
    reranking_strategy: Optional[str]  # lightweight/medium/full
    reranking_metadata: Optional[Dict]
    
    # ===================================================================
    # REACT (Agentic Path Only)
    # ===================================================================
    react_steps: Optional[List[Dict]]  # List of thought-action-observation
    react_confidence: Optional[float]
    react_iteration: int  # Current iteration count (default: 0)
    react_force_finalize: Optional[bool]  # Force finalize flag
    
    # ===================================================================
    # LLM GENERATION
    # ===================================================================
    system_prompt: Optional[str]
    user_prompt: Optional[str]
    llm_response: Optional[str]
    llm_tokens: Optional[Dict[str, int]]
    llm_cost_usd: Optional[float]
    langsmith_run_id: Optional[str]  # CRITICAL FIX #2
    
    # ===================================================================
    # RESPONSE FORMATTING
    # ===================================================================
    citations: Optional[List[Dict]]
    sources: Optional[List[str]]
    formatted_response: Optional[Dict]
    
    # ===================================================================
    # GraphRAG Global Search
    # ===================================================================
    global_context: Optional[Dict]  # GraphRAG community-based context

    # ===================================================================
    # RAGAS Evaluation
    # ===================================================================
    enable_evaluation: Optional[bool]  # Flag to enable RAGAS evaluation
    evaluation_metrics: Optional[Dict]  # RAGAS evaluation results

    # ===================================================================
    # ConversationEngine Integration
    # ===================================================================
    memory_enabled: Optional[bool]  # Enable episodic memory search
    use_conversation_engine: Optional[bool]  # Use ConversationEngine for prompts
    conversation_state: Optional[Dict]  # Updated session state after response
    adaptive_weights: Optional[Dict[str, float]]  # Fusion weights used

    # ===================================================================
    # Cognitive Twin Multi-Turn Memory
    # ===================================================================
    conversation_history: Optional[List[Dict]]  # Previous turns [{"role": "user/assistant", "content": "..."}]
    user_metadata: Optional[Dict]  # User context for relationship adaptation

    # ===================================================================
    # Cognitive Twin State (6-Layer Architecture)
    # ===================================================================
    cognitive: Optional[Dict[str, Any]]  # Full cognitive state from langgraph_integration
    final_response: Optional[str]  # Used by conversational path (greetings, small talk)

    # ===================================================================
    # QUALITY & METRICS
    # ===================================================================
    quality_metrics: Optional[Dict]
    total_latency_ms: Optional[float]
    component_latencies: Optional[Dict[str, float]]
    
    # ===================================================================
    # ERROR HANDLING
    # ===================================================================
    error: Optional[str]
    error_trace: Optional[str]
    error_node: Optional[str]  # Which node failed


def get_default_state(
    query: str,
    user_id: str,
    user_role: str = "employee",
    profile_id: str = "exec_001_test",  # Use database ID as default
    session_id: Optional[str] = None,
    company_id: Optional[str] = None,
    top_k: int = 20,
    min_score: float = 0.15,
    language: str = "en",
    force_path: Optional[str] = None,
    enable_evaluation: bool = False,  # Enable RAGAS evaluation
    memory_enabled: bool = True,  # Enable memory search
    use_conversation_engine: bool = False,  # Use ConversationEngine
) -> RAGState:
    """
    Create a default state with safe defaults
    
    CRITICAL FIX #5: Provides defaults for all optional fields
    Week 2, Day 5: Default changed to database ID format (exec_001_test)
    """
    return {
        # Required inputs
        "query": query,
        "user_id": user_id,
        "user_role": user_role,
        "profile_id": profile_id,
        "session_id": session_id,
        "company_id": company_id,
        "top_k": top_k,
        "min_score": min_score,
        "language": language,
        
        # Query analysis (defaults)
        "query_features": None,
        "query_type": None,
        "complexity": None,
        "entities": [],
        
        # Routing (defaults)
        "selected_path": None,
        "routing_confidence": None,
        "routing_reasoning": None,
        "force_path": force_path,  # Pass through the force_path parameter
        
        # Retrieval (defaults)
        "vector_results": [],
        "graph_context": {"has_context": False},
        "memory_results": [],
        "fused_results": [],
        "reranked_results": [],
        
        # Reranking (defaults)
        "reranking_strategy": None,
        "reranking_metadata": {},
        
        # ReAct (defaults)
        "react_steps": [],
        "react_confidence": 0.0,
        "react_iteration": 0,
        "react_force_finalize": False,
        
        # LLM (defaults)
        "system_prompt": None,
        "user_prompt": None,
        "llm_response": None,
        "llm_tokens": {},
        "llm_cost_usd": 0.0,
        "langsmith_run_id": None,
        
        # Response (defaults)
        "citations": [],
        "sources": [],
        "formatted_response": None,

        # GraphRAG + RAGAS (defaults)
        "global_context": {"has_context": False},
        "enable_evaluation": enable_evaluation,
        "evaluation_metrics": {},

        # ConversationEngine (defaults)
        "memory_enabled": memory_enabled,
        "use_conversation_engine": use_conversation_engine,
        "conversation_state": None,
        "adaptive_weights": None,

        # Cognitive Twin Multi-Turn Memory (defaults)
        "conversation_history": [],  # Previous turns for multi-turn context
        "user_metadata": None,  # User context for relationship adaptation

        # Cognitive Twin State (6-Layer Architecture)
        "cognitive": {
            "routing": None,
            "lens_result": None,
            "frame_result": None,
            "situation": None,
            "relationship": None,
            "assembled_prompt": None,
            "should_skip_retrieval": False,
            "personality_response": None,
            "layer_timings_ms": {},
        },
        "final_response": None,  # Used by conversational path

        # Metrics (defaults)
        "quality_metrics": {},
        "total_latency_ms": 0.0,
        "component_latencies": {},
        
        # Error (defaults)
        "error": None,
        "error_trace": None,
        "error_node": None
    }


def safe_get(state: RAGState, key: str, default: Any = None) -> Any:
    """
    Safely get value from state with default
    
    CRITICAL FIX #5: Helper to avoid KeyError in nodes
    
    Usage:
        vector_results = safe_get(state, "vector_results", [])
    """
    return state.get(key, default)
