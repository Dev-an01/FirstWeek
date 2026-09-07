"""
Conversation Engine - Unified Prompt Generation System

A 5-stage pipeline for context-aware, conversation-stateful prompt generation
that produces authentic executive voice responses.

Stages:
1. Context Analyzer - Classify query (theme, urgency, emotion)
2. Response Calibrator - Adjust tone/style based on context
3. Example Selector - Match best communication example
4. Precedent Selector - Find relevant decision cases
5. Prompt Assembler - Build final prompt within token budget

Modes:
- STATELESS: No session, ~45ms overhead (curl/API tests)
- SESSION: Multi-turn with history, ~60ms overhead (chat UI)
- MEMORY_AWARE: Session + episodic memory, ~85ms overhead (full relationship)

Usage:
    from conversation_engine import ConversationEngine, ConversationMode

    engine = ConversationEngine(session_manager, profile_manager)
    system_prompt, user_prompt, state = await engine.generate(
        query="What's our approach to budget overruns?",
        profile_id="exec_001_test",
        retrieved_context=context,
        session_id="sess_123"
    )
"""

from .engine import ConversationEngine, get_conversation_engine
from .context.models import (
    ConversationMode,
    ConversationState,
    ConversationTurn,
    ManagedContext,
)
# Context management
from .context.context_manager import ContextManager, create_context_manager
from .context.session_store import SessionStore
from .context.reference_resolver import ReferenceResolver, get_reference_resolver

from .analysis.models import (
    Theme,
    Urgency,
    UserEmotion,
    TurnType,
    QueryType,
    AnalyzedContext,
)
# Analysis
from .analysis.analyzer import ContextAnalyzer, create_context_analyzer, get_context_analyzer

from .calibration.models import ResponseCalibration
# Calibration
from .calibration.calibrator import (
    ResponseCalibrator,
    create_response_calibrator,
    get_response_calibrator,
)
# Attention mechanism
from .calibration.attention import (
    AttentionWeights,
    SemanticAttention,
    get_semantic_attention,
    create_semantic_attention,
)
from .calibration.voiceprint_embeddings import (
    VoiceprintEmbeddingCache,
    get_voiceprint_embedding_cache,
    create_voiceprint_embedding_cache,
    EMBEDDABLE_CATEGORIES,
)

from .examples.models import SelectedExample, ExampleEmbedding
# Example selection
from .examples.embedding_service import (
    EmbeddingService,
    get_embedding_service,
    create_embedding_service,
)
from .examples.embedding_cache import (
    EmbeddingCache,
    get_embedding_cache,
    create_embedding_cache,
)
from .examples.selector import (
    SemanticExampleSelector,
    get_example_selector,
    create_example_selector,
)

from .precedents.models import SelectedPrecedent, PrecedentCategory, PrecedentEmbedding
# Precedent selection
from .precedents.selector import (
    PrecedentSelector,
    get_precedent_selector,
    create_precedent_selector,
)

# Prompt assembly
from .prompt import (
    TokenBudget,
    TokenBudgetManager,
    get_budget_manager,
    create_budget_manager,
    BaseTemplate,
    FastTemplate,
    StandardTemplate,
    AgenticTemplate,
    PromptAssembler,
    get_prompt_assembler,
    create_prompt_assembler,
)

# State management
from .state import (
    StateUpdater,
    StateUpdateResult,
    get_state_updater,
    create_state_updater,
)

__all__ = [
    # Main engine
    "ConversationEngine",
    "get_conversation_engine",
    # Context models
    "ConversationMode",
    "ConversationState",
    "ConversationTurn",
    "ManagedContext",
    # Context management
    "ContextManager",
    "create_context_manager",
    "SessionStore",
    "ReferenceResolver",
    "get_reference_resolver",
    # Analysis models
    "Theme",
    "Urgency",
    "UserEmotion",
    "TurnType",
    "QueryType",
    "AnalyzedContext",
    # Analysis
    "ContextAnalyzer",
    "create_context_analyzer",
    "get_context_analyzer",
    # Calibration
    "ResponseCalibration",
    "ResponseCalibrator",
    "create_response_calibrator",
    "get_response_calibrator",
    # Attention mechanism
    "AttentionWeights",
    "SemanticAttention",
    "get_semantic_attention",
    "create_semantic_attention",
    "VoiceprintEmbeddingCache",
    "get_voiceprint_embedding_cache",
    "create_voiceprint_embedding_cache",
    "EMBEDDABLE_CATEGORIES",
    # Example selection
    "SelectedExample",
    "ExampleEmbedding",
    "EmbeddingService",
    "get_embedding_service",
    "create_embedding_service",
    "EmbeddingCache",
    "get_embedding_cache",
    "create_embedding_cache",
    "SemanticExampleSelector",
    "get_example_selector",
    "create_example_selector",
    # Precedent selection
    "SelectedPrecedent",
    "PrecedentCategory",
    "PrecedentEmbedding",
    "PrecedentSelector",
    "get_precedent_selector",
    "create_precedent_selector",
    # Prompt assembly
    "TokenBudget",
    "TokenBudgetManager",
    "get_budget_manager",
    "create_budget_manager",
    "BaseTemplate",
    "FastTemplate",
    "StandardTemplate",
    "AgenticTemplate",
    "PromptAssembler",
    "get_prompt_assembler",
    "create_prompt_assembler",
    # State management
    "StateUpdater",
    "StateUpdateResult",
    "get_state_updater",
    "create_state_updater",
]

__version__ = "0.3.0"
