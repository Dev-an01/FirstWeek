"""
Cognitive Twin Module - Makes executives THINK differently, not just speak differently.

This module implements the six-layer cognitive architecture:
- Layer 0: ConversationalRouter (Intent Detection)
- Layer 1: CognitiveLens (Domain Affinity Reranking)
- Layer 2: CognitiveFrame (Reasoning Injection)
- Layer 3: Voice Expression (Existing voiceprint system)
- Layer 4: SituationAnalyzer (Context Understanding)
- Layer 5: RelationshipAdapter (Communication Adaptation)
- Layer 6: MemorySystem (Continuity - future)

The key principle: Database is the brain. All cognitive data comes from PostgreSQL,
not hardcoded dictionaries.

Usage:
    from cognitive_twin import (
        get_cognitive_profile_loader,
        get_conversational_router,
        get_cognitive_lens,
        get_cognitive_frame_builder,
        get_situation_analyzer,
        get_relationship_adapter,
        get_cognitive_prompt_assembler,
    )

    # Load cognitive profile
    loader = get_cognitive_profile_loader()
    profile = loader.load_profile("exec_001_test")

    # Check if conversational query
    router = get_conversational_router()
    routing = router.route(query, profile_id)

    if routing.should_skip_retrieval:
        # Use personality-driven response
        response = routing.personality_response
    else:
        # Apply cognitive lens to retrieval results
        lens = get_cognitive_lens()
        lens_result = lens.apply(results, profile_id)

        # Build cognitive frame
        frame_builder = get_cognitive_frame_builder()
        frame_result = frame_builder.build(query, profile_id)

        # Analyze situation
        analyzer = get_situation_analyzer()
        situation = analyzer.analyze(query)

        # Get relationship context
        adapter = get_relationship_adapter()
        relationship = adapter.adapt(profile_id, user_metadata=user_meta)

        # Assemble cognitive prompt
        assembler = get_cognitive_prompt_assembler()
        prompt = assembler.assemble(CognitivePromptContext(
            query=query,
            profile_id=profile_id,
            cognitive_frame=frame_result,
            situation_context=situation,
            relationship_context=relationship,
            retrieved_sources=lens_result.reranked_results,
        ))
"""

from .config import COGNITIVE_CONFIG, is_layer_enabled, get_layer_config
from .profile_loader import (
    CognitiveProfileLoader,
    get_cognitive_profile_loader,
    CognitiveProfile,
    ThinkingPatterns,
    RedFlags,
    DecisionCase,
    CommunicationStyle,
    DomainAffinity,
)
from .conversational_router import (
    ConversationalRouter,
    get_conversational_router,
    ConversationalContext,
    QueryIntent,
)
from .cognitive_lens import (
    CognitiveLens,
    get_cognitive_lens,
    CognitiveLensResult,
)
from .cognitive_frame import (
    CognitiveFrameBuilder,
    get_cognitive_frame_builder,
    CognitiveFrameResult,
    ReasoningFramework,
)
from .situation_analyzer import (
    SituationAnalyzer,
    get_situation_analyzer,
    SituationContext,
    EmotionalTone,
    UrgencyLevel,
    ImplicitNeed,
    TemporalContext,
)
from .relationship_adapter import (
    RelationshipAdapter,
    get_relationship_adapter,
    RelationshipContext,
    RelationshipType,
    UserRole,
)
from .prompt_assembler import (
    CognitivePromptAssembler,
    get_cognitive_prompt_assembler,
    CognitivePromptContext,
    AssembledPrompt,
)
from .dspy_module import (
    CognitiveResponseModule,
    get_cognitive_response_module,
    personality_consistency_metric,
    cognitive_consistency_metric,
    ragas_relevance_metric,
    combined_quality_metric,
    generate_training_example,
)
from .dspy_training_dataset import (
    DSPyTrainingDatasetGenerator,
    TrainingExample,
    generate_training_dataset,
)
from .inference_engine import (
    InferenceEngine,
    get_inference_engine,
    QueryNatureClassifier,
    QueryNature,
    QueryClassification,
    InferenceResult,
)
from .langgraph_integration import (
    cognitive_route_node,
    inference_analysis_node,  # NEW: Query classification + inference preparation
    cognitive_lens_node,
    cognitive_frame_node,
    situation_analysis_node,
    relationship_adaptation_node,
    cognitive_prompt_assembly_node,
    parallel_cognitive_analysis_node,  # Priority 3: Parallelized cognitive layers
    should_skip_retrieval,
    create_cognitive_workflow_nodes,
    add_cognitive_nodes_to_graph,
    extend_state_with_cognitive,
)

__all__ = [
    # Config
    "COGNITIVE_CONFIG",
    "is_layer_enabled",
    "get_layer_config",
    # Profile Loader
    "CognitiveProfileLoader",
    "get_cognitive_profile_loader",
    "CognitiveProfile",
    "ThinkingPatterns",
    "RedFlags",
    "DecisionCase",
    "CommunicationStyle",
    "DomainAffinity",
    # Conversational Router
    "ConversationalRouter",
    "get_conversational_router",
    "ConversationalContext",
    "QueryIntent",
    # Cognitive Lens
    "CognitiveLens",
    "get_cognitive_lens",
    "CognitiveLensResult",
    # Cognitive Frame
    "CognitiveFrameBuilder",
    "get_cognitive_frame_builder",
    "CognitiveFrameResult",
    "ReasoningFramework",
    # Situation Analyzer
    "SituationAnalyzer",
    "get_situation_analyzer",
    "SituationContext",
    "EmotionalTone",
    "UrgencyLevel",
    "ImplicitNeed",
    "TemporalContext",
    # Relationship Adapter
    "RelationshipAdapter",
    "get_relationship_adapter",
    "RelationshipContext",
    "RelationshipType",
    "UserRole",
    # Prompt Assembler
    "CognitivePromptAssembler",
    "get_cognitive_prompt_assembler",
    "CognitivePromptContext",
    "AssembledPrompt",
    # DSPy Module
    "CognitiveResponseModule",
    "get_cognitive_response_module",
    "personality_consistency_metric",
    "cognitive_consistency_metric",
    "ragas_relevance_metric",
    "combined_quality_metric",
    "generate_training_example",
    # DSPy Training Dataset
    "DSPyTrainingDatasetGenerator",
    "TrainingExample",
    "generate_training_dataset",
    # Inference Engine
    "InferenceEngine",
    "get_inference_engine",
    "QueryNatureClassifier",
    "QueryNature",
    "QueryClassification",
    "InferenceResult",
    # LangGraph Integration
    "cognitive_route_node",
    "inference_analysis_node",  # NEW: Query classification + inference preparation
    "cognitive_lens_node",
    "cognitive_frame_node",
    "situation_analysis_node",
    "relationship_adaptation_node",
    "cognitive_prompt_assembly_node",
    "parallel_cognitive_analysis_node",  # Priority 3: Parallelized cognitive layers
    "should_skip_retrieval",
    "create_cognitive_workflow_nodes",
    "add_cognitive_nodes_to_graph",
    "extend_state_with_cognitive",
]
