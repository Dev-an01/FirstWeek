  Deep Explanation: LangGraph Workflow, Conversation Engine & Cognitive Twin

  1. LangGraph Workflow

  The LangGraph workflow is the central orchestration layer that routes queries through the appropriate processing path and coordinates 
  all RAG components.

  1.1 State Schema (state.py:9-131)

  The RAGState TypedDict defines the complete state passed through all workflow nodes:

  ┌─────────────────────────────────────────────────────────────────┐
  │                         RAGState                                 │
  ├─────────────────────────────────────────────────────────────────┤
  │ INPUT                                                            │
  │  • query, user_id, user_role, profile_id, session_id            │
  │  • top_k, min_score, language ("en"/"ja")                       │
  ├─────────────────────────────────────────────────────────────────┤
  │ QUERY ANALYSIS                                                   │
  │  • query_features: Dict (from QueryAnalyzer)                    │
  │  • query_type: factual/decision/analysis/navigation             │
  │  • complexity: simple/medium/complex                            │
  │  • entities: List[Dict] (spaCy NER extraction)                  │
  ├─────────────────────────────────────────────────────────────────┤
  │ ROUTING                                                          │
  │  • selected_path: "fast" | "standard" | "agentic"               │
  │  • routing_confidence: float (0.0-1.0)                          │
  │  • force_path: Override automatic routing                       │
  │  • skip_generation: bool (for streaming mode)                   │
  ├─────────────────────────────────────────────────────────────────┤
  │ RETRIEVAL                                                        │
  │  • vector_results, graph_context, memory_results                │
  │  • fused_results (after ResultFusion)                           │
  │  • reranked_results (after AdaptiveReranker)                    │
  ├─────────────────────────────────────────────────────────────────┤
  │ REACT (Agentic Only)                                             │
  │  • react_steps: List[{thought, action, observation}]            │
  │  • react_confidence: float (0.0-1.0)                            │
  │  • react_iteration: int (current step, max 6)                   │
  ├─────────────────────────────────────────────────────────────────┤
  │ COGNITIVE TWIN (6-Layer)                                         │
  │  • cognitive.routing: ConversationalContext                     │
  │  • cognitive.lens_result: CognitiveLensResult                   │
  │  • cognitive.frame_result: CognitiveFrameResult                 │
  │  • cognitive.situation: SituationContext                        │
  │  • cognitive.relationship: RelationshipContext                  │
  │  • cognitive.assembled_prompt: AssembledPrompt                  │
  ├─────────────────────────────────────────────────────────────────┤
  │ LLM GENERATION                                                   │
  │  • system_prompt, user_prompt                                   │
  │  • llm_response, llm_tokens, llm_cost_usd                       │
  └─────────────────────────────────────────────────────────────────┘

  1.2 Workflow Graph (graph.py:63-518)

  The graph is built using LangGraph's StateGraph:

  workflow = StateGraph(RAGState)

  Complete Workflow Flow with Cognitive Twin:

  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         ENTRY POINT                                          │
  │                    cognitive_route_node                                      │
  │                          │                                                   │
  │           ┌──────────────┼───────────────┐                                  │
  │           ▼              ▼               │                                  │
  │    [conversational]  [retrieval]         │                                  │
  │           │              │               │                                  │
  │           ▼              ▼               │                                  │
  │    generate_conversational  analyze_query                                   │
  │           │              │               │                                  │
  │           ▼              ▼               │                                  │
  │          END        route_query ─────────┼──────────────────┐               │
  │                          │               │                  │               │
  │           ┌──────────────┼───────────────┼──────────────────┤               │
  │           ▼              ▼               ▼                  │               │
  │        [FAST]       [STANDARD]       [AGENTIC]              │               │
  │           │              │               │                  │               │
  │           ▼              ▼               ▼                  │               │
  │    retrieve_unified  GraphRAG_global  GraphRAG_global       │               │
  │           │              │               │                  │               │
  │           ▼              ▼               ▼                  │               │
  │    cognitive_lens   parallel_retrieve  parallel_retrieve    │               │
  │           │              │               │                  │               │
  │           ▼              ▼               ▼                  │               │
  │    generate_fast      fuse_results    fuse_results          │               │
  │           │              │               │                  │               │
  │           ▼              ▼               ▼                  │               │
  │          END        rerank_results   rerank_results         │               │
  │                          │               │                  │               │
  │                          ▼               ▼                  │               │
  │                   cognitive_lens    react_think ◄──┐        │               │
  │                          │               │         │        │               │
  │                          ▼               ▼         │        │               │
  │                   cognitive_frame   react_act      │        │               │
  │                          │               │         │        │               │
  │                          ▼               ▼         │        │               │
  │                   situation_analysis react_observe │        │               │
  │                          │               │         │        │               │
  │                          ▼               ├─────────┘        │               │
  │                   relationship_adapt  [continue?]           │               │
  │                          │               │                  │               │
  │                          ▼               ▼                  │               │
  │                   prompt_assembly   react_finalize          │               │
  │                          │               │                  │               │
  │                          ▼               ▼                  │               │
  │                   generate_standard     END                 │               │
  │                          │                                  │               │
  │                          ▼                                  │               │
  │                         END                                 │               │
  └─────────────────────────────────────────────────────────────────────────────┘

  Key Conditional Edges:

  1. route_cognitive (graph.py:50-60): Decides if conversational (skip retrieval) or continue to retrieval
  2. route_to_path (graph.py:41-47): Routes to fast/standard/agentic based on selected_path
  3. should_continue_react: Decides if ReAct loop continues or finalizes

  1.3 Node Functions (nodes.py)

  Nodes use a closure pattern for dependency injection:

  def create_nodes(
      vector_engine,
      graph_provider,
      query_analyzer,
      query_router,
      result_fusion,
      adaptive_reranker,
      llm_orchestrator,
      session_manager,
      memory_search_engine,
      graphrag_provider,
      ragas_evaluator,
      conversation_engine
  ) -> Dict[str, Callable]:
      """Create nodes with injected dependencies."""

      def analyze_query(state: RAGState) -> RAGState:
          # Uses query_analyzer from closure
          features = query_analyzer.analyze(state["query"])
          state["query_features"] = features
          return state

      def route_query(state: RAGState) -> RAGState:
          # Uses query_router from closure
          result = query_router.route(
              query=state["query"],
              features=state["query_features"]
          )
          state["selected_path"] = result.path
          return state

      # ... more nodes
      return {
          "analyze_query": analyze_query,
          "route_query": route_query,
          # ...
      }

  ---
  2. Conversation Engine

  The Conversation Engine (conversation_engine/engine.py:78-787) provides context-aware, conversation-stateful prompt generation with   
  authentic executive voice.

  2.1 Architecture Overview

  ┌─────────────────────────────────────────────────────────────────┐
  │                    ConversationEngine                            │
  │                                                                  │
  │  Dependencies:                                                   │
  │  • session_manager (SessionManager)                             │
  │  • profile_manager (ProfileManager)                             │
  │  • memory_search (MultiSignalMemorySearch)                      │
  │  • embedding_model (EmbeddingModel)                             │
  │                                                                  │
  │  Internal Components:                                            │
  │  • _context_manager (ContextManager)                            │
  │  • _context_analyzer (ContextAnalyzer)                          │
  │  • _response_calibrator (ResponseCalibrator)                    │
  │  • _example_selector (SemanticExampleSelector)                  │
  │  • _precedent_selector (PrecedentSelector)                      │
  │  • _prompt_assembler (PromptAssembler)                          │
  │  • _state_updater (StateUpdater)                                │
  └─────────────────────────────────────────────────────────────────┘

  2.2 Five-Stage Pipeline

  The generate() method (engine.py:183-342) orchestrates a 5-stage pipeline:

  Query Input
      │
      ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 0: Load Context (engine.py:496-541)                       │
  │                                                                  │
  │  Mode Detection:                                                 │
  │  ┌──────────────┬──────────────┬─────────────────────┐          │
  │  │   STATELESS  │   SESSION    │    MEMORY_AWARE     │          │
  │  ├──────────────┼──────────────┼─────────────────────┤          │
  │  │ No session   │ Multi-turn   │ Session + episodic  │          │
  │  │ ~45ms        │ history      │ memory search       │          │
  │  │              │ ~60ms        │ ~85ms               │          │
  │  └──────────────┴──────────────┴─────────────────────┘          │
  │                                                                  │
  │  Output: ManagedContext with:                                    │
  │  • mode: ConversationMode                                        │
  │  • session_state: ConversationState (if SESSION/MEMORY)          │
  │  • episodic_memories: List[Memory] (if MEMORY_AWARE)            │
  │  • resolved_query: str (with resolved references)                │
  └─────────────────────────────────────────────────────────────────┘
      │
      ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 1: Analyze Context (engine.py:543-567)                    │
  │                                                                  │
  │  Uses ContextAnalyzer to classify query:                         │
  │                                                                  │
  │  AnalyzedContext:                                                │
  │  • theme: Theme (strategic/operational/financial/people/risk)   │
  │  • urgency: Urgency (critical/high/normal/low)                  │
  │  • emotion: UserEmotion (frustrated/anxious/curious/neutral)    │
  │  • turn_type: TurnType (initial/follow_up/clarification)        │
  │  • query_type: QueryType (decision/information/advice/task)     │
  │  • implicit_needs: List[str]                                    │
  └─────────────────────────────────────────────────────────────────┘
      │
      ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 2: Calibrate Response (engine.py:569-593)                 │
  │                                                                  │
  │  Uses ResponseCalibrator with voiceprint and rules:              │
  │                                                                  │
  │  ResponseCalibration:                                            │
  │  • formality_level: float (0.0-1.0)                             │
  │  • detail_depth: float (0.0-1.0)                                │
  │  • empathy_level: float (0.0-1.0)                               │
  │  • directness_level: float (0.0-1.0)                            │
  │  • attention_weights: AttentionWeights (domain focus)           │
  │  • suggested_structure: str (bullet_points/narrative/mixed)     │
  └─────────────────────────────────────────────────────────────────┘
      │
      ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 3: Select Example (engine.py:595-630)                     │
  │                                                                  │
  │  Uses SemanticExampleSelector:                                   │
  │  • Embeds query using BAAI/bge-m3                               │
  │  • Searches executive's communication examples                   │
  │  • Multi-signal matching (semantic + category + channel)         │
  │                                                                  │
  │  Output:                                                         │
  │  • SelectedExample: Best matching communication example          │
  │  • query_embedding: numpy array (1024D) for reuse               │
  │                                                                  │
  │  Also refines attention with semantic similarity (line 276-291)  │
  └─────────────────────────────────────────────────────────────────┘
      │
      ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 4: Select Precedent (engine.py:632-667)                   │
  │                                                                  │
  │  Uses PrecedentSelector (ONLY for decision queries):            │
  │                                                                  │
  │  • Searches executive's past decision cases                      │
  │  • Uses query_embedding from Stage 3 (zero extra embedding cost)│
  │  • Scoring: category (0.4) + semantic (0.4) + recency (0.2)     │
  │                                                                  │
  │  Output: SelectedPrecedent                                       │
  │  • precedent: DecisionCase with situation/decision/outcome       │
  │  • relevance_score: float                                        │
  │  • match_reason: str                                             │
  └─────────────────────────────────────────────────────────────────┘
      │
      ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │ STAGE 5: Assemble Prompt (engine.py:669-722)                    │
  │                                                                  │
  │  Uses PromptAssembler with all previous outputs:                 │
  │                                                                  │
  │  Inputs:                                                         │
  │  • profile_id, path, language                                    │
  │  • retrieved_context (vector/graph results)                      │
  │  • analyzed_context (theme/urgency/emotion)                      │
  │  • calibration (tone/style parameters)                           │
  │  • selected_example (communication style guide)                  │
  │  • selected_precedent (decision reference)                       │
  │  • managed_context (session/memory state)                        │
  │  • audio_mode (natural speech patterns)                          │
  │                                                                  │
  │  Output: (system_prompt, user_prompt)                            │
  │  • System: Executive persona + instructions + style              │
  │  • User: Query + context + examples + precedents                 │
  └─────────────────────────────────────────────────────────────────┘
      │
      ▼
  (system_prompt, user_prompt, updated_state)

  2.3 State Update After Response

  The post_response_update() method (engine.py:390-494) updates session state after LLM response:

  await engine.post_response_update(
      session_id="sess_123",
      query="Original question",
      response="LLM response",
      analyzed_context=analyzed_context,
      calibration=calibration,
      sources_used=["source_1", "source_2"],
      llm_tokens={"prompt": 500, "completion": 200}
  )

  This stores:
  - Turn in session history
  - Facts provided (avoid repetition)
  - Sources cited
  - Emotional state update
  - Topic tracking

  ---
  3. Cognitive Twin (6-Layer Architecture)

  The Cognitive Twin system (cognitive_twin/) makes the AI executive "think" like the real executive, not just mimic their voice.       

  3.1 Configuration (config.py:7-81)

  COGNITIVE_CONFIG = {
      "enabled": True,

      # Foundation Layers (THINK differently)
      "foundation": {
          "cognitive_lens": {
              "enabled": True,
              "affinity_weight": 0.4,    # Domain affinity reranking strength
              "min_similarity": 0.3,     # Minimum domain match
          },
          "cognitive_frame": {
              "enabled": True,
              "include_thinking_patterns": True,
              "include_red_flags": True,
              "include_decision_cases": True,
              "max_decision_cases": 3,
          },
      },

      # Enhancement Layers (AWARE and CONTEXTUAL)
      "enhancement": {
          "conversational_router": {
              "enabled": True,
              "skip_retrieval_for_greetings": True,
          },
          "inference_engine": {
              "enabled": True,
              "use_for_no_retrieval": True,
              "force_opinion_response": True,
          },
          "situation_analyzer": {
              "enabled": True,
              "detect_implicit_needs": True,
              "detect_urgency": True,
              "detect_emotion": True,
          },
          "relationship_dynamics": {
              "enabled": True,
              "adapt_formality": True,
              "adapt_depth": True,
          },
      },

      # Performance
      "performance": {
          "parallel_cognitive_layers": True,  # ~40% speedup
          "max_parallel_workers": 3,
      },
  }

  3.2 Six-Layer Architecture

  ┌─────────────────────────────────────────────────────────────────┐
  │              COGNITIVE TWIN 6-LAYER ARCHITECTURE                 │
  ├─────────────────────────────────────────────────────────────────┤
  │                                                                  │
  │  LAYER 0: CONVERSATIONAL ROUTER                                  │
  │  ┌─────────────────────────────────────────────────────────┐     │
  │  │  cognitive_route_node (langgraph_integration.py:150-223)│     │
  │  │                                                          │    │
  │  │  Intent Detection:                                       │    │
  │  │  • greeting → Skip retrieval, personality response       │    │
  │  │  • small_talk → Skip retrieval, personality response     │    │
  │  │  • acknowledgment → Skip retrieval                       │    │
  │  │  • farewell → Skip retrieval                             │    │
  │  │  • business_query → Continue to retrieval               │    │
  │  │                                                          │    │
  │  │  Output: should_skip_retrieval, personality_response     │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  │  LAYER 1: COGNITIVE LENS                                         │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │  cognitive_lens_node (langgraph_integration.py:303-362) │    │
  │  │                                                          │    │
  │  │  Domain Affinity Reranking:                              │    │
  │  │  • Loads executive's domain expertise profile            │    │
  │  │  • Boosts documents matching executive's domains         │    │
  │  │  • Score = original_score + affinity_weight * similarity│    │
  │  │                                                          │    │
  │  │  Example:                                                │    │
  │  │  • Executive: Supply Chain expert                        │    │
  │  │  • Query: "logistics optimization"                       │    │
  │  │  • Supply chain docs boosted by 40%                      │    │
  │  │                                                          │    │
  │  │  Output: lens_result, reranked_results                   │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  │  LAYER 2: COGNITIVE FRAME                                        │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │  cognitive_frame_node (langgraph_integration.py:365-413)│    │
  │  │                                                          │    │
  │  │  Reasoning Pattern Injection:                            │    │
  │  │  • thinking_patterns: How executive approaches problems  │    │
  │  │  • red_flags: Things executive watches out for           │    │
  │  │  • decision_cases: Similar past decisions (max 3)        │    │
  │  │                                                          │    │
  │  │  Example (sample-san):                                   │    │
  │  │  • Thinking: "Start with customer impact, then costs"    │    │
  │  │  • Red flags: ["rushed decisions", "missing data"]       │    │
  │  │  • Cases: [{"situation": "...", "decision": "..."}]      │    │
  │  │                                                          │    │
  │  │  Output: frame_result                                    │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  │  LAYER 4: SITUATION ANALYZER                                     │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │  situation_analysis_node (langgraph_integration.py:416-466)│ │
  │  │                                                          │    │
  │  │  Context Understanding:                                   │    │
  │  │  • emotional_tone: frustrated/anxious/curious/neutral    │    │
  │  │  • urgency_level: critical/high/normal/low               │    │
  │  │  • implicit_needs: ["reassurance", "quick answer"]       │    │
  │  │  • time_context: business hours, weekend, late night     │    │
  │  │                                                          │    │
  │  │  Adapts response accordingly:                            │    │
  │  │  • Frustrated user → More empathetic, solution-focused   │    │
  │  │  • Urgent query → Concise, actionable                    │    │
  │  │                                                          │    │
  │  │  Output: situation                                        │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  │  LAYER 5: RELATIONSHIP ADAPTER                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │  relationship_adaptation_node (langgraph_integration.py:469-518)│
  │  │                                                          │    │
  │  │  Communication Style Adaptation:                          │    │
  │  │  • relationship_type: peer/subordinate/superior/external │    │
  │  │  • user_role: executive/manager/employee/client          │    │
  │  │  • formality_adjustment: -0.2 to +0.2                    │    │
  │  │  • detail_preference: more/less/same                     │    │
  │  │                                                          │    │
  │  │  Example:                                                │    │
  │  │  • CEO asking → More formal, high-level summary          │    │
  │  │  • Peer asking → Casual, detailed technical discussion   │    │
  │  │  • New employee → Supportive, explanatory                │    │
  │  │                                                          │    │
  │  │  Output: relationship                                     │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  │  PROMPT ASSEMBLY (Final Stage)                                   │
  │  ┌─────────────────────────────────────────────────────────┐    │
  │  │  cognitive_prompt_assembly_node (langgraph_integration.py:521-657)│
  │  │                                                          │    │
  │  │  Combines all cognitive layers into prompts:              │    │
  │  │                                                          │    │
  │  │  SYSTEM PROMPT:                                           │    │
  │  │  ┌─────────────────────────────────────────────────────┐│    │
  │  │  │ You are [Executive Name], [Role].                    ││    │
  │  │  │                                                       ││    │
  │  │  │ THINKING PATTERNS:                                    ││    │
  │  │  │ {from cognitive_frame}                                ││    │
  │  │  │                                                       ││    │
  │  │  │ RED FLAGS TO WATCH:                                   ││    │
  │  │  │ {from cognitive_frame}                                ││    │
  │  │  │                                                       ││    │
  │  │  │ SIMILAR PAST DECISIONS:                               ││    │
  │  │  │ {from cognitive_frame}                                ││    │
  │  │  │                                                       ││    │
  │  │  │ SITUATION CONTEXT:                                    ││    │
  │  │  │ User seems {emotional_tone}, urgency is {urgency}     ││    │
  │  │  │                                                       ││    │
  │  │  │ COMMUNICATION STYLE:                                  ││    │
  │  │  │ Adapt for {relationship_type}, {formality_level}      ││    │
  │  │  └─────────────────────────────────────────────────────┘│    │
  │  │                                                          │    │
  │  │  USER PROMPT:                                             │    │
  │  │  ┌─────────────────────────────────────────────────────┐│    │
  │  │  │ CONTEXT:                                              ││    │
  │  │  │ {reranked retrieval results}                          ││    │
  │  │  │                                                       ││    │
  │  │  │ QUESTION:                                             ││    │
  │  │  │ {user query}                                          ││    │
  │  │  └─────────────────────────────────────────────────────┘│    │
  │  │                                                          │    │
  │  │  Output: system_prompt, user_prompt                       │    │
  │  └─────────────────────────────────────────────────────────┘    │
  │                                                                  │
  └─────────────────────────────────────────────────────────────────┘

  3.3 Parallel Cognitive Analysis

  For ~40% speedup, layers 2, 4, and 5 run in parallel (langgraph_integration.py:759-879):

  def parallel_cognitive_analysis_node(state):
      """Run frame, situation, relationship in PARALLEL."""

      with ThreadPoolExecutor(max_workers=3) as executor:
          futures = [
              executor.submit(run_frame_analysis),      # Layer 2
              executor.submit(run_situation_analysis),  # Layer 4
              executor.submit(run_relationship_adaptation),  # Layer 5
          ]

          for future in as_completed(futures):
              result, layer_name, elapsed_ms = future.result()
              # Store results in state

  3.4 Inference Engine (Opinion/Decision Queries)

  When retrieval yields no results for opinion/decision queries, the inference engine (langgraph_integration.py:226-300) takes over:    

  Query: "Should we expand to Europe?"
          │
          ▼
  ┌────────────────────────────────────┐
  │      Query Classification           │
  │  nature: "decision"                 │
  │  needs_retrieval: True              │
  │  needs_inference: True              │
  └────────────────────────────────────┘
          │
          ▼
      (Retrieval finds nothing)
          │
          ▼
  ┌────────────────────────────────────┐
  │      Inference Reasoning            │
  │                                     │
  │  applied_values:                    │
  │  • "customer-first thinking"        │
  │  • "data-driven decisions"          │
  │                                     │
  │  red_flags_triggered:               │
  │  • "rushing without market data"    │
  │                                     │
  │  suggested_response_pattern:        │
  │  • "raise_concerns_constructively"  │
  │                                     │
  │  confidence: 0.75                   │
  │  should_escalate: False             │
  └────────────────────────────────────┘
          │
          ▼
  ┌────────────────────────────────────┐
  │   Inference-Based Prompt            │
  │                                     │
  │   "As someone who believes in       │
  │    data-driven decisions, I'd       │
  │    want to see market research      │
  │    before committing to Europe..."  │
  └────────────────────────────────────┘

  3.5 Data Flow Summary

  User Query
      │
      ▼
  cognitive_route ──────► [conversational?] ──► generate_conversational ──► END
      │
      │ [business query]
      ▼
  analyze_query
      │
      ▼
  route_query ──────────► [fast/standard/agentic]
      │
      ▼
  [Retrieval + Fusion + Reranking]
      │
      ▼
  cognitive_lens (Layer 1) ────► Domain affinity reranking
      │
      ▼
  ┌─────────────────────────────────────────┐
  │    PARALLEL EXECUTION (~200ms)          │
  │    ┌─────────────────┐                  │
  │    │ cognitive_frame │ Layer 2          │
  │    │ (reasoning)     │                  │
  │    └─────────────────┘                  │
  │    ┌─────────────────┐                  │
  │    │ situation_analysis│ Layer 4        │
  │    │ (emotion/urgency)│                 │
  │    └─────────────────┘                  │
  │    ┌─────────────────┐                  │
  │    │ relationship_adapt│ Layer 5        │
  │    │ (communication)  │                 │
  │    └─────────────────┘                  │
  └─────────────────────────────────────────┘
      │
      ▼
  cognitive_prompt_assembly
      │
      ▼
  generate_[fast|standard] ──► LLM ──► Response
      │
      ▼
  END

  This architecture ensures the AI executive:
  1. Routes intelligently (skip retrieval for small talk)
  2. Thinks like the executive (domain affinity, reasoning patterns)
  3. Understands context (emotion, urgency, implicit needs)
  4. Adapts communication (based on who's asking)
  5. Can reason without data (inference engine for opinions) 