  🔬 RAG SYSTEM - COMPLETE RESPONSE GENERATION DEEP DIVE

  EXECUTIVE SUMMARY

  The response generation follows a 9-phase pipeline from query input to final response:

  Query → Routing → Retrieval → Fusion → Reranking → Cognitive Enhancement → Prompt Assembly → LLM Generation → Response Formatting

  ---
  1. ENTRY POINT: /api/v1/chat (main.py:879-1114)

  POST /api/v1/chat
      ↓
  [1] Profile ID Normalization (lines 917-938)
      "sample_profile" → "sample_profile"
      ↓
  [2] Query Routing (lines 941-951)
      QueryRouter.route() → "fast" | "standard" | "agentic"
      ↓
  [3] Vector Search (lines 953-961)
      VectorSearchEngine.search() → top_k documents
      ↓
  [4] Graph Context (lines 963-974)
      GraphContextProvider.discover_context() → relationships
      ↓
  [5] Session Management (lines 976-990)
      SessionManager.get_or_create_session() → session_id
      ↓
  [6] LLM Generation (lines 992-1006) ⭐ THE CORE
      LLMOrchestrator.generate() → response
      ↓
  [7] Response Formatting (lines 1027-1076)
      Build citations, metadata
      ↓
  [8] Session Storage (lines 1083-1097)
      Store conversation turn for memory
      ↓
  [9] Return ChatResponse

  ---
  2. PROMPT BUILDING: 5-STAGE CONVERSATION ENGINE

  Location: conversation_engine/engine.py (184-723 lines)

  The 5 Stages:

  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 1: Context Analyzer (~5-8ms)                                  │
  │   Classifies: theme, urgency, user_emotion, query_type, turn_type   │
  │   Output: AnalyzedContext                                           │
  └─────────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 2: Response Calibrator (~2-3ms)                               │
  │   From voiceprint: warmth, directness, formality                    │
  │   Applies: situation rules, multi-turn rules, executive rules       │
  │   Output: ResponseCalibration (tone, opener, signoff, emoji_usage)  │
  └─────────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 3: Semantic Example Selector (~30ms)                          │
  │   Multi-Signal Scoring:                                             │
  │   0.70×semantic + 0.10×type_bonus + 0.10×length + 0.10×tone         │
  │   Output: SelectedExample (real communication sample)               │
  └─────────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 4: Precedent Selector (~5ms)                                  │
  │   For DECISION queries only                                         │
  │   Scoring: 0.40×category + 0.40×semantic + 0.20×recency             │
  │   Output: SelectedPrecedent (past decisions like DC_sample_005)     │
  └─────────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 5: Prompt Assembler (~3ms)                                    │
  │   Builds SYSTEM PROMPT (8 sections) + USER PROMPT                   │
  │   Output: (system_prompt, user_prompt)                              │
  └─────────────────────────────────────────────────────────────────────┘

  ---
  3. PROMPT ASSEMBLY: 8 SECTIONS (assembler.py:106-481)

  System Prompt Structure:

  ┌─────────────────────────────────────────────────────────────────────┐
  │ [1] REASONING SECTION (ALWAYS FIRST)                                │
  │     Cognitive scaffolding - "Think before you speak"                │
  │     Contains: typical_questions, red_flags, value_trade_offs        │
  │     Budget: ~130 tokens                                             │
  ├─────────────────────────────────────────────────────────────────────┤
  │ [2] IDENTITY SECTION (VOICEPRINT HEAVY) ⭐                          │
  │     Full personality injection with 18+ voiceprint components       │
  │     Contains: openers, signoffs, key_phrases, style_markers,        │
  │              emoji_guidance, thinking_patterns, decision_cadence    │
  │     Budget: 150-200 tokens                                          │
  ├─────────────────────────────────────────────────────────────────────┤
  │ [3] CONVERSATION CONTEXT (if session exists)                        │
  │     "This is turn 3. Topic: Budget. User feeling: stressed"         │
  │     Budget: 45-80 tokens                                            │
  ├─────────────────────────────────────────────────────────────────────┤
  │ [4] EXAMPLE SECTION                                                 │
  │     "MATCH THIS EXAMPLE (tone, structure, warmth):"                 │
  │     Real communication sample from profile                          │
  │     Budget: 85-120 tokens                                           │
  ├─────────────────────────────────────────────────────────────────────┤
  │ [5] CALIBRATION SECTION                                             │
  │     "FOR THIS RESPONSE: Tone: serious, Length: medium (~60 words)"  │
  │     Budget: 50-80 tokens                                            │
  ├─────────────────────────────────────────────────────────────────────┤
  │ [6] VALUES SECTION (standard/agentic only)                          │
  │     "YOUR INTERNAL VALUES (embody, never state):"                   │
  │     Budget: 50-70 tokens                                            │
  ├─────────────────────────────────────────────────────────────────────┤
  │ [7] PRECEDENT SECTION (decision queries only)                       │
  │     "RELEVANT PAST DECISION: In DC_sample_005, I approved..."       │
  │     Budget: 50-60 tokens                                            │
  ├─────────────────────────────────────────────────────────────────────┤
  │ [8] INSTRUCTIONS SECTION                                            │
  │     Anti-AI rules + word limits + forbidden phrases                 │
  │     Budget: 55-100 tokens                                           │
  └─────────────────────────────────────────────────────────────────────┘

  User Prompt Structure:

  ┌─────────────────────────────────────────────────────────────────────┐
  │ AVAILABLE CONTEXT:                                                  │
  │                                                                     │
  │ Source: Q3_Performance_Report (Relevance: 0.85)                     │
  │     Revenue grew 23% YoY driven by enterprise segment...            │
  │                                                                     │
  │ Source: Board_Minutes_Jan (Relevance: 0.79)                         │
  │     Approved expansion into three new markets...                    │
  │                                                                     │
  │ (Use this as background knowledge - do NOT cite in response)        │
  ├─────────────────────────────────────────────────────────────────────┤
  │ [GRAPH CONTEXT if available]                                        │
  │ [CONVERSATION HISTORY if multi-turn]                                │
  ├─────────────────────────────────────────────────────────────────────┤
  │ ★★★ RESPOND AS sample-SAN ★★★                                      │
  │ • "I think..." soft assertions (for OPINIONS only)                  │
  │ • Enthusiasm with "!"                                               │
  │ • Forward-looking: "Let's..."                                       │
  │ • ~60 words. Concise, warm, forward-looking.                        │
  └─────────────────────────────────────────────────────────────────────┘

  ---
  4. TOKEN BUDGETS BY PATH
  ┌──────────────┬────────────┬────────────────┬───────────────┐
  │   Section    │ Fast (450) │ Standard (620) │ Agentic (780) │
  ├──────────────┼────────────┼────────────────┼───────────────┤
  │ Identity     │ 150        │ 180            │ 200           │
  ├──────────────┼────────────┼────────────────┼───────────────┤
  │ Conversation │ 0          │ 60             │ 80            │
  ├──────────────┼────────────┼────────────────┼───────────────┤
  │ Example      │ 100        │ 100            │ 120           │
  ├──────────────┼────────────┼────────────────┼───────────────┤
  │ Calibration  │ 50         │ 70             │ 80            │
  ├──────────────┼────────────┼────────────────┼───────────────┤
  │ Values       │ 0          │ 70             │ 100           │
  ├──────────────┼────────────┼────────────────┼───────────────┤
  │ Precedent    │ 0          │ 60             │ 80            │
  ├──────────────┼────────────┼────────────────┼───────────────┤
  │ Instructions │ 50         │ 60             │ 100           │
  └──────────────┴────────────┴────────────────┴───────────────┘
  Dynamic Reallocation: Unused sections (no session, no precedent) → budget goes to example section

  ---
  5. LLM ORCHESTRATOR FLOW (llm_integration/orchestrator.py)

  LLMOrchestrator.generate()
      ↓
  [1] Query Routing (forced or automatic)
      → path: "fast" | "standard" | "agentic"
      ↓
  [2] Get Path Handler (cached)
      → FastPathHandler | StandardPathHandler | AgenticPathHandler
      ↓
  [3] Handler Execution
      ├─ Build RetrievalContext
      ├─ ConversationEngine.generate() → (system_prompt, user_prompt)
      ├─ Create LLMMessages
      └─ LLM API Call
      ↓
  [4] Response Formatting
      → Extract answer, citations, sources
      ↓
  [5] Quality Evaluation
      → Store metrics for monitoring
      ↓
  [6] Return Response Dict

  Path Handler Differences:
  ┌─────────────────┬───────┬──────────┬─────────────────┐
  │     Aspect      │ Fast  │ Standard │     Agentic     │
  ├─────────────────┼───────┼──────────┼─────────────────┤
  │ Results Used    │ 5     │ 10       │ 15              │
  ├─────────────────┼───────┼──────────┼─────────────────┤
  │ Graph Context   │ No    │ Yes (5)  │ Yes (10)        │
  ├─────────────────┼───────┼──────────┼─────────────────┤
  │ Precedents      │ No    │ Yes (3)  │ Yes (5)         │
  ├─────────────────┼───────┼──────────┼─────────────────┤
  │ Target Latency  │ <1.5s │ <2.5s    │ <5s             │
  ├─────────────────┼───────┼──────────┼─────────────────┤
  │ ReAct Reasoning │ No    │ No       │ Yes (4-6 steps) │
  ├─────────────────┼───────┼──────────┼─────────────────┤
  │ Word Limit      │ ~30   │ ~60      │ ~120            │
  └─────────────────┴───────┴──────────┴─────────────────┘
  ---
  6. VOICEPRINT INJECTION (identity_section.py)

  18+ Voiceprint Components Extracted:

  # Lines 204-227
  signature_openers     # "I see. Let me share my thoughts..."
  sign_offs             # "Let me know if questions."
  key_phrases           # From lexicon: "crushing it", "game-changing"
  disagreement_patterns # "I hear you, and..." + pushback
  style_desc            # warmth:7, directness:8, formality:6
  emoji_guidance        # "AVOID in formal. Only 😊👍 in casual Slack"
  analogy_examples      # "Think of it like..."
  emotional_language    # "I'm proud of...", "This concerns me..."
  thinking_patterns     # "I think... / In my view..." (soft assertions)
  numbers_cadence       # Data-driven storytelling
  transparency_phrases  # "Here's how I think about this:"
  challenge_invitation  # "Thoughts? Pushback?"
  deference_phrases     # "You know X better than me"
  accountability_phrases# "This is on me as CEO"
  mentorship_phrases    # Coaching language
  energy_words          # "You're a legend"
  humor_markers         # "(lol)", "Questions? Memes?"
  core_reasoning        # Express opinions → Explain reasoning

  Context-Aware Emphasis:

  # Lines 1748-1801
  if urgency == CRISIS:
      emphasis["risk_language"] = True
      emphasis["accountability"] = True

  if user_emotion == STRESSED:
      emphasis["supportive"] = True
      emphasis["coaching"] = True

  if query_type == DECISION:
      emphasis["decision_cadence"] = True
      emphasis["analogies"] = True

  ---
  7. LANGGRAPH WORKFLOW (langgraph_workflow/)

  Three Execution Paths:

                      ┌─────────────────────────────────────────┐
                      │           COGNITIVE ROUTE               │
                      │  (Layer 0: Conversational vs Retrieval) │
                      └─────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            ▼                   ▼                   ▼
      ┌──────────┐        ┌──────────┐        ┌──────────┐
      │   FAST   │        │ STANDARD │        │ AGENTIC  │
      │  <1.5s   │        │  <2.5s   │        │   <5s    │
      └──────────┘        └──────────┘        └──────────┘
            │                   │                   │
            ▼                   ▼                   ▼
      ┌──────────┐        ┌──────────┐        ┌──────────┐
      │ retrieve │        │ graphrag │        │ graphrag │
      │  (top 5) │        │ parallel │        │ parallel │
      └──────────┘        │ retrieve │        │ retrieve │
            │             └──────────┘        └──────────┘
            │                   │                   │
            │                   ▼                   ▼
            │             ┌──────────┐        ┌──────────┐
            │             │   fuse   │        │   fuse   │
            │             └──────────┘        └──────────┘
            │                   │                   │
            │                   ▼                   ▼
            │             ┌──────────┐        ┌──────────┐
            │             │  rerank  │        │  rerank  │
            │             └──────────┘        └──────────┘
            │                   │                   │
            │                   ▼                   ▼
            │             ┌──────────┐        ┌──────────┐
            │             │ cognitive│        │  ReAct   │
            │             │  layers  │        │  Loop    │
            │             │  (1-5)   │        │ (4-6     │
            │             └──────────┘        │  steps)  │
            │                   │             └──────────┘
            ▼                   ▼                   │
      ┌──────────┐        ┌──────────┐              │
      │ generate │        │ generate │              ▼
      │   fast   │        │ standard │        ┌──────────┐
      └──────────┘        └──────────┘        │ finalize │
            │                   │             └──────────┘
            └───────────────────┼───────────────────┘
                                ▼
                           ┌─────────┐
                           │   END   │
                           └─────────┘

  ReAct Loop (Agentic Path):

  react_think → react_act → react_observe → should_continue?
       ↑                                         │
       └─────────── [continue] ─────────────────┘
                          │
                     [finalize]
                          ↓
                  react_finalize → END

  Available Tools:
  ┌──────────────┬────────────────────┬─────────────────────────┐
  │     Tool     │      Purpose       │       Data Source       │
  ├──────────────┼────────────────────┼─────────────────────────┤
  │ SEARCH       │ Hybrid retrieval   │ Vector + Graph + Memory │
  ├──────────────┼────────────────────┼─────────────────────────┤
  │ ANALYZE      │ Examine context    │ State.reranked_results  │
  ├──────────────┼────────────────────┼─────────────────────────┤
  │ RELATIONSHIP │ Entity connections │ Neo4j                   │
  ├──────────────┼────────────────────┼─────────────────────────┤
  │ PRECEDENT    │ Past decisions     │ PostgreSQL              │
  ├──────────────┼────────────────────┼─────────────────────────┤
  │ PATTERN      │ Decision patterns  │ decision_cases table    │
  ├──────────────┼────────────────────┼─────────────────────────┤
  │ FINALIZE     │ Exit loop          │ -                       │
  └──────────────┴────────────────────┴─────────────────────────┘
  Continuation Logic:
  - Confidence >= 0.85 → finalize
  - Iterations >= 6 → finalize (hard limit)
  - ENFORCE minimum 4 iterations before allowing finalization

  ---
  8. RESULT FUSION & SCORING (hybrid_retrieval/)

  Fusion Formula:

  composite_score = 0.60 × vector_score + 0.30 × graph_score + 0.10 × memory_score

  # Multi-source boost:
  if found_in_2_sources: composite += 0.10
  if found_in_3_sources: composite += 0.15

  Query-Type Weights:
  ┌──────────────┬────────┬───────┬────────┐
  │  Query Type  │ Vector │ Graph │ Memory │
  ├──────────────┼────────┼───────┼────────┤
  │ Factual      │ 80%    │ 15%   │ 5%     │
  ├──────────────┼────────┼───────┼────────┤
  │ Decision     │ 35%    │ 25%   │ 40%    │
  ├──────────────┼────────┼───────┼────────┤
  │ Analysis     │ 45%    │ 30%   │ 25%    │
  ├──────────────┼────────┼───────┼────────┤
  │ Relationship │ 30%    │ 65%   │ 5%     │
  └──────────────┴────────┴───────┴────────┘
  Memory Scoring (5-Signal):

  memory_score = (
      0.40 × semantic_similarity +
      0.25 × temporal_decay +        # exp(-days/60)
      0.20 × decision_importance
  ) × feedback_multiplier × user_context_multiplier

  ---
  9. ANTI-AI RULES (rules.py - Single Source of Truth)

  Forbidden Phrases:

  [
      "I'd be happy to",
      "Certainly!",
      "Great question!",
      "As an AI",
      "Let me help you with",
      "synergy", "leverage", "circle back",
  ]

  Forbidden Patterns:

  [
      "NO bullet points unless explicitly listing items",
      "NO markdown headers",
      "NO numbered lists (except sample: use ①②③)",
      "NO 'First... Second... Third...' structure",
  ]

  Word Limits (Based on Real sample Analysis):
  ┌──────────┬────────┬──────────┬──────────┐
  │   Path   │ Target │ Soft Max │ Hard Max │
  ├──────────┼────────┼──────────┼──────────┤
  │ Fast     │ 15     │ 25       │ 40       │
  ├──────────┼────────┼──────────┼──────────┤
  │ Standard │ 35     │ 50       │ 80       │
  ├──────────┼────────┼──────────┼──────────┤
  │ Agentic  │ 60     │ 100      │ 150      │
  └──────────┴────────┴──────────┴──────────┘
  ---
  10. COMPLETE DATA TRANSFORMATION CHAIN

  User Query (string)
      ↓
  QueryProcessor → normalized params + threshold adjustment
      ↓
  QueryRouter → RouteDecision(path, confidence, reasoning)
      ↓
  EntityExtractor → List[Entity] with confidence scores
      ↓
  GraphContextProvider → candidate_ids + graph_distances
      ↓
  VectorSearchEngine → results with similarity_score
      ↓
  ResultFusion → fused_results with composite_score
      ↓
  AdaptiveReranker → reranked_results with final_score
      ↓
  ConversationEngine (5 stages) → (system_prompt, user_prompt)
      ↓
  LLMOrchestrator → LLMResponse(content, tokens, cost)
      ↓
  ResponseFormatter → FormattedResponse(content, citations, sources)
      ↓
  ChatResponse (JSON to client)

  ---
  KEY INSIGHTS

  1. Reasoning Section is ALWAYS FIRST - Makes LLM "think" before personality takes over
  2. Identity Section is VOICEPRINT HEAVY - 18+ components extracted and injected contextually
  3. Token Budgets are Dynamic - Unused sections reallocate to example section
  4. Path Choice Drives Everything - Determines results count, cognitive layers, word limits
  5. ReAct enforces 4+ iterations - Prevents shallow analysis in agentic path
  6. Single Source of Truth - All anti-AI rules in rules.py prevent contradictions
  7. sample has Special Handling - ①②③ numbered lists, specific voice guidance

  This is the complete inner mechanics of how responses are generated in the RAG system.