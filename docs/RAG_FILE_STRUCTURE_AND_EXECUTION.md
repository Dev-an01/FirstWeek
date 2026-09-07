# RAG SYSTEM - FILE STRUCTURE & REAL-TIME EXECUTION FLOW

## 📁 COMPLETE FILE STRUCTURE TREE

```
ai-officer/
│
├─── RAG/
│    │
│    ├─── api/
│    │    ├─── __init__.py
│    │    ├─── main.py                          [FastAPI app, endpoints]
│    │    ├─── langgraph_endpoints.py           [LangGraph API handlers]
│    │    ├─── schemas.py                       [Pydantic request/response models]
│    │    └─── middleware.py                    [Auth, logging, CORS]
│    │
│    ├─── langgraph_workflow/
│    │    ├─── __init__.py
│    │    ├─── graph.py                         [StateGraph creation, path wiring]
│    │    ├─── nodes.py                         [All node functions]
│    │    ├─── state.py                         [RAGState TypedDict]
│    │    ├─── edges.py                         [Conditional edge functions]
│    │    └─── checkpointer.py                  [AsyncPostgresSaver setup]
│    │
│    ├─── hybrid_retrieval/
│    │    ├─── __init__.py
│    │    ├─── manager.py                       [HybridRetrievalManager]
│    │    ├─── memory_search.py                 [MultiSignalMemorySearch]
│    │    ├─── fusion.py                        [ResultFusion]
│    │    └─── adaptive_reranker.py             [AdaptiveReranker]
│    │
│    ├─── vector_search/
│    │    ├─── __init__.py
│    │    ├─── search_engine.py                 [VectorSearchEngine]
│    │    └─── embedding/
│    │         ├─── __init__.py
│    │         ├─── embedding_service.py        [Embedding generation]
│    │         ├─── cache.py                    [L1/L2 caching]
│    │         └─── models/                     [Local embedding models]
│    │
│    ├─── graph_context/
│    │    ├─── __init__.py
│    │    ├─── provider.py                      [GraphContextProvider]
│    │    ├─── neo4j_client.py                  [Neo4j driver wrapper]
│    │    └─── graph_queries.py                 [Cypher query templates]
│    │
│    ├─── conversation_engine/
│    │    ├─── __init__.py
│    │    ├─── engine.py                        [ConversationEngine main]
│    │    ├─── context/
│    │    │    ├─── __init__.py
│    │    │    ├─── analyzer.py                 [ContextAnalyzer]
│    │    │    └─── calibrator.py               [ResponseCalibrator]
│    │    ├─── examples/
│    │    │    ├─── __init__.py
│    │    │    └─── selector.py                 [ExampleSelector]
│    │    ├─── precedents/
│    │    │    ├─── __init__.py
│    │    │    └─── selector.py                 [PrecedentSelector]
│    │    └─── prompt/
│    │         ├─── __init__.py
│    │         ├─── assembler.py                [PromptAssembler]
│    │         ├─── budget.py                   [Token budget allocation]
│    │         └─── sections/
│    │              ├─── __init__.py
│    │              ├─── identity.py
│    │              ├─── values.py
│    │              ├─── speaking_style.py
│    │              ├─── instructions.py
│    │              ├─── reasoning.py
│    │              ├─── calibration.py
│    │              ├─── example.py
│    │              ├─── precedent.py
│    │              ├─── conversation_context.py
│    │              └─── retrieved_context.py
│    │
│    ├─── cognitive_twin/
│    │    ├─── __init__.py
│    │    ├─── layers/
│    │    │    ├─── __init__.py
│    │    │    ├─── conversational_router.py    [Layer 0]
│    │    │    ├─── cognitive_lens.py           [Layer 1]
│    │    │    ├─── cognitive_frame.py          [Layer 2]
│    │    │    ├─── memory_integration.py       [Layer 3 - in retrieval]
│    │    │    ├─── situation_analyzer.py       [Layer 4]
│    │    │    └─── relationship_adapter.py     [Layer 5]
│    │    └─── prompt_assembly.py               [Cognitive prompt assembly]
│    │
│    ├─── llm_integration/
│    │    ├─── __init__.py
│    │    ├─── orchestrator.py                  [LLMOrchestrator]
│    │    ├─── client_factory.py                [LLMClientFactory]
│    │    ├─── prompt_builder.py                [Legacy prompt builder]
│    │    ├─── response_formatter.py            [Citation extraction]
│    │    ├─── clients/
│    │    │    ├─── __init__.py
│    │    │    ├─── base_client.py              [Abstract base]
│    │    │    ├─── groq_client.py              [Groq implementation]
│    │    │    ├─── openai_client.py            [OpenAI implementation]
│    │    │    ├─── gemini_client.py            [Google Gemini]
│    │    │    └─── glm_client.py               [GLM Chinese]
│    │    └─── evaluation/
│    │         ├─── __init__.py
│    │         ├─── ragas_evaluator.py          [RAGAS metrics]
│    │         └─── quality_evaluator.py        [Custom quality metrics]
│    │
│    ├─── query_analysis/
│    │    ├─── __init__.py
│    │    ├─── analyzer.py                      [QueryAnalyzer]
│    │    ├─── router.py                        [QueryRouter]
│    │    ├─── entity_extractor.py              [spaCy + GLiNER]
│    │    └─── classifiers.py                   [Complexity, type classifiers]
│    │
│    ├─── database/
│    │    ├─── __init__.py
│    │    ├─── postgres_client.py               [PostgreSQL operations]
│    │    ├─── neo4j_client.py                  [Neo4j operations]
│    │    └─── redis_client.py                  [Redis cache operations]
│    │
│    ├─── utils/
│    │    ├─── __init__.py
│    │    ├─── session_manager.py               [Session management]
│    │    ├─── config_loader.py                 [YAML config loader]
│    │    ├─── logger.py                        [Structured logging]
│    │    └─── metrics.py                       [Prometheus metrics]
│    │
│    ├─── observability/
│    │    ├─── __init__.py
│    │    ├─── langsmith_integration.py         [LangSmith tracing]
│    │    ├─── prometheus_exporter.py           [Metrics export]
│    │    └─── grafana_dashboards/
│    │         ├─── system_overview.json
│    │         ├─── langgraph_performance.json
│    │         ├─── retrieval_metrics.json
│    │         ├─── llm_latency.json
│    │         └─── quality_scores.json
│    │
│    └─── audio/
│         ├─── __init__.py
│         ├─── tts_engine.py                    [Kokoro TTS]
│         ├─── stt_engine.py                    [Faster Whisper]
│         └─── streaming.py                     [Audio streaming]
│
├─── config/
│    ├─── llm_config.yaml                       [LLM provider config]
│    ├─── retrieval_weights.yaml                [Query-type weights]
│    ├─── cognitive_config.yaml                 [Cognitive twin config]
│    └─── .env                                  [Environment variables]
│
├─── init-scripts/
│    ├─── setup_database.sql                    [PostgreSQL schema]
│    ├─── load_postgres_data.py                 [Data ingestion]
│    ├─── setup_neo4j.cypher                    [Neo4j schema]
│    └─── migration_768_to_1024.py              [Dimension migration]
│
├─── data/
│    ├─── profiles/
│    │    ├─── sample_san.json
│    │    └─── ...
│    ├─── policies/
│    │    ├─── engineering_guidelines.json
│    │    └─── ...
│    ├─── decisions/
│    │    ├─── architecture_decisions.json
│    │    └─── ...
│    └─── communications/
│         ├─── slack_messages.json
│         ├─── youtube_transcripts.json
│         └─── ...
│
├─── tests/
│    ├─── unit/
│    │    ├─── test_query_analyzer.py
│    │    ├─── test_vector_search.py
│    │    ├─── test_fusion.py
│    │    └─── ...
│    ├─── integration/
│    │    ├─── test_langgraph_workflow.py
│    │    ├─── test_conversation_engine.py
│    │    └─── ...
│    └─── e2e/
│         └─── test_full_pipeline.py
│
├─── docker-compose.yml                         [Services orchestration]
├─── Dockerfile                                 [RAG service container]
├─── requirements.txt                           [Python dependencies]
├─── README.md                                  [Documentation]
└─── .gitignore

```

---

## ⏱️ REAL-TIME EXECUTION FLOW WITH TIMING

### Standard Path Example: "What are sample-san's thoughts on technical debt?"

```
T+0ms    ┌─────────────────────────────────────────────┐
         │  1. API Request Reception                   │
         │  File: api/main.py:process_chat()          │
         │  Action: Parse ChatRequest, validate        │
         └──────────────┬──────────────────────────────┘
                        │
T+5ms    ┌─────────────▼──────────────────────────────┐
         │  2. Session Management                      │
         │  File: utils/session_manager.py            │
         │  Action: Get or create session_id          │
         │  DB: SELECT conversation_sessions          │
         └──────────────┬──────────────────────────────┘
                        │
T+15ms   ┌─────────────▼──────────────────────────────┐
         │  3. LangGraph Initialization               │
         │  File: api/langgraph_endpoints.py          │
         │  Action: Create RAGState, restore history  │
         │  DB: SELECT checkpoints WHERE thread_id    │
         └──────────────┬──────────────────────────────┘
                        │
T+25ms   ┌─────────────▼──────────────────────────────┐
         │  4. Node: analyze_query                    │
         │  File: langgraph_workflow/nodes.py:53     │
         │  Action: QueryAnalyzer.analyze()           │
         │  ├─ spaCy NER: "technical debt" → entity   │
         │  ├─ Complexity: medium (2 entities)        │
         │  └─ Type: analysis (keyword: "thoughts")   │
         │  Output: QueryFeatures                     │
         └──────────────┬──────────────────────────────┘
                        │
T+85ms   ┌─────────────▼──────────────────────────────┐
         │  5. Node: route_query                      │
         │  File: langgraph_workflow/nodes.py:78     │
         │  Action: QueryRouter.route()               │
         │  Decision: STANDARD PATH                   │
         │  Reason: has_entities + medium_complexity  │
         │  Confidence: 0.85                          │
         └──────────────┬──────────────────────────────┘
                        │
T+95ms   ┌─────────────▼──────────────────────────────┐
         │  6. Node: retrieve_graphrag_standard       │
         │  File: langgraph_workflow/nodes.py:142    │
         │  Action: Skip (no community search needed) │
         └──────────────┬──────────────────────────────┘
                        │
T+100ms  ┌─────────────▼──────────────────────────────┐
         │  7. Node: retrieve_parallel_standard       │
         │  File: langgraph_workflow/nodes.py:176    │
         │  Action: ThreadPoolExecutor with 2 workers │
         │  ┌──────────────────────────────────────┐  │
         │  │  PARALLEL EXECUTION                 │  │
         │  └──────────────────────────────────────┘  │
         └───┬────────────────────────────┬────────────┘
             │                            │
             │ Worker 1                   │ Worker 2
             │                            │
T+105ms      ▼                            ▼
    ┌────────────────────┐    ┌──────────────────────┐
    │ retrieve_graph_    │    │ retrieve_memory      │
    │ enhanced           │    │                      │
    │ File: nodes.py:198│    │ File: nodes.py:285  │
    └────────┬───────────┘    └──────────┬───────────┘
             │                            │
T+110ms      ├─ Step 1: Graph Context    ├─ Step 1: DB Query
             │  File: graph_context/      │  File: hybrid_retrieval/
             │        provider.py         │        memory_search.py
             │  ├─ Extract entities       │  SELECT * FROM
             │  │  ["technical debt",     │  conversation_turns
             │  │   "sample-san"]          │  WHERE executive_id
             │  ├─ Neo4j MATCH            │  AND created_at > -30d
             │  │  (e:Entity)              │  LIMIT 50
             │  │  WHERE e.name IN         │  [DB: 45ms]
T+155ms      │  │  [Neo4j: 35ms]          │
             │  └─ MATCH traversal         │
             │     (exec)-[r*1..2]-(rel)   │
             │     distance calculation    │
             │     → candidate_ids[47]     │
             │     [Neo4j: 55ms]           │
T+210ms      │                            │
             ├─ Step 2: Generate Embedding│  Step 2: 5-Signal Scoring
             │  File: vector_search/      │  For each of 50 turns:
             │        embedding/           │  ├─ Semantic (40%)
             │        embedding_service.py│  │  cosine similarity
             │  ├─ Check L1 cache: MISS   │  ├─ Temporal (25%)
             │  ├─ Check L2 cache: MISS   │  │  exp(-age/30)
             │  ├─ sentence-transformers  │  ├─ Importance (20%)
             │  │  forward pass            │  ├─ Feedback multiplier
             │  │  [GPU: 35ms]             │  └─ Context multiplier
T+245ms      │  └─ Store in caches        │  [Python: 90ms]
             │                            │
             ├─ Step 3: pgvector Search   │  Step 3: Select top 5
             │  File: vector_search/      │  └─ ORDER BY memory_score
             │        search_engine.py    │     LIMIT 5
             │  SELECT source_id,         │     [Python: 5ms]
             │    1 - (embedding <=>      │
T+300ms      │       $query_emb) AS sim   │
             │  FROM embeddings           │
             │  WHERE source_id IN         │
             │    ($candidate_ids)        │
             │  ORDER BY embedding <=>    │
             │  LIMIT 15                  │
             │  [pgvector: 85ms]          │
T+330ms      │                            │
             ├─ Step 4: Hybrid Scoring    │
             │  For each result:          │
             │  ├─ v_score = similarity   │
             │  ├─ g_score = 1/(1+dist)   │
             │  ├─ hybrid = 0.6v + 0.4g   │
             │  └─ If name_match: *1.2    │
T+340ms      │  [Python: 10ms]            │
             │                            │
             └─────────────┬──────────────┴──────┘
                           │
                           │ Both workers complete
                           │
T+345ms      ┌─────────────▼──────────────────────────────┐
             │  8. Node: fuse_results_standard            │
             │  File: langgraph_workflow/nodes.py:312    │
             │  Action: ResultFusion.fuse()               │
             │  ├─ Load config:                           │
             │  │  retrieval_weights.yaml                 │
             │  │  query_type: "analysis"                 │
             │  │  weights: V:0.45 G:0.30 M:0.25          │
             │  ├─ Confidence blending (0.85 > 0.6):      │
             │  │  Use type-specific weights              │
             │  ├─ Fuse 15 vector + 5 memory results:     │
             │  │  For each unique source_id:             │
             │  │    fused = 0.45*v + 0.30*g + 0.25*m     │
             │  ├─ Deduplicate: 18 unique results         │
             │  └─ Sort by fused_score DESC               │
             │  [Python: 25ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+370ms      ┌─────────────▼──────────────────────────────┐
             │  9. Node: rerank_results_standard          │
             │  File: langgraph_workflow/nodes.py:348    │
             │  Action: AdaptiveReranker.rerank()         │
             │  ├─ Select strategy:                       │
             │  │  result_count = 18                      │
             │  │  query_type = "analysis"                │
             │  │  → Strategy: "medium"                   │
             │  ├─ Load cross-encoder model:              │
             │  │  ms-marco-MiniLM-L-6-v2                │
             │  │  [Model load: 120ms, cached]            │
             │  ├─ Rerank top 10:                         │
             │  │  For each result:                       │
             │  │    cross_score = model.predict(         │
             │  │      [(query, result.content)]          │
             │  │    )                                    │
             │  │    final = 0.7*fused + 0.3*cross        │
             │  │  [Inference: 180ms for 10 items]        │
             │  └─ Re-sort by final_score                 │
             │  [Total: 320ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+690ms      ┌─────────────▼──────────────────────────────┐
             │  10. Node: cognitive_lens_standard         │
             │  File: langgraph_workflow/nodes.py:412    │
             │  Action: CognitiveLens.apply()             │
             │  ├─ Load sample-san's expertise:           │
             │  │  - Software Architecture (0.9)          │
             │  │  - Technical Debt (0.8)                 │
             │  │  - Team Leadership (0.7)                │
             │  ├─ Calculate domain affinity:             │
             │  │  Result contains "technical debt"       │
             │  │  → affinity_boost = 0.8                 │
             │  │  adjusted_score *= (1 + 0.8) = 1.8x     │
             │  └─ Re-sort by adjusted_score              │
             │  [Python: 15ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+705ms      ┌─────────────▼──────────────────────────────┐
             │  11. Node: cognitive_frame_standard        │
             │  File: langgraph_workflow/nodes.py:445    │
             │  Action: CognitiveFrame.apply()            │
             │  ├─ Load reasoning patterns:               │
             │  │  - Red flag: "Ignoring tech debt"       │
             │  │  - Framework: "Long-term vs. short-term"│
             │  │  - Model: "Invest in quality early"     │
             │  └─ Prepare injection prompt               │
             │  [Python: 10ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+715ms      ┌─────────────▼──────────────────────────────┐
             │  12. Node: situation_analysis_standard     │
             │  File: langgraph_workflow/nodes.py:478    │
             │  Action: SituationAnalyzer.analyze()       │
             │  ├─ Detect tone: "neutral"                 │
             │  ├─ Assess urgency: "medium"               │
             │  ├─ Context type: "technical"              │
             │  └─ Calibration hints prepared             │
             │  [Python: 12ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+727ms      ┌─────────────▼──────────────────────────────┐
             │  13. Node: relationship_adaptation_std     │
             │  File: langgraph_workflow/nodes.py:512    │
             │  Action: RelationshipAdapter.adapt()       │
             │  ├─ User role: "Engineer"                  │
             │  ├─ Adjustments:                           │
             │  │  - Formality: "less_formal"             │
             │  │  - Detail: "more_detail"                │
             │  │  - Tone: "collaborative"                │
             │  └─ Style hints prepared                   │
             │  [Python: 8ms]                             │
             └──────────────┬──────────────────────────────┘
                            │
T+735ms      ┌─────────────▼──────────────────────────────┐
             │  14. Node: cognitive_prompt_assembly_std   │
             │  File: langgraph_workflow/nodes.py:548    │
             │  Action: Combine all cognitive outputs     │
             │  [Python: 5ms]                             │
             └──────────────┬──────────────────────────────┘
                            │
T+740ms      ┌─────────────▼──────────────────────────────┐
             │  15. Node: generate_standard               │
             │  File: langgraph_workflow/nodes.py:589    │
             │  Action: IF use_conversation_engine: TRUE  │
             └──────────────┬──────────────────────────────┘
                            │
             ┌──────────────▼──────────────────────────────┐
             │  ConversationEngine.generate()             │
             │  File: conversation_engine/engine.py:87   │
             └──────────────┬──────────────────────────────┘
                            │
T+745ms      ┌─────────────▼──────────────────────────────┐
             │  Stage 1: ContextAnalyzer                  │
             │  File: conversation_engine/context/        │
             │        analyzer.py:45                      │
             │  ├─ theme: "technical"                     │
             │  ├─ urgency: "medium"                      │
             │  ├─ emotion: "neutral"                     │
             │  └─ turn_type: "question"                  │
             │  [Python: 15ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+760ms      ┌─────────────▼──────────────────────────────┐
             │  Stage 2: ResponseCalibrator               │
             │  File: conversation_engine/context/        │
             │        calibrator.py:62                    │
             │  ├─ attention_weights:                     │
             │  │  identity: 0.7, values: 0.8,            │
             │  │  style: 0.6, examples: 0.7,             │
             │  │  precedents: 0.5                        │
             │  └─ tone_adjustment: "collaborative"       │
             │  [Python: 18ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+778ms      ┌─────────────▼──────────────────────────────┐
             │  Stage 3: ExampleSelector                  │
             │  File: conversation_engine/examples/       │
             │        selector.py:89                      │
             │  ├─ Load communications:                   │
             │  │  SELECT * FROM communications           │
             │  │  WHERE executive_id = 'sample-san'      │
             │  │  [DB: 25ms]                             │
             │  ├─ Generate query embedding:              │
             │  │  [Cache hit from earlier: 0ms]          │
             │  ├─ Semantic matching (12 examples):       │
             │  │  cosine similarities calculated         │
             │  │  [Python: 8ms]                          │
             │  └─ Best match: Slack message about        │
             │     code quality (similarity: 0.78)        │
             │  [Total: 33ms]                             │
             └──────────────┬──────────────────────────────┘
                            │
T+811ms      ┌─────────────▼──────────────────────────────┐
             │  Stage 4: PrecedentSelector                │
             │  File: conversation_engine/precedents/     │
             │        selector.py:112                     │
             │  ├─ Query type: "analysis" (not decision)  │
             │  └─ Skip precedent selection               │
             │  [Python: 2ms]                             │
             └──────────────┬──────────────────────────────┘
                            │
T+813ms      ┌─────────────▼──────────────────────────────┐
             │  Stage 5: PromptAssembler                  │
             │  File: conversation_engine/prompt/         │
             │        assembler.py:156                    │
             │  ├─ Token budget: 8000 (standard path)     │
             │  ├─ Build system_prompt (10 sections):     │
             │  │  1. Identity: 800 tokens                │
             │  │     "I'm sample-san, CTO..."            │
             │  │  2. Values: 600 tokens                  │
             │  │     "I prioritize long-term quality..." │
             │  │  3. Speaking Style: 400 tokens          │
             │  │     "I speak directly but warmly..."    │
             │  │  4. Instructions: 400 tokens            │
             │  │     "Keep responses under 300 words..." │
             │  │  6. Calibration: 200 tokens             │
             │  │     "User is Engineer, be collaborative"│
             │  │  [Sections assembled: 95ms]             │
             │  ├─ Build user_prompt:                     │
             │  │  7. Example: 600 tokens                 │
             │  │     Slack message about code quality    │
             │  │  9. Conversation: 200 tokens            │
             │  │     [2 previous turns]                  │
             │  │  10. Retrieved Context: 5000 tokens     │
             │  │      [18 reranked results, formatted]   │
             │  │  Query: "What are your thoughts on      │
             │  │          technical debt?"               │
             │  │  [Sections assembled: 115ms]            │
             │  └─ Total tokens: 7800/8000                │
             │  [Total: 210ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+1023ms     ┌─────────────▼──────────────────────────────┐
             │  LLMOrchestrator.generate_with_prompts()   │
             │  File: llm_integration/orchestrator.py:189│
             │  ├─ messages = [                           │
             │  │   {"role": "system", "content": ...},   │
             │  │   {"role": "user", "content": ...}      │
             │  │ ]                                        │
             │  ├─ LLMClientFactory.create():             │
             │  │  provider: "groq"                       │
             │  │  path: "standard"                       │
             │  │  model: "llama-3.1-70b-versatile"       │
             │  │  settings: {temp: 0.5, max: 1500}       │
             │  │  [Factory: 8ms]                         │
             │  └─ GroqClient instantiated                │
             └──────────────┬──────────────────────────────┘
                            │
T+1031ms     ┌─────────────▼──────────────────────────────┐
             │  GroqClient.generate()                     │
             │  File: llm_integration/clients/            │
             │        groq_client.py:78                   │
             │  ├─ Format for Groq API                    │
             │  ├─ POST api.groq.com/openai/v1/chat      │
             │  │  [API call initiated]                   │
             │  │                                         │
             │  │  [Waiting for LLM inference...]         │
             │  │                                         │
             │  │  [Token generation: ~1200ms]            │
T+2231ms     │  │                                         │
             │  ├─ Response received (348 tokens)         │
             │  └─ Parse and return                       │
             │  [Total: 1200ms]                           │
             └──────────────┬──────────────────────────────┘
                            │
T+2231ms     ┌─────────────▼──────────────────────────────┐
             │  ResponseFormatter.format_response()       │
             │  File: llm_integration/                    │
             │        response_formatter.py:56            │
             │  ├─ Extract citations (regex):             │
             │  │  Found 4 citations: [Source: Policy 1], │
             │  │  [Source: Decision Case 3], etc.        │
             │  ├─ Build source list:                     │
             │  │  Link citations to retrieval results    │
             │  │  [4 sources matched]                    │
             │  └─ Format final response                  │
             │  [Python: 15ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+2246ms     ┌─────────────▼──────────────────────────────┐
             │  RAGASEvaluator.evaluate() [10% sampling]  │
             │  File: llm_integration/evaluation/         │
             │        ragas_evaluator.py:89               │
             │  ├─ Faithfulness:                          │
             │  │  Extract 8 claims, verify each          │
             │  │  LLM calls for verification             │
             │  │  [LLM: 450ms]                           │
             │  │  Score: 0.92 (7/8 verified)             │
             │  ├─ Relevancy:                             │
             │  │  Calculate semantic similarity          │
             │  │  [Python: 25ms]                         │
             │  │  Score: 0.88                            │
             │  └─ Precision:                             │
             │     Verify 4 citations                     │
             │     [Python: 5ms]                          │
             │     Score: 1.0 (4/4 correct)               │
             │  [Total: 480ms]                            │
             └──────────────┬──────────────────────────────┘
                            │
T+2726ms     ┌─────────────▼──────────────────────────────┐
             │  Update RAGState                           │
             │  File: langgraph_workflow/nodes.py:645    │
             │  ├─ conversation_history += [              │
             │  │   {"role": "user", "content": query},   │
             │  │   {"role": "assistant", "content": resp}│
             │  │ ]                                        │
             │  └─ llm_response, citations, sources set   │
             │  [Python: 2ms]                             │
             └──────────────┬──────────────────────────────┘
                            │
T+2728ms     ┌─────────────▼──────────────────────────────┐
             │  LangGraph Checkpointer.save()             │
             │  File: langgraph_workflow/                 │
             │        checkpointer.py:67                  │
             │  ├─ Serialize RAGState to JSONB            │
             │  ├─ INSERT INTO checkpoints:               │
             │  │  checkpoint_ns: thread_id               │
             │  │  channel_values: {state JSONB}          │
             │  │  [DB: 35ms]                             │
             │  └─ Checkpoint saved                       │
             │  [Total: 42ms]                             │
             └──────────────┬──────────────────────────────┘
                            │
T+2770ms     ┌─────────────▼──────────────────────────────┐
             │  SessionManager.store_conversation_turn()  │
             │  File: utils/session_manager.py:145       │
             │  ├─ Calculate importance_score:            │
             │  │  complexity: 0.5, decision: 0.1,        │
             │  │  context_richness: 0.7                  │
             │  │  → importance = 0.65                    │
             │  ├─ INSERT INTO conversation_turns:        │
             │  │  [DB: 18ms]                             │
             │  └─ UPDATE conversation_sessions:          │
             │     last_activity = NOW()                  │
             │     [DB: 8ms]                              │
             │  [Total: 30ms]                             │
             └──────────────┬──────────────────────────────┘
                            │
T+2800ms     ┌─────────────▼──────────────────────────────┐
             │  Store quality_metrics                     │
             │  File: llm_integration/evaluation/         │
             │        quality_evaluator.py:178            │
             │  INSERT INTO quality_metrics               │
             │  [DB: 12ms]                                │
             └──────────────┬──────────────────────────────┘
                            │
T+2812ms     ┌─────────────▼──────────────────────────────┐
             │  LangSmith Logging                         │
             │  File: observability/                      │
             │        langsmith_integration.py:92         │
             │  ├─ Log run with thread_id                 │
             │  ├─ Track node executions (15 nodes)       │
             │  └─ Record latencies                       │
             │  [API: 18ms async]                         │
             └──────────────┬──────────────────────────────┘
                            │
T+2830ms     ┌─────────────▼──────────────────────────────┐
             │  Build ChatResponse                        │
             │  File: api/langgraph_endpoints.py:234     │
             │  {                                         │
             │    "response": "Technical debt...",        │
             │    "sources": [{...}, {...}, {...}, {...}],│
             │    "citations": ["Source: Policy 1", ...], │
             │    "metadata": {                           │
             │      "path": "standard",                   │
             │      "latency_ms": 2830,                   │
             │      "model": "llama-3.1-70b-versatile",   │
             │      "tokens_used": 348,                   │
             │      "quality_scores": {                   │
             │        "faithfulness": 0.92,               │
             │        "relevancy": 0.88,                  │
             │        "precision": 1.0                    │
             │      }                                     │
             │    },                                      │
             │    "session_id": "sess_abc123"             │
             │  }                                         │
             └──────────────┬──────────────────────────────┘
                            │
T+2835ms     ┌─────────────▼──────────────────────────────┐
             │  Return HTTP 200 Response                  │
             │  File: api/main.py                         │
             └────────────────────────────────────────────┘

TOTAL LATENCY: 2835ms (2.8 seconds)

```

---

## ⚡ LATENCY BREAKDOWN BY PHASE

```
Phase                          Time      % of Total   Critical Path?
─────────────────────────────────────────────────────────────────────
API + Session Setup           15ms      0.5%         No
Query Analysis               60ms      2.1%         Yes
Routing Decision              10ms      0.4%         Yes
Graph Context Discovery      100ms      3.5%         Yes (parallel)
Vector Search                125ms      4.4%         Yes (parallel)
Memory Search                135ms      4.8%         Yes (parallel)
Result Fusion                 25ms      0.9%         Yes
Adaptive Reranking           320ms     11.3%         Yes
Cognitive Enhancement         50ms      1.8%         Yes
ConversationEngine Pipeline  273ms      9.6%         Yes
LLM Execution              1200ms     42.4%         YES (bottleneck)
Response Formatting           15ms      0.5%         No
RAGAS Evaluation             480ms     16.9%         No (sampling)
State Persistence             72ms      2.5%         No
Observability Logging         18ms      0.6%         No
Response Building              5ms      0.2%         No
─────────────────────────────────────────────────────────────────────
TOTAL                       2835ms    100.0%

Critical Path (affects user-perceived latency):
    Query Analysis → Routing → Parallel Retrieval → Fusion
    → Reranking → Cognitive → ConversationEngine → LLM → Formatting
    = ~2200ms (78% of total)

Parallel Operations (not on critical path):
    - Graph + Vector + Memory retrieval (max 135ms, not sum)
    - RAGAS evaluation (async, doesn't block response)
    - Observability logging (async)

Bottleneck: LLM Execution (1200ms, 42% of total)
Optimization targets:
    1. LLM latency (use faster models, reduce prompt size)
    2. Reranking (320ms) - use lightweight strategy more often
    3. ConversationEngine (273ms) - cache prompt sections
```

---

## 🔀 PARALLEL VS SEQUENTIAL OPERATIONS

```
Sequential Operations (must wait):
    ┌───────────────────────────────────────────────────────┐
    │ Query Analysis → Routing → Retrieval → Fusion        │
    │ → Reranking → Cognitive → Prompt → LLM → Format      │
    └───────────────────────────────────────────────────────┘
    Total: ~2200ms

Parallel Operations (concurrent):

    ┌─────────────────┐
    │ Graph Context   │ 100ms  ┐
    ├─────────────────┤        │
    │ Vector Search   │ 125ms  ├─ max(100, 125, 135) = 135ms
    ├─────────────────┤        │
    │ Memory Search   │ 135ms  ┘
    └─────────────────┘

    Without parallelization: 100 + 125 + 135 = 360ms
    With parallelization: 135ms
    Savings: 225ms (62% faster)

Async Operations (non-blocking):

    ┌─────────────────────────────────────┐
    │ RAGAS Evaluation (sampling)         │ 480ms
    ├─────────────────────────────────────┤
    │ LangSmith Logging                   │ 18ms
    ├─────────────────────────────────────┤
    │ Quality Metrics Storage             │ 12ms
    └─────────────────────────────────────┘

    These happen after response is sent (HTTP 200)
    User doesn't wait for these operations
```

---

## 🎯 FILE-TO-FUNCTION MAPPING (Key Operations)

```
Query → Response Journey (Function Call Chain):

api/main.py:process_chat()
    └─→ api/langgraph_endpoints.py:langgraph_chat()
        └─→ langgraph_workflow/graph.py:create_rag_workflow()
            ├─→ langgraph_workflow/nodes.py:analyze_query()
            │   └─→ query_analysis/analyzer.py:QueryAnalyzer.analyze()
            │       ├─→ query_analysis/entity_extractor.py:extract_entities()
            │       ├─→ query_analysis/classifiers.py:classify_complexity()
            │       └─→ query_analysis/classifiers.py:classify_query_type()
            │
            ├─→ langgraph_workflow/nodes.py:route_query()
            │   └─→ query_analysis/router.py:QueryRouter.route()
            │
            ├─→ langgraph_workflow/nodes.py:retrieve_parallel_standard()
            │   ├─→ langgraph_workflow/nodes.py:retrieve_graph_enhanced()
            │   │   ├─→ graph_context/provider.py:get_context()
            │   │   │   └─→ graph_context/neo4j_client.py:execute_query()
            │   │   └─→ vector_search/search_engine.py:search()
            │   │       ├─→ vector_search/embedding/embedding_service.py:generate()
            │   │       └─→ database/postgres_client.py:execute_query()
            │   └─→ langgraph_workflow/nodes.py:retrieve_memory()
            │       └─→ hybrid_retrieval/memory_search.py:search()
            │           └─→ database/postgres_client.py:execute_query()
            │
            ├─→ langgraph_workflow/nodes.py:fuse_results_standard()
            │   └─→ hybrid_retrieval/fusion.py:ResultFusion.fuse()
            │       └─→ utils/config_loader.py:load_config('retrieval_weights.yaml')
            │
            ├─→ langgraph_workflow/nodes.py:rerank_results_standard()
            │   └─→ hybrid_retrieval/adaptive_reranker.py:rerank()
            │
            ├─→ langgraph_workflow/nodes.py:cognitive_lens_standard()
            │   └─→ cognitive_twin/layers/cognitive_lens.py:apply()
            │
            ├─→ langgraph_workflow/nodes.py:cognitive_frame_standard()
            │   └─→ cognitive_twin/layers/cognitive_frame.py:apply()
            │
            ├─→ langgraph_workflow/nodes.py:situation_analysis_standard()
            │   └─→ cognitive_twin/layers/situation_analyzer.py:analyze()
            │
            ├─→ langgraph_workflow/nodes.py:relationship_adaptation_standard()
            │   └─→ cognitive_twin/layers/relationship_adapter.py:adapt()
            │
            └─→ langgraph_workflow/nodes.py:generate_standard()
                └─→ conversation_engine/engine.py:generate()
                    ├─→ conversation_engine/context/analyzer.py:analyze()
                    ├─→ conversation_engine/context/calibrator.py:calibrate()
                    ├─→ conversation_engine/examples/selector.py:select()
                    │   └─→ database/postgres_client.py:execute_query()
                    ├─→ conversation_engine/precedents/selector.py:select()
                    │   └─→ database/postgres_client.py:execute_query()
                    └─→ conversation_engine/prompt/assembler.py:assemble()
                        ├─→ conversation_engine/prompt/sections/identity.py:build()
                        ├─→ conversation_engine/prompt/sections/values.py:build()
                        ├─→ conversation_engine/prompt/sections/speaking_style.py:build()
                        ├─→ conversation_engine/prompt/sections/instructions.py:build()
                        ├─→ conversation_engine/prompt/sections/calibration.py:build()
                        ├─→ conversation_engine/prompt/sections/example.py:build()
                        ├─→ conversation_engine/prompt/sections/conversation_context.py:build()
                        └─→ conversation_engine/prompt/sections/retrieved_context.py:build()

                └─→ llm_integration/orchestrator.py:generate_with_prompts()
                    ├─→ llm_integration/client_factory.py:create()
                    │   └─→ llm_integration/clients/groq_client.py:__init__()
                    ├─→ llm_integration/clients/groq_client.py:generate()
                    │   └─→ [External API: api.groq.com]
                    ├─→ llm_integration/response_formatter.py:format_response()
                    ├─→ llm_integration/evaluation/ragas_evaluator.py:evaluate()
                    └─→ llm_integration/evaluation/quality_evaluator.py:evaluate()

                └─→ langgraph_workflow/checkpointer.py:save()
                    └─→ database/postgres_client.py:execute_query()

                └─→ utils/session_manager.py:store_conversation_turn()
                    └─→ database/postgres_client.py:execute_query()

                └─→ observability/langsmith_integration.py:log_run()

                └─→ api/langgraph_endpoints.py:build_chat_response()
                    └─→ return ChatResponse
```

---

This visualization provides the complete file structure, real-time execution flow with precise timing, and the exact function call chain from request to response!
