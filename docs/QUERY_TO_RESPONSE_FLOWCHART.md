# COMPLETE QUERY-TO-RESPONSE FLOWCHART DIAGRAM

## 🔄 END-TO-END VISUAL FLOW WITH ALL TRANSFORMATIONS

```
╔═══════════════════════════════════════════════════════════════════════════════════╗
║                                  USER QUERY INPUT                                 ║
║  "What are sample-san's thoughts on technical debt?"                              ║
║  + profile_id: "sample-san" + user_role: "Engineer" + session_id: "sess_123"     ║
╚═══════════════════════════════════════════════════════════════════════════════════╝
                                         │
                                         │ HTTP POST /api/v1/langgraph/chat
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          ① API LAYER - REQUEST RECEPTION                        │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: api/main.py:process_chat()                                        │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  INPUT:  ChatRequest {                                                   │  │
│  │            query: str,                                                   │  │
│  │            profile_id: str,                                              │  │
│  │            user_role: str,                                               │  │
│  │            session_id: str                                               │  │
│  │          }                                                                │  │
│  │                                                                           │  │
│  │  OPERATIONS:                                                             │  │
│  │    • Validate request schema (Pydantic)                                  │  │
│  │    • Normalize profile_id (legacy format → db format)                    │  │
│  │    • Extract user_id from context                                        │  │
│  │                                                                           │  │
│  │  OUTPUT: Validated request object                                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       ② SESSION MANAGEMENT - GET/CREATE                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: utils/session_manager.py:get_or_create_session()                 │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  OPERATIONS:                                                             │  │
│  │    IF session_id provided:                                               │  │
│  │      → SELECT * FROM conversation_sessions WHERE id = session_id         │  │
│  │      → If found: return existing session                                 │  │
│  │    ELSE:                                                                 │  │
│  │      → INSERT INTO conversation_sessions (user_id, executive_id)         │  │
│  │      → Generate new session_id (UUID)                                    │  │
│  │                                                                           │  │
│  │  DATABASE: PostgreSQL                                                    │  │
│  │    Table: conversation_sessions                                          │  │
│  │    Query time: ~5ms                                                      │  │
│  │                                                                           │  │
│  │  OUTPUT: session_id (UUID)                                               │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    ③ LANGGRAPH INITIALIZATION - STATE SETUP                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: api/langgraph_endpoints.py:langgraph_chat()                      │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  OPERATIONS:                                                             │  │
│  │    • Create initial RAGState (TypedDict with defaults)                   │  │
│  │    • Restore conversation_history from checkpointer                      │  │
│  │      → SELECT channel_values FROM checkpoints                            │  │
│  │         WHERE checkpoint_ns = session_id                                 │  │
│  │         ORDER BY created_at DESC LIMIT 1                                 │  │
│  │                                                                           │  │
│  │  DATABASE: PostgreSQL                                                    │  │
│  │    Table: checkpoints                                                    │  │
│  │    Query time: ~10ms                                                     │  │
│  │                                                                           │  │
│  │  STATE CREATED:                                                          │  │
│  │    RAGState = {                                                          │  │
│  │      query: "What are sample-san's thoughts on technical debt?",         │  │
│  │      user_id: "user_456",                                                │  │
│  │      profile_id: "sample-san",                                           │  │
│  │      session_id: "sess_123",                                             │  │
│  │      user_role: "Engineer",                                              │  │
│  │      conversation_history: [                                             │  │
│  │        {role: "user", content: "...", timestamp: "..."},    # Previous   │  │
│  │        {role: "assistant", content: "...", timestamp: "..."}  # turns    │  │
│  │      ],                                                                  │  │
│  │      query_features: None,  # To be filled                              │  │
│  │      selected_path: None,   # To be filled                              │  │
│  │      # ... all other fields initialized to None                          │  │
│  │    }                                                                     │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║                    LANGGRAPH WORKFLOW EXECUTION BEGINS                          ║
║  File: langgraph_workflow/graph.py:create_rag_workflow()                       ║
╚═════════════════════════════════════════════════════════════════════════════════╝
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ④ NODE: ANALYZE_QUERY                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:analyze_query()                      │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  INPUT: state.query (string)                                             │  │
│  │                                                                           │  │
│  │  STEP 1: Entity Extraction                                               │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐ │  │
│  │  │ File: query_analysis/entity_extractor.py                           │ │  │
│  │  │                                                                     │ │  │
│  │  │ A. spaCy NER (English):                                            │ │  │
│  │  │    query → nlp(query) → doc.ents                                   │ │  │
│  │  │    Entities found:                                                 │ │  │
│  │  │      • "sample-san" → PERSON                                       │ │  │
│  │  │      • "technical debt" → CONCEPT (custom pattern)                 │ │  │
│  │  │                                                                     │ │  │
│  │  │ B. GLiNER (Multilingual):                                          │ │  │
│  │  │    query → gliner.predict_entities(query)                          │ │  │
│  │  │    Additional entities: (none in this case)                        │ │  │
│  │  │                                                                     │ │  │
│  │  │ entities = [                                                       │ │  │
│  │  │   {name: "sample-san", type: "PERSON", span: [13, 23]},           │ │  │
│  │  │   {name: "technical debt", type: "CONCEPT", span: [38, 52]}       │ │  │
│  │  │ ]                                                                  │ │  │
│  │  │                                                                     │ │  │
│  │  │ Time: ~60ms                                                        │ │  │
│  │  └────────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                           │  │
│  │  STEP 2: Complexity Classification                                       │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐ │  │
│  │  │ File: query_analysis/classifiers.py:classify_complexity()         │ │  │
│  │  │                                                                     │ │  │
│  │  │ Factors:                                                           │ │  │
│  │  │   • Entity count: 2 → "medium" contribution                        │ │  │
│  │  │   • Query length: 8 words → "simple" contribution                  │ │  │
│  │  │   • Multi-part query: No → "simple" contribution                   │ │  │
│  │  │   • Nested conditions: No                                          │ │  │
│  │  │                                                                     │ │  │
│  │  │ Decision: MEDIUM complexity                                        │ │  │
│  │  │ Confidence: 0.75                                                   │ │  │
│  │  │                                                                     │ │  │
│  │  │ Time: ~5ms                                                         │ │  │
│  │  └────────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                           │  │
│  │  STEP 3: Query Type Detection                                            │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐ │  │
│  │  │ File: query_analysis/classifiers.py:classify_query_type()         │ │  │
│  │  │                                                                     │ │  │
│  │  │ Pattern matching:                                                  │ │  │
│  │  │   • "thoughts on" → ANALYSIS keyword                               │ │  │
│  │  │   • No "should/recommend" → NOT decision                           │ │  │
│  │  │   • No "compare/vs" → NOT comparison                               │ │  │
│  │  │   • No "who/what/when" → NOT factual_lookup                        │ │  │
│  │  │                                                                     │ │  │
│  │  │ Decision: ANALYSIS query type                                      │ │  │
│  │  │ Confidence: 0.82                                                   │ │  │
│  │  │                                                                     │ │  │
│  │  │ Time: ~5ms                                                         │ │  │
│  │  └────────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                           │  │
│  │  OUTPUT: QueryFeatures {                                                 │  │
│  │    entities: [                                                           │  │
│  │      {name: "sample-san", type: "PERSON"},                               │  │
│  │      {name: "technical debt", type: "CONCEPT"}                           │  │
│  │    ],                                                                    │  │
│  │    complexity: "medium",                                                 │  │
│  │    query_type: "analysis",                                               │  │
│  │    confidence: 0.82,                                                     │  │
│  │    metadata: {                                                           │  │
│  │      word_count: 8,                                                      │  │
│  │      char_count: 53,                                                     │  │
│  │      has_question_word: true                                             │  │
│  │    }                                                                     │  │
│  │  }                                                                       │  │
│  │                                                                           │  │
│  │  STATE UPDATE: state.query_features = QueryFeatures                      │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: ~70ms                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ⑤ NODE: ROUTE_QUERY                                   │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:route_query()                        │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  INPUT: state.query_features                                             │  │
│  │                                                                           │  │
│  │  ROUTING LOGIC:                                                          │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐ │  │
│  │  │ File: query_analysis/router.py:QueryRouter.route()                │ │  │
│  │  │                                                                     │ │  │
│  │  │ Decision Tree:                                                     │ │  │
│  │  │                                                                     │ │  │
│  │  │  IF complexity == "simple" AND                                     │ │  │
│  │  │     entity_count == 0 AND                                          │ │  │
│  │  │     confidence > 0.85:                                             │ │  │
│  │  │       → FAST PATH                                                  │ │  │
│  │  │                                                                     │ │  │
│  │  │  ELIF complexity == "complex" OR                                   │ │  │
│  │  │       query_type == "multi_step" OR                                │ │  │
│  │  │       confidence < 0.6:                                            │ │  │
│  │  │       → AGENTIC PATH                                               │ │  │
│  │  │                                                                     │ │  │
│  │  │  ELSE:                                                             │ │  │
│  │  │       → STANDARD PATH ✓✓✓ (SELECTED)                              │ │  │
│  │  │                                                                     │ │  │
│  │  │ Evaluation for our query:                                          │ │  │
│  │  │   • complexity: "medium" → not simple, not complex                 │ │  │
│  │  │   • entity_count: 2 → has entities                                 │ │  │
│  │  │   • confidence: 0.82 → sufficient confidence                       │ │  │
│  │  │   • query_type: "analysis" → standard handling                     │ │  │
│  │  │                                                                     │ │  │
│  │  │ DECISION: STANDARD PATH                                            │ │  │
│  │  │ Confidence: 0.85                                                   │ │  │
│  │  │ Reasoning: "Medium complexity analysis query with entities"        │ │  │
│  │  └────────────────────────────────────────────────────────────────────┘ │  │
│  │                                                                           │  │
│  │  OUTPUT: RouteDecision {                                                 │  │
│  │    path: "standard",                                                     │  │
│  │    confidence: 0.85,                                                     │  │
│  │    reasoning: "Medium complexity analysis query with entities"           │  │
│  │  }                                                                       │  │
│  │                                                                           │  │
│  │  STATE UPDATE:                                                           │  │
│  │    state.selected_path = "standard"                                      │  │
│  │    state.routing_confidence = 0.85                                       │  │
│  │    state.routing_reasoning = "..."                                       │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: ~10ms                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║                         STANDARD PATH EXECUTION                                 ║
╚═════════════════════════════════════════════════════════════════════════════════╝
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                   ⑥ NODE: RETRIEVE_GRAPHRAG_STANDARD                            │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:retrieve_graphrag_standard()         │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Global/community-based search (for broad queries)              │  │
│  │                                                                           │  │
│  │  CONDITION CHECK:                                                        │  │
│  │    IF entity_count <= 1 OR query_type == "broad_overview":              │  │
│  │       → Execute GraphRAG global search                                   │  │
│  │    ELSE:                                                                 │  │
│  │       → SKIP (has specific entities) ✓✓✓                                 │  │
│  │                                                                           │  │
│  │  DECISION: SKIPPED                                                       │  │
│  │  Reason: Query has 2 specific entities                                   │  │
│  │                                                                           │  │
│  │  OUTPUT: state.graph_context = None                                      │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: ~5ms                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                  ⑦ NODE: RETRIEVE_PARALLEL_STANDARD                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:retrieve_parallel_standard()         │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Execute multiple retrieval strategies in parallel              │  │
│  │                                                                           │  │
│  │  PARALLEL EXECUTOR: ThreadPoolExecutor(max_workers=2)                    │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                     ┌───────────────────┴────────────────────┐
                     │                                        │
                     │ PARALLEL EXECUTION                     │
                     │                                        │
          ┌──────────▼──────────┐              ┌─────────────▼──────────┐
          │   WORKER 1 (FUTURE)  │              │   WORKER 2 (FUTURE)    │
          │                      │              │                        │
          │  retrieve_graph_     │              │  retrieve_memory       │
          │  enhanced()          │              │  ()                    │
          └──────────┬───────────┘              └─────────────┬──────────┘
                     │                                        │
                     ▼                                        ▼

┌─────────────────────────────────────────┐    ┌──────────────────────────────────┐
│  ⑦A. RETRIEVE_GRAPH_ENHANCED            │    │  ⑦B. RETRIEVE_MEMORY             │
│  ────────────────────────────────────── │    │  ──────────────────────────────  │
│  File: nodes.py:retrieve_graph_enhanced │    │  File: nodes.py:retrieve_memory  │
│                                         │    │                                  │
│  ╔═══════════════════════════════════╗ │    │  ╔════════════════════════════╗  │
│  ║  STEP 1: GRAPH CONTEXT DISCOVERY  ║ │    │  ║  STEP 1: DATABASE QUERY    ║  │
│  ╚═══════════════════════════════════╝ │    │  ╚════════════════════════════╝  │
│  ┌─────────────────────────────────┐   │    │  ┌──────────────────────────┐    │
│  │ File: graph_context/provider.py │   │    │  │ File: hybrid_retrieval/  │    │
│  │                                  │   │    │  │       memory_search.py   │    │
│  │ INPUT: entities from query       │   │    │  │                          │    │
│  │   ["sample-san", "technical debt"]  │    │  │ SQL QUERY:               │    │
│  │                                  │   │    │  │ SELECT *                 │    │
│  │ SUB-STEP 1A: Match Entities     │   │    │  │ FROM conversation_turns  │    │
│  │ ────────────────────────────     │   │    │  │ WHERE executive_id =     │    │
│  │ Neo4j Cypher:                   │   │    │  │   'sample-san'           │    │
│  │   MATCH (e:Entity)               │   │    │  │ AND created_at >         │    │
│  │   WHERE e.name IN                │   │    │  │   (NOW() - INTERVAL      │    │
│  │     ['sample-san',               │   │    │  │    '30 days')            │    │
│  │      'technical debt']           │   │    │  │ ORDER BY importance_score│    │
│  │   RETURN e.id, e.type            │   │    │  │ LIMIT 50                 │    │
│  │                                  │   │    │  │                          │    │
│  │ RESULT:                          │   │    │  │ Time: 45ms               │    │
│  │   [                              │   │    │  │                          │    │
│  │     {id: "ent_1", type: "PERSON"},  │    │  │ RESULT: 47 turns         │    │
│  │     {id: "ent_2", type: "CONCEPT"}  │    │  └──────────────────────────┘    │
│  │   ]                              │   │    │                                  │
│  │ Time: 35ms                       │   │    │  ╔════════════════════════════╗  │
│  │                                  │   │    │  ║  STEP 2: 5-SIGNAL SCORING  ║  │
│  │ SUB-STEP 1B: Traverse Graph     │   │    │  ╚════════════════════════════╝  │
│  │ ────────────────────────────     │   │    │  ┌──────────────────────────┐    │
│  │ Neo4j Cypher:                   │   │    │  │ For each of 47 turns:    │    │
│  │   MATCH (exec:Executive          │   │    │  │                          │    │
│  │     {id: 'sample-san'})          │   │    │  │ SIGNAL 1: Semantic (40%) │    │
│  │   -[r*1..2]-(related)            │   │    │  │ ──────────────────────── │    │
│  │   WHERE related.id IN            │   │    │  │ embedding_sim =          │    │
│  │     ['ent_1', 'ent_2']           │   │    │  │   cosine(query_emb,      │    │
│  │   RETURN                         │   │    │  │          turn.embedding) │    │
│  │     related.id,                  │   │    │  │ score_1 = 0.40 * sim     │    │
│  │     length(r) as distance        │   │    │  │                          │    │
│  │                                  │   │    │  │ SIGNAL 2: Temporal (25%) │    │
│  │ RESULT:                          │   │    │  │ ──────────────────────── │    │
│  │   [                              │   │    │  │ age_days = (NOW() -      │    │
│  │     {id: "doc_1", distance: 1},  │   │    │  │   turn.created_at).days  │    │
│  │     {id: "doc_2", distance: 2},  │   │    │  │ decay = exp(-age/30)     │    │
│  │     {id: "doc_3", distance: 1},  │   │    │  │ score_2 = 0.25 * decay   │    │
│  │     ... (47 docs total)          │   │    │  │                          │    │
│  │   ]                              │   │    │  │ SIGNAL 3: Importance (20%)│   │
│  │ Time: 55ms                       │   │    │  │ ──────────────────────── │    │
│  │                                  │   │    │  │ score_3 = 0.20 *         │    │
│  │ SUB-STEP 1C: Calculate Scores   │   │    │  │   turn.importance_score  │    │
│  │ ────────────────────────────     │   │    │  │                          │    │
│  │ For each doc:                    │   │    │  │ SIGNAL 4: Feedback Mult  │    │
│  │   graph_score =                  │   │    │  │ ──────────────────────── │    │
│  │     1 / (1 + distance)           │   │    │  │ multiplier = 1.0 +       │    │
│  │                                  │   │    │  │   (turn.feedback/10)     │    │
│  │ Example:                         │   │    │  │                          │    │
│  │   doc_1: 1/(1+1) = 0.50          │   │    │  │ SIGNAL 5: Context Mult   │    │
│  │   doc_2: 1/(1+2) = 0.33          │   │    │  │ ──────────────────────── │    │
│  │   doc_3: 1/(1+1) = 0.50          │   │    │  │ IF turn.user_role ==     │    │
│  │                                  │   │    │  │    current_user_role:     │    │
│  │ OUTPUT:                          │   │    │  │   multiplier = 1.2       │    │
│  │   GraphContext {                 │   │    │  │ ELSE: multiplier = 1.0   │    │
│  │     candidate_ids: [             │   │    │  │                          │    │
│  │       "doc_1", "doc_2", ...      │   │    │  │ FINAL SCORE:             │    │
│  │     ],  # 47 docs                │   │    │  │ ──────────────────────── │    │
│  │     graph_distances: {           │   │    │  │ base = score_1 +         │    │
│  │       "doc_1": 1,                │   │    │  │        score_2 +         │    │
│  │       "doc_2": 2, ...            │   │    │  │        score_3           │    │
│  │     },                           │   │    │  │ final = base *           │    │
│  │     graph_scores: {              │   │    │  │         signal_4 *       │    │
│  │       "doc_1": 0.50,             │   │    │  │         signal_5         │    │
│  │       "doc_2": 0.33, ...         │   │    │  │                          │    │
│  │     }                            │   │    │  │ Time: 90ms               │    │
│  │   }                              │   │    │  └──────────────────────────┘    │
│  │ Time: 10ms                       │   │    │                                  │
│  └─────────────────────────────────┘   │    │  ╔════════════════════════════╗  │
│                                         │    │  ║  STEP 3: SELECT TOP 5      ║  │
│  ╔═══════════════════════════════════╗ │    │  ╚════════════════════════════╝  │
│  ║  STEP 2: EMBEDDING GENERATION     ║ │    │  ┌──────────────────────────┐    │
│  ╚═══════════════════════════════════╝ │    │  │ ORDER BY memory_score    │    │
│  ┌─────────────────────────────────┐   │    │  │ DESC LIMIT 5             │    │
│  │ File: vector_search/embedding/  │   │    │  │                          │    │
│  │       embedding_service.py       │   │    │  │ SELECTED:                │    │
│  │                                  │   │    │  │  [                       │    │
│  │ INPUT: query string              │   │    │  │    Turn #42 (score: 0.89)│    │
│  │                                  │   │    │  │    Turn #31 (score: 0.84)│    │
│  │ CHECK L1 CACHE (In-memory):     │   │    │  │    Turn #18 (score: 0.78)│    │
│  │   hash = sha256(query)           │   │    │  │    Turn #12 (score: 0.71)│    │
│  │   cache.get(hash) → MISS         │   │    │  │    Turn #5  (score: 0.68)│    │
│  │                                  │   │    │  │  ]                       │    │
│  │ CHECK L2 CACHE (Redis):         │   │    │  │                          │    │
│  │   redis.get(f"emb:{hash}") →    │   │    │  │ Time: 5ms                │    │
│  │   MISS                           │   │    │  └──────────────────────────┘    │
│  │                                  │   │    │                                  │
│  │ GENERATE EMBEDDING:              │   │    │  OUTPUT: MemoryResults {         │
│  │   model.encode(query)            │   │    │    results: [                    │
│  │   ↓                              │   │    │      {                           │
│  │   sentence-transformers          │   │    │        source_id: "turn_42",     │
│  │   ↓                              │   │    │        content: "...",           │
│  │   Tokenize                       │   │    │        memory_score: 0.89,       │
│  │   ↓                              │   │    │        metadata: {...}           │
│  │   Forward pass (GPU)             │   │    │      },                          │
│  │   ↓                              │   │    │      ... (5 total)               │
│  │   Mean pooling                   │   │    │    ]                             │
│  │   ↓                              │   │    │  }                               │
│  │   vector[1024]                   │   │    │                                  │
│  │                                  │   │    │  Total time: 140ms               │
│  │ Time: 35ms                       │   │    └──────────────────────────────────┘
│  │                                  │   │
│  │ STORE IN CACHES:                │   │
│  │   L1: cache.put(hash, vector)    │   │
│  │   L2: redis.set(f"emb:{hash}",   │   │
│  │                 vector, TTL=3600) │   │
│  │ Time: 5ms                        │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ╔═══════════════════════════════════╗ │
│  ║  STEP 3: VECTOR SEARCH (pgvector) ║ │
│  ╚═══════════════════════════════════╝ │
│  ┌─────────────────────────────────┐   │
│  │ File: vector_search/            │   │
│  │       search_engine.py           │   │
│  │                                  │   │
│  │ SQL QUERY:                       │   │
│  │   SELECT                         │   │
│  │     e.source_id,                 │   │
│  │     e.source_type,               │   │
│  │     e.embedding,                 │   │
│  │     p.content,                   │   │
│  │     1 - (e.embedding <=>         │   │
│  │       $query_embedding::vector)  │   │
│  │       AS similarity              │   │
│  │   FROM embeddings e              │   │
│  │   JOIN policies p ON             │   │
│  │     e.source_id = p.id           │   │
│  │   WHERE                          │   │
│  │     e.source_type IN             │   │
│  │       ('policy', 'decision',     │   │
│  │        'communication')          │   │
│  │     AND e.source_id =            │   │
│  │       ANY($candidate_ids)        │   │
│  │   ORDER BY                       │   │
│  │     e.embedding <=>              │   │
│  │     $query_embedding             │   │
│  │   LIMIT 15                       │   │
│  │                                  │   │
│  │ Parameters:                      │   │
│  │   query_embedding: vector[1024]  │   │
│  │   candidate_ids: [47 doc IDs]   │   │
│  │                                  │   │
│  │ Time: 85ms                       │   │
│  │                                  │   │
│  │ RESULT: 15 documents             │   │
│  │   [                              │   │
│  │     {                            │   │
│  │       source_id: "doc_1",        │   │
│  │       source_type: "policy",     │   │
│  │       content: "...",            │   │
│  │       similarity: 0.87           │   │
│  │     },                           │   │
│  │     {                            │   │
│  │       source_id: "doc_5",        │   │
│  │       source_type: "decision",   │   │
│  │       content: "...",            │   │
│  │       similarity: 0.82           │   │
│  │     },                           │   │
│  │     ... (15 total)               │   │
│  │   ]                              │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ╔═══════════════════════════════════╗ │
│  ║  STEP 4: HYBRID SCORING           ║ │
│  ╚═══════════════════════════════════╝ │
│  ┌─────────────────────────────────┐   │
│  │ For each result:                 │   │
│  │                                  │   │
│  │ Example (doc_1):                 │   │
│  │   vector_score = 0.87            │   │
│  │   graph_score = 0.50             │   │
│  │                                  │   │
│  │   HYBRID FORMULA:                │   │
│  │   hybrid_score =                 │   │
│  │     0.6 × vector_score +         │   │
│  │     0.4 × graph_score            │   │
│  │                                  │   │
│  │   = 0.6 × 0.87 + 0.4 × 0.50      │   │
│  │   = 0.522 + 0.200                │   │
│  │   = 0.722                        │   │
│  │                                  │   │
│  │ PERSON NAME BOOST:               │   │
│  │   IF "sample-san" in query AND   │   │
│  │      "sample-san" in content:    │   │
│  │     hybrid_score *= 1.2          │   │
│  │                                  │   │
│  │ Example (doc_3 has name):        │   │
│  │   base_hybrid = 0.688            │   │
│  │   boosted = 0.688 × 1.2 = 0.826  │   │
│  │                                  │   │
│  │ Time: 10ms                       │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ╔═══════════════════════════════════╗ │
│  ║  STEP 5: RBAC FILTERING           ║ │
│  ╚═══════════════════════════════════╝ │
│  ┌─────────────────────────────────┐   │
│  │ user_role: "Engineer"            │   │
│  │                                  │   │
│  │ Filter results by permissions:   │   │
│  │   For each result:               │   │
│  │     IF result.allowed_roles      │   │
│  │        .includes(user_role):     │   │
│  │       KEEP                       │   │
│  │     ELSE:                        │   │
│  │       REMOVE                     │   │
│  │                                  │   │
│  │ Before: 15 results               │   │
│  │ After:  15 results (all allowed) │   │
│  │                                  │   │
│  │ Time: 5ms                        │   │
│  └─────────────────────────────────┘   │
│                                         │
│  OUTPUT: VectorSearchResults {          │
│    results: [                           │
│      {                                  │
│        source_id: "doc_3",              │
│        source_type: "policy",           │
│        content: "...",                  │
│        vector_score: 0.85,              │
│        graph_score: 0.50,               │
│        hybrid_score: 0.826,  # boosted  │
│        metadata: {...}                  │
│      },                                 │
│      ... (15 total, sorted by hybrid)   │
│    ]                                    │
│  }                                      │
│                                         │
│  Total time: 210ms                      │
└─────────────────────────────────────────┘

                     │                                        │
                     │ Both workers complete                  │
                     └───────────────────┬────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      ⑧ NODE: FUSE_RESULTS_STANDARD                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:fuse_results_standard()              │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  INPUT:                                                                   │  │
│  │    • VectorSearchResults (15 docs)                                       │  │
│  │    • MemoryResults (5 turns)                                             │  │
│  │    • query_type: "analysis"                                              │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 1: LOAD QUERY-TYPE WEIGHTS                                   ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ File: config/retrieval_weights.yaml                              │   │  │
│  │  │                                                                   │   │  │
│  │  │ query_type_weights:                                               │   │  │
│  │  │   analysis:  # ← Our query type                                  │   │  │
│  │  │     vector: 0.45                                                  │   │  │
│  │  │     graph:  0.30                                                  │   │  │
│  │  │     memory: 0.25                                                  │   │  │
│  │  │                                                                   │   │  │
│  │  │ LOADED: W_v = 0.45, W_g = 0.30, W_m = 0.25                       │   │  │
│  │  │ Time: 2ms                                                         │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 2: CONFIDENCE BLENDING                                       ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ File: hybrid_retrieval/fusion.py                                 │   │  │
│  │  │                                                                   │   │  │
│  │  │ classification_confidence: 0.82                                   │   │  │
│  │  │ threshold: 0.6                                                    │   │  │
│  │  │                                                                   │   │  │
│  │  │ IF confidence >= threshold:                                       │   │  │
│  │  │   USE type-specific weights ✓                                    │   │  │
│  │  │ ELSE:                                                             │   │  │
│  │  │   Blend with default weights                                      │   │  │
│  │  │                                                                   │   │  │
│  │  │ DECISION: Use analysis weights (confidence is 0.82 > 0.6)         │   │  │
│  │  │ Time: 1ms                                                         │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 3: SCORE FUSION                                              ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ Merge all results by source_id:                                   │   │  │
│  │  │                                                                   │   │  │
│  │  │ Example: doc_3                                                    │   │  │
│  │  │   v_score = 0.826 (from vector search)                           │   │  │
│  │  │   g_score = 0.50  (from graph context)                           │   │  │
│  │  │   m_score = 0.0   (not in memory results)                        │   │  │
│  │  │                                                                   │   │  │
│  │  │   FUSION FORMULA:                                                 │   │  │
│  │  │   fused_score = W_v × v + W_g × g + W_m × m                      │   │  │
│  │  │              = 0.45 × 0.826 + 0.30 × 0.50 + 0.25 × 0.0           │   │  │
│  │  │              = 0.372 + 0.150 + 0.0                               │   │  │
│  │  │              = 0.522                                              │   │  │
│  │  │                                                                   │   │  │
│  │  │ Example: turn_42                                                  │   │  │
│  │  │   v_score = 0.0   (not in vector results)                        │   │  │
│  │  │   g_score = 0.0   (memory doesn't use graph)                     │   │  │
│  │  │   m_score = 0.89  (from memory search)                           │   │  │
│  │  │                                                                   │   │  │
│  │  │   fused_score = 0.45 × 0.0 + 0.30 × 0.0 + 0.25 × 0.89           │   │  │
│  │  │              = 0.0 + 0.0 + 0.223                                 │   │  │
│  │  │              = 0.223                                              │   │  │
│  │  │                                                                   │   │  │
│  │  │ Process all 18 unique results (15 vector + 5 memory, some overlap)│  │  │
│  │  │ Time: 15ms                                                        │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 4: DEDUPLICATION                                             ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ Group by source_id, keep highest fused_score                      │   │  │
│  │  │                                                                   │   │  │
│  │  │ Example: doc_7 appears in both vector and memory                  │   │  │
│  │  │   Instance 1: fused_score = 0.418 (vector-heavy)                 │   │  │
│  │  │   Instance 2: fused_score = 0.391 (memory-heavy)                 │   │  │
│  │  │   → KEEP Instance 1 with score 0.418                             │   │  │
│  │  │                                                                   │   │  │
│  │  │ After dedup: 18 unique results                                    │   │  │
│  │  │ Time: 5ms                                                         │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 5: SORT BY FUSED SCORE                                       ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ ORDER BY fused_score DESC                                         │   │  │
│  │  │                                                                   │   │  │
│  │  │ Top 5:                                                            │   │  │
│  │  │   1. doc_3:   fused_score = 0.522                                │   │  │
│  │  │   2. doc_1:   fused_score = 0.497                                │   │  │
│  │  │   3. doc_11:  fused_score = 0.468                                │   │  │
│  │  │   4. doc_7:   fused_score = 0.418                                │   │  │
│  │  │   5. doc_14:  fused_score = 0.392                                │   │  │
│  │  │                                                                   │   │  │
│  │  │ Time: 3ms                                                         │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  OUTPUT: FusedResults {                                                  │  │
│  │    results: [                                                            │  │
│  │      {                                                                   │  │
│  │        source_id: "doc_3",                                               │  │
│  │        content: "...",                                                   │  │
│  │        vector_score: 0.826,                                              │  │
│  │        graph_score: 0.50,                                                │  │
│  │        memory_score: 0.0,                                                │  │
│  │        fused_score: 0.522,                                               │  │
│  │        source_breakdown: {v: 0.372, g: 0.150, m: 0.0}                    │  │
│  │      },                                                                  │  │
│  │      ... (18 total, sorted)                                              │  │
│  │    ]                                                                     │  │
│  │  }                                                                       │  │
│  │                                                                           │  │
│  │  STATE UPDATE: state.fused_results = FusedResults                        │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 26ms                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼

[Due to length constraints, I'll create this as a multi-file visualization]
