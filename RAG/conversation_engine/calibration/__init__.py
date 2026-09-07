"""
Response Calibration Module

Stage 2 of the Conversation Engine pipeline.
Adjusts response tone, warmth, and style based on context analysis.
"""

# Models
from .models import ResponseCalibration

# Calibrator and rules
from .calibrator import (
    ResponseCalibrator,
    create_response_calibrator,
    get_response_calibrator,
)
from .rules import (
    SituationRules,
    MultiturnRules,
    ExecutiveRules,
    get_situation_rules,
    get_multiturn_rules,
    get_executive_rules,
)

# Attention mechanism
from .attention import (
    AttentionWeights,
    SemanticAttention,
    get_semantic_attention,
    create_semantic_attention,
)
from .voiceprint_embeddings import (
    VoiceprintEmbeddingCache,
    get_voiceprint_embedding_cache,
    create_voiceprint_embedding_cache,
    EMBEDDABLE_CATEGORIES,
)

__all__ = [
    # Models
    "ResponseCalibration",
    # Calibrator
    "ResponseCalibrator",
    "create_response_calibrator",
    "get_response_calibrator",
    # Rule engines
    "SituationRules",
    "MultiturnRules",
    "ExecutiveRules",
    "get_situation_rules",
    "get_multiturn_rules",
    "get_executive_rules",
    # Attention mechanism
    "AttentionWeights",
    "SemanticAttention",
    "get_semantic_attention",
    "create_semantic_attention",
    "VoiceprintEmbeddingCache",
    "get_voiceprint_embedding_cache",
    "create_voiceprint_embedding_cache",
    "EMBEDDABLE_CATEGORIES",
]
