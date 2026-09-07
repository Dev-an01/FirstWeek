🔬 RAG SYSTEM - COMPLETE INNER MECHANICS DEEP DIVE

  EXECUTIVE SUMMARY

  The RAG system is a sophisticated enterprise decision intelligence platform with:
  - 3-path query routing (fast/standard/agentic)
  - 5-stage conversation engine for authentic executive voice
  - Hybrid retrieval (vector + graph + memory fusion)
  - ReAct reasoning loop for complex analysis
  - 6-layer Cognitive Twin architecture (optional)

  ---
  1. COMPLETE REQUEST LIFECYCLE

  Entry Point: /api/v1/chat (main.py:879-1114)

  POST /api/v1/chat
      │
      ├─[1] UTF8EncodingMiddleware (lines 606-647)
      │     └─ Decode body, detect encoding issues, log warnings
      │
      ├─[2] Request Logging Middleware (lines 687-708)
      │     └─ Generate request_id (8-char UUID), start timer
      │
      ├─[3] Profile ID Normalization (lines 917-938)
      │     └─ "sample_profile" → "sample_profile"
      │     └─ Validate against known profiles
      │
      ├─[4] Query Routing (lines 941-951)
      │     └─ QueryRouter.route() → RouteDecision(path, confidence, reasoning)
      │     └─ Pattern matching + feature extraction (NO LLM)
      │
      ├─[5] Parallel Retrieval (lines 953-990)
      │     ├─ VectorSearchEngine.search() → vector_results
      │     ├─ GraphContextProvider.discover_context() → graph_context
      │     └─ SessionManager.get_or_create_session() → session_id
      │
      ├─[6] LLM Generation (lines 992-1006)
      │     └─ LLMOrchestrator.generate() → response
      │         ├─ Handler selection (Fast/Standard/Agentic)
      │         ├─ Prompt building (system + user)
      │         ├─ LLM API call
      │         └─ Response formatting
      │
      ├─[7] Response Formatting (lines 1027-1076)
      │     └─ Extract citations, build metadata, validate word count
      │
      ├─[8] Session Storage (lines 1083-1097)
      │     └─ Store conversation turn for multi-turn memory
      │
      └─[9] Return ChatResponse (lines 1099-1107)

  ---
  2. QUERY ROUTING - EXACT MECHANICS

  Pattern-Based Classification (query_routing/router.py)

  NO LLM involved - pure regex + heuristics (~35-45ms)

  FAST_PATTERNS = ["what is", "who is", "define", "explain briefly", "list", "show me"]
  STANDARD_PATTERNS = ["should we", "recommend", "advise", "how should", "best practice", "your opinion"]
  AGENTIC_PATTERNS = ["compare", "analyze", "evaluate", "trade-off", "comprehensive", "deep dive"]

  Scoring Algorithm

  # FAST PATH (simple factual)
  if simple_pattern_matches > 0:     scores['fast'] += 0.5
  if word_count <= 10:               scores['fast'] += 0.3
  if entity_count <= 2:              scores['fast'] += 0.2

  # STANDARD PATH (decision/recommendation)
  if standard_pattern_matches > 0:   scores['standard'] += 0.6
  if 6 < word_count <= 20:           scores['standard'] += 0.2
  if 2 < entity_count <= 5:          scores['standard'] += 0.2

  # AGENTIC PATH (complex analysis)
  if agentic_pattern_matches > 0:    scores['agentic'] += 0.7
  if word_count > 30:                scores['agentic'] += 0.3
  if entity_count > 5:               scores['agentic'] += 0.3
  if has_comparison:                 scores['agentic'] += 0.4
  if has_analysis_request:           scores['agentic'] += 0.4
  if needs_decomposition:            scores['agentic'] += 0.4

  # SHORT QUERY PENALTY
  if word_count < 15 and scores['agentic'] > 0:
      scores['agentic'] *= 0.5  # Halve agentic score

  Thresholds (config/llm_config.yaml)
  ┌──────────────────────────┬───────┬─────────────────────────────────────────────┐
  │        Threshold         │ Value │                   Purpose                   │
  ├──────────────────────────┼───────┼─────────────────────────────────────────────┤
  │ word_count_for_agentic   │ 30    │ Queries >30 words → agentic consideration   │
  ├──────────────────────────┼───────┼─────────────────────────────────────────────┤
  │ entity_count_for_agentic │ 5     │ Queries >5 entities → agentic consideration │
  ├──────────────────────────┼───────┼─────────────────────────────────────────────┤
  │ min_confidence           │ 0.5   │ Below this → default to standard            │
  └──────────────────────────┴───────┴─────────────────────────────────────────────┘
  ---
  3. VECTOR SEARCH - EXACT SQL & SCORING

  PostgreSQL pgvector Query (postgres_client.py:149-173)

  SELECT
      id, source_id, source_type, text_content,
      embedding <=> $query_embedding::vector AS distance,
      1 - (embedding <=> $query_embedding::vector) AS similarity_score,
      created_at
  FROM embeddings
  WHERE
      source_type = ANY($types)
      AND source_id = ANY($candidate_ids)  -- Graph constraint (if any)
      AND (1 - (embedding <=> $query_embedding::vector)) >= $min_score
  ORDER BY embedding <=> $query_embedding ASC
  LIMIT $top_k

  Embedding Cache (2-Level)

  Query Text
      ↓
  L1 Cache (In-Memory LRU, 1000 entries)
      ├─ HIT: Return cached embedding
      └─ MISS ↓
  L2 Cache (Redis, 7-day TTL)
      ├─ HIT: Promote to L1, return
      └─ MISS ↓
  Generate Embedding (BAAI/bge-m3, 1024-dim)
      ↓
  Store in L1 + L2

  RBAC Filtering (rbac_filter.py)

  ROLE_SCOPES = {
      'admin':     ['public', 'internal', 'executive', 'confidential'],
      'executive': ['public', 'internal', 'executive'],
      'employee':  ['public', 'internal'],
      'guest':     ['public']
  }

  # Scope inference by source_type:
  # executive_profile → 'executive'
  # decision_case with confidence > 0.8 → 'executive'
  # policy with confidentiality field → direct mapping

  ---
  4. GRAPH CONTEXT - CYPHER & SCORING

  Entity Extraction (Hybrid Approach)

  Query Text
      ↓
  [1] Domain Patterns (100% confidence)
      └─ POLICY-[A-Z]{2,4}-\d{3}, DC_[A-Z]+_\d{3}, exec_\d{3}_test
      ↓
  [2] GLiNER (Multilingual, GPU, ~50-80ms)
      └─ Labels: Person, Company, Organization, Location, Product, Policy, Decision
      └─ Threshold: 0.3
      ↓
  [3] spaCy (Fallback, ~100-150ms)
      └─ en_core_web_lg model
      └─ Default confidence: 0.8
      ↓
  [4] Deduplicate + Neo4j Matching

  Cypher Traversal Query

  MATCH (anchor {id: $anchor_id})
  MATCH path = (anchor)-[*1..$max_hops]-(doc)
  WHERE (doc:Decision OR doc:Policy)
    AND (doc.confidentiality IS NULL OR doc.confidentiality IN $allowed_scopes)
  WITH DISTINCT doc,
       length(shortestPath((anchor)-[*]-(doc))) AS distance
  RETURN doc.id AS doc_id, distance
  ORDER BY distance ASC
  LIMIT $max_candidates

  Graph Proximity Score

  def calculate_graph_score(distance: int) -> float:
      if distance <= 0: return 1.0
      if distance >= 5: return 0.1
      return 1.0 / distance  # 1 hop → 1.0, 2 hops → 0.5, 3 hops → 0.33

  Hybrid Score Formula

  hybrid_score = 0.6 × vector_similarity + 0.4 × graph_proximity

  ---
  5. HYBRID RETRIEVAL - FUSION & RERANKING

  Result Fusion (result_fusion.py)

  Query-Type Dependent Weights:
  ┌──────────────┬────────┬───────┬────────┐
  │  Query Type  │ Vector │ Graph │ Memory │
  ├──────────────┼────────┼───────┼────────┤
  │ factual      │ 80%    │ 15%   │ 5%     │
  ├──────────────┼────────┼───────┼────────┤
  │ decision     │ 35%    │ 25%   │ 40%    │
  ├──────────────┼────────┼───────┼────────┤
  │ analysis     │ 45%    │ 30%   │ 25%    │
  ├──────────────┼────────┼───────┼────────┤
  │ relationship │ 30%    │ 65%   │ 5%     │
  └──────────────┴────────┴───────┴────────┘
  Multi-Source Boost:
  - Found in 2 sources: +10% composite boost
  - Found in 3+ sources: +15% composite boost

  Memory Search (5-Signal Scoring)

  memory_score = (
      0.40 × semantic_similarity +     # Cosine distance
      0.25 × temporal_decay +          # exp(-days/60)
      0.20 × decision_importance       # Pre-calculated
  ) × feedback_multiplier ×            # 0.5 (negative) to 1.2 (positive)
    user_context_multiplier            # 1.0 to 1.1

  Adaptive Reranker (3 Strategies)
  ┌─────────────┬──────────────────┬─────────┬──────────────────────────────────────┐
  │  Strategy   │       When       │ Latency │                Method                │
  ├─────────────┼──────────────────┼─────────┼──────────────────────────────────────┤
  │ Lightweight │ result_count ≤ 5 │ ~50ms   │ Sort + MMR diversity                 │
  ├─────────────┼──────────────────┼─────────┼──────────────────────────────────────┤
  │ Medium      │ 5 < count ≤ 15   │ ~100ms  │ Cross-encoder on top-10, blend 60/40 │
  ├─────────────┼──────────────────┼─────────┼──────────────────────────────────────┤
  │ Full        │ count > 15       │ ~200ms  │ Cross-encoder on all 40, blend 30/70 │
  └─────────────┴──────────────────┴─────────┴──────────────────────────────────────┘
  ---
  6. CONVERSATION ENGINE - 5-STAGE PIPELINE

  Stage 1: Context Analyzer (~5-8ms)

  Classifies:
  - Theme: security/budget/people/strategy/technical/operations/customer
  - Urgency: crisis/urgent/routine/planning
  - Emotion: stressed/tense/neutral/positive/celebratory
  - Query Type: factual/decision/emotional/analytical
  - Turn Type: new_topic/followup/clarification

  Stage 2: Response Calibrator (~2-3ms)

  From Voiceprint:
  warmth = style_markers.get("warmth", 5)      # 1-10
  directness = style_markers.get("directness", 5)
  formality = style_markers.get("formality", 5)

  # Tone determination
  if warmth >= 7 and directness >= 7: tone = "warm_direct"
  elif warmth >= 7: tone = "warm"
  elif directness >= 7: tone = "direct"
  else: tone = "neutral"

  Rules Applied:
  - Situation rules (crisis → serious tone)
  - Multi-turn rules (followup → shorter response)
  - Executive rules (per-exec customization)

  Stage 3: Semantic Example Selector (~30ms)

  Multi-Signal Scoring:
  total = (
      0.70 × semantic_similarity +  # Embedding cosine
      0.10 × type_bonus +           # email/slack match
      0.10 × length_bonus +         # Word count fit
      0.10 × tone_bonus             # Emotion match
  )

  Stage 4: Precedent Selector (~5ms)

  For Decision Queries Only:
  total = (
      0.40 × category_score +       # Intent-aware category match
      0.40 × semantic_similarity +  # Reuses query embedding
      0.20 × recency_score          # Exponential decay (365-day half-life)
  )

  Stage 5: Prompt Assembler (~3ms)

  Section Order:
  1. Reasoning (cognitive scaffolding - ALWAYS first)
  2. Identity (voiceprint personality injection)
  3. Conversation Context (if session)
  4. Example (communication style)
  5. Calibration (tone guidance)
  6. Values (core reasoning patterns)
  7. Precedent (past decisions if applicable)
  8. Instructions (word limits, anti-AI rules)

  ---
  7. LLM ORCHESTRATOR - PATH HANDLERS

  Fast Path Handler (<1.5s)

  max_results = 5
  # Vector results only
  # No graph, no precedents
  # Optimized for speed

  Standard Path Handler (<2.5s)

  max_results = 10
  graph_results = 5
  precedents = 3
  # Full context integration
  # Balanced for business queries

  Agentic Path Handler (<5s)

  max_results = 15
  graph_results = 10
  precedents = 5
  multi_hop_enabled = True
  max_react_steps = 5
  # Document summarization (prevents 413 errors)
  # ReAct loop with tool integration

  ---
  8. ReAct REASONING LOOP (Agentic Path)

  Loop Structure

  react_think → react_act → react_observe → should_continue?
       ↑                                           │
       └─────────── [continue] ──────────────────┘
                         │
                    [finalize]
                         ↓
                 react_finalize → END

  Available Tools
  ┌──────────────┬─────────────────────────────┬─────────────────────────┐
  │     Tool     │           Purpose           │       Data Source       │
  ├──────────────┼─────────────────────────────┼─────────────────────────┤
  │ SEARCH       │ Hybrid retrieval            │ Vector + Graph + Memory │
  ├──────────────┼─────────────────────────────┼─────────────────────────┤
  │ ANALYZE      │ Examine current context     │ State.reranked_results  │
  ├──────────────┼─────────────────────────────┼─────────────────────────┤
  │ RELATIONSHIP │ Entity connections          │ Neo4j graph             │
  ├──────────────┼─────────────────────────────┼─────────────────────────┤
  │ PRECEDENT    │ Similar past decisions      │ PostgreSQL + pgvector   │
  ├──────────────┼─────────────────────────────┼─────────────────────────┤
  │ PATTERN      │ Executive decision patterns │ decision_cases table    │
  ├──────────────┼─────────────────────────────┼─────────────────────────┤
  │ FINALIZE     │ Exit loop                   │ -                       │
  └──────────────┴─────────────────────────────┴─────────────────────────┘
  Confidence Calculation (Capped at 0.70)

  # Factor 1: Result Count (0-0.15)
  # Factor 2: Specific Data (0-0.15) - numbers, dates, IDs
  # Factor 3: Content Diversity (0-0.10)
  # Factor 4: Step Progression (0-0.30) - MOST IMPORTANT
  #   5 steps → 0.30, 4 steps → 0.22, 3 steps → 0.15
  # Factor 5: Error Penalty (-0.10)

  # Only FINALIZE action = 1.0 confidence

  Continuation Logic

  should_finalize = (
      confidence >= 0.85 or           # High confidence
      iterations >= max_steps (6) or  # Hard limit
      force_finalize or               # Error condition
      last_action == "finalize"       # Explicit finalize
  )

  # ENFORCE minimum 4 iterations before allowing finalization
  if should_finalize and iterations < 4:
      decision = "continue"  # Need more analysis

  ---
  9. LANGGRAPH WORKFLOW - STATE FLOW

  Complete Graph Structure

  START
    ↓
  [cognitive_route] ─────────────────────────────────────┐
    ├─ [conversational] → generate_conversational → END  │
    └─ [retrieval] ↓                                     │
  [analyze_query]                                        │
    ↓                                                    │
  [route_query]                                          │
    ├─ [fast] → retrieve → cognitive_lens → generate → END
    ├─ [standard] → graphrag → parallel_retrieve → fuse → rerank
    │              → cognitive_lens → cognitive_frame
    │              → situation_analysis → relationship_adaptation
    │              → prompt_assembly → generate → END
    └─ [agentic] → graphrag → parallel_retrieve → fuse → rerank
                 → react_think → react_act → react_observe
                 → should_continue?
                     ├─ [continue] → (loop)
                     └─ [finalize] → react_finalize → END

  State Serialization (CRITICAL)

  def sanitize_node(func):
      """Convert numpy types to Python native for msgpack serialization."""
      @wraps(func)
      def wrapper(state):
          result = func(state)
          return _sanitize_state_for_serialization(result)
      return wrapper

  # Applied to ALL nodes to enable LangGraph checkpointing

  ---
  10. PERFORMANCE TARGETS & LATENCIES
  ┌─────────────────────────┬────────┬──────────────────┐
  │        Component        │ Target │     Typical      │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Query Routing           │ <50ms  │ 35-45ms          │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Entity Extraction       │ <150ms │ 50-80ms (GLiNER) │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Vector Search           │ <500ms │ 200-300ms        │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Graph Traversal         │ <100ms │ 50-85ms          │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Memory Search           │ <200ms │ 100-150ms        │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Result Fusion           │ <50ms  │ 20-30ms          │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Reranking (lightweight) │ ~50ms  │ 40-50ms          │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Reranking (full)        │ ~200ms │ 150-200ms        │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Conversation Engine     │ <50ms  │ 45-50ms          │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Fast Path Total         │ <1.5s  │ 0.8-1.2s         │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Standard Path Total     │ <2.5s  │ 1.5-2.0s         │
  ├─────────────────────────┼────────┼──────────────────┤
  │ Agentic Path Total      │ <5s    │ 3-4s             │
  └─────────────────────────┴────────┴──────────────────┘
  ---
  11. KEY ARCHITECTURAL PATTERNS

  1. Factory Pattern - LLMClientFactory for multi-provider support
  2. Singleton Pattern - ProfileManager, EmbeddingModel (GPU memory)
  3. Decorator Pattern - @traceable, sanitize_node
  4. Strategy Pattern - Path handlers, reranking strategies
  5. State Machine - LangGraph workflow
  6. Chain of Responsibility - 5-stage prompt assembly
  7. Observer Pattern - Observability middleware
  8. Graceful Degradation - Fallbacks at every layer

  ---
  12. DATA TRANSFORMATION SUMMARY

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
  This represents a complete deep understanding of the RAG system's inner mechanics, data flows, and transformations across all components. Every file contributes to this pipeline, from query preprocessing through retrieval, fusion, prompt engineering, and response generation.      