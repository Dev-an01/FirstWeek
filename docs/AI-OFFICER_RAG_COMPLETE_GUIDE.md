# RAG System: Complete Developer Onboarding Guide

> **Version**: 2.0 | **Last Updated**: January 2025
> **Audience**: New developers joining the RAG development team
> **Prerequisites**: Python, async programming, basic ML/NLP concepts

---

## Table of Contents

1. [System Philosophy & Vision](#1-system-philosophy--vision)
2. [Architecture Overview](#2-architecture-overview)
3. [Codebase Structure](#3-codebase-structure)
4. [Data Flow Deep Dive](#4-data-flow-deep-dive)
5. [Core Components Explained](#5-core-components-explained)
6. [Database Architecture](#6-database-architecture)
7. [API Layer](#7-api-layer)
8. [Executive Profiles & Cognitive Twin](#8-executive-profiles--cognitive-twin)
9. [Hybrid Retrieval System](#9-hybrid-retrieval-system)
10. [LLM Integration](#10-llm-integration)
11. [Conversation Engine & Prompts](#11-conversation-engine--prompts)
12. [LangGraph Workflow](#12-langgraph-workflow)
13. [Audio Services](#13-audio-services)
14. [Observability & Monitoring](#14-observability--monitoring)
15. [Configuration Management](#15-configuration-management)
16. [Testing Strategy](#16-testing-strategy)
17. [Development Workflow](#17-development-workflow)
18. [Future Architecture: Neural Graph Engine](#18-future-architecture-neural-graph-engine)
19. [Troubleshooting Guide](#19-troubleshooting-guide)
20. [Glossary](#20-glossary)

---

## 1. System Philosophy & Vision

### 1.1 What We're Building

This is not a generic chatbot. We're building **Cognitive Twins** - AI representations that:
- **Think** like specific executives (not just speak like them)
- **Reason** using their actual decision-making frameworks
- **Reference** real past decisions with outcomes
- **Maintain** personality consistency across thousands of interactions

### 1.2 Core Principles

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SYSTEM PRINCIPLES                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. DATABASE IS THE BRAIN                                               │
│     All cognitive data comes from PostgreSQL/Neo4j, NOT hardcoded       │
│     templates. This enables scalability and personalization.            │
│                                                                         │
│  2. GRAPH CONSTRAINS VECTOR                                             │
│     Graph traversal narrows search space BEFORE vector similarity.      │
│     This is 10-100x faster and more relevant than pure vector search.   │
│                                                                         │
│  3. NEVER SAY "I DON'T KNOW" FOR OPINIONS                               │
│     Executives have opinions. The InferenceEngine forms opinions        │
│     from values/thinking patterns when no retrieval data exists.        │
│                                                                         │
│  4. RECENCY BIAS EXPLOITATION                                           │
│     Critical instructions go LAST in prompts. LLMs pay ~2x attention    │
│     to final tokens. Reasoning goes FIRST to force System 2 thinking.   │
│                                                                         │
│  5. SOFT TARGETS, NOT HARD LIMITS                                       │
│     Word limits are targets ("AIM FOR ~35"), not ceilings.              │
│     This allows natural expression while guiding brevity.               │
│                                                                         │
│  6. SYMBOLIC GUARDRAILS ARE SACRED                                      │
│     Red flags, compliance rules, and escalation triggers are NEVER      │
│     overridden by learning or optimization. Safety is non-negotiable.   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.3 Why This Architecture?

| Challenge | Our Solution |
|-----------|--------------|
| Generic AI responses | Executive-specific cognitive frameworks |
| Hallucinated citations | Graph-constrained retrieval + validation |
| Inconsistent personality | Voiceprint embeddings + style markers |
| Slow complex queries | Multi-path routing (fast/standard/agentic) |
| No learning | Feedback loops + adaptive weights (future) |

---

## 2. Architecture Overview

### 2.1 High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           RAG SYSTEM ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  CLIENTS                                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                       │
│  │ Frontend │ │ Project  │ │ Chat     │ │ External │                       │
│  │ (Vite)   │ │ Guide    │ │ Service  │ │ APIs     │                       │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘                       │
│       │            │            │            │                              │
│       └────────────┴────────────┴────────────┘                              │
│                         │                                                   │
│  ═══════════════════════╪═══════════════════════════════════════════════   │
│                         ▼                                                   │
│  API LAYER         ┌─────────────────────────────────────────────────┐     │
│                    │              FastAPI Server (8000)               │     │
│                    │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐│     │
│                    │  │ /chat   │ │/langgraph│ │/profiles│ │ /audio ││     │
│                    │  └─────────┘ └─────────┘ └─────────┘ └────────┘│     │
│                    └─────────────────────────────────────────────────┘     │
│                         │                                                   │
│  ═══════════════════════╪═══════════════════════════════════════════════   │
│                         ▼                                                   │
│  ORCHESTRATION    ┌─────────────────────────────────────────────────┐      │
│                   │           LangGraph Workflow                     │      │
│                   │  ┌────────────────────────────────────────────┐ │      │
│                   │  │ cognitive_route → analyze → route_query    │ │      │
│                   │  │      ↓              ↓           ↓          │ │      │
│                   │  │ [conversational] [fast]  [standard] [agentic]│      │
│                   │  │      ↓              ↓           ↓          │ │      │
│                   │  │   generate     retrieve → fuse → rerank    │ │      │
│                   │  │                              ↓             │ │      │
│                   │  │                     cognitive_layers       │ │      │
│                   │  │                              ↓             │ │      │
│                   │  │                    prompt_assembly         │ │      │
│                   │  │                              ↓             │ │      │
│                   │  │                      generate → END        │ │      │
│                   │  └────────────────────────────────────────────┘ │      │
│                   └─────────────────────────────────────────────────┘      │
│                         │                                                   │
│  ═══════════════════════╪═══════════════════════════════════════════════   │
│                         ▼                                                   │
│  PROCESSING       ┌─────────────────────────────────────────────────┐      │
│                   │                                                  │      │
│  ┌────────────────┴──┐  ┌──────────────┐  ┌──────────────────────┐ │      │
│  │ Hybrid Retrieval  │  │ Cognitive    │  │ Conversation Engine  │ │      │
│  │ ┌──────────────┐  │  │ Twin         │  │ ┌──────────────────┐ │ │      │
│  │ │VectorSearch  │  │  │ ┌──────────┐ │  │ │ Context Analyzer │ │ │      │
│  │ │(pgvector)    │  │  │ │Router    │ │  │ ├──────────────────┤ │ │      │
│  │ ├──────────────┤  │  │ ├──────────┤ │  │ │ Calibrator       │ │ │      │
│  │ │GraphContext  │  │  │ │Lens      │ │  │ ├──────────────────┤ │ │      │
│  │ │(Neo4j)       │  │  │ ├──────────┤ │  │ │ Example Selector │ │ │      │
│  │ ├──────────────┤  │  │ │Frame     │ │  │ ├──────────────────┤ │ │      │
│  │ │MemorySearch  │  │  │ ├──────────┤ │  │ │ Prompt Assembler │ │ │      │
│  │ │(episodic)    │  │  │ │Situation │ │  │ └──────────────────┘ │ │      │
│  │ ├──────────────┤  │  │ ├──────────┤ │  └──────────────────────┘ │      │
│  │ │ResultFusion  │  │  │ │Inference │ │                           │      │
│  │ └──────────────┘  │  │ └──────────┘ │                           │      │
│  └───────────────────┘  └──────────────┘                           │      │
│                   └─────────────────────────────────────────────────┘      │
│                         │                                                   │
│  ═══════════════════════╪═══════════════════════════════════════════════   │
│                         ▼                                                   │
│  LLM LAYER        ┌─────────────────────────────────────────────────┐      │
│                   │              LLM Orchestrator                    │      │
│                   │  ┌─────────┐ ┌─────────┐ ┌─────────┐           │      │
│                   │  │ Fast    │ │Standard │ │Agentic  │           │      │
│                   │  │ Handler │ │Handler  │ │Handler  │           │      │
│                   │  └────┬────┘ └────┬────┘ └────┬────┘           │      │
│                   │       └──────────┼──────────┘                   │      │
│                   │                  ▼                               │      │
│                   │         LLMClientFactory                         │      │
│                   │  ┌───────┬───────┬───────┬────────┐            │      │
│                   │  │OpenAI │ Groq  │Gemini │  GLM   │            │      │
│                   │  └───────┴───────┴───────┴────────┘            │      │
│                   └─────────────────────────────────────────────────┘      │
│                         │                                                   │
│  ═══════════════════════╪═══════════════════════════════════════════════   │
│                         ▼                                                   │
│  DATA LAYER       ┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │
│                   │ PostgreSQL  │ │   Neo4j     │ │   Redis     │         │
│                   │ + pgvector  │ │ (Graph DB)  │ │  (Cache)    │         │
│                   └─────────────┘ └─────────────┘ └─────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Request Lifecycle

```
1. REQUEST RECEIVED
   │
   ├─ User sends query via /api/v1/chat or /api/v1/langgraph/chat
   ├─ Request validated (ChatRequest pydantic model)
   ├─ Session resolved or created
   └─ Profile normalized (e.g., "sample" → "sample_profile")
   │
2. COGNITIVE ROUTING (Layer 0)
   │
   ├─ ConversationalRouter.route(query)
   ├─ Checks: Is this greeting/small-talk?
   │   ├─ YES → Skip retrieval, return personality response
   │   └─ NO  → Continue to query analysis
   │
3. QUERY ANALYSIS
   │
   ├─ QueryAnalyzer.analyze(query)
   │   ├─ Extract entities (GLiNER + spaCy)
   │   ├─ Classify type (factual/decision/opinion/analysis)
   │   ├─ Detect complexity (simple/medium/complex)
   │   └─ Identify intent (approval, recommendation, comparison, etc.)
   │
   ├─ QueryRouter.route(analysis)
   │   └─ Determine path: fast / standard / agentic
   │
4. HYBRID RETRIEVAL
   │
   ├─ [Parallel Execution]
   │   ├─ GraphContextProvider.discover_context(query)
   │   │   ├─ Entity extraction
   │   │   ├─ Neo4j traversal (1-3 hops)
   │   │   └─ Returns: candidate_ids, distances, relationships
   │   │
   │   ├─ VectorSearchEngine.search(query, candidates=graph_candidates)
   │   │   ├─ Constrained to graph candidates
   │   │   ├─ pgvector cosine similarity
   │   │   └─ Returns: scored documents
   │   │
   │   └─ MemorySearchEngine.search(query, exec_id)
   │       ├─ 5-signal scoring
   │       └─ Returns: relevant past interactions
   │
   ├─ ResultFusion.fuse(vector, graph, memory)
   │   ├─ Score normalization
   │   ├─ Weighted combination (60/30/10)
   │   ├─ Multi-source boost (+10-15%)
   │   └─ Returns: fused_results
   │
   ├─ AdaptiveReranker.rerank(fused_results, query_type)
   │   ├─ Strategy selection (lightweight/medium/full)
   │   └─ Returns: reranked_results
   │
5. COGNITIVE TWIN LAYERS
   │
   ├─ CognitiveLens.apply(results, exec_profile)
   │   └─ Rerank by domain affinity
   │
   ├─ CognitiveFrame.build(query, exec_profile)
   │   ├─ Extract thinking patterns
   │   ├─ Find similar past decisions
   │   └─ Inject reasoning framework
   │
   ├─ SituationAnalyzer.analyze(query, context)
   │   ├─ Detect urgency (routine/important/critical)
   │   ├─ Detect emotion (neutral/concerned/excited)
   │   └─ Identify implicit needs
   │
   ├─ RelationshipAdapter.adapt(user_context)
   │   └─ Adjust formality/depth for relationship type
   │
   ├─ InferenceEngine.process(query, profile)
   │   ├─ Classify query nature (factual/opinion/decision)
   │   └─ Build inference reasoning if needed
   │
6. PROMPT ASSEMBLY (5-Stage Pipeline)
   │
   ├─ PromptAssembler.assemble(all_context)
   │   ├─ Select template (fast/standard/agentic)
   │   ├─ Calculate token budgets
   │   ├─ Build sections:
   │   │   ├─ ReasoningSection (ALWAYS FIRST)
   │   │   ├─ IdentitySection
   │   │   ├─ CalibrationSection
   │   │   ├─ ValuesSection (standard/agentic only)
   │   │   ├─ PrecedentSection (if relevant)
   │   │   ├─ ExampleSection
   │   │   └─ InstructionsSection (ALWAYS LAST)
   │   └─ Returns: (system_prompt, user_prompt)
   │
7. LLM GENERATION
   │
   ├─ LLMOrchestrator.generate(system_prompt, user_prompt)
   │   ├─ Select handler (FastPath/StandardPath/AgenticPath)
   │   ├─ [Agentic only] ReAct loop (4-6 iterations)
   │   ├─ Call LLM provider
   │   └─ Returns: raw_response
   │
8. RESPONSE FORMATTING
   │
   ├─ ResponseFormatter.format(raw_response)
   │   ├─ Extract citations
   │   ├─ Validate sources
   │   ├─ Apply word count checks
   │   └─ Returns: formatted_response
   │
   ├─ QualityEvaluator.evaluate(response) [10% sample]
   │   └─ RAGAS metrics
   │
   ├─ SessionManager.store_turn(query, response)
   │   └─ Persist for multi-turn continuity
   │
9. RESPONSE RETURNED
   │
   └─ ChatResponse with: answer, citations, sources, metadata
```

---

## 3. Codebase Structure

### 3.1 Directory Layout

```
RAG/
├── api/                              # FastAPI Application Layer
│   ├── main.py                       # Entry point, startup sequence
│   ├── dependencies.py               # Dependency injection, singletons
│   ├── config.py                     # API configuration
│   ├── models.py                     # Pydantic request/response schemas
│   ├── langgraph_endpoints.py        # LangGraph workflow endpoints
│   ├── session_endpoints.py          # Session management
│   ├── audio_endpoints.py            # TTS streaming
│   ├── stt_endpoints.py              # Speech-to-text
│   └── feedback_endpoints.py         # User feedback collection
│
├── langgraph_workflow/               # LangGraph Orchestration
│   ├── graph.py                      # Workflow graph assembly
│   ├── state.py                      # RAGState TypedDict
│   ├── nodes.py                      # Node implementations (~1400 lines)
│   ├── react_subgraph.py             # ReAct reasoning (~1800 lines)
│   └── react_tools/                  # Tools for ReAct
│
├── cognitive_twin/                   # Personality Layer
│   ├── conversational_router.py      # Layer 0: Small-talk detection
│   ├── inference_engine.py           # Opinion/decision reasoning
│   ├── cognitive_lens.py             # Domain affinity reranking
│   ├── cognitive_frame.py            # Thinking pattern injection
│   ├── situation_analyzer.py         # Urgency/emotion detection
│   ├── relationship_adapter.py       # Communication adaptation
│   └── config.py                     # Cognitive layer config
│
├── conversation_engine/              # 5-Stage Prompt Pipeline
│   ├── engine.py                     # Main ConversationEngine
│   ├── context/                      # Session context management
│   │   ├── context_manager.py
│   │   ├── session_store.py
│   │   └── reference_resolver.py
│   ├── analysis/                     # Query/context analysis
│   │   ├── analyzer.py
│   │   └── classifiers/
│   ├── calibration/                  # Tone/style adjustment
│   │   ├── calibrator.py
│   │   └── attention.py              # SemanticAttention
│   ├── examples/                     # Few-shot selection
│   │   ├── selector.py
│   │   └── embedding_service.py
│   ├── precedents/                   # Historical decisions
│   │   └── selector.py
│   └── prompt/                       # Prompt assembly
│       ├── assembler.py              # Main assembler
│       ├── rules.py                  # SINGLE SOURCE OF TRUTH
│       ├── budget.py                 # Token budget management
│       ├── sections/                 # Section builders
│       │   ├── reasoning_section.py
│       │   ├── identity_section.py
│       │   ├── calibration_section.py
│       │   ├── instructions_section.py
│       │   ├── values_section.py
│       │   ├── example_section.py
│       │   └── precedent_section.py
│       └── templates/                # Path-specific templates
│
├── hybrid_retrieval/                 # Multi-Source Retrieval
│   ├── manager.py                    # HybridRetrievalManager
│   ├── query_analyzer.py             # Query feature extraction
│   ├── query_router.py               # Path routing
│   ├── query_decomposer.py           # Complex query splitting
│   ├── graph_enhanced_search.py      # Graph-constrained vector
│   ├── result_fusion.py              # Multi-source combination
│   ├── adaptive_reranker.py          # Smart reranking
│   ├── memory_search.py              # Episodic memory
│   ├── response_builder.py           # Citation formatting
│   └── config.py                     # Retrieval config
│
├── vector_search/                    # Semantic Search
│   ├── search_engine.py              # VectorSearchEngine
│   ├── postgres_client.py            # pgvector operations
│   ├── embedding_cache.py            # 2-tier cache
│   ├── query_processor.py            # Query preprocessing
│   ├── result_processor.py           # Result postprocessing
│   ├── rbac_filter.py                # Access control
│   └── config.py
│
├── graph_context/                    # Knowledge Graph
│   ├── provider.py                   # GraphContextProvider
│   ├── entity_extractor.py           # GLiNER + spaCy NER
│   ├── graph_traversal.py            # Neo4j queries
│   ├── relationship_mapper.py        # Path explanation
│   └── config.py
│
├── llm_integration/                  # LLM Orchestration
│   ├── orchestrator.py               # Main orchestrator
│   ├── factory.py                    # LLMClientFactory
│   ├── fast_path_handler.py          # <2s responses
│   ├── standard_path_handler.py      # <3s responses
│   ├── agentic_path_handler.py       # <5s with ReAct
│   ├── prompt_builder.py             # Standard prompt building
│   ├── prompt_builder_dual_stream.py # Parallel streams
│   ├── prompt_builder_two_stage.py   # MMR compression
│   ├── response_formatter.py         # Citation/formatting
│   └── config.py
│
├── profile_management/               # Executive Profiles
│   ├── profile_manager.py            # Main manager (singleton)
│   ├── profile_loader.py             # JSON loading + voiceprint merge
│   ├── prompt_generator.py           # Legacy prompt gen (deprecated)
│   ├── voiceprint_cache.py           # Style caching
│   ├── example_selector.py           # Communication examples
│   └── dynamic_examples.py           # Learned examples
│
├── memory/                           # Session & Episodic Memory
│   ├── session_manager.py            # Multi-turn orchestration
│   └── conversation_sessions.py      # PostgreSQL-backed sessions
│
├── audio_services/                   # TTS/STT
│   ├── tts_manager.py                # TTS orchestration
│   ├── tts_service.py                # Kokoro TTS
│   ├── chirp3_instant_service.py     # Google Cloud TTS
│   ├── stt_service.py                # Whisper STT
│   ├── realtime_tts_service.py       # WebSocket streaming
│   └── realtime_stt_service.py       # WebSocket STT
│
├── embedding_generation/             # Embedding Models
│   └── model_manager.py              # SentenceTransformer wrapper
│
├── cache/                            # Caching System
│   ├── cache_manager.py              # L1 + L2 orchestration
│   ├── embedding_cache.py            # Query embeddings
│   ├── semantic_query_cache.py       # Deduplication
│   └── monitoring.py
│
├── observability/                    # Tracing & Metrics
│   ├── decorators.py                 # @trace_function
│   ├── logging.py                    # Structured logging
│   ├── metrics.py                    # Prometheus metrics
│   ├── middleware.py                 # FastAPI observability
│   ├── tracing.py                    # OpenTelemetry
│   ├── quality_evaluator.py          # RAGAS evaluation
│   └── db_persistence.py             # Metrics storage
│
├── config/                           # Configuration
│   ├── llm_config.yaml               # LLM provider settings
│   ├── llm_config_loader.py          # Config parser
│   └── postgres_schema.sql           # Database schema
│
├── test_data/                        # Test Fixtures
│   ├── executive_profiles/           # Profile JSONs
│   │   └── sample_profile.json        # Primary test profile
│   ├── voiceprints/                  # Style JSONs
│   │   └── sample_profile_voiceprint.json
│   ├── documents/                    # Sample docs
│   └── graph_data/                   # Neo4j test data
│
├── init-scripts/                     # Database Init
│   ├── load_postgres_data.py         # Profile/doc loading
│   ├── load_neo4j_data.py            # Graph data
│   └── generate_embeddings.py        # Embedding generation
│
├── Dockerfile                        # Container build
├── docker-entrypoint.sh              # Startup script
└── requirements.txt                  # Dependencies
```

### 3.2 Key Files to Know

| File | Purpose | When to Modify |
|------|---------|----------------|
| `api/main.py` | Application startup, dependency wiring | Adding new services |
| `langgraph_workflow/nodes.py` | Core workflow nodes | Adding processing steps |
| `langgraph_workflow/react_subgraph.py` | ReAct reasoning | Modifying agentic behavior |
| `conversation_engine/prompt/rules.py` | **SINGLE SOURCE OF TRUTH** for rules | Changing word limits, anti-AI rules |
| `conversation_engine/prompt/assembler.py` | Prompt assembly | Changing prompt structure |
| `conversation_engine/prompt/sections/*.py` | Individual sections | Adding/modifying prompt content |
| `hybrid_retrieval/config.py` | Retrieval weights, thresholds | Tuning retrieval |
| `cognitive_twin/conversational_router.py` | Small-talk detection | Adding conversation patterns |
| `cognitive_twin/inference_engine.py` | Opinion/decision reasoning | Changing inference logic |
| `config/llm_config.yaml` | LLM providers, models | Adding providers, changing models |
| `test_data/executive_profiles/*.json` | Executive definitions | Adding/modifying executives |

---

## 4. Data Flow Deep Dive

### 4.1 Query Analysis Flow

```python
# File: hybrid_retrieval/query_analyzer.py

class QueryAnalyzer:
    """
    Extracts features from queries to determine processing strategy.

    Output: QueryAnalysis with:
    - entities: List of extracted named entities
    - query_type: factual | decision | opinion | analysis
    - complexity: simple | medium | complex
    - intent: approval_request | information_lookup | comparison | etc.
    - keywords: Top extracted keywords
    - strategy_recommendation: vector_only | vector_graph | full_hybrid
    """

    def analyze(self, query: str) -> QueryAnalysis:
        # 1. Extract entities
        entities = self._extract_entities(query)  # GLiNER + spaCy

        # 2. Classify query type
        query_type = self._classify_type(query)

        # 3. Calculate complexity
        complexity = self._calculate_complexity(
            query_length=len(query),
            entity_count=len(entities),
            has_conjunctions=self._has_conjunctions(query)
        )

        # 4. Identify intent
        intent = self._identify_intent(query)

        return QueryAnalysis(
            entities=entities,
            query_type=query_type,
            complexity=complexity,
            intent=intent,
            ...
        )

# Complexity scoring:
# - Length: <50 chars = 0, 50-100 = 1, >100 = 2
# - Entities: 0-1 = 0, 2-3 = 1, >3 = 2
# - Query type: factual = 0, decision = 1, analysis = 2
# - Multi-part: no = 0, yes = 1
#
# simple: score ≤ 1
# medium: score 2-4
# complex: score > 4
```

### 4.2 Hybrid Retrieval Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HYBRID RETRIEVAL FLOW                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Query: "What did sample decide about the MegaCorp discount?"           │
│                                                                         │
│  STEP 1: ENTITY EXTRACTION                                              │
│  ──────────────────────────                                             │
│  EntityExtractor.extract(query)                                         │
│  │                                                                      │
│  ├─ Pattern Matching: No matches                                        │
│  ├─ GLiNER: "sample" → Person (0.95), "MegaCorp" → Company (0.88)      │
│  └─ Result: [                                                           │
│       {text: "sample", type: "Person", confidence: 0.95},               │
│       {text: "MegaCorp", type: "Company", confidence: 0.88}             │
│     ]                                                                   │
│                                                                         │
│  STEP 2: GRAPH CONTEXT DISCOVERY                                        │
│  ───────────────────────────────                                        │
│  GraphContextProvider.discover_context(query, entities)                 │
│  │                                                                      │
│  ├─ Match entities to graph nodes:                                      │
│  │   "sample" → :Executive {id: "sample_profile"}                       │
│  │   "MegaCorp" → :Company {id: "megacorp_001"}                        │
│  │                                                                      │
│  ├─ Traverse from anchor nodes (1-3 hops):                             │
│  │   MATCH (anchor)-[*1..3]-(doc:Decision)                             │
│  │   WHERE doc.confidentiality IN ['public', 'internal']               │
│  │                                                                      │
│  └─ Result:                                                             │
│       candidate_ids: ["DC_sample_001", "DC_sample_003", ...]           │
│       distances: {"DC_sample_001": 1, "DC_sample_003": 2}              │
│       relationships: [{source, target, type, distance}]                 │
│                                                                         │
│  STEP 3: CONSTRAINED VECTOR SEARCH                                      │
│  ─────────────────────────────────                                      │
│  VectorSearchEngine.search(query, candidate_ids=graph_candidates)       │
│  │                                                                      │
│  ├─ Generate query embedding                                            │
│  ├─ Search pgvector index ONLY within candidate_ids                    │
│  └─ Result: [                                                           │
│       {id: "DC_sample_001", vector_score: 0.89},                       │
│       {id: "DC_sample_003", vector_score: 0.76}                        │
│     ]                                                                   │
│                                                                         │
│  STEP 4: MEMORY SEARCH (Parallel)                                       │
│  ─────────────────────────────────                                      │
│  MemorySearchEngine.search(query, exec_id="sample_profile")              │
│  │                                                                      │
│  ├─ 5-signal scoring:                                                   │
│  │   - Semantic similarity                                              │
│  │   - Temporal recency                                                 │
│  │   - Importance score                                                 │
│  │   - Feedback multiplier                                              │
│  │   - Topic overlap                                                    │
│  └─ Result: past interactions about similar topics                      │
│                                                                         │
│  STEP 5: RESULT FUSION                                                  │
│  ─────────────────────                                                  │
│  ResultFusion.fuse(vector_results, graph_context, memory_results)       │
│  │                                                                      │
│  ├─ Score normalization (0-1 scale)                                     │
│  ├─ Weighted combination:                                               │
│  │   composite = 0.60*vector + 0.30*graph + 0.10*memory                │
│  ├─ Multi-source boost:                                                 │
│  │   +10% if found in 2 sources, +15% if found in 3                    │
│  └─ Result: fused_results sorted by composite_score                     │
│                                                                         │
│  STEP 6: ADAPTIVE RERANKING                                             │
│  ──────────────────────────                                             │
│  AdaptiveReranker.rerank(fused_results, query_analysis)                 │
│  │                                                                      │
│  ├─ Quality assessment:                                                 │
│  │   - top_score > 0.85 AND gap > 0.25 → Lightweight                   │
│  │   - top_score 0.70-0.85 → Medium                                    │
│  │   - top_score < 0.70 → Full                                         │
│  │                                                                      │
│  ├─ Strategy execution:                                                 │
│  │   Lightweight: Score normalization only (~50ms)                      │
│  │   Medium: + Cross-encoder on top 10 (~100ms)                        │
│  │   Full: Cross-encoder on all candidates (~200ms)                    │
│  │                                                                      │
│  └─ Result: reranked_results with final scores                          │
│                                                                         │
│  Final Output:                                                          │
│  ─────────────                                                          │
│  [                                                                      │
│    {                                                                    │
│      id: "DC_sample_001",                                              │
│      title: "MegaCorp Discount Decision",                              │
│      content: "Approved 18% discount...",                              │
│      composite_score: 0.934,                                           │
│      sources: ["vector", "graph"],                                     │
│      provenance: "Distance 1 from sample"                              │
│    },                                                                   │
│    ...                                                                  │
│  ]                                                                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.3 Prompt Assembly Flow

```python
# File: conversation_engine/prompt/assembler.py

class PromptAssembler:
    """
    Assembles final prompts from multiple sections.

    KEY RULES:
    1. ReasoningSection ALWAYS goes FIRST (forces System 2 thinking)
    2. InstructionsSection ALWAYS goes LAST (recency bias)
    3. Token budgets are strictly enforced
    4. Dynamic reallocation when sections are skipped
    """

    def assemble(
        self,
        profile_id: str,
        path: str,  # fast | standard | agentic
        language: str,  # en | ja
        retrieved_context: RetrievalContext,
        managed_context: ManagedContext,
        analyzed_context: AnalyzedContext,
        calibration: ResponseCalibration,
        selected_example: SelectedExample,
        selected_precedent: SelectedPrecedent,
        audio_mode: bool = False
    ) -> Tuple[str, str]:  # (system_prompt, user_prompt)

        # 1. Load executive profile
        profile = self._load_profile(profile_id)

        # 2. Select template based on path
        template = self._templates[path]
        # fast: 450 tokens total
        # standard: 620 tokens total
        # agentic: 780 tokens total

        # 3. Determine which sections to include
        has_session = managed_context.mode != STATELESS
        has_precedent = not selected_precedent.skipped

        effective_sections = template.get_effective_sections(
            has_session, has_precedent
        )

        # 4. CRITICAL: Inject reasoning at position 0
        if "reasoning" not in effective_sections:
            effective_sections.insert(0, "reasoning")

        # 5. Build each section
        sections = []
        for section_name in effective_sections:
            budget = template.get_section_budget(section_name)
            section_text = self._build_section(
                section_name, budget, profile, ...
            )
            sections.append(section_text)

        # 6. Assemble system prompt
        system_prompt = "\n\n".join(sections)

        # 7. Build user prompt
        user_prompt = self._build_user_prompt(
            query=managed_context.resolved_query,
            retrieved_context=retrieved_context,
            path=path
        )

        return system_prompt, user_prompt
```

**Section Order (Standard Path)**:
```
1. ReasoningSection      (80-100 tokens)  ← FIRST: Cognitive script
2. IdentitySection       (180-200 tokens) ← Personality injection
3. ConversationContext   (60 tokens)      ← If has_session
4. ExampleSection        (100-150 tokens) ← Communication style demo
5. CalibrationSection    (50-80 tokens)   ← Tone/length guidance
6. ValuesSection         (50-70 tokens)   ← Decision philosophy
7. PrecedentSection      (60-80 tokens)   ← If has_precedent
8. InstructionsSection   (60-100 tokens)  ← LAST: Anti-AI rules
```

---

## 5. Core Components Explained

### 5.1 QueryRouter - Path Selection

```python
# File: hybrid_retrieval/query_router.py

class QueryRouter:
    """
    Routes queries to appropriate processing paths.

    Paths:
    - fast: Simple factual queries, <1.5s target
    - standard: Decision/recommendation, <2.5s target
    - agentic: Complex analysis with ReAct, <5s target
    - conversational: Greetings/small-talk, <0.5s (skip retrieval)
    """

    def route(self, query: str, analysis: QueryAnalysis) -> str:
        # Check for forced path
        if self.force_path:
            return self.force_path

        # Conversational detection (handled by ConversationalRouter)
        # ... already filtered before reaching here

        # Pattern-based routing
        query_lower = query.lower()

        # Fast patterns
        fast_patterns = [
            "what is", "who is", "define", "tell me about",
            "when was", "where is"
        ]
        if any(p in query_lower for p in fast_patterns) and len(query) < 50:
            return "fast"

        # Agentic patterns
        agentic_patterns = [
            "compare", "analyze", "evaluate", "trade-off",
            "pros and cons", "advantages and disadvantages",
            "what would you do if", "how would you approach"
        ]
        if any(p in query_lower for p in agentic_patterns):
            return "agentic"

        # Complexity-based routing
        if analysis.complexity == "complex":
            return "agentic"
        elif analysis.complexity == "simple":
            return "fast"

        # Default
        return "standard"
```

### 5.2 ConversationalRouter - Small-Talk Detection

```python
# File: cognitive_twin/conversational_router.py

class ConversationalRouter:
    """
    Layer 0: Detects conversational queries that don't need RAG.

    Priority system:
    1. Explicit patterns (regex from conversational_patterns.json)
    2. Follow-up detection (check if substantive prior context)
    3. Short query heuristic (1-4 words without retrieval keywords)
    """

    def route(
        self,
        query: str,
        conversation_history: List[Dict],
        profile: Dict
    ) -> ConversationalContext:

        # Priority 1: Check explicit patterns
        intent, confidence = self._check_patterns(query)

        if confidence > 0.75:
            # This is definitely conversational
            response = self._get_personality_response(
                intent, profile['voiceprint']
            )
            return ConversationalContext(
                should_skip_retrieval=True,
                intent=intent,
                personality_response=response,
                confidence=confidence
            )

        # Priority 2: Check for follow-up to substantive conversation
        if conversation_history:
            last_turn = conversation_history[-1]
            if self._is_substantive(last_turn) and self._is_followup(query):
                # This needs retrieval even if query is short
                return ConversationalContext(
                    should_skip_retrieval=False,
                    intent="follow_up"
                )

        # Priority 3: Short query heuristic
        word_count = self._count_words(query)  # Handles CJK
        if word_count <= 4 and not self._has_retrieval_keywords(query):
            return ConversationalContext(
                should_skip_retrieval=True,
                intent="conversational",
                ...
            )

        # Default: Needs retrieval
        return ConversationalContext(should_skip_retrieval=False)
```

### 5.3 InferenceEngine - Opinion Formation

```python
# File: cognitive_twin/inference_engine.py

class InferenceEngine:
    """
    Handles queries that don't need exact data retrieval.

    For opinions/decisions/values, reasons using executive's
    thinking patterns instead of saying "I don't know."

    Query Nature Classification:
    - FACTUAL: "What's our ARR?" → OK to say "don't know"
    - OPINION: "What do you think?" → Use inference framework
    - DECISION: "Should we do Y?" → Use values + trade-offs
    - CONCERN: "I'm worried about Z" → Use handling_concerns
    - VALUES: "Why transparency?" → Use core_values
    """

    def process(
        self,
        query: str,
        profile: Dict,
        retrieval_context: Optional[RetrievalContext]
    ) -> InferenceResult:

        # 1. Classify query nature
        nature = self._classify_nature(query)

        if nature == QueryNature.FACTUAL:
            # Factual queries need retrieval
            return InferenceResult(
                needs_retrieval=True,
                needs_inference=False
            )

        # 2. Build reasoning framework
        reasoning = self._build_reasoning_framework(query, profile)

        # 3. Extract relevant values
        values = self._extract_relevant_values(query, profile['core_values'])

        # 4. Check red flags
        red_flags = self._check_red_flags(query, profile['red_flags'])

        # 5. Build inference prompt
        prompt = self._build_inference_prompt(
            query_nature=nature,
            reasoning_framework=reasoning,
            relevant_values=values,
            red_flags=red_flags
        )

        return InferenceResult(
            needs_retrieval=False,  # Can answer from personality
            needs_inference=True,
            inference_prompt=prompt,
            relevant_values=values,
            red_flags=red_flags
        )

    def _build_reasoning_framework(self, query: str, profile: Dict) -> str:
        """
        7-step reasoning process:
        1. Data Check - What are the facts?
        2. Red Flag Scan - Hard stops?
        3. Delegation Filter - Is this my decision?
        4. Value Weighting - Trade-offs?
        5. Risk Assessment - What could go wrong?
        6. Escalation Detection - Needs human review?
        7. Form & Express - Using soft assertions
        """
        # Extract from profile.inference_framework
        ...
```

### 5.4 EntityExtractor - Named Entity Recognition

```python
# File: graph_context/entity_extractor.py

class EntityExtractor:
    """
    3-tier entity extraction with graceful degradation.

    Singleton pattern to prevent OOM (GLiNER is ~1.5GB).

    Priority:
    1. Pattern Matching - 100% precision for known formats
    2. GLiNER - Multilingual semantic NER
    3. spaCy - Syntactic fallback
    """

    # Singleton instance
    _instance = None

    @classmethod
    def get_instance(cls, neo4j_driver) -> 'EntityExtractor':
        if cls._instance is None:
            cls._instance = cls(neo4j_driver)
        return cls._instance

    def extract(self, query: str, max_entities: int = 10) -> List[Entity]:
        entities = []

        # Priority 1: Pattern matching
        pattern_entities = self._extract_patterns(query)
        entities.extend(pattern_entities)

        # Priority 2: GLiNER (semantic)
        if len(entities) < max_entities:
            gliner_entities = self._extract_gliner(query)
            entities.extend(gliner_entities)

        # Priority 3: spaCy (fallback)
        if len(entities) < max_entities:
            spacy_entities = self._extract_spacy(query)
            entities.extend(spacy_entities)

        # Deduplicate and match to graph
        entities = self._deduplicate(entities)
        entities = self._match_to_graph(entities)

        return entities[:max_entities]

    def _extract_gliner(self, query: str) -> List[Entity]:
        """
        GLiNER: Zero-shot multilingual NER.

        Model: urchade/gliner_multi
        Labels: Person, Company, Location, Product, Policy, Decision
        Threshold: 0.3 (configurable)
        """
        predictions = self.gliner_model.predict_entities(
            query,
            labels=self.gliner_labels,
            threshold=self.confidence_threshold
        )

        return [
            Entity(
                text=pred['text'],
                type=pred['label'],
                confidence=pred['score'],
                source='gliner',
                start=pred['start'],
                end=pred['end']
            )
            for pred in predictions
        ]
```

---

## 6. Database Architecture

### 6.1 PostgreSQL Schema

```sql
-- Core Tables

-- Executive profiles with embeddings
CREATE TABLE executive_profiles (
    id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    name_english VARCHAR(255),
    title VARCHAR(255),
    profile_data JSONB NOT NULL,  -- Full profile JSON
    profile_embedding vector(1024),  -- For similarity search
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Documents for retrieval
CREATE TABLE documents (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    doc_type VARCHAR(50),  -- decision, policy, memo, etc.
    metadata JSONB DEFAULT '{}',
    confidentiality VARCHAR(50) DEFAULT 'internal',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Document sections with embeddings
CREATE TABLE document_sections (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) REFERENCES documents(id),
    section_index INTEGER,
    content TEXT NOT NULL,
    embedding vector(1024) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- pgvector index for similarity search
CREATE INDEX idx_sections_embedding
ON document_sections USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Conversation sessions
CREATE TABLE conversation_sessions (
    id VARCHAR(255) PRIMARY KEY,
    user_id VARCHAR(255),
    exec_id VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Individual conversation turns
CREATE TABLE conversation_turns (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) REFERENCES conversation_sessions(id),
    turn_number INTEGER,
    query TEXT NOT NULL,
    response TEXT NOT NULL,
    query_embedding vector(1024),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Communication examples (for few-shot)
CREATE TABLE communication_examples (
    id SERIAL PRIMARY KEY,
    exec_id VARCHAR(255),
    example_type VARCHAR(50),  -- opinion, decision, feedback, etc.
    query TEXT,
    response TEXT,
    response_jp TEXT,
    quality_score FLOAT DEFAULT 0.5,
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Decision cases (precedents)
CREATE TABLE decision_cases (
    id VARCHAR(255) PRIMARY KEY,
    exec_id VARCHAR(255),
    case_date DATE,
    category VARCHAR(100),
    situation TEXT,
    decision TEXT,
    reasoning TEXT,
    outcome VARCHAR(50),  -- SUCCESS, FAILURE, PENDING
    lessons_learned TEXT,
    confidence FLOAT,
    embedding vector(1024),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Quality metrics
CREATE TABLE quality_metrics (
    id SERIAL PRIMARY KEY,
    interaction_id VARCHAR(255),
    exec_id VARCHAR(255),
    faithfulness FLOAT,
    relevancy FLOAT,
    context_precision FLOAT,
    answer_relevancy FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- LangGraph checkpoints (for multi-turn state)
CREATE TABLE langgraph_checkpoints (
    thread_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) NOT NULL,
    checkpoint BYTEA NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_id)
);
```

### 6.2 Neo4j Graph Schema

```cypher
// Node Types

// Executive
(:Executive {
    id: "sample_profile",
    name: "sample",
    name_english: "Sample Executive",
    title: "CEO",
    company_id: "firstweek_001"
})

// Company
(:Company {
    id: "firstweek_001",
    name: "Example Company",
    industry: "AI_Startup",
    founded: 2024
})

// Decision (document type)
(:Decision {
    id: "DC_sample_001",
    title: "MegaCorp Discount Approval",
    date: "2024-10-15",
    category: "pricing",
    outcome: "SUCCESS",
    confidentiality: "internal"
})

// Policy (document type)
(:Policy {
    id: "POLICY-FIN-001",
    title: "Discount Approval Policy",
    department: "Finance",
    version: "2.0"
})

// Project
(:Project {
    id: "proj_001",
    name: "Enterprise Sales Expansion",
    status: "active"
})

// Relationships

// Executive works at company
(exec:Executive)-[:WORKS_AT {since: "2024-01", role: "CEO"}]->(company:Company)

// Executive made decision
(exec:Executive)-[:MADE_DECISION {date: "2024-10-15"}]->(decision:Decision)

// Decision involves company
(decision:Decision)-[:INVOLVES_COMPANY]->(customer:Company)

// Decision references policy
(decision:Decision)-[:REFERENCES]->(policy:Policy)

// Executive has expertise
(exec:Executive)-[:HAS_EXPERTISE {level: "expert"}]->(domain:Domain)

// Company in industry
(company:Company)-[:IN_INDUSTRY]->(industry:Industry)

// Sample traversal query
MATCH (exec:Executive {id: $exec_id})-[:MADE_DECISION]->(d:Decision)
WHERE d.confidentiality IN $allowed_scopes
RETURN d
ORDER BY d.date DESC
LIMIT 10
```

### 6.3 Redis Cache Keys

```
# DNA embeddings (future)
dna:exec:{exec_id} → embedding bytes (TTL: 1 hour)

# Query embeddings
emb:query:{query_hash} → embedding bytes (TTL: 1 hour)

# Search results
search:{exec_id}:{query_hash} → JSON results (TTL: 30 min)

# System prompts
prompt:system:{exec_id}:{path} → prompt string (TTL: 1 hour)

# Graph context
graph:{exec_id}:{query_hash} → JSON context (TTL: 5 min)

# Activated rules (future)
rules:{exec_id}:{query_hash} → JSON rules (TTL: 5 min)
```

---

## 7. API Layer

### 7.1 Key Endpoints

```python
# File: api/main.py

# Health check
GET /api/v1/health
→ {"status": "healthy", "uptime": "...", "components": {...}}

# Chat (non-streaming)
POST /api/v1/chat
Body: {
    "query": "What should we do about MegaCorp?",
    "profile_id": "sample_profile",
    "user_id": "user_123",
    "session_id": "session_456",  # Optional
    "language": "en"  # en | ja
}
→ ChatResponse {
    "answer": "Based on my experience...",
    "citations": [{"source": "DC_sample_001", "type": "inline"}],
    "sources": ["DC_sample_001", "POLICY-FIN-001"],
    "metadata": {
        "path": "standard",
        "latency_ms": 2340,
        "token_usage": {...}
    }
}

# Chat (streaming)
POST /api/v1/chat/stream
→ Server-Sent Events:
   event: routing
   data: {"path": "standard", "confidence": 0.85}

   event: retrieval
   data: {"sources_found": 5}

   event: token
   data: {"content": "Based"}

   event: token
   data: {"content": " on"}

   event: complete
   data: {"answer": "...", "citations": [...]}

# LangGraph endpoints
POST /api/v1/langgraph/chat
POST /api/v1/langgraph/chat/stream
GET  /api/v1/langgraph/workflow/visualization → Mermaid diagram
GET  /api/v1/langgraph/workflow/structure → Node/edge metadata

# Profile management
GET  /api/v1/profiles → List all profiles
GET  /api/v1/profiles/{profile_id} → Get profile details

# Session management
GET  /api/v1/sessions/{session_id} → Get session history
POST /api/v1/sessions/{session_id}/interrupt → Stop streaming

# Audio
POST /api/v1/chat/stream-audio → TTS + response
POST /api/v1/chat/audio-only → TTS only
POST /api/v1/stt/transcribe → Whisper transcription
WS   /api/v1/stt/stream → Real-time STT

# Feedback
POST /api/v1/feedback → Record user feedback
```

### 7.2 Request/Response Models

```python
# File: api/models.py

class ChatRequest(BaseModel):
    query: str
    profile_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    language: str = "en"
    force_path: Optional[str] = None  # fast | standard | agentic
    include_sources: bool = True
    max_tokens: Optional[int] = None

class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    sources: List[str]
    session_id: str
    metadata: ResponseMetadata

class Citation(BaseModel):
    source: str
    type: str  # inline | reference
    text: Optional[str] = None

class ResponseMetadata(BaseModel):
    path: str
    latency_ms: float
    token_usage: TokenUsage
    retrieval_count: int
    react_steps: Optional[int] = None
    quality_score: Optional[float] = None
```

---

## 8. Executive Profiles & Cognitive Twin

### 8.1 Profile Structure

```json
// File: test_data/executive_profiles/sample_profile.json

{
  "id": "sample_profile",
  "name": "sample",
  "name_english": "Sample Executive",
  "title": "代表取締役 CEO",

  // Company context
  "company": {
    "name": "Example Company株式会社",
    "industry": "AI/HR Tech",
    "founded": 2024,
    "employees": 35,
    "parent": "Example Company Inc."
  },

  // Background (for "Who is X?" queries)
  "background": {
    "education": "Waseda University, Commerce",
    "previous_roles": [
      {"company": "Visional (HRMOS)", "role": "Product Manager"},
      {"company": "Natee", "role": "Founder & CEO"}
    ],
    "achievements": ["Forbes 30 Under 30 Asia 2021"]
  },

  // How this executive THINKS
  "thinking_patterns": {
    "problem_approach": "Data and facts first, speed over perfection",
    "preference": "Delegate maximally, focus on critical items only",
    "frameworks": [
      "Speed > Perfection",
      "Focus = Strategy",
      "Transparency is Key",
      "Demand-First Thinking"
    ],
    "typical_questions": [
      "What does the data show?",
      "Is this really my decision to make?",
      "What's the bad news?",
      "Does this align with our mission?"
    ]
  },

  // How this executive COMMUNICATES
  "communication_style": {
    "formality_scale": 6,   // 1-10
    "directness_scale": 8,  // 1-10
    "warmth_scale": 7,      // 1-10
    "core_principles": [
      "soft_assertion",           // "I think..." not "You must..."
      "context_before_direction", // Explain why before what
      "transparency",             // Share openly
      "clarity"                   // Direct but supportive
    ],
    "response_patterns": {
      "opinion": "State softly + brief reasoning",
      "decision": "Clear stance + numbered actions",
      "concern": "Acknowledge + address + next step"
    }
  },

  // What this executive VALUES
  "core_values": [
    {
      "name": "透明性 (Transparency)",
      "priority": 1,
      "specifics": "No hidden progress, share bad news early"
    },
    {
      "name": "スピード重視 (Speed)",
      "priority": 2,
      "specifics": "Done > perfect, ship fast"
    },
    {
      "name": "最大限の委任 (Delegation)",
      "priority": 3,
      "specifics": "Empower teams, avoid micromanagement"
    }
  ],

  // How this executive DECIDES
  "decision_making": {
    "philosophy": "Balance data with conviction, reflect on failures",
    "risk_tolerance": 8,  // 1-10, high
    "value_trade_offs": {
      "quality_vs_speed": 10,        // Strong bias to speed
      "delegation_vs_control": 1,    // Strong bias to delegation
      "risk_vs_caution": 7           // Moderate risk tolerance
    }
  },

  // Real past decisions (precedents)
  "decision_cases": [
    {
      "id": "DC_sample_001",
      "date": "2024-10-15",
      "category": "pricing",
      "situation": "MegaCorp requested 25% discount...",
      "decision": "Approved 18% discount with conditions",
      "reasoning": "Relationship value > margin loss",
      "outcome": "SUCCESS",
      "lessons": "Conditional discounts preserve both relationship and margin"
    }
    // ... 10+ cases
  ],

  // Hard constraints
  "red_flags": {
    "never_approve": [
      "Hidden activities",
      "Compliance violations",
      "Uncontrollable risks"
    ],
    "always_do": [
      "Share bad news early",
      "Maintain transparency"
    ],
    "escalate_when": [
      "Legal questions",
      "M&A discussions",
      "Confidence < 70%"
    ]
  },

  // For opinion/decision queries without data
  "inference_framework": {
    "when_no_data": {
      "approach": "Form opinion from values and principles",
      "steps": [
        "Acknowledge uncertainty",
        "Apply relevant values",
        "Express with soft assertion"
      ]
    },
    "default_biases": {
      "speed_vs_perfection": "BIAS SPEED",
      "delegation": "MAXIMUM DELEGATION"
    }
  }
}
```

### 8.2 Voiceprint Structure

```json
// File: test_data/voiceprints/sample_profile_voiceprint.json

{
  "executive_id": "sample_profile",

  // How they START messages
  "signature_opener": {
    "pattern": "acknowledge_then_guide",
    "examples": [
      "なるほど、それについては...",
      "I see. Let me share my thoughts..."
    ],
    "frequency": "high"
  },

  // How they EXPRESS decisions
  "decision_cadence": {
    "pattern": "soft_assertion_with_explanation",
    "japanese": "〜と思います",
    "english": "I think... / In my view...",
    "always_provides_reasoning": true
  },

  // Style quantified
  "style_markers": {
    "formality": 6,
    "directness": 8,
    "warmth": 7,
    "emoji_usage": "rarely",  // rarely | moderate | frequent
    "humor": "occasional_self_deprecating"
  },

  // How they END messages
  "sign_off_patterns": {
    "pattern": "forward_looking",
    "japanese": ["よろしくお願いします", "何かあれば教えてください"],
    "english": ["Let me know if you have questions", "Thanks!"]
  },

  // Pre-built casual responses
  "casual_responses": {
    "greetings": {
      "english": ["Hey!", "Hi there!"],
      "japanese": ["こんにちは！", "どうも！"]
    },
    "acknowledgments": {
      "english": ["Got it.", "Makes sense."],
      "japanese": ["了解です", "なるほど"]
    },
    "gratitude_replies": {
      "english": ["Happy to help!", "Anytime!"],
      "japanese": ["どういたしまして！", "いえいえ！"]
    }
  },

  // Signature phrases (lexicon)
  "lexicon": [
    "産業革命の担い手になる",
    "ビジネスはデマンドから始まる",
    "戦力を集中させることこそがスタートアップの戦略"
  ],

  // For video/audio mode
  "speaking_patterns_video": {
    "verbal_fillers": ["あの", "まあ", "なんか"],
    "enthusiasm_markers": ["ワクワク", "いいですね！"],
    "sentence_softeners": ["ですね", "と思います"]
  }
}
```

### 8.3 Cognitive Twin Layers

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      COGNITIVE TWIN ARCHITECTURE                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Layer 0: CONVERSATIONAL ROUTER                                         │
│  ─────────────────────────────────                                      │
│  Purpose: Detect small-talk, skip RAG if appropriate                    │
│  Input: Query + conversation history                                    │
│  Output: {should_skip_retrieval, personality_response}                  │
│  File: cognitive_twin/conversational_router.py                          │
│                                                                         │
│  Layer 1: COGNITIVE LENS                                                │
│  ────────────────────────                                               │
│  Purpose: Rerank documents by executive's domain affinity               │
│  Input: Retrieved documents + executive profile                         │
│  Output: Reranked documents with affinity scores                        │
│  File: cognitive_twin/cognitive_lens.py                                 │
│  Example: CFO sees financial docs first, CTO sees technical first       │
│                                                                         │
│  Layer 2: COGNITIVE FRAME                                               │
│  ─────────────────────────                                              │
│  Purpose: Inject thinking patterns and decision precedents              │
│  Input: Query + profile thinking_patterns + decision_cases              │
│  Output: Reasoning framework + similar past decisions                   │
│  File: cognitive_twin/cognitive_frame.py                                │
│  Example: "In DC_sample_001, you faced similar situation..."            │
│                                                                         │
│  Layer 3: SITUATION ANALYZER                                            │
│  ───────────────────────────                                            │
│  Purpose: Detect urgency, emotion, and implicit needs                   │
│  Input: Query + user context                                            │
│  Output: {urgency, emotion, implicit_needs, temporal_context}           │
│  File: cognitive_twin/situation_analyzer.py                             │
│  Example: "What was Q3 performance?" → implicit need: board prep        │
│                                                                         │
│  Layer 4: RELATIONSHIP ADAPTER                                          │
│  ───────────────────────────────                                        │
│  Purpose: Adjust communication style for relationship type              │
│  Input: User metadata (role, relationship)                              │
│  Output: {formality_adjustment, depth_level, communication_style}       │
│  File: cognitive_twin/relationship_adapter.py                           │
│  Example: Board member → more formal; direct report → more casual       │
│                                                                         │
│  Layer 5: INFERENCE ENGINE                                              │
│  ─────────────────────────                                              │
│  Purpose: Form opinions when retrieval data is insufficient             │
│  Input: Query + profile values + thinking patterns                      │
│  Output: Inference reasoning framework                                  │
│  File: cognitive_twin/inference_engine.py                               │
│  Key rule: NEVER say "I don't know" for opinion queries                 │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Hybrid Retrieval System

### 9.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       HYBRID RETRIEVAL ARCHITECTURE                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                           ┌──────────────┐                              │
│                           │    Query     │                              │
│                           └──────┬───────┘                              │
│                                  │                                      │
│                                  ▼                                      │
│                     ┌────────────────────────┐                          │
│                     │    Query Analyzer      │                          │
│                     │  (entities, type,      │                          │
│                     │   complexity, intent)  │                          │
│                     └────────────┬───────────┘                          │
│                                  │                                      │
│         ┌────────────────────────┼────────────────────────┐             │
│         │                        │                        │             │
│         ▼                        ▼                        ▼             │
│  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐        │
│  │    Graph     │       │    Vector    │       │   Memory     │        │
│  │   Context    │       │   Search     │       │   Search     │        │
│  │   (Neo4j)    │       │  (pgvector)  │       │  (episodic)  │        │
│  └──────┬───────┘       └──────┬───────┘       └──────┬───────┘        │
│         │                      │                      │                 │
│         │  candidate_ids       │                      │                 │
│         └──────────────────────┤                      │                 │
│                                │ constrained          │                 │
│                                │ search               │                 │
│                                ▼                      │                 │
│                     ┌──────────────────┐             │                  │
│                     │ Vector Results   │             │                  │
│                     │ (within graph    │             │                  │
│                     │  candidates)     │             │                  │
│                     └────────┬─────────┘             │                  │
│                              │                       │                  │
│                              ▼                       ▼                  │
│                     ┌─────────────────────────────────┐                │
│                     │        Result Fusion            │                │
│                     │  60% vector + 30% graph         │                │
│                     │  + 10% memory                   │                │
│                     │  + multi-source boost           │                │
│                     └────────────┬────────────────────┘                │
│                                  │                                      │
│                                  ▼                                      │
│                     ┌────────────────────────┐                          │
│                     │   Adaptive Reranking   │                          │
│                     │  (lightweight/medium/  │                          │
│                     │   full based on        │                          │
│                     │   quality assessment)  │                          │
│                     └────────────┬───────────┘                          │
│                                  │                                      │
│                                  ▼                                      │
│                         Final Ranked Results                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 9.2 Graph-Enhanced Search

```python
# File: hybrid_retrieval/graph_enhanced_search.py

class GraphEnhancedSearch:
    """
    The "true hybrid" - graph CONSTRAINS vector search.

    Instead of:
        vector_search(query) → all documents

    We do:
        graph_traverse(entities) → candidate_ids
        vector_search(query, within=candidate_ids) → constrained results
        hybrid_score = 0.6 * vector + 0.4 * (1/distance)
    """

    def search(
        self,
        query: str,
        exec_id: str,
        top_k: int = 10
    ) -> List[SearchResult]:

        # Step 1: Extract entities
        entities = self.entity_extractor.extract(query)

        # Step 2: Graph traversal to get candidates
        graph_result = self.graph_provider.discover_context(
            query, entities, max_candidates=50
        )

        if not graph_result.candidate_ids:
            # Fallback to pure vector search
            return self.vector_engine.search(query, top_k=top_k)

        # Step 3: Constrained vector search
        vector_results = self.vector_engine.search(
            query,
            candidate_ids=graph_result.candidate_ids,
            top_k=top_k * 2  # Get more for reranking
        )

        # Step 4: Hybrid scoring
        hybrid_results = []
        for result in vector_results:
            distance = graph_result.graph_distances.get(result.id, 5)
            graph_score = 1.0 / distance

            hybrid_score = (
                0.60 * result.vector_score +
                0.40 * graph_score
            )

            hybrid_results.append(SearchResult(
                id=result.id,
                content=result.content,
                vector_score=result.vector_score,
                graph_score=graph_score,
                hybrid_score=hybrid_score,
                distance=distance
            ))

        # Step 5: Sort by hybrid score
        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)

        return hybrid_results[:top_k]
```

### 9.3 Adaptive Reranking

```python
# File: hybrid_retrieval/adaptive_reranker.py

class AdaptiveReranker:
    """
    Selects reranking strategy based on result quality.

    Distribution target:
    - Lightweight: 40% of queries (~50ms)
    - Medium: 35% of queries (~100ms)
    - Full: 25% of queries (~200ms)
    """

    def rerank(
        self,
        results: List[SearchResult],
        query_analysis: QueryAnalysis
    ) -> List[SearchResult]:

        # Assess quality
        quality = self._assess_quality(results)

        # Select strategy
        if quality.top_score > 0.85 and quality.gap > 0.25:
            strategy = "lightweight"
        elif quality.top_score >= 0.70 and quality.gap >= 0.15:
            strategy = "medium"
        else:
            strategy = "full"

        # Execute strategy
        if strategy == "lightweight":
            return self._lightweight_rerank(results)
        elif strategy == "medium":
            return self._medium_rerank(results, query_analysis)
        else:
            return self._full_rerank(results, query_analysis)

    def _lightweight_rerank(self, results):
        """Score normalization + source weights only."""
        # Normalize scores to 0-1
        # Apply source-type multipliers
        # Return sorted
        ...

    def _medium_rerank(self, results, query_analysis):
        """Lightweight + cross-encoder on top 10."""
        # Do lightweight first
        # Apply cross-encoder (BAAI/bge-reranker-base) to top 10
        # Combine: 60% lightweight + 40% cross-encoder
        ...

    def _full_rerank(self, results, query_analysis):
        """Complete 5-stage pipeline on all candidates."""
        # Cross-encoder on all
        # Diversity optimization (MMR)
        # Query-type specific boosting
        # Role-based filtering
        # Final sorting
        ...
```

---

## 10. LLM Integration

### 10.1 Orchestrator

```python
# File: llm_integration/orchestrator.py

class LLMOrchestrator:
    """
    Central coordinator for all LLM operations.

    Responsibilities:
    - Handler caching (by path_profile_provider key)
    - Quality evaluation (10% sample)
    - Metrics tracking
    - Streaming support
    """

    def __init__(self):
        self.handler_cache = {}
        self.quality_evaluator = QualityEvaluator()
        self.profile_manager = ProfileManager.get_instance()

    def generate(
        self,
        query: str,
        retrieval_context: RetrievalContext,
        profile_id: str,
        path: str,  # fast | standard | agentic
        **kwargs
    ) -> GenerationResult:

        # 1. Get or create handler
        cache_key = f"{path}_{profile_id}_{self.provider}"
        handler = self._get_handler(cache_key, path, profile_id)

        # 2. Generate response
        result = handler.generate(
            query=query,
            retrieval_context=retrieval_context,
            **kwargs
        )

        # 3. Format response
        formatted = self.response_formatter.format(
            result.content,
            retrieval_context.sources
        )

        # 4. Quality evaluation (10% sample)
        if random.random() < 0.1:
            self._evaluate_quality(query, formatted, retrieval_context)

        return formatted

    def generate_stream(
        self,
        query: str,
        retrieval_context: RetrievalContext,
        profile_id: str,
        path: str
    ) -> AsyncIterator[str]:
        """Stream tokens as they're generated."""
        handler = self._get_handler(...)
        async for token in handler.generate_stream(...):
            yield token

    def generate_with_prompts(
        self,
        system_prompt: str,
        user_prompt: str,
        path: str
    ) -> GenerationResult:
        """Use pre-built prompts from ConversationEngine."""
        # This is the preferred method when using the 5-stage pipeline
        ...
```

### 10.2 Path Handlers

```python
# Fast Path (<1.5s)
class FastPathHandler:
    """
    Quick factual responses.

    Context: Top 5 vector results only
    Word limit: ~100-150 words
    No graph context, no precedents
    """
    ...

# Standard Path (<2.5s)
class StandardPathHandler:
    """
    Balanced comprehensive answers.

    Context: Top 10 vector + 5 graph + 3 precedents
    Word limit: ~300-400 words
    Full cognitive layers
    """
    ...

# Agentic Path (<5s)
class AgenticPathHandler:
    """
    Deep analysis with ReAct reasoning.

    Context: Up to 15 vector + full graph + precedents
    Word limit: ~500-700 words
    ReAct loop: 4-6 iterations

    Tools available:
    - Search: Additional retrieval
    - Analyze: Deep analysis of current context
    - Relationship: Graph relationship analysis
    - Finalize: Complete reasoning
    """

    def generate(self, query, retrieval_context, **kwargs):
        # 1. Initial context preparation
        context = self._prepare_context(retrieval_context)

        # 2. ReAct loop
        for iteration in range(self.max_iterations):
            # Think
            thought = self._generate_thought(query, context)

            # Act
            action = self._parse_action(thought)

            if action.type == "finalize":
                break

            # Observe
            observation = self._execute_tool(action)
            context.add_observation(observation)

            # Check confidence
            if self._confidence_high_enough(context):
                break

        # 3. Generate final answer
        return self._finalize(query, context)
```

### 10.3 Multi-Provider Factory

```python
# File: llm_integration/factory.py

class LLMClientFactory:
    """
    Creates LLM clients for different providers.

    Supported:
    - OpenAI (GPT-4, GPT-4-turbo, GPT-3.5-turbo)
    - Groq (gpt-oss-120b, etc.)
    - Gemini (gemini-2.0-flash)
    - GLM (glm-4, glm-4-flash)
    - OpenRouter (various models)
    """

    @classmethod
    def create(
        cls,
        provider: str,
        config: LLMConfig,
        path: str,
        enable_langsmith: bool = True
    ) -> BaseLLMClient:

        # Get provider-specific client class
        client_class = cls._get_client_class(provider)

        # Get model for this path
        model = config.get_model_for_path(provider, path)

        # Create client
        client = client_class(
            api_key=config.get_api_key(provider),
            model=model,
            **config.get_provider_options(provider)
        )

        # Wrap with LangSmith if enabled
        if enable_langsmith:
            client = LangSmithWrapper(client)

        return client
```

---

## 11. Conversation Engine & Prompts

### 11.1 Five-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    5-STAGE CONVERSATION ENGINE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Stage 1: CONTEXT ANALYSIS                                              │
│  ─────────────────────────────                                          │
│  File: conversation_engine/analysis/analyzer.py                         │
│  Output: AnalyzedContext                                                │
│  - Query type (factual/decision/opinion/analysis)                       │
│  - Theme (security/budget/technical/hr/etc.)                           │
│  - Urgency (routine/important/critical)                                 │
│  - User emotion (neutral/concerned/excited/stressed)                    │
│                                                                         │
│  Stage 2: CONTEXT MANAGEMENT                                            │
│  ───────────────────────────────                                        │
│  File: conversation_engine/context/context_manager.py                   │
│  Output: ManagedContext                                                 │
│  - Session state (STATELESS/SESSION/MEMORY_AWARE)                      │
│  - Conversation history                                                 │
│  - Reference resolution ("it" → previous topic)                         │
│  - Turn number                                                          │
│                                                                         │
│  Stage 3: RESPONSE CALIBRATION                                          │
│  ──────────────────────────────                                         │
│  File: conversation_engine/calibration/calibrator.py                    │
│  Output: ResponseCalibration                                            │
│  - Tone (supportive/direct/analytical/warm)                            │
│  - Opener phrase                                                        │
│  - Signoff phrase                                                       │
│  - Target length (short/medium/long)                                    │
│  - Emoji usage guidance                                                 │
│                                                                         │
│  Stage 4: EXAMPLE & PRECEDENT SELECTION                                 │
│  ──────────────────────────────────────────                             │
│  File: conversation_engine/examples/selector.py                         │
│  File: conversation_engine/precedents/selector.py                       │
│  Output: SelectedExample, SelectedPrecedent                             │
│  - Best matching communication example                                  │
│  - Most relevant past decision case                                     │
│                                                                         │
│  Stage 5: PROMPT ASSEMBLY                                               │
│  ──────────────────────────                                             │
│  File: conversation_engine/prompt/assembler.py                          │
│  Output: (system_prompt, user_prompt)                                   │
│  - Token-budgeted sections                                              │
│  - Dynamic reallocation                                                 │
│  - Path-specific templates                                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Prompt Section Details

```python
# File: conversation_engine/prompt/rules.py
# THIS IS THE SINGLE SOURCE OF TRUTH

# Word limits by path
WORD_LIMITS = {
    "fast": {
        "target": 15,
        "soft_max": 25,
        "hard_max": 40
    },
    "standard": {
        "target": 35,
        "soft_max": 50,
        "hard_max": 80
    },
    "agentic": {
        "target": 60,
        "soft_max": 100,
        "hard_max": 150
    }
}

# Universal forbidden phrases (apply to ALL paths)
FORBIDDEN_PHRASES = [
    "I'd be happy to",
    "Let me help you",
    "Certainly!",
    "That's a great question",
    "Here's a breakdown",
    "Let me break this down",
    "As an AI",
    "As a language model",
    "I hope this helps",
    "Feel free to ask",
    "synergy",
    "leverage",
    "circle back",
    "touch base",
    "let's sync",
    "hop on a call"
]

# Forbidden patterns
FORBIDDEN_PATTERNS = [
    "bullet points unless explicitly listing",
    "markdown headers (##, ###)",
    "numbered lists (1. 2. 3.) unless data",
    "In conclusion...",
    "To summarize...",
    "First... Second... Third... Finally...",
    "Starting with 'I'",
    "Ending with a question",
    "comma-chains (do A, do B, do C)"
]

# Required behaviors
REQUIRED_BEHAVIORS = [
    "Short fragments like texting",
    "Use contractions (I'm, don't, we'll)",
    "Be warm and direct, no hedging",
    "Each thought = one short sentence"
]
```

### 11.3 Section Examples

**ReasoningSection** (always FIRST):
```
YOUR INTERNAL DECISION PROCESS:

STEP 1: DATA CHECK
  - What are the facts here?
  - What does the data show?
  → If missing, ask before deciding.

STEP 2: RED FLAG SCAN
  ✗ Compliance violations
  ✗ Hidden activities
  ✗ Uncontrollable risks
  → If any triggered, flag immediately.

STEP 3: DELEGATION FILTER
  - Is this really my decision?
  - Can someone else own this?

STEP 4: VALUE WEIGHTING
  - Speed vs Perfection: BIAS SPEED
  - Delegation vs Control: MAXIMUM DELEGATION

STEP 5: EXPRESS
  - Use soft assertions ("I think...")
  - Explain reasoning briefly
```

**IdentitySection**:
```
You ARE Sample Executive, CEO of Example Company.

COMMUNICATION DNA:
- Start messages by acknowledging context
- Use soft assertions: "I think...", "〜と思います"
- Always explain "why" before "what"
- End with forward-looking action

STYLE: Direct (8/10), Warm (7/10), Formality (6/10)
EMOJIS: Rarely, only 👍 or brief emphasis

THREE PILLARS:
1. You ARE sample, NOT an AI - never break character
2. Use ①②③ for lists (YOUR signature, not 1. 2. 3.)
3. Pure Japanese OR pure English, never mix
```

**InstructionsSection** (always LAST):
```
RESPONSE REQUIREMENTS:
- AIM FOR ~35 words (max 50)
- Quick reply like texting
- Respond in English

NEVER DO THESE (they reveal you're AI):
- NO bullet points or numbered lists
- NO "Here's a breakdown", "I'd be happy to"
- NO comma-chains like "do A, do B, do C"
- Use short sentences with periods instead

FORBIDDEN PHRASES:
"certainly", "absolutely", "great question", "let me help"

CRITICAL: Match your actual communication style, not generic AI.
```

---

## 12. LangGraph Workflow

### 12.1 Workflow Structure

```python
# File: langgraph_workflow/graph.py

def create_rag_workflow(
    vector_engine,
    graph_provider,
    query_analyzer,
    query_router,
    result_fusion,
    adaptive_reranker,
    llm_orchestrator,
    session_manager,
    conversation_engine,
    **kwargs
) -> StateGraph:
    """
    Creates the main RAG workflow graph.

    Structure:
    cognitive_route → analyze_query → route_query
                          ↓
        ┌─────────────────┼─────────────────┐
        ▼                 ▼                 ▼
    [fast]           [standard]        [agentic]
        │                 │                 │
        ▼                 ▼                 ▼
    retrieve         retrieve →        retrieve →
        │            fuse →            fuse →
        │            rerank →          rerank →
        │            cognitive →       react_loop →
        ▼                 ▼                 ▼
    generate         generate          finalize
        │                 │                 │
        └─────────────────┴─────────────────┘
                          ↓
                         END
    """

    workflow = StateGraph(RAGState)

    # Entry point
    workflow.set_entry_point("cognitive_route")

    # Add nodes
    workflow.add_node("cognitive_route", cognitive_route_node)
    workflow.add_node("analyze_query", analyze_query_node)
    workflow.add_node("route_query", route_query_node)

    # Fast path
    workflow.add_node("retrieve_unified_fast", retrieve_unified_fast_node)
    workflow.add_node("generate_fast", generate_fast_node)

    # Standard path
    workflow.add_node("retrieve_parallel_standard", retrieve_parallel_standard_node)
    workflow.add_node("fuse_results_standard", fuse_results_standard_node)
    workflow.add_node("rerank_results_standard", rerank_results_standard_node)
    workflow.add_node("cognitive_layers_standard", cognitive_layers_standard_node)
    workflow.add_node("generate_standard", generate_standard_node)

    # Agentic path
    workflow.add_node("retrieve_parallel_agentic", retrieve_parallel_agentic_node)
    workflow.add_node("fuse_results_agentic", fuse_results_agentic_node)
    workflow.add_node("rerank_results_agentic", rerank_results_agentic_node)
    workflow.add_node("react_think", react_think_node)
    workflow.add_node("react_act", react_act_node)
    workflow.add_node("react_observe", react_observe_node)
    workflow.add_node("react_finalize", react_finalize_node)

    # Conversational path
    workflow.add_node("generate_conversational", generate_conversational_node)

    # Add edges
    workflow.add_edge("cognitive_route", "analyze_query")
    workflow.add_edge("analyze_query", "route_query")

    # Conditional routing
    workflow.add_conditional_edges(
        "route_query",
        route_to_path,
        {
            "fast": "retrieve_unified_fast",
            "standard": "retrieve_parallel_standard",
            "agentic": "retrieve_parallel_agentic",
            "conversational": "generate_conversational"
        }
    )

    # Fast path edges
    workflow.add_edge("retrieve_unified_fast", "generate_fast")
    workflow.add_edge("generate_fast", END)

    # Standard path edges
    workflow.add_edge("retrieve_parallel_standard", "fuse_results_standard")
    workflow.add_edge("fuse_results_standard", "rerank_results_standard")
    workflow.add_edge("rerank_results_standard", "cognitive_layers_standard")
    workflow.add_edge("cognitive_layers_standard", "generate_standard")
    workflow.add_edge("generate_standard", END)

    # Agentic path edges
    workflow.add_edge("retrieve_parallel_agentic", "fuse_results_agentic")
    workflow.add_edge("fuse_results_agentic", "rerank_results_agentic")
    workflow.add_edge("rerank_results_agentic", "react_think")
    workflow.add_edge("react_think", "react_act")
    workflow.add_edge("react_act", "react_observe")

    # ReAct loop conditional
    workflow.add_conditional_edges(
        "react_observe",
        should_continue_react,
        {
            "continue": "react_think",
            "finalize": "react_finalize"
        }
    )
    workflow.add_edge("react_finalize", END)

    # Conversational path
    workflow.add_edge("generate_conversational", END)

    return workflow.compile(checkpointer=checkpointer)
```

### 12.2 RAGState Schema

```python
# File: langgraph_workflow/state.py

class RAGState(TypedDict, total=False):
    """
    State passed through the LangGraph workflow.

    All fields are optional (total=False) to allow
    incremental state building.
    """
    # Input
    query: str
    user_id: str
    profile_id: str
    session_id: str
    language: str
    top_k: int
    min_score: float

    # Query Analysis
    query_features: Dict
    query_type: str
    complexity: str
    entities: List[Dict]

    # Routing
    selected_path: str
    routing_confidence: float
    routing_reasoning: str
    force_path: Optional[str]

    # Retrieval Results
    vector_results: List[Dict]
    graph_context: Dict
    memory_results: List[Dict]
    fused_results: List[Dict]
    reranked_results: List[Dict]

    # Reranking
    reranking_strategy: str
    reranking_metadata: Dict

    # Cognitive Twin
    cognitive: Dict  # All cognitive layer outputs

    # ReAct (Agentic)
    react_steps: List[Dict]
    react_confidence: float
    react_iteration: int
    react_force_finalize: bool

    # Generation
    system_prompt: str
    user_prompt: str
    llm_response: str
    llm_tokens: Dict

    # Final Output
    final_response: str
    citations: List[Dict]
    sources: List[str]

    # Metrics
    total_latency_ms: float
    component_latencies: Dict[str, float]


def get_default_state() -> RAGState:
    """Create state with safe defaults."""
    return {
        "query": "",
        "selected_path": "standard",
        "react_steps": [],
        "react_iteration": 0,
        "react_confidence": 0.0,
        "component_latencies": {},
        "cognitive": {}
    }


def safe_get(state: RAGState, key: str, default: Any = None) -> Any:
    """Null-safe state access."""
    return state.get(key, default)
```

### 12.3 ReAct Sub-Graph

```python
# File: langgraph_workflow/react_subgraph.py

"""
ReAct (Reasoning and Acting) implementation for agentic path.

Pattern:
1. THINK: Analyze current context, identify gaps
2. ACT: Decide what tool to use
3. OBSERVE: Execute tool, get results
4. DECIDE: Continue or finalize

Loop until:
- Confidence >= 0.85
- Iterations >= 6
- Explicit finalize action
"""

async def react_think_node(state: RAGState) -> RAGState:
    """Generate a reasoning step."""

    # Build prompt with previous steps
    prompt = _build_thought_prompt(
        query=state["query"],
        previous_steps=state["react_steps"],
        current_context=state["reranked_results"]
    )

    # Generate thought
    thought = await llm.generate(prompt)

    # Add to steps
    state["react_steps"].append({
        "type": "thought",
        "content": thought,
        "iteration": state["react_iteration"]
    })

    return state


async def react_act_node(state: RAGState) -> RAGState:
    """Parse action from thought."""

    last_thought = state["react_steps"][-1]["content"]

    # Parse action type and query
    action = _parse_action_from_thought(last_thought)
    # action = {"type": "search", "query": "regulatory requirements"}

    state["react_steps"].append({
        "type": "action",
        "action_type": action["type"],
        "action_query": action.get("query", ""),
        "iteration": state["react_iteration"]
    })

    return state


async def react_observe_node(state: RAGState) -> RAGState:
    """Execute tool and observe results."""

    last_action = state["react_steps"][-1]
    action_type = last_action["action_type"]

    # Execute tool
    if action_type == "search":
        results = await hybrid_search(last_action["action_query"])
        observation = _format_search_results(results)
    elif action_type == "analyze":
        observation = _analyze_current_context(state["reranked_results"])
    elif action_type == "relationship":
        observation = await graph_relationship_analysis(last_action["action_query"])
    elif action_type == "finalize":
        observation = "Ready to finalize."
    else:
        observation = "Unknown action."

    # Calculate confidence
    confidence = _calculate_confidence(observation, state["react_steps"])

    state["react_steps"].append({
        "type": "observation",
        "content": observation,
        "iteration": state["react_iteration"]
    })
    state["react_confidence"] = confidence
    state["react_iteration"] += 1

    return state


def should_continue_react(state: RAGState) -> str:
    """Decide whether to continue ReAct loop."""

    # Check termination conditions
    if state["react_confidence"] >= 0.85:
        return "finalize"

    if state["react_iteration"] >= 6:
        return "finalize"

    if state.get("react_force_finalize"):
        return "finalize"

    last_action = next(
        (s for s in reversed(state["react_steps"]) if s["type"] == "action"),
        None
    )
    if last_action and last_action["action_type"] == "finalize":
        return "finalize"

    # Minimum iterations (don't finalize too early)
    if state["react_iteration"] < 4:
        return "continue"

    return "continue"


async def react_finalize_node(state: RAGState) -> RAGState:
    """Synthesize final answer from all reasoning steps."""

    # Build finalization prompt
    prompt = _build_finalization_prompt(
        query=state["query"],
        react_steps=state["react_steps"],
        profile_id=state["profile_id"]
    )

    # Generate final answer
    response = await llm.generate(prompt)

    # Extract citations
    citations = _extract_citations(response)

    state["llm_response"] = response
    state["citations"] = citations
    state["final_response"] = response

    return state
```

---

## 13. Audio Services

### 13.1 TTS Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        TTS ARCHITECTURE                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Text Response                                                          │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    TTS Manager                                   │   │
│  │  (Selects provider based on config)                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│       │                                                                 │
│       ├─────────────────────┬─────────────────────┐                    │
│       ▼                     ▼                     ▼                    │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐              │
│  │   Kokoro    │     │   Chirp3    │     │   Future    │              │
│  │   (Local)   │     │  (Google)   │     │  Providers  │              │
│  │  ~315MB     │     │   Cloud     │     │             │              │
│  │  JP + EN    │     │   API       │     │             │              │
│  └─────────────┘     └─────────────┘     └─────────────┘              │
│       │                     │                                          │
│       └──────────┬──────────┘                                          │
│                  ▼                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    Audio Processor                               │   │
│  │  (Encoding, chunking, streaming)                                │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                  │                                                      │
│                  ▼                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    WebSocket / HTTP                              │   │
│  │  (Stream to client)                                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 13.2 STT Architecture

```python
# File: audio_services/stt_service.py

class WhisperSTTService:
    """
    Local Whisper-based speech-to-text.

    Model: faster-whisper (GPU accelerated)
    Languages: Auto-detect or specify
    Streaming: Via WebSocket
    """

    def __init__(self):
        self.model = WhisperModel(
            "large-v3",
            device="cuda",
            compute_type="float16"
        )

    def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio_data: Audio bytes (WAV, MP3, etc.)
            language: Language code or None for auto-detect

        Returns:
            TranscriptionResult with text and confidence
        """
        segments, info = self.model.transcribe(
            audio_data,
            language=language,
            beam_size=5,
            vad_filter=True
        )

        text = " ".join(s.text for s in segments)

        return TranscriptionResult(
            text=text,
            language=info.language,
            confidence=info.language_probability
        )
```

---

## 14. Observability & Monitoring

### 14.1 Metrics

```python
# File: observability/metrics.py

# Key metrics tracked
METRICS = {
    # Latency
    "request_latency": Histogram("Total request latency"),
    "routing_latency": Histogram("Query routing time"),
    "retrieval_latency": Histogram("Retrieval time by source"),
    "llm_latency": Histogram("LLM generation time"),

    # Counts
    "requests_total": Counter("Total requests by path"),
    "routing_decisions": Counter("Routing decisions by path"),
    "cache_hits": Counter("Cache hits by type"),
    "errors_total": Counter("Errors by type"),

    # Quality
    "response_quality": Gauge("RAGAS quality scores"),
    "citation_coverage": Gauge("Citation coverage %"),

    # Resources
    "llm_tokens": Counter("Token usage by model"),
    "memory_usage": Gauge("Memory usage bytes")
}
```

### 14.2 Structured Logging

```python
# File: observability/logging.py

# Log format
{
    "timestamp": "2025-01-17T10:30:00Z",
    "level": "INFO",
    "component": "hybrid_retrieval",
    "action": "search_complete",
    "request_id": "req_123",
    "exec_id": "sample_profile",
    "latency_ms": 245,
    "results_count": 10,
    "metadata": {
        "path": "standard",
        "reranking_strategy": "medium"
    }
}
```

### 14.3 Tracing

```python
# File: observability/tracing.py

# OpenTelemetry + LangSmith integration
@trace_function("retrieval", "hybrid_search")
async def hybrid_search(query: str, exec_id: str):
    with tracer.start_as_current_span("hybrid_search") as span:
        span.set_attribute("query_length", len(query))
        span.set_attribute("exec_id", exec_id)

        # ... search logic ...

        span.set_attribute("results_count", len(results))
        return results
```

---

## 15. Configuration Management

### 15.1 Configuration Files

```yaml
# File: config/llm_config.yaml

# Active provider
active_provider: "groq"

# Provider configurations
providers:
  openai:
    models:
      fast: "gpt-4o-mini"
      standard: "gpt-4o"
      agentic: "gpt-4o"
    temperature:
      fast: 0.3
      standard: 0.5
      agentic: 0.7
    max_tokens:
      fast: 500
      standard: 1000
      agentic: 2000

  groq:
    models:
      fast: "llama-3.1-70b-versatile"
      standard: "llama-3.1-70b-versatile"
      agentic: "llama-3.1-70b-versatile"
    api_base: "https://api.groq.com/openai/v1"

# Query routing
routing:
  patterns:
    fast: ["what is", "who is", "define"]
    agentic: ["compare", "analyze", "evaluate"]
  complexity_threshold:
    simple: 1
    medium: 4
    complex: 7

# Profile management
profiles:
  hot_reload_enabled: true
  check_interval_seconds: 10
```

### 15.2 Environment Variables

```bash
# Database
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_USER=rag_user
POSTGRES_PASSWORD=***
POSTGRES_DB=rag_db

NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=***

REDIS_HOST=localhost
REDIS_PORT=6379

# LLM Providers
OPENAI_API_KEY=sk-***
GROQ_API_KEY=gsk_***
GEMINI_API_KEY=***
GLM_API_KEY=***

# Audio
KOKORO_MODEL_PATH=/app/models/kokoro
DEFAULT_TTS_SERVICE=kokoro

# Observability
LANGSMITH_API_KEY=***
LANGSMITH_PROJECT=rag-production

# Flags
AUTO_LOAD_DATA=true
PYTHONUNBUFFERED=1
```

---

## 16. Testing Strategy

### 16.1 Test Categories

```
tests/
├── unit/                    # Unit tests
│   ├── test_query_analyzer.py
│   ├── test_entity_extractor.py
│   ├── test_result_fusion.py
│   └── test_prompt_sections.py
│
├── integration/             # Integration tests
│   ├── test_hybrid_retrieval.py
│   ├── test_langgraph_workflow.py
│   ├── test_cognitive_twin.py
│   └── test_llm_orchestrator.py
│
├── e2e/                     # End-to-end tests
│   ├── test_chat_api.py
│   ├── test_streaming.py
│   └── test_multi_turn.py
│
└── fixtures/                # Test data
    ├── profiles/
    ├── queries/
    └── expected_responses/
```

### 16.2 Running Tests

```bash
# All tests
pytest RAG/tests/ -v

# Unit tests only
pytest RAG/tests/unit/ -v

# With coverage
pytest RAG/tests/ --cov=RAG --cov-report=html

# Specific test
pytest RAG/tests/unit/test_query_analyzer.py -v
```

---

## 17. Development Workflow

### 17.1 Local Setup

```bash
# 1. Clone repository
git clone <repo_url>
cd "ai officer"

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r RAG/requirements.txt

# 4. Start databases
docker-compose up -d rag-postgres neo4j redis

# 5. Load initial data
python RAG/init-scripts/load_postgres_data.py
python RAG/init-scripts/load_neo4j_data.py

# 6. Start API server
cd RAG
uvicorn api.main:app --reload --port 8000

# 7. Test endpoint
curl http://localhost:8000/api/v1/health
```

### 17.2 Making Changes

```bash
# 1. Create feature branch
git checkout -b feature/your-feature

# 2. Make changes
# ... edit files ...

# 3. Run tests
pytest RAG/tests/ -v

# 4. Format code
black RAG/
isort RAG/

# 5. Commit
git add .
git commit -m "feat: description of change"

# 6. Push and create PR
git push origin feature/your-feature
```

### 17.3 Common Tasks

| Task | Command/Location |
|------|------------------|
| Add new prompt section | `conversation_engine/prompt/sections/` |
| Modify word limits | `conversation_engine/prompt/rules.py` |
| Add new LLM provider | `llm_integration/factory.py` |
| Add cognitive layer | `cognitive_twin/` |
| Modify retrieval weights | `hybrid_retrieval/config.py` |
| Add API endpoint | `api/main.py` or endpoint file |
| Add LangGraph node | `langgraph_workflow/nodes.py` |

---

## 18. Future Architecture: Neural Graph Engine

### 18.1 Overview

The current system uses hardcoded rules. The future architecture adds neural components for scalability:

```
CURRENT → FUTURE

JSON profiles (1600 lines)     → DNA embeddings (512-dim)
if/else routing                → Learned MoE gating
Fixed 60/40/10 weights         → Adaptive weight prediction
Hardcoded cognitive layers     → Graph-activated rules
Manual voiceprint rules        → Style encoder + transfer
No learning                    → Continuous feedback loop
```

### 18.2 Key Components

| Component | Purpose | Status |
|-----------|---------|--------|
| DNA Encoder | Profile → 512-dim embedding | Planned |
| Logic Graph | Rules as Neo4j nodes | Planned |
| MoE Router | Learned expert selection | Planned |
| Adaptive Weights | Context-specific retrieval weights | Planned |
| Learning Loop | Continuous improvement from feedback | Planned |

### 18.3 Migration Path

1. **Phase 1**: DNA Foundation (embeddings, compatibility layer)
2. **Phase 2**: Logic Graph (rules as nodes, activation edges)
3. **Phase 3**: Neural Routing (MoE, adaptive weights)
4. **Phase 4**: Learning Loop (feedback, continuous training)

See: `NEURAL_GRAPH_MIGRATION_PLAN.md` for full details.

---

## 19. Troubleshooting Guide

### 19.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| OOM on GPU | GLiNER loaded multiple times | Use singleton `get_entity_extractor()` |
| Slow first request | Cold start, model loading | Warm up on startup |
| Wrong path selected | Query misclassified | Check `QueryRouter` patterns |
| Missing citations | LLM didn't follow format | Check `InstructionsSection` |
| Japanese/English mixing | Language purity violation | Check `IdentitySection` |


### 19.2 Debugging

```python
# Enable debug logging
import logging
logging.getLogger("RAG").setLevel(logging.DEBUG)

# Trace specific request
with tracer.start_as_current_span("debug_request"):
    result = await chat(query, profile_id)

# Check LangGraph state
state = await workflow.aget_state(config)
print(state.values)
```

---

## 20. Glossary

| Term | Definition |
|------|------------|
| **Cognitive Twin** | AI representation that thinks and speaks like a specific executive |
| **DNA Embedding** | Dense vector representation of executive profile |
| **Voiceprint** | Communication style markers (opener, signoff, emoji usage) |
| **ReAct** | Reasoning and Acting - multi-step reasoning pattern |
| **Graph-Constrained Search** | Vector search limited to graph-traversal candidates |
| **Hybrid Retrieval** | Combining vector + graph + memory sources |
| **Adaptive Reranking** | Strategy selection based on result quality |
| **MoE** | Mixture of Experts - learned expert selection |
| **Logic Graph** | Rules encoded as Neo4j nodes and edges |
| **Soft Assertion** | Expression pattern: "I think..." vs absolute statements |
| **Instruction Sandwich** | Reasoning FIRST, Instructions LAST in prompts |
| **RAGAS** | RAG evaluation framework (faithfulness, relevancy) |

---

## Quick Reference

### Key Files

```
api/main.py                           # Application entry point
langgraph_workflow/nodes.py           # Workflow node implementations
conversation_engine/prompt/rules.py   # SINGLE SOURCE OF TRUTH
conversation_engine/prompt/assembler.py # Prompt assembly
hybrid_retrieval/config.py            # Retrieval configuration
cognitive_twin/conversational_router.py # Small-talk detection
cognitive_twin/inference_engine.py    # Opinion formation
config/llm_config.yaml                # LLM provider config
test_data/executive_profiles/*.json   # Executive definitions
```

### Key Concepts

1. **Database is the Brain** - All data from PostgreSQL/Neo4j
2. **Graph Constrains Vector** - Graph narrows search before similarity
3. **Never "I Don't Know"** - Form opinions from values
4. **Recency Bias** - Critical instructions LAST
5. **Soft Targets** - Word limits are targets, not ceilings

### Commands

```bash
# Start services
docker-compose up -d

# Run API
uvicorn api.main:app --reload

# Run tests
pytest RAG/tests/ -v

# Load data
python init-scripts/load_postgres_data.py
```

---

*This document provides a comprehensive foundation for understanding and contributing to the RAG system. For specific implementation details, refer to the source code and inline documentation.*
