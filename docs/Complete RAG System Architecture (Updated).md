Complete RAG System Architecture (Updated)                                                                                                  
                                                                                                                                                System Identity

  This is an Executive Cognitive Twin - a sophisticated AI system that creates a digital representation of an executive capable of responding
  with authentic personality, reasoning patterns, and domain expertise.

  ---
  Architecture Summary

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                           API LAYER (FastAPI)                                │
  │  /api/v1/chat  /api/v1/langgraph/chat  /api/v1/langgraph/chat/stream       │
  └────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                    LANGGRAPH ORCHESTRATION ENGINE                            │
  │  ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐                │
  │  │  FAST PATH   │  │ STANDARD PATH  │  │  AGENTIC PATH    │                │
  │  │   < 2s       │  │    < 3s        │  │     < 5s         │                │
  │  │  4000 tokens │  │  8000 tokens   │  │  12000 tokens    │                │
  │  └──────────────┘  └────────────────┘  └──────────────────┘                │
  └────────────────────────────────┬────────────────────────────────────────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────┐
       │                           │                           │
       ▼                           ▼                           ▼
  ┌──────────────┐        ┌──────────────┐        ┌──────────────────┐
  │    VECTOR    │        │    GRAPH     │        │     MEMORY       │
  │    SEARCH    │        │   CONTEXT    │        │     SEARCH       │
  │  (pgvector)  │        │   (Neo4j)    │        │  (5-signal)      │
  └──────┬───────┘        └──────┬───────┘        └────────┬─────────┘
         │                       │                         │
         └───────────────────────┼─────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                       RESULT FUSION ENGINE                                   │
  │  Query-Type Adaptive Weighting: factual/decision/analysis/comparison/rel    │
  │  Adaptive Reranking: lightweight/medium/full (cross-encoder)                │
  └────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                    COGNITIVE TWIN (6 LAYERS)                                 │
  │  Layer 0: Conversational Router (greeting detection)                        │
  │  Layer 1: Cognitive Lens (domain affinity reranking)                        │
  │  Layer 2: Cognitive Frame (reasoning patterns injection)                    │
  │  Layer 3: Memory Integration (handled in retrieval)                         │
  │  Layer 4: Situation Analyzer (tone/urgency/context)                         │
  │  Layer 5: Relationship Adapter (user role adjustments)                      │
  └────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                  CONVERSATION ENGINE (5 STAGES)                              │
  │  Stage 1: Context Analyzer (theme/urgency/emotion/turn_type)                │
  │  Stage 2: Response Calibrator (attention weights + tone adjustment)         │
  │  Stage 3: Example Selector (Slack/YouTube communication samples)            │
  │  Stage 4: Precedent Selector (decision cases for decision queries)          │
  │  Stage 5: Prompt Assembler (10 modular sections within token budget)        │
  └────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                       LLM INTEGRATION                                        │
  │  Providers: Groq / OpenAI / Google Gemini / GLM                             │
  │  Path-specific: temp 0.3-0.7, max_tokens 800-2500, timeout 10-30s           │
  └────────────────────────────────┬────────────────────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │           POST-PROCESSING & PERSISTENCE                                      │
  │  Citation Extraction → RAGAS Evaluation → Session Storage → Checkpoint      │
  └─────────────────────────────────────────────────────────────────────────────┘

  ---
  Complete Data Transformation Pipeline
  ┌────────────────────┬────────────────────┬─────────────────────────────────────────┬───────────────────────────────────────┬─────────┐     
  │       Stage        │       Input        │             Transformation              │                Output                 │  Time   │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Query Analysis     │ Raw query          │ spaCy/GLiNER NER, complexity classifier │ QueryFeatures                         │ ~70ms   │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Routing            │ QueryFeatures      │ Decision tree logic                     │ RouteDecision (fast/standard/agentic) │ ~10ms   │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Graph Context      │ Entities           │ Neo4j traversal (1-2 hops)              │ candidate_ids + distances             │ ~100ms  │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Vector Search      │ Query + candidates │ pgvector cosine similarity              │ 15 docs with hybrid scores            │ ~125ms  │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Memory Search      │ Query + session    │ 5-signal scoring                        │ 5 memory results                      │ ~140ms  │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Fusion             │ All results        │ Query-type weights, dedup               │ 18 fused results                      │ ~26ms   │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Reranking          │ Fused results      │ Cross-encoder (medium strategy)         │ Reranked results                      │ ~188ms  │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Cognitive Lens     │ Results + profile  │ Domain affinity boost                   │ Enhanced results                      │ ~15ms   │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Cognitive Frame    │ Query              │ Pattern matching                        │ Reasoning prompts                     │ ~10ms   │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Situation Analysis │ Query + history    │ Tone/urgency detection                  │ Calibration hints                     │ ~12ms   │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Relationship Adapt │ User role          │ Role-based adjustments                  │ Style hints                           │ ~8ms    │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ ConversationEngine │ All context        │ 5-stage assembly                        │ system + user prompts                 │ ~273ms  │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ LLM Execution      │ Prompts            │ Groq/OpenAI API                         │ Generated response                    │ ~1200ms │     
  ├────────────────────┼────────────────────┼─────────────────────────────────────────┼───────────────────────────────────────┼─────────┤     
  │ Post-processing    │ Response           │ Citation extraction, RAGAS              │ Final ChatResponse                    │ ~580ms  │     
  └────────────────────┴────────────────────┴─────────────────────────────────────────┴───────────────────────────────────────┴─────────┘     
  ---
  Key Configuration Insights

  Query-Type Adaptive Weights (retrieval_weights.yaml)

  factual_lookup:   V: 80%  G: 15%  M:  5%   # Vector-heavy
  decision:         V: 35%  G: 25%  M: 40%   # Memory-heavy!
  comparison:       V: 40%  G: 35%  M: 25%   # Balanced
  analysis:         V: 45%  G: 30%  M: 25%   # Balanced
  relationship:     V: 30%  G: 65%  M:  5%   # Graph-heavy!

  Token Budget Allocation (Standard Path: 8000 tokens)

  Identity:           800 tokens
  Values:             600 tokens
  Speaking Style:     400 tokens
  Instructions:       400 tokens
  Calibration:        200 tokens
  Example:            600 tokens
  Precedent:          0-400 tokens (if decision query)
  Conversation:       ~200 tokens (previous turns)
  Retrieved Context:  ~4800 tokens (remaining)

  5-Signal Memory Scoring Formula

  base = (0.40 × semantic_similarity) +
         (0.25 × temporal_decay) +
         (0.20 × importance_score)

  memory_score = base × feedback_multiplier × user_context_multiplier

  temporal_decay = exp(-age_days / 30)

  ---
  Real-Time Execution Example

  Query: "What are sample-san's thoughts on technical debt?"
  ┌───────────────────────┬───────────────┬──────────────┐
  │         Step          │     Time      │  Cumulative  │
  ├───────────────────────┼───────────────┼──────────────┤
  │ API Reception         │ 5ms           │ 5ms          │
  ├───────────────────────┼───────────────┼──────────────┤
  │ Session Management    │ 5ms           │ 10ms         │
  ├───────────────────────┼───────────────┼──────────────┤
  │ LangGraph Init        │ 10ms          │ 20ms         │
  ├───────────────────────┼───────────────┼──────────────┤
  │ Query Analysis        │ 70ms          │ 90ms         │
  ├───────────────────────┼───────────────┼──────────────┤
  │ Route Query           │ 10ms          │ 100ms        │
  ├───────────────────────┼───────────────┼──────────────┤
  │ Parallel Retrieval    │ 210ms (max)   │ 310ms        │
  ├───────────────────────┼───────────────┼──────────────┤
  │ ├─ Graph Context      │ 100ms         │ -            │
  ├───────────────────────┼───────────────┼──────────────┤
  │ ├─ Vector Search      │ 125ms         │ -            │
  ├───────────────────────┼───────────────┼──────────────┤
  │ └─ Memory Search      │ 140ms         │ -            │
  ├───────────────────────┼───────────────┼──────────────┤
  │ Fusion                │ 26ms          │ 336ms        │
  ├───────────────────────┼───────────────┼──────────────┤
  │ Reranking             │ 188ms         │ 524ms        │
  ├───────────────────────┼───────────────┼──────────────┤
  │ Cognitive Enhancement │ 50ms          │ 574ms        │
  ├───────────────────────┼───────────────┼──────────────┤
  │ ConversationEngine    │ 273ms         │ 847ms        │
  ├───────────────────────┼───────────────┼──────────────┤
  │ LLM Execution         │ 1210ms        │ 2057ms       │
  ├───────────────────────┼───────────────┼──────────────┤
  │ Response Formatting   │ 15ms          │ 2072ms       │
  ├───────────────────────┼───────────────┼──────────────┤
  │ RAGAS Evaluation      │ 527ms (async) │ -            │
  ├───────────────────────┼───────────────┼──────────────┤
  │ State Persistence     │ 63ms          │ 2135ms       │
  ├───────────────────────┼───────────────┼──────────────┤
  │ TOTAL                 │ -             │ ~2.8 seconds │
  └───────────────────────┴───────────────┴──────────────┘
  Bottleneck: LLM Execution (42.7% of total time)

  ---
  Database Schema Summary

  PostgreSQL (pgvector):
  - embeddings - 1024-dim vectors with IVFFlat index
  - executive_profiles - Profile data (JSONB)
  - policies, decision_cases, communications
  - conversation_sessions, conversation_turns
  - checkpoints - LangGraph state persistence
  - quality_metrics

  Neo4j (Knowledge Graph):
  - Nodes: Executive, DecisionCase, Policy, Communication, Entity
  - Relationships: MADE_DECISION, HAS_POLICY, SENT_COMMUNICATION, RELATED_TO, MENTIONED_ENTITY

  ---
  This is a production-grade Executive Cognitive Twin system designed for authentic voice, quality-first retrieval, and complete 
  observability. The architecture prioritizes personality consistency and grounded responses over raw speed.

  Would you like me to dive deeper into any specific component? 
