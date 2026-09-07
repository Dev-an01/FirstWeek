# QUERY-TO-RESPONSE FLOWCHART - PART 2

## Continuation from Fusion Results...

```
                                         │
                                         │ fused_results (18 docs)
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     ⑨ NODE: RERANK_RESULTS_STANDARD                             │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:rerank_results_standard()            │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  INPUT: state.fused_results (18 documents)                               │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 1: STRATEGY SELECTION                                        ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ File: hybrid_retrieval/adaptive_reranker.py                       │   │  │
│  │  │                                                                   │   │  │
│  │  │ Decision Logic:                                                   │   │  │
│  │  │   IF result_count <= 5:                                           │   │  │
│  │  │     → "lightweight" (score sorting only)                          │   │  │
│  │  │   ELIF result_count <= 15 OR query_type == "factual":            │   │  │
│  │  │     → "medium" (cross-encoder for top-k)                          │   │  │
│  │  │   ELSE:                                                           │   │  │
│  │  │     → "full" (iterative reranking)                                │   │  │
│  │  │                                                                   │   │  │
│  │  │ Our case:                                                         │   │  │
│  │  │   result_count: 18 (> 15)                                         │   │  │
│  │  │   query_type: "analysis" (not factual)                            │   │  │
│  │  │                                                                   │   │  │
│  │  │ DECISION: "medium" strategy                                       │   │  │
│  │  │ (Using medium because 18 is close to threshold)                   │   │  │
│  │  │ Time: 1ms                                                         │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 2: LOAD CROSS-ENCODER MODEL                                 ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ Model: ms-marco-MiniLM-L-6-v2                                     │   │  │
│  │  │                                                                   │   │  │
│  │  │ IF model_cache.has("cross-encoder"):                              │   │  │
│  │  │   model = model_cache.get("cross-encoder")  ✓ (cached)           │   │  │
│  │  │   Time: 0ms                                                       │   │  │
│  │  │ ELSE:                                                             │   │  │
│  │  │   model = CrossEncoder("ms-marco-MiniLM-L-6-v2")                  │   │  │
│  │  │   model_cache.put("cross-encoder", model)                         │   │  │
│  │  │   Time: 120ms (first time only)                                   │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 3: CROSS-ENCODER SCORING (Top 10 results)                   ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ Select top 10 by fused_score for reranking                        │   │  │
│  │  │                                                                   │   │  │
│  │  │ For each result in top_10:                                        │   │  │
│  │  │   pair = (query, result.content)                                  │   │  │
│  │  │   cross_score = model.predict([pair])                             │   │  │
│  │  │                                                                   │   │  │
│  │  │ Example: doc_3                                                    │   │  │
│  │  │   Input:                                                          │   │  │
│  │  │     query: "What are sample-san's thoughts on technical debt?"    │   │  │
│  │  │     content: "sample-san emphasizes that technical debt..."       │   │  │
│  │  │                                                                   │   │  │
│  │  │   model.predict() →                                               │   │  │
│  │  │     [Tokenize query + content]                                    │   │  │
│  │  │     [BERT-style encoding]                                         │   │  │
│  │  │     [Classification head]                                         │   │  │
│  │  │     → relevance_score: 0.92                                       │   │  │
│  │  │                                                                   │   │  │
│  │  │   Time per prediction: ~18ms                                      │   │  │
│  │  │   Total for 10 docs: ~180ms                                       │   │  │
│  │  │                                                                   │   │  │
│  │  │ Cross-encoder scores:                                             │   │  │
│  │  │   doc_3:  0.92                                                    │   │  │
│  │  │   doc_1:  0.88                                                    │   │  │
│  │  │   doc_11: 0.81                                                    │   │  │
│  │  │   doc_7:  0.79                                                    │   │  │
│  │  │   doc_14: 0.76                                                    │   │  │
│  │  │   ... (10 total)                                                  │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 4: COMBINE SCORES                                            ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ For top 10 reranked results:                                      │   │  │
│  │  │   final_score = 0.7 × fused_score + 0.3 × cross_encoder_score    │   │  │
│  │  │                                                                   │   │  │
│  │  │ Example: doc_3                                                    │   │  │
│  │  │   fused_score: 0.522                                              │   │  │
│  │  │   cross_score: 0.92                                               │   │  │
│  │  │                                                                   │   │  │
│  │  │   final = 0.7 × 0.522 + 0.3 × 0.92                               │   │  │
│  │  │        = 0.365 + 0.276                                            │   │  │
│  │  │        = 0.641                                                    │   │  │
│  │  │                                                                   │   │  │
│  │  │ For remaining 8 results (not reranked):                           │   │  │
│  │  │   final_score = fused_score (unchanged)                           │   │  │
│  │  │                                                                   │   │  │
│  │  │ Time: 5ms                                                         │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  ╔════════════════════════════════════════════════════════════════════╗  │  │
│  │  ║  STEP 5: FINAL SORT                                                ║  │  │
│  │  ╚════════════════════════════════════════════════════════════════════╝  │  │
│  │  ┌──────────────────────────────────────────────────────────────────┐   │  │
│  │  │ ORDER BY final_score DESC                                         │   │  │
│  │  │                                                                   │   │  │
│  │  │ Final ranking (top 10):                                           │   │  │
│  │  │   1. doc_3:   final_score = 0.641  (↑ stayed #1)                 │   │  │
│  │  │   2. doc_1:   final_score = 0.612  (↑ stayed #2)                 │   │  │
│  │  │   3. doc_11:  final_score = 0.571  (↑ stayed #3)                 │   │  │
│  │  │   4. doc_14:  final_score = 0.521  (↑ moved up from #5)          │   │  │
│  │  │   5. doc_7:   final_score = 0.518  (↓ moved down from #4)        │   │  │
│  │  │   6. doc_22:  final_score = 0.487                                 │   │  │
│  │  │   7. doc_8:   final_score = 0.465                                 │   │  │
│  │  │   8. doc_31:  final_score = 0.441                                 │   │  │
│  │  │   9. doc_12:  final_score = 0.428                                 │   │  │
│  │  │  10. doc_19:  final_score = 0.402                                 │   │  │
│  │  │  ... (remaining 8 docs)                                           │   │  │
│  │  │                                                                   │   │  │
│  │  │ Time: 2ms                                                         │   │  │
│  │  └──────────────────────────────────────────────────────────────────┘   │  │
│  │                                                                           │  │
│  │  OUTPUT: RerankedResults {                                               │  │
│  │    results: [18 documents with final_score, sorted],                     │  │
│  │    metadata: {                                                           │  │
│  │      strategy: "medium",                                                 │  │
│  │      reranked_count: 10,                                                 │  │
│  │      total_count: 18                                                     │  │
│  │    }                                                                     │  │
│  │  }                                                                       │  │
│  │                                                                           │  │
│  │  STATE UPDATE: state.reranked_results = RerankedResults                  │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 188ms                                                              │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
╔═════════════════════════════════════════════════════════════════════════════════╗
║                     COGNITIVE ENHANCEMENT PIPELINE (6 Layers)                   ║
╚═════════════════════════════════════════════════════════════════════════════════╝
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                   ⑩ NODE: COGNITIVE_LENS_STANDARD (Layer 1)                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:cognitive_lens_standard()            │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Domain affinity reranking based on executive expertise         │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ File: cognitive_twin/layers/cognitive_lens.py                      │  │  │
│  │  │                                                                     │  │  │
│  │  │ STEP 1: Load Executive Expertise                                   │  │  │
│  │  │ ────────────────────────────────────────────                       │  │  │
│  │  │ SELECT profile_data FROM executive_profiles                        │  │  │
│  │  │ WHERE id = 'sample-san'                                            │  │  │
│  │  │                                                                     │  │  │
│  │  │ expertise_areas = [                                                │  │  │
│  │  │   {domain: "Software Architecture", weight: 0.9},                  │  │  │
│  │  │   {domain: "Technical Debt", weight: 0.8},                         │  │  │
│  │  │   {domain: "Team Leadership", weight: 0.7},                        │  │  │
│  │  │   {domain: "Code Quality", weight: 0.75},                          │  │  │
│  │  │   {domain: "System Design", weight: 0.85}                          │  │  │
│  │  │ ]                                                                  │  │  │
│  │  │ Time: 8ms                                                          │  │  │
│  │  │                                                                     │  │  │
│  │  │ STEP 2: Calculate Domain Affinity                                  │  │  │
│  │  │ ────────────────────────────────────────────                       │  │  │
│  │  │ For each result:                                                   │  │  │
│  │  │   Extract document domain (from metadata or content analysis)      │  │  │
│  │  │   Match to expertise_areas                                         │  │  │
│  │  │   Calculate affinity boost                                         │  │  │
│  │  │                                                                     │  │  │
│  │  │ Example: doc_3                                                     │  │  │
│  │  │   document_domain: "Technical Debt" (from tags)                    │  │  │
│  │  │   expertise_match: weight = 0.8                                    │  │  │
│  │  │   affinity_boost = 0.8                                             │  │  │
│  │  │                                                                     │  │  │
│  │  │   adjusted_score = final_score × (1 + affinity_boost)             │  │  │
│  │  │                 = 0.641 × (1 + 0.8)                               │  │  │
│  │  │                 = 0.641 × 1.8                                      │  │  │
│  │  │                 = 1.154                                            │  │  │
│  │  │                                                                     │  │  │
│  │  │ Example: doc_7                                                     │  │  │
│  │  │   document_domain: "Product Strategy" (not in expertise)           │  │  │
│  │  │   expertise_match: No match                                        │  │  │
│  │  │   affinity_boost = 0.0                                             │  │  │
│  │  │   adjusted_score = 0.518 × (1 + 0.0) = 0.518                      │  │  │
│  │  │                                                                     │  │  │
│  │  │ Time: 7ms                                                          │  │  │
│  │  │                                                                     │  │  │
│  │  │ STEP 3: Re-sort by Adjusted Score                                  │  │  │
│  │  │ ────────────────────────────────────────────                       │  │  │
│  │  │ New ranking:                                                       │  │  │
│  │  │   1. doc_3:  1.154  (↑ boosted, still #1)                         │  │  │
│  │  │   2. doc_14: 0.938  (↑ boosted, moved up from #4)                 │  │  │
│  │  │   3. doc_1:  0.612  (↔ no boost, moved down)                      │  │  │
│  │  │   ... (reordered by domain relevance)                              │  │  │
│  │  │                                                                     │  │  │
│  │  │ OUTPUT: lens_output (string for prompt injection)                  │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  STATE UPDATE:                                                            │  │
│  │    state.cognitive.lens_output = "Domain-prioritized: Tech Debt focus"   │  │
│  │    state.reranked_results = [re-sorted with affinity boosts]             │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 15ms                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                  ⑪ NODE: COGNITIVE_FRAME_STANDARD (Layer 2)                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:cognitive_frame_standard()           │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Inject reasoning patterns and mental models                    │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ File: cognitive_twin/layers/cognitive_frame.py                     │  │  │
│  │  │                                                                     │  │  │
│  │  │ STEP 1: Load Reasoning Patterns                                    │  │  │
│  │  │ ────────────────────────────────────────────                       │  │  │
│  │  │ SELECT profile_data->>'reasoning_patterns'                         │  │  │
│  │  │ FROM executive_profiles                                            │  │  │
│  │  │ WHERE id = 'sample-san'                                            │  │  │
│  │  │                                                                     │  │  │
│  │  │ reasoning_patterns = {                                             │  │  │
│  │  │   red_flags: [                                                     │  │  │
│  │  │     "Ignoring technical debt",                                     │  │  │
│  │  │     "Short-term thinking in architecture",                         │  │  │
│  │  │     "Lack of testing coverage"                                     │  │  │
│  │  │   ],                                                               │  │  │
│  │  │   decision_frameworks: [                                           │  │  │
│  │  │     "Long-term vs. short-term trade-offs",                         │  │  │
│  │  │     "Technical excellence vs. speed",                              │  │  │
│  │  │     "Team capability building"                                     │  │  │
│  │  │   ],                                                               │  │  │
│  │  │   mental_models: [                                                 │  │  │
│  │  │     "Invest in quality early",                                     │  │  │
│  │  │     "Sustainable pace over heroics",                               │  │  │
│  │  │     "Architecture evolves with learning"                           │  │  │
│  │  │   ]                                                                │  │  │
│  │  │ }                                                                  │  │  │
│  │  │ Time: 6ms                                                          │  │  │
│  │  │                                                                     │  │  │
│  │  │ STEP 2: Match Patterns to Query                                    │  │  │
│  │  │ ────────────────────────────────────────────                       │  │  │
│  │  │ Query analysis: "thoughts on technical debt"                       │  │  │
│  │  │                                                                     │  │  │
│  │  │ Matched red_flags:                                                 │  │  │
│  │  │   • "Ignoring technical debt" ✓                                    │  │  │
│  │  │                                                                     │  │  │
│  │  │ Matched frameworks:                                                │  │  │
│  │  │   • "Long-term vs. short-term trade-offs" ✓                        │  │  │
│  │  │                                                                     │  │  │
│  │  │ Matched mental_models:                                             │  │  │
│  │  │   • "Invest in quality early" ✓                                    │  │  │
│  │  │                                                                     │  │  │
│  │  │ Time: 4ms                                                          │  │  │
│  │  │                                                                     │  │  │
│  │  │ STEP 3: Prepare Injection Prompt                                   │  │  │
│  │  │ ────────────────────────────────────────────                       │  │  │
│  │  │ frame_output = """                                                 │  │  │
│  │  │ When thinking about technical debt, consider:                      │  │  │
│  │  │ • Red flag: Ignoring technical debt                                │  │  │
│  │  │ • Framework: Long-term vs. short-term trade-offs                   │  │  │
│  │  │ • Mental model: Invest in quality early                            │  │  │
│  │  │ """                                                                │  │  │
│  │  │                                                                     │  │  │
│  │  │ OUTPUT: frame_output (string for prompt injection)                 │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  STATE UPDATE:                                                            │  │
│  │    state.cognitive.frame_output = frame_output                            │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 10ms                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                ⑫ NODE: SITUATION_ANALYSIS_STANDARD (Layer 4)                    │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:situation_analysis_standard()        │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Detect emotional tone, urgency, and context type               │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ File: cognitive_twin/layers/situation_analyzer.py                  │  │  │
│  │  │                                                                     │  │  │
│  │  │ Analyze: query + conversation_history                              │  │  │
│  │  │                                                                     │  │  │
│  │  │ DETECTION 1: Emotional Tone                                        │  │  │
│  │  │ ───────────────────────────                                        │  │  │
│  │  │ Patterns:                                                          │  │  │
│  │  │   • Urgent words: none                                             │  │  │
│  │  │   • Concern words: none                                            │  │  │
│  │  │   • Excitement words: none                                         │  │  │
│  │  │   • Neutral phrasing: "thoughts on" ✓                              │  │  │
│  │  │                                                                     │  │  │
│  │  │ RESULT: tone = "neutral"                                           │  │  │
│  │  │                                                                     │  │  │
│  │  │ DETECTION 2: Urgency Level                                         │  │  │
│  │  │ ───────────────────────────                                        │  │  │
│  │  │ Indicators:                                                        │  │  │
│  │  │   • Urgency keywords: none                                         │  │  │
│  │  │   • Deadline mentions: none                                        │  │  │
│  │  │   • Exclamation marks: none                                        │  │  │
│  │  │   • Question is exploratory: yes                                   │  │  │
│  │  │                                                                     │  │  │
│  │  │ RESULT: urgency = "low"                                            │  │  │
│  │  │                                                                     │  │  │
│  │  │ DETECTION 3: Context Type                                          │  │  │
│  │  │ ───────────────────────────                                        │  │  │
│  │  │ Domain analysis:                                                   │  │  │
│  │  │   • Technical terms: "technical debt" ✓                            │  │  │
│  │  │   • Business terms: none                                           │  │  │
│  │  │   • Strategic terms: "thoughts" (high-level)                       │  │  │
│  │  │                                                                     │  │  │
│  │  │ RESULT: context_type = "technical"                                 │  │  │
│  │  │                                                                     │  │  │
│  │  │ OUTPUT: SituationAnalysis {                                        │  │  │
│  │  │   tone: "neutral",                                                 │  │  │
│  │  │   urgency: "low",                                                  │  │  │
│  │  │   context_type: "technical",                                       │  │  │
│  │  │   calibration_hints: {                                             │  │  │
│  │  │     response_style: "thoughtful and detailed",                     │  │  │
│  │  │     pacing: "unhurried",                                           │  │  │
│  │  │     depth: "comprehensive"                                         │  │  │
│  │  │   }                                                                │  │  │
│  │  │ }                                                                  │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  STATE UPDATE:                                                            │  │
│  │    state.cognitive.situation_analysis = SituationAnalysis                 │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 12ms                                                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│              ⑬ NODE: RELATIONSHIP_ADAPTATION_STANDARD (Layer 5)                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:relationship_adaptation_standard()   │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Adjust communication style based on user role                  │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ File: cognitive_twin/layers/relationship_adapter.py                │  │  │
│  │  │                                                                     │  │  │
│  │  │ INPUT: user_role = "Engineer"                                      │  │  │
│  │  │                                                                     │  │  │
│  │  │ ADAPTATION RULES:                                                  │  │  │
│  │  │ ─────────────────                                                  │  │  │
│  │  │ IF user_role == "CEO":                                             │  │  │
│  │  │   formality: "more_formal"                                         │  │  │
│  │  │   detail: "high-level summaries"                                   │  │  │
│  │  │   tone: "directive"                                                │  │  │
│  │  │                                                                     │  │  │
│  │  │ ELIF user_role == "Manager":                                       │  │  │
│  │  │   formality: "balanced"                                            │  │  │
│  │  │   detail: "actionable insights"                                    │  │  │
│  │  │   tone: "collaborative"                                            │  │  │
│  │  │                                                                     │  │  │
│  │  │ ELIF user_role == "Engineer":  ✓✓✓                                │  │  │
│  │  │   formality: "less_formal"                                         │  │  │
│  │  │   detail: "technical depth"                                        │  │  │
│  │  │   tone: "peer-to-peer"                                             │  │  │
│  │  │                                                                     │  │  │
│  │  │ ELIF user_role == "External":                                      │  │  │
│  │  │   formality: "more_formal"                                         │  │  │
│  │  │   detail: "comprehensive"                                          │  │  │
│  │  │   tone: "professional"                                             │  │  │
│  │  │                                                                     │  │  │
│  │  │ APPLIED ADJUSTMENTS:                                               │  │  │
│  │  │   formality_adjustment: "less_formal"                              │  │  │
│  │  │   detail_adjustment: "more_detail"                                 │  │  │
│  │  │   tone_adjustment: "collaborative"                                 │  │  │
│  │  │                                                                     │  │  │
│  │  │ OUTPUT: RelationshipAdaptation {                                   │  │  │
│  │  │   formality_adjustment: "less_formal",                             │  │  │
│  │  │   detail_adjustment: "more_detail",                                │  │  │
│  │  │   tone_adjustment: "collaborative",                                │  │  │
│  │  │   style_hints: {                                                   │  │  │
│  │  │     language: "technical jargon acceptable",                       │  │  │
│  │  │     examples: "include code/architecture examples",                │  │  │
│  │  │     depth: "dive into implementation details"                      │  │  │
│  │  │   }                                                                │  │  │
│  │  │ }                                                                  │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  STATE UPDATE:                                                            │  │
│  │    state.cognitive.relationship_adaptation = RelationshipAdaptation       │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 8ms                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│              ⑭ NODE: COGNITIVE_PROMPT_ASSEMBLY_STANDARD                         │
│  ┌──────────────────────────────────────────────────────────────────────────┐  │
│  │  File: langgraph_workflow/nodes.py:cognitive_prompt_assembly_standard() │  │
│  │  ────────────────────────────────────────────────────────────────────────│  │
│  │  PURPOSE: Combine all cognitive outputs into structured prompts          │  │
│  │                                                                           │  │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │  │
│  │  │ Combine:                                                            │  │  │
│  │  │   • lens_output (domain prioritization)                            │  │  │
│  │  │   • frame_output (reasoning patterns)                              │  │  │
│  │  │   • situation_analysis (tone/urgency/context)                      │  │  │
│  │  │   • relationship_adaptation (style adjustments)                    │  │  │
│  │  │                                                                     │  │  │
│  │  │ OUTPUT: cognitive.assembled_prompts = {                            │  │  │
│  │  │   domain_focus: "Prioritize technical debt expertise",             │  │  │
│  │  │   reasoning_guide: "Consider long-term vs short-term...",          │  │  │
│  │  │   tone_guide: "Neutral tone, unhurried, comprehensive",            │  │  │
│  │  │   style_guide: "Less formal, technical depth, collaborative"       │  │  │
│  │  │ }                                                                  │  │  │
│  │  └────────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                           │  │
│  │  STATE UPDATE: state.cognitive.assembled_prompts = {...}                 │  │
│  └──────────────────────────────────────────────────────────────────────────┘  │
│  Total time: 5ms                                                                │
└─────────────────────────────────────────────────────────────────────────────────┘

[Continuing in Part 3 with ConversationEngine and LLM execution...]
```
