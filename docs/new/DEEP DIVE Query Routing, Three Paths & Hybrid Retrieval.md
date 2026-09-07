 1. QUERY ROUTING SYSTEM

  1.1 Router Architecture (query_routing/router.py & hybrid_retrieval/query_router.py)

  The query router classifies incoming queries WITHOUT ANY LLM CALL (pattern matching + heuristics) for zero-latency routing decisions. 

  USER QUERY → Feature Extraction → Path Score Calculation → Decision → Route

  1.2 Feature Extraction

  Features extracted from query:
  ┌──────────────────────────┬────────────────────────────────────────────────────┬─────────────────────────────────┐
  │         Feature          │                    How Detected                    │             Example             │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ word_count               │ len(query.split())                                 │ "What is the policy?" → 4       │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ entity_count             │ Capitalized words or spaCy NER                     │ "Should Acme Corp approve?" → 1 │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ fast_pattern_matches     │ Regex: what is, who is, define                     │ "What is discount policy?" → 1  │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ standard_pattern_matches │ Regex: should we, recommend, advise                │ "Should we approve?" → 1        │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ agentic_pattern_matches  │ Regex: compare, analyze, evaluate                  │ "Compare options A and B" → 1   │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ has_comparison           │ Regex: compare, versus, vs                         │ Boolean                         │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ has_analysis_request     │ Regex: analyze, evaluate, assess                   │ Boolean                         │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ has_multiple_questions   │ query.count('?') > 1                               │ Boolean                         │
  ├──────────────────────────┼────────────────────────────────────────────────────┼─────────────────────────────────┤
  │ needs_decomposition      │ Conjunction count, entity count, query length >150 │ Boolean                         │
  └──────────────────────────┴────────────────────────────────────────────────────┴─────────────────────────────────┘
  1.3 Path Score Calculation

  Scoring Algorithm:
  # FAST PATH (simple factual)
  if fast_pattern_matches > 0:     score['fast'] += 0.5
  if word_count <= 10:              score['fast'] += 0.3
  if entity_count <= 2:             score['fast'] += 0.2

  # STANDARD PATH (decisions/recommendations)
  if standard_pattern_matches > 0:  score['standard'] += 0.6  # Strong signal
  if 6 < word_count <= 20:          score['standard'] += 0.2
  if 2 < entity_count <= 5:         score['standard'] += 0.2

  # AGENTIC PATH (complex analysis)
  if agentic_pattern_matches > 0:   score['agentic'] += 0.7  # Very strong
  if word_count > 30:               score['agentic'] += 0.2
  if entity_count > 5:              score['agentic'] += 0.3
  if has_comparison:                score['agentic'] += 0.5  # Strong signal
  if has_analysis_request:          score['agentic'] += 0.5
  if needs_decomposition:           score['agentic'] += 0.4

  # ANTI-OVERROUTING: Penalty for short queries claiming agentic
  if word_count < 15 and score['agentic'] > 0:
      score['agentic'] *= 0.5  # Reduce false positives

  1.4 Path Decision Output

  RouteDecision(
      path="standard",           # fast | standard | agentic
      complexity="medium",       # simple | medium | complex
      confidence=0.85,           # 0-1 score
      reasoning="Chose standard path: decision/recommendation pattern",
      features={...},            # All extracted features
      processing_time_ms=2500,   # Target latency
      cost_estimate=0.06         # ~$0.06 per query
  )

  ---
  2. THE THREE PROCESSING PATHS

  2.1 FAST PATH (60% of queries, 0.8-1.5s target)

  Use Cases: "What is...", "Who is...", "Define...", "List..."

  ┌─────────────────────────────────────────────────────────────────┐
  │                         FAST PATH                               │
  ├─────────────────────────────────────────────────────────────────┤
  │  Query → Vector Search (top 5) → Lightweight Rerank → LLM      │
  │                                                                 │
  │  Components Used:                                               │
  │  ✅ Vector search (pgvector)                                    │
  │  ✅ Graph-light (basic entity extraction only)                  │
  │  ❌ Memory search (SKIPPED for speed)                           │
  │  ✅ Lightweight reranking (~50ms)                               │
  │                                                                 │
  │  LLM Settings:                                                  │
  │  • Temperature: 0.35 (strict persona adherence)                 │
  │  • Max tokens: 1000                                             │
  │  • Timeout: 15 seconds                                          │
  │                                                                 │
  │  Cost: ~$0.02/query                                             │
  └─────────────────────────────────────────────────────────────────┘

  FastPathHandler Flow:
  1. Prepare context (top 5 results only)
  2. Build prompts with TwoStagePromptBuilder or DualStreamPromptBuilder
  3. Single LLM call
  4. Format response with citations

  2.2 STANDARD PATH (30% of queries, 1.5-2.5s target)

  Use Cases: "Should we...", "Recommend...", "How to handle...", opinion queries

  ┌─────────────────────────────────────────────────────────────────┐
  │                       STANDARD PATH                             │
  ├─────────────────────────────────────────────────────────────────┤
  │  Query → GraphRAG → Parallel Retrieval → Fuse → Rerank → LLM   │
  │                                                                 │
  │  PARALLEL EXECUTION:                                            │
  │  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐  │
  │  │ Vector Search  │   │  Graph Search  │   │ Memory Search  │  │
  │  │   (top 20)     │   │   (Neo4j)      │   │  (5-signal)    │  │
  │  └───────┬────────┘   └───────┬────────┘   └───────┬────────┘  │
  │          │                    │                    │            │
  │          └────────────────────┼────────────────────┘            │
  │                               ▼                                 │
  │                        Result Fusion                            │
  │                    (60% vec + 30% graph + 10% mem)              │
  │                               ▼                                 │
  │                      Medium Reranking (~100ms)                  │
  │                    (cross-encoder on top 10)                    │
  │                               ▼                                 │
  │                          LLM Generation                         │
  │                                                                 │
  │  Components Used:                                               │
  │  ✅ Vector search (pgvector, top 10)                            │
  │  ✅ Full graph context (Neo4j relationships)                    │
  │  ✅ Memory search (episodic + precedents)                       │
  │  ✅ GraphRAG global search (for broad themes)                   │
  │  ✅ Medium reranking (60% original + 40% cross-encoder)         │
  │                                                                 │
  │  LLM Settings:                                                  │
  │  • Temperature: 0.40                                            │
  │  • Max tokens: 1500                                             │
  │  • Timeout: 25 seconds                                          │
  │                                                                 │
  │  Cost: ~$0.06/query                                             │
  └─────────────────────────────────────────────────────────────────┘

  StandardPathHandler Flow:
  1. Prepare context (top 10 results + graph + precedents)
  2. Build prompts with full context
  3. Include graph relationships and memory
  4. Single LLM call with comprehensive context
  5. Format response with detailed citations

  2.3 AGENTIC PATH (10% of queries, 3-5s target)

  Use Cases: "Compare...", "Analyze trade-offs...", "Evaluate...", complex multi-hop

  ┌─────────────────────────────────────────────────────────────────┐
  │                       AGENTIC PATH                              │
  ├─────────────────────────────────────────────────────────────────┤
  │  Query → GraphRAG → Parallel Retrieval → Fuse → Full Rerank    │
  │                          ↓                                      │
  │              ┌───────────────────────────────────┐              │
  │              │         ReAct LOOP               │              │
  │              │  ┌─────────────────────────────┐ │              │
  │              │  │        THINK                │ │              │
  │              │  │ "I need to find discount    │ │              │
  │              │  │  policy precedents..."      │ │              │
  │              │  └──────────┬──────────────────┘ │              │
  │              │             ▼                    │              │
  │              │  ┌─────────────────────────────┐ │              │
  │              │  │         ACT                 │ │              │
  │              │  │ search_context("discount    │ │              │
  │              │  │  precedent 20%")            │ │              │
  │              │  └──────────┬──────────────────┘ │              │
  │              │             ▼                    │              │
  │              │  ┌─────────────────────────────┐ │              │
  │              │  │       OBSERVE               │ │              │
  │              │  │ "Found 3 similar decisions: │ │              │
  │              │  │  DC_001, DC_003, DC_007"    │ │              │
  │              │  └──────────┬──────────────────┘ │              │
  │              │             ▼                    │              │
  │              │  ┌─────────────────────────────┐ │              │
  │              │  │    SHOULD CONTINUE?         │ │              │
  │              │  │ confidence >= 0.7?          │ │              │
  │              │  │ steps < max_steps (5)?      │ │              │
  │              │  └──────────┬──────────────────┘ │              │
  │              │       YES   │   NO               │              │
  │              │       ↓     │    ↓               │              │
  │              │    (loop)   │  FINALIZE          │              │
  │              └─────────────────────────────────-┘              │
  │                            ↓                                    │
  │                    Final Answer Generation                      │
  │                                                                 │
  │  Components Used:                                               │
  │  ✅ Vector search (pgvector, top 15)                            │
  │  ✅ Full graph context (Neo4j with extended traversal)          │
  │  ✅ Memory search (extended 365-day window)                     │
  │  ✅ GraphRAG global search                                      │
  │  ✅ Full reranking (30% original + 70% cross-encoder)           │
  │  ✅ Document summarization (token budget management)            │
  │  ✅ ReAct multi-hop reasoning loop                              │
  │  ✅ Profile-based optimizations                                 │
  │                                                                 │
  │  LLM Settings:                                                  │
  │  • Temperature: 0.45                                            │
  │  • Max tokens: 2000                                             │
  │  • Timeout: 45 seconds                                          │
  │                                                                 │
  │  Cost: ~$0.12/query                                             │
  └─────────────────────────────────────────────────────────────────┘

  AgenticPathHandler Flow:
  1. Document Summarization - Prevent token overflow (target 300 tokens/doc)
  2. Profile Loading - Get executive decision patterns
  3. Query Expansion - Add related business terms
  4. Parallel Retrieval - Vector + Graph + Memory (extended windows)
  5. Result Fusion - Profile-aware weights
  6. Full Reranking - 70% cross-encoder weight
  7. ReAct Loop (if multi_hop_enabled):
    - Think → Act → Observe → Continue/Finalize
    - Max 5 iterations, confidence threshold 0.7
  8. Final Answer Generation

  ---
  3. HYBRID RETRIEVAL SYSTEM

  3.1 UnifiedRetrieval Orchestration (unified_retrieval.py)

                           ┌─────────────────────────────────┐
                           │      UnifiedRetrieval           │
                           │                                 │
  Query ──────────────────▶│  1. Route Query (router.route)  │
                           │  2. Select Path                 │
                           │  3. Execute Path-Specific       │
                           │     Retrieval                   │
                           │  4. Return Results + Metadata   │
                           └─────────────────────────────────┘
                                         │
            ┌────────────────────────────┼────────────────────────────┐
            ▼                            ▼                            ▼
      ┌───────────┐              ┌───────────────┐            ┌───────────────┐
      │ FAST PATH │              │ STANDARD PATH │            │ AGENTIC PATH  │
      │           │              │               │            │               │
      │ • vector  │              │ • vector      │            │ • vector ×3   │
      │ • graph   │              │ • graph       │            │ • graph       │
      │   light   │              │ • memory      │            │ • memory ext  │
      │ • rerank  │              │ • fuse        │            │ • fuse        │
      │   light   │              │ • rerank med  │            │ • rerank full │
      └───────────┘              └───────────────┘            │ • ReAct loop  │
                                                             └───────────────┘

  3.2 Result Fusion (result_fusion.py)

  Fusion Formula:
  # Composite weights (configurable per query type)
  weights = {
      "vector": 0.60,   # Primary semantic signal
      "graph":  0.30,   # Relationship context
      "memory": 0.10    # Historical precedents
  }

  # For each document:
  composite_score = (
      weights["vector"] * vector_score +
      weights["graph"]  * graph_score +
      weights["memory"] * memory_score
  )

  # Multi-source boost (found in 2+ sources)
  if len(found_in) >= 2:
      boost = 0.10 if len(found_in) == 2 else 0.15
      composite_score = min(1.0, composite_score + boost)

  Query-Type Adaptive Weights:
  ┌────────────────┬────────┬───────┬────────┬─────────────────────┐
  │   Query Type   │ Vector │ Graph │ Memory │      Use Case       │
  ├────────────────┼────────┼───────┼────────┼─────────────────────┤
  │ Factual Lookup │ 80%    │ 15%   │ 5%     │ Simple facts        │
  ├────────────────┼────────┼───────┼────────┼─────────────────────┤
  │ Relationship   │ 30%    │ 65%   │ 5%     │ Entity connections  │
  ├────────────────┼────────┼───────┼────────┼─────────────────────┤
  │ Decision       │ 35%    │ 25%   │ 40%    │ Need precedents     │
  ├────────────────┼────────┼───────┼────────┼─────────────────────┤
  │ Procedural     │ 30%    │ 20%   │ 50%    │ How-to with history │
  ├────────────────┼────────┼───────┼────────┼─────────────────────┤
  │ Comparison     │ 40%    │ 35%   │ 25%    │ Comparing entities  │
  ├────────────────┼────────┼───────┼────────┼─────────────────────┤
  │ Conversational │ 30%    │ 10%   │ 60%    │ Past conversation   │
  └────────────────┴────────┴───────┴────────┴─────────────────────┘
  3.3 Adaptive Reranking (adaptive_reranker.py)

  Quality Assessment (triggers reranking strategy):
  def assess_result_quality(results):
      top_score = results[0]["composite_score"]
      fifth_score = results[4]["composite_score"]
      gap = top_score - fifth_score

      # HIGH: Clear winner → Lightweight
      if top_score > 0.85 and gap > 0.25:
          return "HIGH"

      # MEDIUM: Reasonable results → Medium reranking
      elif 0.70 <= top_score <= 0.85 and 0.15 <= gap <= 0.25:
          return "MEDIUM"

      # LOW: Unclear best result → Full reranking
      else:
          return "LOW"

  Three Reranking Strategies:
  ┌─────────────┬────────┬────────────────┬───────────────────────────────────────┬───────────────┐
  │  Strategy   │ Target │  Distribution  │               Pipeline                │ Cross-Encoder │
  ├─────────────┼────────┼────────────────┼───────────────────────────────────────┼───────────────┤
  │ Lightweight │ 50ms   │ 40% of queries │ Normalize → Source Weights → MMR      │ No            │
  ├─────────────┼────────┼────────────────┼───────────────────────────────────────┼───────────────┤
  │ Medium      │ 100ms  │ 35% of queries │ Lightweight + Cross-encoder (top 10)  │ 60/40 blend   │
  ├─────────────┼────────┼────────────────┼───────────────────────────────────────┼───────────────┤
  │ Full        │ 200ms  │ 25% of queries │ Complete pipeline (all 40 candidates) │ 30/70 blend   │
  └─────────────┴────────┴────────────────┴───────────────────────────────────────┴───────────────┘
  Cross-Encoder Model: cross-encoder/ms-marco-MiniLM-L12-v2

  Source Weights Applied:
  - Policy documents: 1.2x boost
  - Decision precedents: 1.1x boost
  - Other: 1.0x (no boost)

  ---
  4. LANGGRAPH WORKFLOW (langgraph_workflow/graph.py)

  4.1 Complete Workflow Graph

                                      START
                                        │
                          ┌─────────────▼─────────────┐
                          │     cognitive_route       │  (Layer 0: Intent Detection)
                          └─────────────┬─────────────┘
                                        │
                      ┌─────────────────┴─────────────────┐
                      │                                   │
            [conversational]                      [retrieval]
                      │                                   │
                      ▼                                   ▼
           ┌──────────────────┐               ┌──────────────────┐
           │generate_convers. │               │   analyze_query  │
           └────────┬─────────┘               └────────┬─────────┘
                    │                                  │
                    ▼                                  ▼
                   END                        ┌──────────────────┐
                                             │    route_query   │
                                             └────────┬─────────┘
                                                      │
                      ┌───────────────────────────────┼───────────────────────────────┐
                      │                               │                               │
                [fast]│                        [standard]                      [agentic]
                      │                               │                               │
                      ▼                               ▼                               ▼
           ┌──────────────────┐           ┌──────────────────┐            ┌──────────────────┐
           │retrieve_unified  │           │retrieve_graphrag │            │retrieve_graphrag │
           │     _fast        │           │    _standard     │            │    _agentic      │
           └────────┬─────────┘           └────────┬─────────┘            └────────┬─────────┘
                    │                               │                               │
                    │                               ▼                               ▼
                    │                   ┌──────────────────┐            ┌──────────────────┐
                    │                   │retrieve_parallel │            │retrieve_parallel │
                    │                   │    _standard     │            │    _agentic      │
                    │                   └────────┬─────────┘            └────────┬─────────┘
                    │                            │                               │
                    │                            ▼                               ▼
                    │                   ┌──────────────────┐            ┌──────────────────┐
                    │                   │ fuse_results_std │            │fuse_results_agent│
                    │                   └────────┬─────────┘            └────────┬─────────┘
                    │                            │                               │
                    │                            ▼                               ▼
                    │                   ┌──────────────────┐            ┌──────────────────┐
                    │                   │rerank_results_std│            │rerank_results_ag │
                    │                   └────────┬─────────┘            └────────┬─────────┘
                    │                            │                               │
                    │    ┌───────────────────────┘                               │
                    │    │ COGNITIVE TWIN LAYERS                                 │
                    │    │ (if enabled)                                          │
                    │    ▼                                                       │
           ┌────────────────────┐                                               │
           │cognitive_lens_fast │                                               │
           └────────┬───────────┘                                               │
                    │                   ┌──────────────────┐                     │
                    │                   │cognitive_lens_std│                     │
                    │                   └────────┬─────────┘                     │
                    │                            ▼                               │
                    │                   ┌──────────────────┐                     │
                    │                   │cognitive_frame   │                     │
                    │                   └────────┬─────────┘                     │
                    │                            ▼                               │
                    │                   ┌──────────────────┐                     │
                    │                   │situation_analysis│                     │
                    │                   └────────┬─────────┘                     │
                    │                            ▼                               │
                    │                   ┌──────────────────┐                     │
                    │                   │relationship_adapt│                     │
                    │                   └────────┬─────────┘                     │
                    │                            ▼                               │
                    │                   ┌──────────────────┐                     │
                    │                   │prompt_assembly   │                     │
                    │                   └────────┬─────────┘                     │
                    │                            │                               │
                    ▼                            ▼                               ▼
           ┌──────────────────┐       ┌──────────────────┐           ┌──────────────────┐
           │  generate_fast   │       │ generate_standard│           │   react_think    │
           └────────┬─────────┘       └────────┬─────────┘           └────────┬─────────┘
                    │                          │                              │
                    │                          │                              ▼
                    │                          │                    ┌──────────────────┐
                    │                          │                    │    react_act     │
                    │                          │                    └────────┬─────────┘
                    │                          │                             │
                    │                          │                             ▼
                    │                          │                    ┌──────────────────┐
                    │                          │                    │   react_observe  │
                    │                          │                    └────────┬─────────┘
                    │                          │                             │
                    │                          │              ┌──────────────┴──────────────┐
                    │                          │        [continue]                    [finalize]
                    │                          │              │                             │
                    │                          │              │ (loop back)                 ▼
                    │                          │              │                    ┌──────────────────┐
                    │                          │              │                    │  react_finalize  │
                    │                          │              │                    └────────┬─────────┘
                    │                          │              │                             │
                    ▼                          ▼              ▼                             ▼
                  ╔══════════════════════════════════════════════════════════════════════════╗
                  ║                                  END                                     ║
                  ╚══════════════════════════════════════════════════════════════════════════╝

  4.2 Cognitive Twin Integration (6-Layer Architecture)

  When cognitive twin is enabled, additional processing layers enhance responses:
  ┌───────┬─────────────────────────┬────────────────────────────────────────────────┐
  │ Layer │          Node           │                    Function                    │
  ├───────┼─────────────────────────┼────────────────────────────────────────────────┤
  │ 0     │ cognitive_route         │ Intent detection, skip retrieval for greetings │
  ├───────┼─────────────────────────┼────────────────────────────────────────────────┤
  │ 1     │ cognitive_lens          │ Domain affinity reranking based on profile     │
  ├───────┼─────────────────────────┼────────────────────────────────────────────────┤
  │ 2     │ cognitive_frame         │ Reasoning patterns, red flags, decision cases  │
  ├───────┼─────────────────────────┼────────────────────────────────────────────────┤
  │ 4     │ situation_analysis      │ Emotional tone, urgency, implicit needs        │
  ├───────┼─────────────────────────┼────────────────────────────────────────────────┤
  │ 5     │ relationship_adaptation │ Communication style based on user role         │
  ├───────┼─────────────────────────┼────────────────────────────────────────────────┤
  │ -     │ prompt_assembly         │ Combines all cognitive outputs                 │
  └───────┴─────────────────────────┴────────────────────────────────────────────────┘
  ---
  5. CONFIGURATION SUMMARY (llm_config.yaml)

  Active Provider

  active_provider: "groq"  # Using Groq GPT-OSS-120B

  Path Settings
  ┌──────────┬─────────────┬────────────┬─────────┐
  │   Path   │ Temperature │ Max Tokens │ Timeout │
  ├──────────┼─────────────┼────────────┼─────────┤
  │ Fast     │ 0.35        │ 1000       │ 15s     │
  ├──────────┼─────────────┼────────────┼─────────┤
  │ Standard │ 0.40        │ 1500       │ 25s     │
  ├──────────┼─────────────┼────────────┼─────────┤
  │ Agentic  │ 0.45        │ 2000       │ 45s     │
  └──────────┴─────────────┴────────────┴─────────┘
  Router Patterns

  Fast: what is, who is, define, list, tell me about
  Standard: should we, recommend, advise, how should, your opinion
  Agentic: compare, analyze, evaluate, trade-off, comprehensive

  Thresholds

  - Entity count for agentic: >5 entities
  - Word count for agentic: >30 words
  - Min confidence: 0.5

  ---
  This is the complete deep mechanics of how query routing, the three processing paths, hybrid retrieval, and LangGraph workflow operate
   together in your RAG system!