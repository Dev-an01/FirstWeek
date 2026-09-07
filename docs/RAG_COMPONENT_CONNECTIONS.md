# RAG SYSTEM - COMPONENT CONNECTIONS & DATA TRANSFORMATIONS

## 🔄 COMPLETE DATA TRANSFORMATION PIPELINE

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INPUT TRANSFORMATION                            │
└─────────────────────────────────────────────────────────────────────────┘

Raw Query (String)
    │
    ├─→ QueryAnalyzer.analyze()
    │   ├─→ spaCy NER: query → entities[]
    │   ├─→ GLiNER: query → multilingual_entities[]
    │   ├─→ ComplexityClassifier: query → complexity_level
    │   └─→ TypeDetector: query → query_type
    │
    ├─→ Output: QueryFeatures
    │   ├─ entities: List[Entity]
    │   ├─ complexity: "simple" | "medium" | "complex"
    │   ├─ query_type: "factual" | "decision" | "analysis" | "comparison" | "relationship"
    │   └─ confidence: float
    │
    └─→ QueryRouter.route()
        └─→ Output: RouteDecision
            ├─ path: "fast" | "standard" | "agentic"
            ├─ confidence: float
            └─ reasoning: string

┌─────────────────────────────────────────────────────────────────────────┐
│                       EMBEDDING TRANSFORMATION                          │
└─────────────────────────────────────────────────────────────────────────┘

Query (String)
    │
    ├─→ Check L1 Cache (In-Memory LRU)
    │   ├─ Hit: return cached embedding
    │   └─ Miss: continue
    │
    ├─→ Check L2 Cache (Redis)
    │   ├─ Hit: return cached embedding, store in L1
    │   └─ Miss: continue
    │
    ├─→ EmbeddingService.generate()
    │   ├─→ Load model: sentence-transformers/all-MiniLM-L6-v2
    │   ├─→ Tokenize query
    │   ├─→ Forward pass (GPU if available)
    │   └─→ Mean pooling
    │
    ├─→ Output: embedding (numpy.ndarray, shape: [1024])
    │
    ├─→ Store in L2 Cache (Redis, TTL: 1h)
    │
    └─→ Store in L1 Cache (LRU)

┌─────────────────────────────────────────────────────────────────────────┐
│                      GRAPH CONTEXT TRANSFORMATION                       │
└─────────────────────────────────────────────────────────────────────────┘

entities[] (from QueryAnalyzer)
    │
    ├─→ GraphContextProvider.get_context()
    │   │
    │   ├─→ Step 1: Entity Matching
    │   │   ├─→ Cypher Query:
    │   │   │   MATCH (e:Entity) WHERE e.name IN $entity_names
    │   │   │   RETURN e.id, e.type
    │   │   └─→ Output: matched_entity_ids[]
    │   │
    │   ├─→ Step 2: Graph Traversal
    │   │   ├─→ Cypher Query:
    │   │   │   MATCH (e:Executive {id: $exec_id})-[r*1..2]-(related)
    │   │   │   WHERE related.id IN $entity_ids
    │   │   │   RETURN related.id, length(r) as distance
    │   │   └─→ Output: graph_results[]
    │   │
    │   ├─→ Step 3: Distance Calculation
    │   │   └─→ For each result:
    │   │       graph_distance = shortest_path_length
    │   │       graph_score = 1 / (1 + graph_distance)
    │   │
    │   └─→ Output: GraphContext
    │       ├─ candidate_ids: List[str]
    │       ├─ graph_distances: Dict[str, int]
    │       └─ graph_scores: Dict[str, float]
    │
    └─→ Pass to VectorSearchEngine

┌─────────────────────────────────────────────────────────────────────────┐
│                     VECTOR SEARCH TRANSFORMATION                        │
└─────────────────────────────────────────────────────────────────────────┘

embedding[] + GraphContext
    │
    ├─→ VectorSearchEngine.search()
    │   │
    │   ├─→ Step 1: pgvector Query
    │   │   ├─→ SQL:
    │   │   │   SELECT source_id, source_type, content,
    │   │   │          1 - (embedding <=> $query_embedding) AS similarity
    │   │   │   FROM embeddings
    │   │   │   WHERE source_type = ANY($types)
    │   │   │   AND ($candidate_ids IS NULL OR source_id = ANY($candidate_ids))
    │   │   │   ORDER BY embedding <=> $query_embedding
    │   │   │   LIMIT $top_k
    │   │   └─→ Output: vector_results[]
    │   │
    │   ├─→ Step 2: Hybrid Scoring
    │   │   └─→ For each result:
    │   │       vector_score = similarity (from pgvector)
    │   │       graph_score = graph_scores[result.source_id] OR 0
    │   │       hybrid_score = 0.6 * vector_score + 0.4 * graph_score
    │   │
    │   ├─→ Step 3: Person Name Boost
    │   │   └─→ If query.contains(person_name) AND result.contains(person_name):
    │   │       hybrid_score *= 1.2
    │   │
    │   ├─→ Step 4: RBAC Filtering
    │   │   └─→ Filter results by user_role permissions
    │   │
    │   └─→ Output: VectorSearchResults
    │       ├─ results: List[SearchResult]
    │       │   ├─ source_id: str
    │       │   ├─ content: str
    │       │   ├─ vector_score: float
    │       │   ├─ graph_score: float
    │       │   └─ hybrid_score: float
    │       └─ metadata: Dict
    │
    └─→ Pass to ResultFusion

┌─────────────────────────────────────────────────────────────────────────┐
│                      MEMORY SEARCH TRANSFORMATION                       │
└─────────────────────────────────────────────────────────────────────────┘

query + executive_id + user_context
    │
    ├─→ MultiSignalMemorySearch.search()
    │   │
    │   ├─→ Step 1: Database Query
    │   │   ├─→ SQL:
    │   │   │   SELECT * FROM conversation_turns
    │   │   │   WHERE executive_id = $exec_id
    │   │   │   AND created_at > (NOW() - INTERVAL '30 days')
    │   │   │   ORDER BY importance_score DESC
    │   │   │   LIMIT 50
    │   │   └─→ Output: candidate_turns[]
    │   │
    │   ├─→ Step 2: 5-Signal Scoring
    │   │   └─→ For each turn:
    │   │       │
    │   │       ├─ Signal 1: Semantic Similarity (40%)
    │   │       │   semantic = cosine(query_emb, turn_emb)
    │   │       │
    │   │       ├─ Signal 2: Temporal Decay (25%)
    │   │       │   age_days = (NOW() - turn.created_at).days
    │   │       │   temporal = exp(-age_days / 30)
    │   │       │
    │   │       ├─ Signal 3: Importance Score (20%)
    │   │       │   importance = turn.importance_score (pre-calculated)
    │   │       │
    │   │       ├─ Signal 4: Feedback Quality Multiplier
    │   │       │   feedback_mult = 1.0 + (turn.feedback_score / 10)
    │   │       │
    │   │       ├─ Signal 5: User Context Multiplier
    │   │       │   IF turn.user_role == current_user_role:
    │   │       │       context_mult = 1.2
    │   │       │   ELSE:
    │   │       │       context_mult = 1.0
    │   │       │
    │   │       └─ Final Score:
    │   │           base = 0.40*semantic + 0.25*temporal + 0.20*importance
    │   │           memory_score = base * feedback_mult * context_mult
    │   │
    │   └─→ Output: MemorySearchResults
    │       └─ results: List[MemoryResult]
    │           ├─ source_id: str
    │           ├─ content: str (query + response)
    │           ├─ memory_score: float
    │           └─ metadata: Dict (timestamp, user_role, etc.)
    │
    └─→ Pass to ResultFusion

┌─────────────────────────────────────────────────────────────────────────┐
│                        RESULT FUSION TRANSFORMATION                     │
└─────────────────────────────────────────────────────────────────────────┘

VectorResults + GraphContext + MemoryResults + query_type
    │
    ├─→ ResultFusion.fuse()
    │   │
    │   ├─→ Step 1: Load Query-Type Weights
    │   │   ├─→ From retrieval_weights.yaml
    │   │   ├─→ query_type_weights[query_type]:
    │   │   │   factual:      {V:0.80, G:0.15, M:0.05}
    │   │   │   decision:     {V:0.35, G:0.25, M:0.40}
    │   │   │   comparison:   {V:0.40, G:0.35, M:0.25}
    │   │   │   analysis:     {V:0.45, G:0.30, M:0.25}
    │   │   │   relationship: {V:0.30, G:0.65, M:0.05}
    │   │   └─→ Output: W_v, W_g, W_m
    │   │
    │   ├─→ Step 2: Confidence Blending (if conf < 0.6)
    │   │   └─→ blended_weights = conf * type_weights + (1-conf) * default_weights
    │   │
    │   ├─→ Step 3: Score Fusion
    │   │   └─→ For each unique source_id:
    │   │       v_score = vector_results[source_id].score OR 0
    │   │       g_score = graph_context[source_id].score OR 0
    │   │       m_score = memory_results[source_id].score OR 0
    │   │       fused_score = W_v*v_score + W_g*g_score + W_m*m_score
    │   │
    │   ├─→ Step 4: Deduplication
    │   │   └─→ Group by source_id, keep highest fused_score
    │   │
    │   └─→ Output: FusedResults
    │       └─ results: List[FusedResult]
    │           ├─ source_id: str
    │           ├─ content: str
    │           ├─ vector_score: float
    │           ├─ graph_score: float
    │           ├─ memory_score: float
    │           ├─ fused_score: float
    │           └─ source_breakdown: Dict
    │
    └─→ Pass to AdaptiveReranker

┌─────────────────────────────────────────────────────────────────────────┐
│                      ADAPTIVE RERANKING TRANSFORMATION                  │
└─────────────────────────────────────────────────────────────────────────┘

FusedResults + query + query_type
    │
    ├─→ AdaptiveReranker.rerank()
    │   │
    │   ├─→ Step 1: Strategy Selection
    │   │   ├─→ IF result_count <= 5:
    │   │   │   strategy = "lightweight"
    │   │   ├─→ ELIF result_count <= 15 OR query_type == "factual":
    │   │   │   strategy = "medium"
    │   │   └─→ ELSE:
    │   │       strategy = "full"
    │   │
    │   ├─→ Step 2: Reranking Execution
    │   │   │
    │   │   ├─→ Lightweight Strategy:
    │   │   │   └─→ Sort by fused_score (no additional computation)
    │   │   │
    │   │   ├─→ Medium Strategy:
    │   │   │   ├─→ Load cross-encoder model
    │   │   │   ├─→ For each result in top_k:
    │   │   │   │   cross_score = cross_encoder.predict([(query, result.content)])
    │   │   │   │   final_score = 0.7 * fused_score + 0.3 * cross_score
    │   │   │   └─→ Re-sort by final_score
    │   │   │
    │   │   └─→ Full Strategy:
    │   │       ├─→ Iterative multi-pass reranking
    │   │       ├─→ Pass 1: Cross-encoder on all results
    │   │       ├─→ Pass 2: Diversity injection (MMR)
    │   │       └─→ Pass 3: Final refinement
    │   │
    │   └─→ Output: RerankedResults
    │       └─ results: List[RerankedResult]
    │           ├─ source_id: str
    │           ├─ content: str
    │           ├─ fused_score: float
    │           ├─ rerank_score: float (if applicable)
    │           ├─ final_score: float
    │           └─ rank: int
    │
    └─→ Pass to Cognitive Enhancement OR Prompt Assembly

┌─────────────────────────────────────────────────────────────────────────┐
│                  COGNITIVE ENHANCEMENT TRANSFORMATION                   │
└─────────────────────────────────────────────────────────────────────────┘

RerankedResults + executive_profile + query + user_context
    │
    ├─→ Layer 1: Cognitive Lens
    │   ├─→ Load executive domain expertise
    │   ├─→ Calculate domain affinity scores
    │   │   └─→ For each result:
    │   │       For each expertise_area in profile.expertise:
    │   │           IF result.domain == expertise_area:
    │   │               affinity_boost = expertise_area.weight
    │   │       adjusted_score = final_score * (1 + affinity_boost)
    │   ├─→ Re-sort by adjusted_score
    │   └─→ Output: lens_enhanced_results + lens_output (string)
    │
    ├─→ Layer 2: Cognitive Frame
    │   ├─→ Load reasoning patterns
    │   │   ├─ Red flags: List[Pattern]
    │   │   ├─ Decision frameworks: List[Framework]
    │   │   └─ Mental models: List[Model]
    │   ├─→ Match patterns to query context
    │   ├─→ Prepare injection prompts
    │   └─→ Output: frame_output (string to inject in prompt)
    │
    ├─→ Layer 4: Situation Analysis
    │   ├─→ Analyze query + context
    │   ├─→ Detect:
    │   │   ├─ emotional_tone: "neutral" | "concerned" | "excited" | "urgent"
    │   │   ├─ urgency_level: "low" | "medium" | "high"
    │   │   └─ context_type: "technical" | "business" | "strategic" | "operational"
    │   └─→ Output: SituationAnalysis
    │       ├─ tone: str
    │       ├─ urgency: str
    │       ├─ context_type: str
    │       └─ calibration_hints: Dict
    │
    ├─→ Layer 5: Relationship Adaptation
    │   ├─→ Load user_role (CEO/Manager/Engineer/External)
    │   ├─→ Determine adjustments:
    │   │   ├─ formality: "more_formal" | "less_formal" | "unchanged"
    │   │   ├─ detail_level: "more_detail" | "less_detail" | "balanced"
    │   │   └─ tone: "directive" | "collaborative" | "informative"
    │   └─→ Output: RelationshipAdaptation
    │       ├─ formality_adjustment: str
    │       ├─ detail_adjustment: str
    │       ├─ tone_adjustment: str
    │       └─ style_hints: Dict
    │
    └─→ Combined Output: CognitiveEnhancements
        ├─ enhanced_results: List[Result]
        ├─ lens_output: str
        ├─ frame_output: str
        ├─ situation_analysis: SituationAnalysis
        └─ relationship_adaptation: RelationshipAdaptation

┌─────────────────────────────────────────────────────────────────────────┐
│              CONVERSATION ENGINE TRANSFORMATION (5 Stages)              │
└─────────────────────────────────────────────────────────────────────────┘

query + profile_id + RetrievalContext + CognitiveEnhancements
    │
    ├─→ Stage 1: ContextAnalyzer
    │   ├─→ Input: query + conversation_history + situation_analysis
    │   ├─→ Analysis:
    │   │   ├─ theme = classify_theme(query)
    │   │   │   → "technical" | "business" | "strategic" | "operational"
    │   │   ├─ urgency = detect_urgency(query, situation_analysis)
    │   │   │   → "low" | "medium" | "high"
    │   │   ├─ emotion = detect_emotion(query)
    │   │   │   → "neutral" | "concerned" | "excited" | "frustrated"
    │   │   └─ turn_type = classify_turn(query, history)
    │   │       → "greeting" | "question" | "followup" | "clarification"
    │   └─→ Output: ContextAnalysis
    │       ├─ theme: str
    │       ├─ urgency: str
    │       ├─ emotion: str
    │       └─ turn_type: str
    │
    ├─→ Stage 2: ResponseCalibrator
    │   ├─→ Input: ContextAnalysis + RelationshipAdaptation
    │   ├─→ Calculate attention weights:
    │   │   ├─ identity_weight = base_weight * theme_multiplier
    │   │   ├─ values_weight = base_weight * decision_context_multiplier
    │   │   ├─ style_weight = base_weight * urgency_multiplier
    │   │   ├─ examples_weight = base_weight * communication_multiplier
    │   │   └─ precedents_weight = IF turn_type == "decision": 1.0 ELSE: 0.2
    │   ├─→ Determine tone_adjustment:
    │   │   ├─ IF urgency == "high": more_direct
    │   │   ├─ IF emotion == "concerned": more_empathetic
    │   │   ├─ IF user_role == "CEO": more_concise
    │   │   └─ ELSE: balanced
    │   └─→ Output: CalibrationResult
    │       ├─ attention_weights: Dict[str, float]
    │       └─ tone_adjustment: Dict[str, str]
    │
    ├─→ Stage 3: ExampleSelector
    │   ├─→ Input: query + executive_id
    │   ├─→ Load communication examples:
    │   │   ├─ SELECT * FROM communications
    │   │   ├─ WHERE executive_id = $exec_id
    │   │   └─ AND channel IN ('slack', 'youtube')
    │   ├─→ Semantic matching:
    │   │   ├─ query_emb = generate_embedding(query)
    │   │   ├─ For each example:
    │   │   │   example_emb = embeddings[example.embedding_id]
    │   │   │   similarity = cosine(query_emb, example_emb)
    │   │   └─ Select example with highest similarity
    │   └─→ Output: SelectedExample
    │       ├─ example: Communication
    │       ├─ similarity_score: float
    │       └─ channel: str
    │
    ├─→ Stage 4: PrecedentSelector
    │   ├─→ Input: query + query_type + executive_id
    │   ├─→ IF query_type == "decision":
    │   │   ├─→ Load decision_cases:
    │   │   │   SELECT * FROM decision_cases
    │   │   │   WHERE executive_id = $exec_id
    │   │   ├─→ Semantic matching:
    │   │   │   query_emb = generate_embedding(query)
    │   │   │   For each case:
    │   │   │       case_emb = embeddings[case.embedding_id]
    │   │   │       similarity = cosine(query_emb, case_emb)
    │   │   │   Select case with highest similarity
    │   │   └─→ Output: SelectedPrecedent
    │   │       ├─ case: DecisionCase
    │   │       └─ similarity_score: float
    │   └─→ ELSE: Output: None
    │
    └─→ Stage 5: PromptAssembler
        ├─→ Input: All previous stage outputs + RetrievalContext
        │
        ├─→ Token Budget Allocation:
        │   ├─ path = "standard" → total_budget = 8000
        │   ├─ identity: 800
        │   ├─ values: 600
        │   ├─ speaking_style: 400
        │   ├─ instructions: 400
        │   ├─ calibration: 200
        │   ├─ examples: 600
        │   ├─ precedents: 400 (if decision query)
        │   ├─ conversation_context: min(len(history)*100, 1000)
        │   └─ retrieved_context: remaining (~5000)
        │
        ├─→ Build system_prompt:
        │   ├─→ Section 1: IdentitySection
        │   │   ├─ Profile: {name}, {title}, {role}
        │   │   ├─ Expertise: {expertise_areas[]}
        │   │   └─ Background: {summary}
        │   │   [Weight: identity_weight * token_allocation]
        │   │
        │   ├─→ Section 2: ValuesSection
        │   │   ├─ Principles: {decision_principles[]}
        │   │   ├─ Priorities: {priorities[]}
        │   │   └─ Ethics: {ethical_guidelines[]}
        │   │   [Weight: values_weight * token_allocation]
        │   │
        │   ├─→ Section 3: SpeakingStyleSection
        │   │   ├─ Tone: {tone_characteristics}
        │   │   ├─ Formality: {formality_level} + {formality_adjustment}
        │   │   └─ Patterns: {communication_patterns[]}
        │   │   [Weight: style_weight * token_allocation]
        │   │
        │   ├─→ Section 4: InstructionsSection
        │   │   ├─ Word limit: {based on path}
        │   │   ├─ Citation format: "[Source: X]"
        │   │   ├─ Language: {preferred_language}
        │   │   └─ Custom instructions
        │   │
        │   └─→ Section 6: CalibrationSection
        │       ├─ Tone adjustments: {tone_adjustment}
        │       ├─ Urgency handling: {urgency_level}
        │       └─ Emotion awareness: {emotion}
        │
        ├─→ Build user_prompt:
        │   ├─→ Section 7: ExampleSection
        │   │   ├─ "Here's an example of how you communicate:"
        │   │   ├─ Channel: {example.channel}
        │   │   └─ Content: {example.message_text}
        │   │   [Weight: examples_weight * token_allocation]
        │   │
        │   ├─→ Section 8: PrecedentSection (if decision query)
        │   │   ├─ "Relevant past decision:"
        │   │   ├─ Situation: {case.situation}
        │   │   ├─ Decision: {case.decision_made}
        │   │   └─ Outcome: {case.outcome}
        │   │   [Weight: precedents_weight * token_allocation]
        │   │
        │   ├─→ Section 9: ConversationContextSection
        │   │   ├─ "Previous conversation:"
        │   │   └─ For each turn in history[-N:]:
        │   │       User: {turn.query}
        │   │       Assistant: {turn.response}
        │   │
        │   ├─→ Section 10: RetrievedContextSection
        │   │   ├─ "Relevant information:"
        │   │   └─ For each result in reranked_results:
        │   │       [Source {i}]: {result.content}
        │   │       (from {result.source_type})
        │   │
        │   └─→ Append current query:
        │       "Current question: {query}"
        │
        └─→ Output: AssembledPrompts
            ├─ system_prompt: str (4000-5000 tokens)
            ├─ user_prompt: str (3000-4000 tokens)
            └─ metadata: Dict (weights, adjustments, selections)

┌─────────────────────────────────────────────────────────────────────────┐
│                        LLM EXECUTION TRANSFORMATION                     │
└─────────────────────────────────────────────────────────────────────────┘

system_prompt + user_prompt + path_config
    │
    ├─→ LLMOrchestrator.generate_with_prompts()
    │   │
    │   ├─→ Step 1: Build messages array
    │   │   messages = [
    │   │       {"role": "system", "content": system_prompt},
    │   │       {"role": "user", "content": user_prompt}
    │   │   ]
    │   │
    │   ├─→ Step 2: LLMClientFactory.create()
    │   │   ├─→ provider = config.active_provider (e.g., "groq")
    │   │   ├─→ path = "standard"
    │   │   ├─→ model = providers[provider].models[path]
    │   │   │   (e.g., "llama-3.1-70b-versatile")
    │   │   ├─→ settings = path_settings[path]
    │   │   │   {temperature: 0.5, max_tokens: 1500, timeout: 15}
    │   │   └─→ return GroqClient(model, settings)
    │   │
    │   ├─→ Step 3: llm_client.generate()
    │   │   ├─→ Format messages for provider API
    │   │   ├─→ Execute API call:
    │   │   │   POST https://api.groq.com/openai/v1/chat/completions
    │   │   │   {
    │   │   │       "model": "llama-3.1-70b-versatile",
    │   │   │       "messages": messages,
    │   │   │       "temperature": 0.5,
    │   │   │       "max_tokens": 1500,
    │   │   │       "stream": false
    │   │   │   }
    │   │   ├─→ Parse response
    │   │   └─→ Extract: response_text, token_usage, finish_reason
    │   │
    │   └─→ Output: LLMResponse
    │       ├─ response: str (generated text)
    │       ├─ model: str
    │       ├─ tokens_used: int
    │       ├─ latency_ms: int
    │       └─ finish_reason: str
    │
    └─→ Pass to ResponseFormatter

┌─────────────────────────────────────────────────────────────────────────┐
│                   RESPONSE POST-PROCESSING TRANSFORMATION               │
└─────────────────────────────────────────────────────────────────────────┘

LLMResponse + RetrievalContext
    │
    ├─→ ResponseFormatter.format_response()
    │   │
    │   ├─→ Step 1: Citation Extraction
    │   │   ├─→ Regex patterns:
    │   │   │   r'\[Source:\s*([^\]]+)\]'
    │   │   │   r'\(Source:\s*([^\)]+)\)'
    │   │   ├─→ Extract all matches
    │   │   └─→ Output: citations[] (list of citation strings)
    │   │
    │   ├─→ Step 2: Source Linking
    │   │   ├─→ For each citation:
    │   │   │   ├─ Match to retrieval_results by content/id
    │   │   │   └─ Build Source object:
    │   │   │       {
    │   │   │           source_id: str,
    │   │   │           source_type: str,
    │   │           title: str,
    │   │           snippet: str,
    │   │           score: float
    │   │   │       }
    │   │   └─→ Output: sources[] (list of Source objects)
    │   │
    │   └─→ Output: FormattedResponse
    │       ├─ response: str (cleaned text)
    │       ├─ citations: List[str]
    │       └─ sources: List[Source]
    │
    ├─→ RAGASEvaluator.evaluate() (sampling: 10%)
    │   │
    │   ├─→ Metric 1: Faithfulness
    │   │   ├─→ Extract claims from response (via LLM)
    │   │   ├─→ For each claim:
    │   │   │   LLM prompt: "Is this claim supported by context?"
    │   │   │   Input: claim + retrieved_context
    │   │   │   Output: "yes" | "no"
    │   │   └─→ faithfulness = verified_claims / total_claims
    │   │
    │   ├─→ Metric 2: Relevancy
    │   │   ├─→ For each context chunk:
    │   │   │   semantic_sim = cosine(query_emb, chunk_emb)
    │   │   └─→ relevancy = avg(semantic_similarities)
    │   │
    │   ├─→ Metric 3: Precision
    │   │   ├─→ Verify each citation exists in sources
    │   │   └─→ precision = correct_citations / total_citations
    │   │
    │   └─→ Output: RAGASMetrics
    │       ├─ faithfulness: float (0-1)
    │       ├─ relevancy: float (0-1)
    │       └─ precision: float (0-1)
    │
    ├─→ QualityEvaluator.evaluate() (sampling: 5%)
    │   │
    │   ├─→ Metric 1: Citation Coverage
    │   │   ├─ citation_count = len(citations)
    │   │   ├─ response_length = len(response.split())
    │   │   └─ coverage = citation_count / response_length * 100
    │   │
    │   └─→ Metric 2: Factual Grounding
    │       ├─ Identify factual statements (NLP parsing)
    │       ├─ For each statement:
    │       │   Check if supported by retrieved_context
    │       └─ grounding_rate = grounded / total_statements
    │
    └─→ Store metrics:
        INSERT INTO quality_metrics (
            request_id, executive_id,
            citation_coverage, grounding_rate,
            faithfulness, relevancy, precision,
            created_at
        ) VALUES (...)

┌─────────────────────────────────────────────────────────────────────────┐
│                        STATE PERSISTENCE TRANSFORMATION                 │
└─────────────────────────────────────────────────────────────────────────┘

FormattedResponse + RAGState
    │
    ├─→ Update conversation_history
    │   ├─ Append: {"role": "user", "content": query}
    │   └─ Append: {"role": "assistant", "content": response}
    │
    ├─→ LangGraph Checkpointer.save()
    │   ├─→ Serialize RAGState:
    │   │   state_json = {
    │   │       "query": query,
    │   │       "query_features": {...},
    │   │       "selected_path": "standard",
    │   │       "vector_results": [...],
    │   │       "fused_results": [...],
    │   │       "cognitive": {...},
    │   │       "llm_response": response,
    │   │       "conversation_history": [...]
    │   │   }
    │   ├─→ Save to database:
    │   │   INSERT INTO checkpoints (
    │   │       checkpoint_ns,    -- thread_id
    │   │       checkpoint_id,    -- generated UUID
    │   │       parent_checkpoint_id,
    │   │       channel_values,   -- state_json (JSONB)
    │   │       metadata,         -- {path, timestamp, user_id}
    │   │       created_at
    │   │   )
    │   └─→ Return checkpoint_id
    │
    ├─→ SessionManager.store_conversation_turn()
    │   ├─→ Calculate importance_score:
    │   │   factors = [
    │   │       query_complexity * 0.3,
    │   │       decision_involvement * 0.3,
    │   │       user_feedback * 0.2,
    │   │       context_richness * 0.2
    │   │   ]
    │   │   importance = sum(factors)
    │   │
    │   ├─→ Save turn:
    │   │   INSERT INTO conversation_turns (
    │   │       id, session_id, query, response,
    │   │       sources_used,      -- JSONB
    │   │       importance_score,
    │   │       feedback_score,    -- NULL initially
    │   │       created_at
    │   │   )
    │   │
    │   └─→ Update session:
    │       UPDATE conversation_sessions
    │       SET last_activity = NOW()
    │       WHERE id = session_id
    │
    └─→ Output: PersistedState
        ├─ checkpoint_id: str
        ├─ turn_id: str
        └─ session_updated: bool

┌─────────────────────────────────────────────────────────────────────────┐
│                          FINAL OUTPUT TRANSFORMATION                    │
└─────────────────────────────────────────────────────────────────────────┘

FormattedResponse + Metrics + PersistedState
    │
    └─→ Build ChatResponse
        ├─→ response: str (final response text)
        ├─→ sources: List[Source]
        │   ├─ source_id: str
        │   ├─ source_type: str ("policy", "decision_case", etc.)
        │   ├─ title: str
        │   ├─ snippet: str (truncated content)
        │   └─ score: float (relevance score)
        ├─→ citations: List[str]
        ├─→ metadata: Dict
        │   ├─ path: "fast" | "standard" | "agentic"
        │   ├─ latency_ms: int
        │   ├─ model_used: str
        │   ├─ tokens_used: int
        │   ├─ quality_scores: Dict (if evaluated)
        │   │   ├─ faithfulness: float
        │   │   ├─ relevancy: float
        │   │   ├─ precision: float
        │   │   ├─ citation_coverage: float
        │   │   └─ grounding_rate: float
        │   └─ routing_info: Dict
        │       ├─ query_type: str
        │       ├─ complexity: str
        │       ├─ confidence: float
        │       └─ reasoning: str
        └─→ session_id: str

        ↓

    Return to Client (HTTP 200 JSON)
```

---

## 🔗 CRITICAL INTERCONNECTIONS MAP

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATABASE CONNECTIONS                             │
└─────────────────────────────────────────────────────────────────────┘

PostgreSQL
    ├─→ Used by:
    │   ├─ VectorSearchEngine (embeddings table)
    │   ├─ ConversationEngine (profiles, communications, decision_cases)
    │   ├─ MemorySearch (conversation_turns)
    │   ├─ SessionManager (conversation_sessions)
    │   ├─ LangGraph Checkpointer (checkpoints table)
    │   └─ QualityEvaluator (quality_metrics, user_activity)
    │
    └─→ Tables accessed:
        ├─ embeddings (R: VectorSearch, W: DataLoader)
        ├─ executive_profiles (R: ConversationEngine)
        ├─ policies (R: VectorSearch via embeddings)
        ├─ decision_cases (R: PrecedentSelector, VectorSearch)
        ├─ communications (R: ExampleSelector)
        ├─ conversation_sessions (R/W: SessionManager)
        ├─ conversation_turns (R/W: MemorySearch, SessionManager)
        ├─ checkpoints (R/W: LangGraph)
        ├─ quality_metrics (W: QualityEvaluator)
        └─ user_activity (W: SessionManager)

Neo4j
    ├─→ Used by:
    │   └─ GraphContextProvider (relationship traversal)
    │
    └─→ Operations:
        ├─ MATCH entity nodes by name
        ├─ Traverse relationships (1-2 hops)
        ├─ Calculate shortest path distances
        └─ Return candidate document IDs

Redis (Optional)
    ├─→ Used by:
    │   └─ EmbeddingService (L2 cache)
    │
    └─→ Operations:
        ├─ GET query_embeddings:{hash}
        ├─ SET query_embeddings:{hash} (TTL: 1h)
        └─ GET section_results:{hash} (TTL: 5min)

┌─────────────────────────────────────────────────────────────────────┐
│                   SERVICE DEPENDENCIES                              │
└─────────────────────────────────────────────────────────────────────┘

HybridRetrievalManager
    depends on:
    ├─→ VectorSearchEngine
    ├─→ GraphContextProvider
    ├─→ MemorySearch
    ├─→ ResultFusion
    └─→ AdaptiveReranker

VectorSearchEngine
    depends on:
    ├─→ EmbeddingService
    ├─→ PostgresClient (embeddings table)
    └─→ GraphContextProvider (optional, for hybrid scoring)

GraphContextProvider
    depends on:
    ├─→ Neo4jClient
    └─→ EntityExtractor (spaCy + GLiNER)

ConversationEngine
    depends on:
    ├─→ ContextAnalyzer
    ├─→ ResponseCalibrator
    ├─→ ExampleSelector
    │   ├─→ PostgresClient (communications table)
    │   └─→ EmbeddingService
    ├─→ PrecedentSelector
    │   ├─→ PostgresClient (decision_cases table)
    │   └─→ EmbeddingService
    └─→ PromptAssembler
        └─→ All section builders

LLMOrchestrator
    depends on:
    ├─→ LLMClientFactory
    │   └─→ Provider-specific clients (Groq, OpenAI, Gemini, GLM)
    ├─→ ConversationEngine OR PromptBuilder
    ├─→ ResponseFormatter
    └─→ Evaluation modules (RAGAS, QualityEvaluator)

LangGraph Workflow
    depends on:
    ├─→ QueryAnalyzer
    ├─→ QueryRouter
    ├─→ HybridRetrievalManager
    ├─→ CognitiveTwin layers
    ├─→ ConversationEngine
    ├─→ LLMOrchestrator
    └─→ AsyncPostgresSaver (checkpointer)

┌─────────────────────────────────────────────────────────────────────┐
│                    CONFIGURATION CONNECTIONS                        │
└─────────────────────────────────────────────────────────────────────┘

config/llm_config.yaml
    ├─→ Loaded by: LLMClientFactory
    └─→ Defines:
        ├─ active_provider
        ├─ provider_configs (API keys, endpoints)
        ├─ model_mappings (fast/standard/agentic)
        └─ path_settings (temperature, max_tokens, timeout)

config/retrieval_weights.yaml
    ├─→ Loaded by: ResultFusion
    └─→ Defines:
        ├─ default_weights {V, G, M}
        ├─ query_type_weights (5 types)
        └─ config flags (enabled, min_confidence, blending)

.env
    ├─→ Loaded by: All database clients, LLM clients, observability
    └─→ Defines:
        ├─ POSTGRES_* (connection)
        ├─ NEO4J_* (connection)
        ├─ REDIS_* (optional)
        ├─ GROQ_API_KEY, OPENAI_API_KEY, etc.
        └─ LANGCHAIN_* (tracing)

┌─────────────────────────────────────────────────────────────────────┐
│                  OBSERVABILITY CONNECTIONS                          │
└─────────────────────────────────────────────────────────────────────┘

LangSmith
    ├─→ Traces: Every LangGraph node execution
    ├─→ Links: Conversations via thread_id
    └─→ Metrics: Latency, token usage, path selection

Prometheus
    ├─→ Exporters in:
    │   ├─ api/main.py (request counters)
    │   ├─ langgraph_workflow/graph.py (path distribution)
    │   └─ llm_integration/orchestrator.py (LLM latency)
    └─→ Metrics:
        ├─ rag_requests_total{path, status}
        ├─ rag_latency_seconds{path}
        ├─ rag_path_selection_count{path}
        └─ rag_llm_tokens_used{provider, model}

Grafana
    ├─→ Datasources: Prometheus, Loki, PostgreSQL
    └─→ Dashboards:
        ├─ System Overview
        ├─ LangGraph Performance
        ├─ Retrieval Metrics
        ├─ LLM Latency & Costs
        └─ Quality Scores

Loki
    ├─→ Log sources:
    │   ├─ FastAPI (structured logs)
    │   ├─ LangGraph (node execution logs)
    │   └─ Error tracking
    └─→ Queries: request_id, session_id, user_id correlation
```

---

## 🧬 EMBEDDING PIPELINE CONNECTIONS

```
Document Ingestion → Embedding Generation → Storage → Retrieval
       │                    │                  │          │
       ▼                    ▼                  ▼          ▼
  JSON files        sentence-transformers  PostgreSQL  pgvector
       │                    │              embeddings   search
       │                    │                table        │
       │                    ▼                  │          │
       │            1024-dim vectors           │          │
       │                    │                  │          │
       │                    ├──────────────────┤          │
       │                    │                             │
       ▼                    ▼                             ▼
  executive_profiles → embedding_id ←──── cosine similarity
  policies           → embedding_id          search with
  decision_cases     → embedding_id          graph constraints
  communications     → embedding_id               │
  document_sections  → embedding_id               │
                                                   ▼
                                            Search results
                                            with hybrid scores
```

---

This visualization document provides a complete view of how data transforms through the entire RAG pipeline and how all components interconnect!
