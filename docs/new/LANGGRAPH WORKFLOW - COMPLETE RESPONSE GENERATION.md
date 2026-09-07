🔬 LANGGRAPH WORKFLOW - COMPLETE RESPONSE GENERATION

  ENDPOINTS (What You're Actually Using)
  ┌──────────────────────────────────────────┬──────────────────┬────────────────────────────┐
  │                 Endpoint                 │     Purpose      │            Line            │
  ├──────────────────────────────────────────┼──────────────────┼────────────────────────────┤
  │ POST /api/v1/langgraph/chat              │ Non-streaming    │ langgraph_endpoints.py:33  │
  ├──────────────────────────────────────────┼──────────────────┼────────────────────────────┤
  │ POST /api/v1/langgraph/chat/stream       │ Streaming (Main) │ langgraph_endpoints.py:306 │
  ├──────────────────────────────────────────┼──────────────────┼────────────────────────────┤
  │ POST /api/v1/langgraph/chat/stream-audio │ Audio streaming  │ langgraph_endpoints.py:891 │
  └──────────────────────────────────────────┴──────────────────┴────────────────────────────┘
  ---
  1. REQUEST ENTRY & STATE INITIALIZATION

  Entry Point (langgraph_endpoints.py:306-395):

  # Line 376-395: Create initial LangGraph state
  initial_state = get_default_state(
      query=chat_request.query,
      profile_id=chat_request.profile_id or "sample_profile",
      session_id=session_id,
      language=chat_request.language or "en",
      use_conversation_engine=True  # ← CRITICAL: Uses 5-stage pipeline
  )

  # Line 398: CRITICAL for streaming
  initial_state["skip_generation"] = True  # Nodes skip LLM, endpoint streams it

  Thread Config for Multi-Turn (line 400-408):
  config = {
      "configurable": {
          "thread_id": session_id,  # Enables checkpointing
          "user_id": chat_request.user_id,
          "profile_id": chat_request.profile_id
      }
  }

  ---
  2. WORKFLOW EXECUTION: workflow.astream()

  Line 445 - The Core Execution:
  async for state_update in workflow.astream(initial_state, config=config):
      # state_update is NODE-KEYED: {"node_name": {...partial_state...}}
      accumulated_state.update(node_state)

  Complete Node Execution Path:

  ┌─────────────────────────────────────────────────────────────────────┐
  │                     LANGGRAPH WORKFLOW EXECUTION                     │
  └─────────────────────────────────────────────────────────────────────┘

  START
    ↓
  [cognitive_route] ─────────────────────────────────────┐
    │                                                     │
    ├─ Greeting/small talk? → [generate_conversational] → END
    │                              (personality only)
    │
    └─ Retrieval needed? ↓

  [analyze_query] → Extract entities, complexity, query_type
    ↓
  [route_query] → Select path based on patterns (NO LLM)
    │
    ├─ "fast" ────────────────────────────────────────────┐
    │                                                      │
    │  [retrieve_unified_fast]                            │
    │       ↓                                              │
    │  [cognitive_lens_fast] (optional)                   │
    │       ↓                                              │
    │  [generate_fast] ←── skip_generation=True           │
    │       ↓              (returns empty, endpoint       │
    │      END              handles LLM streaming)        │
    │                                                      │
    ├─ "standard" ────────────────────────────────────────┤
    │                                                      │
    │  [retrieve_graphrag_standard] → global themes       │
    │       ↓                                              │
    │  [retrieve_parallel_standard] → vector ‖ memory     │
    │       ↓                                              │
    │  [fuse_results_standard] → weighted fusion          │
    │       ↓                                              │
    │  [rerank_results_standard] → adaptive reranking     │
    │       ↓                                              │
    │  [cognitive_lens_standard] → Layer 1                │
    │       ↓                                              │
    │  [cognitive_frame_standard] → Layer 2               │
    │       ↓                                              │
    │  [situation_analysis_standard] → Layer 4            │
    │       ↓                                              │
    │  [relationship_adaptation_standard] → Layer 5       │
    │       ↓                                              │
    │  [cognitive_prompt_assembly_standard]               │
    │       ↓                                              │
    │  [generate_standard] ←── skip_generation=True       │
    │       ↓                                              │
    │      END                                             │
    │                                                      │
    └─ "agentic" ─────────────────────────────────────────┤
                                                           │
       [retrieve_graphrag_agentic]                        │
            ↓                                              │
       [retrieve_parallel_agentic]                        │
            ↓                                              │
       [fuse_results_agentic]                             │
            ↓                                              │
       [rerank_results_agentic]                           │
            ↓                                              │
       ┌──────────────────────────────────────┐           │
       │         ReAct REASONING LOOP         │           │
       │  ┌────────────────────────────────┐  │           │
       │  │ [react_think] → Generate thought│  │           │
       │  │      ↓                          │  │           │
       │  │ [react_act] → Parse action      │  │           │
       │  │      ↓                          │  │           │
       │  │ [react_observe] → Execute tool  │  │           │
       │  │      ↓                          │  │           │
       │  │ [should_continue?]              │  │           │
       │  │   ├─ continue → loop back       │  │           │
       │  │   └─ finalize → exit loop       │  │           │
       │  └────────────────────────────────┘  │           │
       │  (Minimum 4 iterations enforced)     │           │
       └──────────────────────────────────────┘           │
            ↓                                              │
       [react_finalize] ←── skip_generation=True          │
            ↓                                              │
           END                                             │
                                                           │
  ─────────────────────────────────────────────────────────┘

  ---
  3. PROMPT BUILDING (After Workflow, Before LLM)

  The workflow sets skip_generation=True, so generation nodes return empty.
  The streaming endpoint then builds prompts and streams LLM output:

  Line 656-682 - ConversationEngine 5-Stage Pipeline:

  # Build RetrievalContext from workflow results
  retrieval_context = RetrievalContext(
      vector_results=final_state.get("reranked_results", []),
      graph_results=final_state.get("graph_context", {}).get("results", []),
      precedents=final_state.get("memory_results", []),
      query=chat_request.query
  )

  # 5-STAGE PIPELINE EXECUTION
  system_prompt, user_prompt, conv_state = await conversation_engine.generate(
      query=chat_request.query,
      profile_id=chat_request.profile_id,
      retrieved_context=retrieval_context,
      path=selected_path,           # "fast" / "standard" / "agentic"
      session_id=session_id,
      language=chat_request.language
  )

  The 5 Stages Inside conversation_engine.generate():

  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 1: ContextAnalyzer                                            │
  │   Input: query                                                      │
  │   Output: theme, urgency, user_emotion, query_type, turn_type       │
  │   Time: ~5-8ms                                                      │
  └─────────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 2: ResponseCalibrator                                         │
  │   Input: AnalyzedContext + voiceprint                               │
  │   Output: tone, opener, signoff, emoji_usage, attention_weights     │
  │   Time: ~2-3ms                                                      │
  └─────────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 3: SemanticExampleSelector                                    │
  │   Input: query embedding + communication_examples                   │
  │   Output: Best matching example for tone/style                      │
  │   Time: ~30ms                                                       │
  └─────────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 4: PrecedentSelector (DECISION queries only)                  │
  │   Input: query + decision_cases database                            │
  │   Output: Relevant past decision (DC_sample_005)                    │
  │   Time: ~5ms                                                        │
  └─────────────────────────────────────────────────────────────────────┘
                                ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ STAGE 5: PromptAssembler                                            │
  │   Input: All above + profile + voiceprint + retrieval_context       │
  │   Output: (system_prompt, user_prompt)                              │
  │   Time: ~3ms                                                        │
  └─────────────────────────────────────────────────────────────────────┘

  ---
  4. SYSTEM PROMPT ASSEMBLY (8 Sections)

  File: conversation_engine/prompt/assembler.py:162-207

  SYSTEM PROMPT STRUCTURE:
  ═══════════════════════════════════════════════════════════════════════

  [1] REASONING SECTION (ALWAYS FIRST - cognitive scaffolding)
      "STEP 1: DATA CHECK - Do I have specific data?"
      "STEP 2: RED FLAG SCAN - Check for: {never_approve items}"
      "STEP 3: VALUE WEIGHTING - My biases: speed > perfection..."
      ~130 tokens

  [2] IDENTITY SECTION (Voiceprint injection - 18+ components)
      "You are sample_profile, CEO of Example Company..."
      HOW YOU START: "I see. Let me share my thoughts..."
      HOW YOU END: "Let me know if questions."
      KEY PHRASES: "crushing it", "Let's just try it"
      SOFT ASSERTIONS: "I think... / In my view..."
      EMOJI: "AVOID in formal. Only 😊👍 in casual Slack"
      ~180 tokens

  [3] CONVERSATION CONTEXT (if multi-turn)
      "This is turn 3. Topic: Budget optimization."
      "User feeling: stressed. DO NOT REPEAT: Q2 figures"
      ~60 tokens

  [4] EXAMPLE SECTION
      "MATCH THIS EXAMPLE (tone, structure, warmth):"
      {actual communication example from profile}
      ~100 tokens

  [5] CALIBRATION SECTION
      "FOR THIS RESPONSE:"
      "- Tone: serious, acknowledge stress"
      "- Length: Medium (~50 words)"
      "- No emojis (serious context)"
      ~70 tokens

  [6] VALUES SECTION (standard/agentic only)
      "YOUR INTERNAL VALUES (embody, never state):"
      "• Speed: Done > perfect"
      "• Delegation: Empower team"
      ~70 tokens

  [7] PRECEDENT SECTION (decision queries only)
      "RELEVANT PAST DECISION:"
      "In DC_sample_005, I approved 15% discount because..."
      ~60 tokens

  [8] INSTRUCTIONS SECTION
      "NEVER DO THESE (they reveal you're AI):"
      "- NO bullet points, NO markdown"
      "- FORBIDDEN: 'I'd be happy to', 'Certainly!'"
      "- AIM FOR ~50 words"
      ~60 tokens

  ═══════════════════════════════════════════════════════════════════════
  Total: ~620 tokens (standard path)

  ---
  5. USER PROMPT ASSEMBLY

  File: conversation_engine/prompt/assembler.py:384-481

  USER PROMPT STRUCTURE:
  ═══════════════════════════════════════════════════════════════════════

  AVAILABLE CONTEXT:

  Source: Q3_Performance_Report.pdf (Relevance: 0.85)
      Revenue grew 23% YoY. Enterprise segment up 45%...

  Source: Board_Minutes_January.md (Relevance: 0.79)
      Approved three new market expansions...

  Source: Budget_Memo_Q4.docx (Relevance: 0.72)
      Recommended 12% increase for R&D...

  (Use as background knowledge - do NOT cite in response)

  ───────────────────────────────────────────────────────────────────────

  [GRAPH CONTEXT if available]
  Related: Enterprise_Strategy → Q3_Performance (2 hops)

  [CONVERSATION HISTORY if multi-turn]
  Q: How's Q3 looking?
  A: Strong quarter, especially enterprise...

  ───────────────────────────────────────────────────────────────────────

  ★★★ RESPOND AS sample-SAN ★★★
  • "I think..." soft assertions (for OPINIONS only)
  • Enthusiasm with "!"
  • Forward-looking: "Let's..."
  • ~50 words. Concise, warm, forward-looking.

  ═══════════════════════════════════════════════════════════════════════

  ---
  6. LLM TOKEN STREAMING

  Line 698-721 - Stream Tokens to Client:

  # Stream using pre-built prompts
  async for chunk in orchestrator.generate_stream_with_prompts(
      system_prompt=system_prompt,
      user_prompt=user_prompt,
      profile_id=chat_request.profile_id,
      path=selected_path
  ):
      if chunk['type'] == 'token':
          token_count += 1
          full_response += chunk['content']

          # Send SSE event
          yield f"event: token\ndata: {json.dumps({'token': chunk['content'], 'index': token_count})}\n\n"

  ---
  7. SSE EVENT SEQUENCE (What Client Receives)

  event: start
  data: {"query": "Should we expand to Singapore?", "request_id": "abc123"}

  event: routing
  data: {"path": "standard", "confidence": 0.87, "reasoning": "Decision query"}

  event: retrieval
  data: {"vector_results": 15, "reranked_results": 10, "memory_results": 2}

  event: token
  data: {"token": "I", "index": 0}

  event: token
  data: {"token": " think", "index": 1}

  event: token
  data: {"token": " we", "index": 2}

  ... (continues for each token)

  event: complete
  data: {
    "success": true,
    "answer": "I think we should focus on Japan first...",
    "citations": [...],
    "sources": ["Q3_Report", "Strategy_Doc"],
    "metadata": {
      "total_latency_ms": 2145,
      "path": "standard",
      "routing_confidence": 0.87,
      "profile_id": "sample_profile",
      "results_used": 10,
      "conversation_engine": true
    }
  }

  ---
  8. KEY DIFFERENCES FROM LEGACY ENDPOINT
  ┌────────────┬───────────────────────────┬─────────────────────────────────────────┐
  │   Aspect   │    Legacy /api/v1/chat    │ LangGraph /api/v1/langgraph/chat/stream │
  ├────────────┼───────────────────────────┼─────────────────────────────────────────┤
  │ Workflow   │ Sequential function calls │ LangGraph StateGraph with nodes         │
  ├────────────┼───────────────────────────┼─────────────────────────────────────────┤
  │ State      │ Passed between functions  │ Accumulated in RAGState TypedDict       │
  ├────────────┼───────────────────────────┼─────────────────────────────────────────┤
  │ Routing    │ QueryRouter only          │ cognitive_route + route_query nodes     │
  ├────────────┼───────────────────────────┼─────────────────────────────────────────┤
  │ Retrieval  │ Single vector search      │ Parallel graph + memory + vector        │
  ├────────────┼───────────────────────────┼─────────────────────────────────────────┤
  │ Streaming  │ Simulated (word-split)    │ True token streaming via astream()      │
  ├────────────┼───────────────────────────┼─────────────────────────────────────────┤
  │ Multi-turn │ Manual session storage    │ PostgreSQL Checkpointer auto-saves      │
  ├────────────┼───────────────────────────┼─────────────────────────────────────────┤
  │ Cognitive  │ Not available             │ 6-layer cognitive twin integration      │
  ├────────────┼───────────────────────────┼─────────────────────────────────────────┤
  │ ReAct      │ Not available             │ Full ReAct loop (4-6 steps)             │
  └────────────┴───────────────────────────┴─────────────────────────────────────────┘
  ---
  9. CRITICAL STATE FIELDS

  Input Fields:
  - query - User question
  - profile_id - Executive persona ("sample_profile")
  - session_id - Thread ID for continuity
  - skip_generation - TRUE for streaming

  Accumulated During Workflow:
  - selected_path - "fast" / "standard" / "agentic"
  - routing_confidence - 0.0-1.0
  - vector_results - Retrieved documents
  - reranked_results - Final ranked results (used for prompt)
  - graph_context - Neo4j relationships
  - memory_results - Episodic memory
  - react_steps - ReAct reasoning (agentic only)
  - conversation_history - Multi-turn context

  Set by Endpoint (After Streaming):
  - llm_response - Final generated answer
  - citations - Extracted citations
  - sources - Source documents used

  ---
  10. COMPLETE DATA FLOW

  User Request
      ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ LANGGRAPH WORKFLOW (skip_generation=True)                           │
  │                                                                     │
  │ cognitive_route → analyze_query → route_query                       │
  │        ↓                                                            │
  │ [PATH-SPECIFIC RETRIEVAL & COGNITIVE ENHANCEMENT]                   │
  │        ↓                                                            │
  │ generate_* node (SKIPS LLM - returns empty)                        │
  │        ↓                                                            │
  │ Returns: accumulated_state with reranked_results                    │
  └─────────────────────────────────────────────────────────────────────┘
      ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ CONVERSATION ENGINE 5-STAGE PIPELINE                                │
  │                                                                     │
  │ ContextAnalyzer → ResponseCalibrator → ExampleSelector              │
  │        ↓                                                            │
  │ PrecedentSelector → PromptAssembler                                 │
  │        ↓                                                            │
  │ Returns: (system_prompt, user_prompt)                               │
  └─────────────────────────────────────────────────────────────────────┘
      ↓
  ┌─────────────────────────────────────────────────────────────────────┐
  │ LLM STREAMING                                                       │
  │                                                                     │
  │ orchestrator.generate_stream_with_prompts()                         │
  │        ↓                                                            │
  │ Token by token → SSE events → Client                                │
  └─────────────────────────────────────────────────────────────────────┘
      ↓
  Final Response + Checkpoint Save

  This is the actual response generation flow through your LangGraph workflow!
