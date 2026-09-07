 Complete RAG System Architecture - Deep Understanding

  Executive Summary

  This is a production-grade enterprise RAG system designed to create AI-powered "Cognitive Twins" of executives. It goes far beyond basic retrieval-augmented generation to capture not just what an executive would say, but how they think, decide, and communicate.

  ---
  System Architecture Overview

  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                              CLIENT LAYER                                          │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │  Frontend (React/Vite)  │  Avatar Interface  │  Recall Service (Meeting Bot)      │
  └──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                           API GATEWAY LAYER                                        │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │  Auth Service (JWT)  │  Chat Service (WebSocket)  │  RAG API (FastAPI)            │
  │                      │                             │  - /api/v1/chat              │
  │                      │                             │  - /api/v1/chat/stream       │
  │                      │                             │  - /api/v1/langgraph/*       │
  └──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                         COGNITIVE TWIN LAYER (6 Layers)                            │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ L0: ConversationalRouter │ L1: CognitiveLens │ L2: CognitiveFrame                 │
  │ (Greetings bypass RAG)   │ (Domain affinity) │ (Mental reasoning)                 │
  │                                                                                    │
  │ L3: Voice Expression     │ L4: SituationAnalyzer │ L5: RelationshipAdapter        │
  │ (Voiceprint patterns)    │ (Urgency/emotion)     │ (CEO→CFO vs CEO→Team)          │
  └──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                       CONVERSATION ENGINE (5-Stage Pipeline)                       │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ Stage 1: Context Analyzer  → Classify theme, urgency, emotion, query type         │
  │ Stage 2: Response Calibrator → Adjust tone/style based on context                 │
  │ Stage 3: Example Selector  → Match semantic examples from profile                 │
  │ Stage 4: Precedent Selector → Find relevant past decisions                        │
  │ Stage 5: Prompt Assembler  → Build system + user prompts with token budget       │
  │                                                                                    │
  │ Sections: [Reasoning] → [Identity] → [Context] → [Example] → [Calibration]       │
  │           → [Values] → [Precedent] → [Instructions]                               │
  └──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                          QUERY ROUTING (3 Paths)                                   │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ FAST (0.8-1.5s)          │ STANDARD (1.5-2.5s)     │ AGENTIC (3-5s)               │
  │ - Simple factual queries │ - Decision queries       │ - Complex analysis          │
  │ - Top 5 vector results   │ - Top 10 + graph + memory│ - Top 15 + ReAct loop       │
  │ - 350 token budget       │ - 500 token budget       │ - 650 token budget          │
  │ - Word limit: 40 words   │ - Word limit: 80 words   │ - Word limit: 150 words     │
  └──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                         HYBRID RETRIEVAL SYSTEM                                    │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │                                                                                    │
  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                   │
  │  │  Vector Search  │  │  Graph Context  │  │  Memory Search  │                   │
  │  │  (pgvector)     │  │  (Neo4j + NER)  │  │  (Episodic)     │                   │
  │  │  Weight: 60%    │  │  Weight: 30%    │  │  Weight: 10%    │                   │
  │  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘                   │
  │           │                    │                    │                             │
  │           └────────────────────┼────────────────────┘                             │
  │                                ▼                                                  │
  │                     ┌─────────────────────┐                                       │
  │                     │    Result Fusion    │ ← Multi-source boost                  │
  │                     │   (Deduplication)   │                                       │
  │                     └──────────┬──────────┘                                       │
  │                                ▼                                                  │
  │                     ┌─────────────────────┐                                       │
  │                     │ Adaptive Reranking  │                                       │
  │                     │ (Cross-encoder)     │                                       │
  │                     └─────────────────────┘                                       │
  └──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                         LLM INTEGRATION LAYER                                      │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ LLM Orchestrator → Factory → Multi-Provider Support:                              │
  │   - OpenAI (GPT-4o, GPT-4o-mini)                                                  │
  │   - Groq (openai/gpt-oss-120b)                                                    │
  │   - Google Gemini (gemini-2.0-flash-exp)                                          │
  │   - Zhipu AI (GLM-4)                                                              │
  │   - OpenRouter (multi-provider gateway)                                           │
  │                                                                                    │
  │ Prompt Builders:                                                                   │
  │   - TwoStagePromptBuilder (77% token reduction via compression)                   │
  │   - DualStreamPromptBuilder (voiceprint + facts + persona streams)                │
  │   - Basic PromptBuilder (no compression, direct)                                  │
  └──────────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼
  ┌──────────────────────────────────────────────────────────────────────────────────┐
  │                         LANGGRAPH WORKFLOW                                         │
  ├──────────────────────────────────────────────────────────────────────────────────┤
  │ StateGraph Orchestration with Conditional Edges:                                  │
  │                                                                                    │
  │ analyze_query → route_query ─┬─→ FAST: retrieve → generate                        │
  │                              ├─→ STANDARD: retrieve_parallel → fuse → rerank →    │
  │                              │             → cognitive_layers → generate          │
  │                              └─→ AGENTIC: retrieve → fuse → rerank →              │
  │                                          → ReAct Loop (think→act→observe)         │
  │                                          → finalize                               │
  │                                                                                    │
  │ ReAct Tools: SEARCH, ANALYZE, RELATIONSHIP, PRECEDENT, PATTERN, FINALIZE         │
  │ Max steps: 6 | Min steps: 4 | Confidence threshold: 0.85                          │
  └──────────────────────────────────────────────────────────────────────────────────┘

  ---
  Data Storage Architecture
  ┌─────────────────────┬─────────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────┐
  │      Database       │             Purpose             │                              Key Tables/Collections                              │
  ├─────────────────────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
  │ PostgreSQL          │ Vector embeddings + structured  │ documents, embeddings, executive_profiles, decision_cases, sessions              │
  │ (pgvector)          │ data                            │                                                                                  │
  ├─────────────────────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
  │ Neo4j               │ Knowledge graph relationships   │ Executive, Decision, Policy, Company nodes with relationships like               │
  │                     │                                 │ MADE_DECISION, WORKED_ON                                                         │
  ├─────────────────────┼─────────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
  │ Redis               │ L2 cache layer                  │ Semantic query cache, embedding cache, system prompt cache                       │
  └─────────────────────┴─────────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────┘
  ---
  Key Data Flows

  1. Chat Request Flow

  User Query: "Should we enter the Singapore market?"
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 1. CONVERSATIONAL ROUTER                                         │
  │    - Is greeting? → Return casual response from voiceprint       │
  │    - Is business query? → Continue to retrieval                  │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 2. QUERY ANALYSIS                                                │
  │    - Type: DECISION                                              │
  │    - Complexity: MEDIUM                                          │
  │    - Entities: ["Singapore"]                                     │
  │    - Route to: STANDARD path                                     │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 3. PARALLEL RETRIEVAL                                            │
  │    ├─→ Vector Search: 10 docs matching "Singapore market"       │
  │    ├─→ Graph Context: Entities → Neo4j → Related decisions      │
  │    └─→ Memory Search: Similar past queries                       │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 4. RESULT FUSION (60% vector + 30% graph + 10% memory)           │
  │    - Deduplicate by document ID                                  │
  │    - Multi-source boost: +10-15% for docs in multiple sources   │
  │    - Calculate composite scores                                  │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 5. ADAPTIVE RERANKING                                            │
  │    - Quality Assessment: HIGH/MEDIUM/LOW                         │
  │    - Strategy: Lightweight/Medium/Full cross-encoder             │
  │    - 40/35/25% target distribution                               │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 6. COGNITIVE TWIN LAYERS                                         │
  │    - CognitiveLens: CFO sees finance docs first                  │
  │    - CognitiveFrame: Apply sample's thinking framework           │
  │    - SituationAnalyzer: Detect urgency, emotion                  │
  │    - RelationshipAdapter: Adjust for audience                    │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 7. CONVERSATION ENGINE                                           │
  │    - Build REASONING section (System 2 thinking)                 │
  │    - Build IDENTITY section (full personality)                   │
  │    - Build EXAMPLE section (few-shot from profile)               │
  │    - Build CALIBRATION section (tone/length guidance)            │
  │    - Build INSTRUCTIONS section (anti-AI rules)                  │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ 8. LLM GENERATION                                                │
  │    System prompt: "You are sample_profile, CEO..."               │
  │    + Voice DNA + Values + Precedents + Instructions              │
  │    User prompt: Query + Context + Knowledge boundaries           │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  Response: "I think we should wait. The core business needs our
            full attention right now. Once that's solid, we can
            explore Singapore. Let's nail Japan first."

  2. ReAct Agentic Flow (Complex Queries)

  Complex Query: "Compare sample's market expansion decisions with industry patterns"
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STEP 1: THINK                                                    │
  │ "Need to find sample's past market expansion decisions first"   │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STEP 1: ACT → SEARCH                                             │
  │ Query: "sample market expansion decisions"                       │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STEP 1: OBSERVE                                                  │
  │ Found: DC_sample_002 (talent → agency pivot)                     │
  │        DC_sample_003 (focus on core, stop expansion)             │
  │ Confidence: 0.35                                                 │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STEP 2: THINK                                                    │
  │ "Now need to find industry patterns for comparison"             │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STEP 2: ACT → PRECEDENT                                          │
  │ Query: "startup market expansion patterns"                       │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STEP 2: OBSERVE                                                  │
  │ Found: 5 precedent cases with similarity scores                  │
  │ Confidence: 0.55                                                 │
  └─────────────────────────────────────────────────────────────────┘
       │
       ▼
  ... continues for 4-6 steps until confidence ≥ 0.85 ...
       │
       ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ FINALIZE: Synthesize all observations                            │
  │ - Apply ConversationEngine persona                               │
  │ - Generate comprehensive response with citations                 │
  └─────────────────────────────────────────────────────────────────┘

  ---
  Executive Profile Architecture

  The profile system captures executives as multi-dimensional personas:

  Profile Components (sample_profile.json)
  ┌─────────────────────┬─────────────────────────────┬───────────────────────────────────────────────────────┐
  │      Component      │           Purpose           │                      Key Fields                       │
  ├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Identity            │ Basic executive info        │ name, title, company, background, education           │
  ├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Thinking Patterns   │ Mental model                │ typical_questions, problem_approach, framework_usage  │
  ├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Communication Style │ Voice calibration           │ formality (6/10), directness (8/10), warmth (7/10)    │
  ├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Core Values         │ Priority-ordered values     │ Transparency, Speed, Delegation, Growth, Data-driven  │
  ├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Decision Making     │ Philosophy + risk tolerance │ value_trade_offs (15 quantified biases)               │
  ├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Decision Cases      │ 10 real precedents          │ situation, decision, outcome, lessons, confidence     │
  ├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Red Flags           │ Hard stops                  │ never_approve, always_do, escalation_triggers         │
  ├─────────────────────┼─────────────────────────────┼───────────────────────────────────────────────────────┤
  │ Inference Framework │ How to handle unknowns      │ Apply typical questions → Check values → Form opinion │
  └─────────────────────┴─────────────────────────────┴───────────────────────────────────────────────────────┘
  Voiceprint Components (sample_profile_voiceprint.json)
  ┌───────────────────┬───────────────────┬────────────────────────────────────────────────────────┐
  │     Component     │      Purpose      │                        Example                         │
  ├───────────────────┼───────────────────┼────────────────────────────────────────────────────────┤
  │ Signature Opener  │ How they start    │ "なるほど、それについては..." (context-first)          │
  ├───────────────────┼───────────────────┼────────────────────────────────────────────────────────┤
  │ Decision Cadence  │ Soft assertions   │ "〜と思います" (I think...) + reasoning + openness     │
  ├───────────────────┼───────────────────┼────────────────────────────────────────────────────────┤
  │ Risk Language     │ Crisis mode       │ "正直に言うと、少し心配しています"                     │
  ├───────────────────┼───────────────────┼────────────────────────────────────────────────────────┤
  │ Numbers Cadence   │ Data storytelling │ "売上は〜から〜に成長した（X%増）"                     │
  ├───────────────────┼───────────────────┼────────────────────────────────────────────────────────┤
  │ Disagreement      │ Pushback style    │ "僕の意見としては..." (respectful but firm)            │
  ├───────────────────┼───────────────────┼────────────────────────────────────────────────────────┤
  │ Style Markers     │ Voice fingerprint │ formality: 6, directness: 8, warmth: 7, emoji: minimal │
  ├───────────────────┼───────────────────┼────────────────────────────────────────────────────────┤
  │ Lexicon           │ Unique phrases    │ 30+ business philosophy expressions                    │
  ├───────────────────┼───────────────────┼────────────────────────────────────────────────────────┤
  │ Speaking Patterns │ Audio mode        │ Verbal fillers, connectors, enthusiasm markers         │
  └───────────────────┴───────────────────┴────────────────────────────────────────────────────────┘
  ---
  Anti-AI Guardrails (Critical for Authenticity)

  The system has extensive rules to prevent robotic AI output:

  Centralized Rules (rules.py)

  # Word limits by path (based on real sample data: 2-45 words)
  FAST: target=15, soft_max=25, hard_max=40
  STANDARD: target=35, soft_max=50, hard_max=80
  AGENTIC: target=60, soft_max=100, hard_max=150

  # Forbidden phrases (reveal AI nature)
  "I'd be happy to", "Let me help you", "As an AI",
  "Here's my perspective", "Let me share", "Based on my analysis"

  # Forbidden patterns
  NO bullet points, NO numbered lists (1. 2. 3.),
  NO markdown headers, NO comma-chains ("do A, do B, do C, and do D")

  # Required behaviors
  Use short sentences with periods, use contractions,
  talk like texting a colleague, warm but brief

  Knowledge Boundaries

  FACTUAL QUESTIONS (times, meetings, numbers):
    If context does NOT contain answer → SAY SO
    "I don't have that information" or "Let me check"
    NEVER make up facts

  OPINION QUESTIONS (what do you think, should we):
    You CAN give opinions based on values/thinking patterns
    Use soft assertions: "I think...", "In my view..."
    But don't invent facts to support opinions

  ---
  Technology Stack
  ┌───────────────────┬───────────────────────────────────────────────┬─────────────────────────┐
  │       Layer       │                  Technology                   │         Purpose         │
  ├───────────────────┼───────────────────────────────────────────────┼─────────────────────────┤
  │ Backend Framework │ FastAPI + Uvicorn                             │ Async web framework     │
  ├───────────────────┼───────────────────────────────────────────────┼─────────────────────────┤
  │ Databases         │ PostgreSQL 16 (pgvector), Neo4j 5.15, Redis 7 │ Vector, graph, cache    │
  ├───────────────────┼───────────────────────────────────────────────┼─────────────────────────┤
  │ Embeddings        │ BAAI/bge-m3 (1024 dim)                        │ Multilingual embeddings │
  ├───────────────────┼───────────────────────────────────────────────┼─────────────────────────┤
  │ NER               │ GLiNER + spaCy                                │ Entity extraction       │
  ├───────────────────┼───────────────────────────────────────────────┼─────────────────────────┤
  │ LLM Providers     │ OpenAI, Groq, Gemini, GLM                     │ Multi-provider support  │
  ├───────────────────┼───────────────────────────────────────────────┼─────────────────────────┤
  │ Orchestration     │ LangGraph + LangSmith                         │ Workflow + tracing      │
  ├───────────────────┼───────────────────────────────────────────────┼─────────────────────────┤
  │ Audio             │ Kokoro TTS + Faster Whisper STT               │ Voice I/O               │
  ├───────────────────┼───────────────────────────────────────────────┼─────────────────────────┤
  │ Observability     │ OpenTelemetry + Prometheus                    │ Metrics + tracing       │
  └───────────────────┴───────────────────────────────────────────────┴─────────────────────────┘
  ---
  Docker Deployment

  10 Services:
  1. frontend - React/Vite UI
  2. auth-service - JWT authentication
  3. chat-service - WebSocket chat management
  4. recall-service - Meeting bot integration
  5. avatar-interface - Avatar display
  6. avatar-user-db - User database (PostgreSQL)
  7. rag-postgres - RAG vector database (pgvector)
  8. neo4j - Knowledge graph
  9. redis - L2 cache
  10. rag-api - Main RAG API (GPU-enabled)

  ---
  Key Differentiators

  1. Cognitive Twin, Not Chatbot: Captures how executives think, not just what they say
  2. 6-Layer Cognitive Architecture: Progressive reasoning through specialized layers
  3. Real Precedent System: References actual past decisions with case IDs
  4. Anti-AI Obsession: Extensive rules to prevent breaking character
  5. Hybrid Retrieval: 60/30/10 weighted combination of vector + graph + memory
  6. ReAct Agentic Loop: Multi-step reasoning with 6 specialized tools
  7. Profile-Driven Prompts: Every response shaped by executive's values and patterns
  8. Adaptive Processing: 3 paths (fast/standard/agentic) based on query complexity

  This is a sophisticated, production-ready system designed to create authentic digital representations of executives that maintain consistency, personality, and decision-making patterns across all interactions.
