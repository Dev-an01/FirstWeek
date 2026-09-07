 RAG System: Complete Architecture & Mechanics

  System Overview

  This is a production-grade, executive-persona RAG system that creates "Cognitive Twins" - AI representations that don't just speak like an executive, but think like them. The system combines:

  - Hybrid retrieval (vector + knowledge graph + episodic memory)
  - Multi-path routing (fast/standard/agentic based on query complexity)
  - ReAct reasoning for complex multi-step analysis
  - 6-layer cognitive twin for personality injection
  - 5-stage conversation engine for context-aware prompt assembly

  ---
  Core Data Flow

  User Query
      ↓
  [Layer 0] ConversationalRouter
      ├─ Greeting/Small-talk? → Personality response (skip RAG)
      └─ Informational? → Continue
           ↓
  [Query Analysis]
      ├─ Extract entities (GLiNER/spaCy)
      ├─ Classify type (factual/decision/opinion)
      ├─ Detect complexity (simple/medium/complex)
      └─ Route to path (fast/standard/agentic)
           ↓
  [Hybrid Retrieval]
      ├─ Graph Context Discovery (Neo4j)
      │   ├─ Entity → Graph Node matching
      │   ├─ 1-3 hop traversal
      │   └─ Candidate document IDs
      ├─ Constrained Vector Search (pgvector)
      │   └─ Search ONLY within graph candidates
      ├─ Memory Search (episodic memory)
      │   └─ 5-signal scoring (semantic + temporal + importance)
      └─ Result Fusion (60% vector + 30% graph + 10% memory)
           ↓
  [Adaptive Reranking]
      ├─ Lightweight (40% queries): Score normalization only
      ├─ Medium (35%): + Cross-encoder on top 10
      └─ Full (25%): Complete 5-stage pipeline
           ↓
  [Cognitive Twin Layers]
      ├─ Layer 1: CognitiveLens (rerank by domain affinity)
      ├─ Layer 2: CognitiveFrame (inject thinking patterns)
      ├─ Layer 3: SituationAnalyzer (detect urgency/emotion)
      ├─ Layer 4: RelationshipAdapter (adjust for who's asking)
      └─ Layer 5: InferenceEngine (form opinions without data)
           ↓
  [Prompt Assembly] (5-Stage Pipeline)
      ├─ ReasoningSection (cognitive script - ALWAYS FIRST)
      ├─ IdentitySection (personality injection)
      ├─ CalibrationSection (tone/length guidance)
      ├─ ValuesSection (decision philosophy)
      ├─ PrecedentSection (past decision cases)
      ├─ ExampleSection (few-shot communication style)
      └─ InstructionsSection (anti-AI rules - ALWAYS LAST)
           ↓
  [LLM Generation]
      ├─ Multi-provider (OpenAI/Groq/Gemini/GLM)
      ├─ Streaming support
      └─ Citation validation
           ↓
  [Response Formatting]
      ├─ Citation extraction & validation
      ├─ Word count enforcement
      └─ Quality evaluation (RAGAS sampling)
           ↓
  Executive-Authentic Response

  ---
  Key Architectural Components

  1. LangGraph Workflow Orchestration

  The system uses LangGraph as a state machine with conditional routing:
  ┌────────────────┬────────────────┬────────────────────────────────┬──────────────────────┐
  │      Path      │ Target Latency │            Use Case            │        ReAct         │
  ├────────────────┼────────────────┼────────────────────────────────┼──────────────────────┤
  │ Fast           │ <1.5s          │ "What is...", "Who is..."      │ No                   │
  ├────────────────┼────────────────┼────────────────────────────────┼──────────────────────┤
  │ Standard       │ <2.5s          │ "Should we...", "Recommend..." │ No                   │
  ├────────────────┼────────────────┼────────────────────────────────┼──────────────────────┤
  │ Agentic        │ <5s            │ "Compare...", "Analyze..."     │ Yes (4-6 iterations) │
  ├────────────────┼────────────────┼────────────────────────────────┼──────────────────────┤
  │ Conversational │ <0.5s          │ "Hi", "Thanks"                 │ No (skip retrieval)  │
  └────────────────┴────────────────┴────────────────────────────────┴──────────────────────┘
  2. Hybrid Retrieval System

  Three complementary sources with weighted fusion:

  Composite Score = 0.60×Vector + 0.30×Graph + 0.10×Memory
  Multi-source boost: +10-15% for docs found in 2+ sources

  Graph-Enhanced Search Formula:
  Graph Score = 1.0 / distance (distance 1=1.0, distance 2=0.5)
  Hybrid Score = 0.60×VectorSimilarity + 0.40×GraphScore

  3. Cognitive Twin (6 Layers)
  ┌───────┬──────────────────────┬─────────────────────────────────────────┐
  │ Layer │      Component       │                 Purpose                 │
  ├───────┼──────────────────────┼─────────────────────────────────────────┤
  │ 0     │ ConversationalRouter │ Detect small-talk, skip RAG             │
  ├───────┼──────────────────────┼─────────────────────────────────────────┤
  │ 1     │ CognitiveLens        │ Rerank docs by domain expertise         │
  ├───────┼──────────────────────┼─────────────────────────────────────────┤
  │ 2     │ CognitiveFrame       │ Inject thinking patterns & precedents   │
  ├───────┼──────────────────────┼─────────────────────────────────────────┤
  │ 3     │ SituationAnalyzer    │ Detect urgency, emotion, implicit needs │
  ├───────┼──────────────────────┼─────────────────────────────────────────┤
  │ 4     │ RelationshipAdapter  │ Adjust tone by who's asking             │
  ├───────┼──────────────────────┼─────────────────────────────────────────┤
  │ 5     │ InferenceEngine      │ Form opinions without retrieval data    │
  └───────┴──────────────────────┴─────────────────────────────────────────┘
  4. Executive Profile Structure

  Profiles contain 15+ components:
  - Identity: Name, title, background, leadership team
  - Thinking Patterns: Framework examples, typical questions, decision approach
  - Communication Style: Formality/directness/warmth scores, soft assertions
  - Core Values: 5 prioritized values with trade-off scores
  - Decision Cases: 10+ real precedents with outcomes (SUCCESS/FAILURE)
  - Red Flags: Never approve conditions, escalation triggers
  - Inference Framework: How to reason through unknowns
  - Voiceprint: Signature openers, sign-offs, lexicon, emoji usage

  5. Prompt Assembly (Token-Budgeted Sections)
  ┌──────────────┬─────────┬───────────────────────────────────────────────────────────────────────────┐
  │   Section    │ Budget  │                                  Purpose                                  │
  ├──────────────┼─────────┼───────────────────────────────────────────────────────────────────────────┤
  │ Reasoning    │ 80-100  │ Cognitive script (data check → red flags → delegation → values → express) │
  ├──────────────┼─────────┼───────────────────────────────────────────────────────────────────────────┤
  │ Identity     │ 180-200 │ Full personality injection with "Three Pillars"                           │
  ├──────────────┼─────────┼───────────────────────────────────────────────────────────────────────────┤
  │ Calibration  │ 50-80   │ Tone, opener, signoff, length guidance                                    │
  ├──────────────┼─────────┼───────────────────────────────────────────────────────────────────────────┤
  │ Values       │ 50-70   │ Decision philosophy (standard/agentic only)                               │
  ├──────────────┼─────────┼───────────────────────────────────────────────────────────────────────────┤
  │ Precedent    │ 60-80   │ Past decision case (if relevant)                                          │
  ├──────────────┼─────────┼───────────────────────────────────────────────────────────────────────────┤
  │ Example      │ 100-150 │ Communication style demonstration                                         │
  ├──────────────┼─────────┼───────────────────────────────────────────────────────────────────────────┤
  │ Instructions │ 60-100  │ Anti-AI rules (35+ forbidden patterns)                                    │
  └──────────────┴─────────┴───────────────────────────────────────────────────────────────────────────┘
  Key Innovation - Instruction Sandwich:
  - Reasoning section FIRST (forces System 2 thinking)
  - Instructions section LAST (leverages recency bias)

  ---
  Entity Extraction & Graph Context

  3-Tier Extraction:
  1. Pattern Matching (POLICY-XX-###, DC_XXXX_###) - 100% precision
  2. GLiNER (multilingual semantic NER) - 95%+ accuracy
  3. spaCy (syntactic fallback) - 80% accuracy

  Singleton Pattern for GLiNER prevents OOM on GPUs <8GB.

  Graph Traversal:
  MATCH (anchor)-[*1..3]-(doc)
  WHERE (doc:Decision OR doc:Policy)
    AND doc.confidentiality IN $scopes
  RETURN doc.id, distance

  ---
  LLM Integration Architecture

  Multi-Provider Factory:
  - OpenAI, Groq, Gemini, GLM, OpenRouter
  - Path-specific model selection
  - LangSmith tracing integration

  Three Prompt Builders:
  1. Standard: Basic assembly with citation instructions
  2. DualStream: Parallel voiceprint + facts + persona streams
  3. TwoStage: MMR compression (77% token reduction)

  AgenticPathHandler with ReAct:
  - Thought → Action → Observe loop
  - Tools: Search, Analyze, Relationship, Finalize
  - Confidence threshold: 0.85 to finalize
  - Max iterations: 6

  ---
  Configuration Hierarchy
  ┌─────────────────┬───────────────────────────────────────────────────────┐
  │     Source      │                        Purpose                        │
  ├─────────────────┼───────────────────────────────────────────────────────┤
  │ llm_config.yaml │ Provider settings, model selection per path           │
  ├─────────────────┼───────────────────────────────────────────────────────┤
  │ rules.py        │ Single source of truth for word limits, anti-AI rules │
  ├─────────────────┼───────────────────────────────────────────────────────┤
  │ config.py       │ API settings, conversation engine flags               │
  ├─────────────────┼───────────────────────────────────────────────────────┤
  │ Profile JSON    │ Executive personality, values, precedents             │
  ├─────────────────┼───────────────────────────────────────────────────────┤
  │ Voiceprint JSON │ Communication style markers                           │
  └─────────────────┴───────────────────────────────────────────────────────┘
  Word Limits (from rules.py):
  - Fast: target 15, max 40 words
  - Standard: target 35, max 80 words
  - Agentic: target 60, max 150 words

  ---
  Database Architecture
  ┌───────────────────────┬──────────────────────────────────────────────────────────────────┐
  │       Database        │                             Purpose                              │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────┤
  │ PostgreSQL + pgvector │ Profiles, documents, embeddings, sessions, episodic memory       │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────┤
  │ Neo4j                 │ Knowledge graph (executives, decisions, policies, relationships) │
  ├───────────────────────┼──────────────────────────────────────────────────────────────────┤
  │ Redis                 │ L2 cache (query results, embeddings, system prompts)             │
  └───────────────────────┴──────────────────────────────────────────────────────────────────┘
  ---
  Key Design Patterns
  ┌───────────────┬────────────────────────────────────────────────┐
  │    Pattern    │                 Implementation                 │
  ├───────────────┼────────────────────────────────────────────────┤
  │ Singleton     │ ProfileManager, EntityExtractor (prevents OOM) │
  ├───────────────┼────────────────────────────────────────────────┤
  │ Factory       │ LLMClientFactory (multi-provider)              │
  ├───────────────┼────────────────────────────────────────────────┤
  │ Strategy      │ Path handlers (fast/standard/agentic)          │
  ├───────────────┼────────────────────────────────────────────────┤
  │ Pipeline      │ 5-stage conversation engine                    │
  ├───────────────┼────────────────────────────────────────────────┤
  │ State Machine │ LangGraph workflow with conditional edges      │
  ├───────────────┼────────────────────────────────────────────────┤
  │ Cache-Aside   │ 2-tier caching (L1 memory + L2 Redis)          │
  └───────────────┴────────────────────────────────────────────────┘
  ---
  Critical Insights

  1. "Database is the Brain" - All cognitive data comes from PostgreSQL profiles, not hardcoded templates
  2. Graph CONSTRAINS Vector Search - Graph traversal narrows search space BEFORE similarity calculations (10-100x faster)
  3. Soft Targets, Not Hard Limits - Word limits are targets ("AIM FOR ~35") not ceilings, allowing natural expression
  4. Recency Bias Exploitation - Critical instructions placed LAST in prompt (LLMs pay ~2x attention to final tokens)
  5. Never Say "I Don't Know" for Opinions - InferenceEngine forms opinions from values/thinking patterns when no retrieval data exists       
  6. Language Purity Enforcement - Pure English OR pure Japanese, no code-switching (except tech terms)
  7. Decision Precedent Citation - LLM must reference real past decisions by case ID (DC_sample_001) with outcomes
  8. Adaptive Reranking Distribution - Enforces 40/35/25 split across lightweight/medium/full to balance quality vs cost

  This system represents a sophisticated approach to creating AI personas that maintain consistency across thousands of interactions while grounding responses in real executive decision-making patterns and organizational knowledge.