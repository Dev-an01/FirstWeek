"""
Cognitive Twin Configuration - Feature flags and settings.

All cognitive layers can be individually enabled/disabled for testing and rollback.
"""

COGNITIVE_CONFIG = {
    # Master switch
    "enabled": True,

    # Foundation Layers (Make executives THINK differently)
    "foundation": {
        "cognitive_lens": {
            "enabled": True,
            "affinity_weight": 0.4,  # How much domain affinity affects reranking
            "min_similarity": 0.3,   # Minimum domain similarity to apply boost
        },
        "cognitive_frame": {
            "enabled": True,
            "include_thinking_patterns": True,
            "include_red_flags": True,
            "include_decision_cases": True,
            "max_decision_cases": 3,  # Max similar cases to include in prompt
        },
    },

    # Enhancement Layers (Make executives AWARE and CONTEXTUAL)
    "enhancement": {
        "conversational_router": {
            "enabled": True,
            "skip_retrieval_for_greetings": True,
        },
        "inference_engine": {
            "enabled": True,  # Enables opinion/decision query handling
            "use_for_no_retrieval": True,  # Use inference when no retrieval data
            "force_opinion_response": True,  # Never say "don't know" for opinions
        },
        "situation_analyzer": {
            "enabled": True,
            "detect_implicit_needs": True,
            "detect_urgency": True,
            "detect_emotion": True,
        },
        "relationship_dynamics": {
            "enabled": True,
            "adapt_formality": True,
            "adapt_depth": True,
        },
        "memory_system": {
            "enabled": True,
            "conversation_memory": True,
            "relationship_memory": True,
            "organizational_memory": False,  # Phase 2
        },
    },

    # Safety and Performance
    "rollback": {
        "latency_threshold_ms": 4000,  # Disable if response exceeds this
        "error_rate_threshold": 0.05,  # Disable if error rate exceeds 5%
        "fallback_to_voice_only": True,  # On error, use existing voiceprint system
    },

    # Performance Optimization (Priority 3)
    "performance": {
        "parallel_cognitive_layers": True,  # Run frame/situation/relationship in parallel
        "max_parallel_workers": 3,  # Thread pool size for parallel execution
    },

    # Cache settings
    "cache": {
        "profile_ttl_seconds": 3600,  # 1 hour
        "domain_embeddings_ttl_seconds": 86400,  # 24 hours
    },

    # Logging
    "logging": {
        "log_cognitive_decisions": True,
        "log_layer_timings": True,
    },
}


def is_layer_enabled(layer_path: str) -> bool:
    """
    Check if a cognitive layer is enabled.

    Args:
        layer_path: Dot-notation path like "foundation.cognitive_lens"

    Returns:
        True if layer is enabled, False otherwise
    """
    if not COGNITIVE_CONFIG.get("enabled", True):
        return False

    parts = layer_path.split(".")
    current = COGNITIVE_CONFIG

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, {})
        else:
            return False

    if isinstance(current, dict):
        return current.get("enabled", True)

    return bool(current)


def get_layer_config(layer_path: str) -> dict:
    """
    Get configuration for a specific layer.

    Args:
        layer_path: Dot-notation path like "foundation.cognitive_lens"

    Returns:
        Configuration dict for the layer
    """
    parts = layer_path.split(".")
    current = COGNITIVE_CONFIG

    for part in parts:
        if isinstance(current, dict):
            current = current.get(part, {})
        else:
            return {}

    return current if isinstance(current, dict) else {}
