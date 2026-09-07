"""
Hybrid Retrieval Configuration
===============================

Configuration for the full hybrid retrieval pipeline combining:
- Vector search (Blueprint #2)
- Graph context (Blueprint #3.5 with enhanced spaCy NER)
- Personal memory (Blueprint #4)
"""

import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from embedding_generation.config import POSTGRES_CONFIG, NEO4J_CONFIG

# Hybrid retrieval specific configuration
HYBRID_RETRIEVAL_CONFIG = {
    # Composite scoring weights (Solution Manual Section 5)
    # vector (60%) + graph (30%) + memory (10%)
    "composite_weights": {
        "vector": 0.60,    # Vector similarity (primary signal)
        "graph": 0.30,     # Graph proximity (secondary)
        "memory": 0.10     # Personal memory (context)
    },
    
    # Adaptive reranking thresholds
    # Determines which reranking strategy to use based on result quality
    "reranking_thresholds": {
        "lightweight": {
            "min_top_score": 0.85,     # Top result score must be >= 0.85
            "min_gap": 0.15            # Gap between top and 5th must be >= 0.15
        },
        "medium": {
            "min_top_score": 0.70,     # Top result score must be >= 0.70
            "min_gap": 0.10            # Gap between top and 5th must be >= 0.10
        },
        "full": {
            "max_top_score": 0.70      # Use full if top score < 0.70
        }
    },
    
    # Performance settings
    "parallel_execution": True,        # Execute sources in parallel (recommended)
    "cache_enabled": True,             # Cache results for repeated queries
    
    # Memory search settings
    "memory_config": {
        "time_window_days": 180,       # Search last 6 months of interactions
        "min_similarity": 0.4,          # Minimum semantic similarity for memory hits
        "max_results": 10               # Top K memories to retrieve
    },
    
    # Result limits per source
    "max_candidates": {
        "vector": 30,      # Increased from 20 for better retrieval coverage
        "graph": 50,       # Up to 50 graph candidates
        "memory": 10       # Top 10 memory results
    },
    
    # Query routing settings
    "query_routing": {
        "enable_auto_strategy": True,  # Automatic strategy selection
        "default_strategy": "auto"     # Default: let system decide
    },
    
    # Cross-encoder settings for reranking
    # NOTE: bge-reranker-v2-m3 returns uniform scores (bug), using bge-reranker-base instead
    # bge-reranker-base works well for both Japanese and English queries
    "cross_encoder": {
        "model_name": "BAAI/bge-reranker-base",
        "batch_size": 32,
        "max_length": 512
    },
    
    # Distribution tracking and enforcement
    "distribution_targets": {
        "lightweight": 0.40,  # 40% of queries
        "medium": 0.35,       # 35% of queries
        "full": 0.25          # 25% of queries
    },
    
    # Time targets for each strategy (in milliseconds)
    "time_targets": {
        "lightweight": 50,   # 50ms target
        "medium": 100,       # 100ms target
        "full": 200          # 200ms target
    },
    
    # Performance optimization settings
    "performance_optimization": {
        "early_termination": True,  # Enable early termination for high confidence
        "high_confidence_threshold": 0.95,  # Early terminate if top score > 0.95
        "clear_winner_gap": 0.15,  # Early terminate if gap > 0.15
        "min_diversity": 0.7,  # Minimum diversity score
        "batch_processing": True,  # Enable batch processing for cross-encoder
        "max_candidates": 40  # Maximum candidates for full reranking
    },
    
    # Query decomposition settings
    "query_decomposition": {
        "enabled": True,                    # Enable query decomposition
        "min_confidence_threshold": 0.5,    # Minimum confidence to decompose
        "max_sub_queries": 4,               # Maximum number of sub-queries
        "llm_provider": "openai",           # LLM provider for decomposition
        "decomposition_model": "gpt-4o-mini",  # Fast model for decomposition
        "synthesis_model": "gpt-4o",        # Quality model for synthesis
        "complexity_indicators": {
            "min_query_length": 150,        # Minimum characters to consider complex
            "min_entity_count": 4,          # Minimum entities to consider complex
            "min_conjunction_count": 2,     # Minimum conjunctions to consider complex
            "comparison_keywords": [        # Keywords that trigger decomposition
                "compare", "versus", "vs", "difference", "similarities",
                "pros and cons", "advantages", "disadvantages"
            ]
        },
        "sub_query_processing": {
            "top_k_per_subquery": 5,        # Results to retrieve per sub-query
            "min_confidence_threshold": 0.3  # Minimum confidence for sub-query results
        }
    }
}

# Export configurations
__all__ = [
    'POSTGRES_CONFIG',
    'NEO4J_CONFIG',
    'HYBRID_RETRIEVAL_CONFIG'
]
