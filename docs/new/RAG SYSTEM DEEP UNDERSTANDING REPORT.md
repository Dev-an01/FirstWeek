🔬 RAG SYSTEM DEEP UNDERSTANDING REPORT

  ARCHITECTURE OVERVIEW

  The RAG system is an enterprise executive decision intelligence platform with:
  ┌────────────┬──────────────────────────────────────────────────────────────┐
  │   Layer    │                          Components                          │
  ├────────────┼──────────────────────────────────────────────────────────────┤
  │ API        │ FastAPI + Uvicorn (main.py - 1531 lines)                     │
  ├────────────┼──────────────────────────────────────────────────────────────┤
  │ Routing    │ 3-path system: Fast (<1.5s), Standard (<2.5s), Agentic (<5s) │
  ├────────────┼──────────────────────────────────────────────────────────────┤
  │ Retrieval  │ Hybrid: Vector + Graph + Memory search                       │
  ├────────────┼──────────────────────────────────────────────────────────────┤
  │ Generation │ Multi-provider LLM (Groq, OpenAI, Gemini, GLM)               │
  ├────────────┼──────────────────────────────────────────────────────────────┤
  │ Persona    │ 5-stage conversation engine with executive profiles          │
  ├────────────┼──────────────────────────────────────────────────────────────┤
  │ Audio      │ Kokoro TTS + Faster Whisper STT                              │
  └────────────┴──────────────────────────────────────────────────────────────┘
  ---
  COMPLETE DATA FLOW

  USER QUERY
      ↓
  [Query Router] → Classify: fast/standard/agentic
      ↓
  [Parallel Retrieval]
  ├── VectorSearchEngine (PostgreSQL pgvector, 1024-dim BAAI/bge-m3)
  ├── GraphContextProvider (Neo4j entity traversal, 1-2 hops)
  └── MultiSignalMemorySearch (5-signal scoring: semantic, temporal, importance)
      ↓
  [ResultFusion] → Dedupe + Weighted scoring (60% vector, 40% graph)
      ↓
  [AdaptiveReranker] → Lightweight/Medium/Full based on quality
      ↓
  [ConversationEngine: 5-Stage Pipeline]
  ├── Stage 1: ContextAnalyzer (theme, urgency, emotion)
  ├── Stage 2: ResponseCalibrator (tone, style)
  ├── Stage 3: SemanticExampleSelector (few-shot examples)
  ├── Stage 4: PrecedentSelector (historical decisions)
  └── Stage 5: PromptAssembler (token-budget aware)
      ↓
  [LLMOrchestrator] → Path-specific handler + streaming
      ↓
  [ResponseFormatter] → Citations, confidence scores
      ↓
  FINAL RESPONSE

  ---
  KEY INNER MECHANICS

  1. Embedding Pipeline:
  - Model: BAAI/bge-m3 (multilingual, 1024-dim)
  - Chunking: 3-signal semantic boundary detection
  - Storage: Dual (PostgreSQL + Neo4j properties)
  - Caching: L1 memory + L2 Redis (7-day TTL)

  2. Hybrid Scoring Formula:
  hybrid_score = 0.6 × vector_similarity + 0.4 × graph_proximity

  3. Memory Multi-Signal Scoring:
  score = (0.40×semantic + 0.25×temporal + 0.20×importance) × feedback × user_context

  4. Query-Type Fusion Weights:
  ┌──────────────┬────────┬───────┬────────┐
  │     Type     │ Vector │ Graph │ Memory │
  ├──────────────┼────────┼───────┼────────┤
  │ factual      │ 80%    │ 15%   │ 5%     │
  ├──────────────┼────────┼───────┼────────┤
  │ decision     │ 35%    │ 25%   │ 40%    │
  ├──────────────┼────────┼───────┼────────┤
  │ relationship │ 30%    │ 65%   │ 5%     │
  └──────────────┴────────┴───────┴────────┘
  ---
  CORE COMPONENTS BY DIRECTORY
  ┌──────────────────────┬──────────────────────────┬─────────────────────────────────────────┐
  │      Directory       │         Purpose          │                Key Files                │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ api/                 │ REST endpoints           │ main.py, models.py, config.py           │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ llm_integration/     │ Multi-LLM abstraction    │ orchestrator.py, *_path_handler.py      │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ vector_search/       │ pgvector similarity      │ search_engine.py, postgres_client.py    │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ graph_context/       │ Neo4j relationships      │ provider.py, entity_extractor.py        │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ hybrid_retrieval/    │ Unified retrieval        │ manager.py, result_fusion.py            │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ conversation_engine/ │ 5-stage persona pipeline │ engine.py, prompt/assembler.py          │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ profile_management/  │ Executive profiles       │ profile_manager.py                      │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ memory/              │ Session + episodic       │ session_manager.py                      │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ cache/               │ 3-level caching          │ cache_manager.py                        │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ langgraph_workflow/  │ Agentic orchestration    │ graph.py, nodes.py                      │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ audio_services/      │ TTS/STT                  │ tts_manager.py, realtime_stt_service.py │
  ├──────────────────────┼──────────────────────────┼─────────────────────────────────────────┤
  │ observability/       │ Metrics + tracing        │ metrics.py, tracing.py                  │
  └──────────────────────┴──────────────────────────┴─────────────────────────────────────────┘
  ---
  EXTERNAL INTEGRATIONS
  ┌───────────┬───────────────────────────┬────────────────────────┐
  │  Service  │        Technology         │        Purpose         │
  ├───────────┼───────────────────────────┼────────────────────────┤
  │ Vector DB │ PostgreSQL + pgvector     │ Semantic search        │
  ├───────────┼───────────────────────────┼────────────────────────┤
  │ Graph DB  │ Neo4j                     │ Relationship discovery │
  ├───────────┼───────────────────────────┼────────────────────────┤
  │ Cache     │ Redis                     │ L2 embedding cache     │
  ├───────────┼───────────────────────────┼────────────────────────┤
  │ LLM       │ Groq/OpenAI/Gemini/GLM    │ Generation             │
  ├───────────┼───────────────────────────┼────────────────────────┤
  │ TTS       │ Kokoro/Google Chirp 3     │ Voice output           │
  ├───────────┼───────────────────────────┼────────────────────────┤
  │ STT       │ Faster Whisper            │ Voice input            │
  ├───────────┼───────────────────────────┼────────────────────────┤
  │ Tracing   │ OpenTelemetry + LangSmith │ Observability          │
  └───────────┴───────────────────────────┴────────────────────────┘
  ---
  CRITICAL ARCHITECTURAL PATTERNS

  1. 3-Path Query Routing - Optimal latency/quality tradeoff
  2. Factory Pattern - LLMClientFactory for multi-provider support
  3. Singleton Pattern - ProfileManager, EmbeddingModel (GPU memory)
  4. State Machine - LangGraph for agentic workflows
  5. Chain of Responsibility - 5-stage prompt assembly
  6. Graceful Degradation - Fallbacks at every layer (Neo4j unavailable → vector-only)

  ---
  LATENCY TARGETS
  ┌──────────┬──────────┬───────────┬─────────────┬──────────────────┐
  │   Path   │  Total   │ Retrieval │     LLM     │      Notes       │
  ├──────────┼──────────┼───────────┼─────────────┼──────────────────┤
  │ Fast     │ 0.8-1.5s │ 100-200ms │ 600-1200ms  │ Simple factual   │
  ├──────────┼──────────┼───────────┼─────────────┼──────────────────┤
  │ Standard │ 1.5-2.5s │ 200-300ms │ 1000-1800ms │ Decision queries │
  ├──────────┼──────────┼───────────┼─────────────┼──────────────────┤
  │ Agentic  │ 3-5s     │ 300-400ms │ 2000-3500ms │ Complex + ReAct  │
  └──────────┴──────────┴───────────┴─────────────┴──────────────────┘
  This RAG system is production-ready with comprehensive error handling, RBAC security, streaming support, and enterprise-grade observability.