# RAG SYSTEM - COMPLETE ARCHITECTURE TREE VISUALIZATION

## 🌳 MASTER SYSTEM TREE

```
RAG System (Executive Cognitive Twin)
│
├─── 🌐 API Layer (FastAPI)
│    ├─── /api/v1/chat
│    ├─── /api/v1/langgraph/chat
│    ├─── /api/v1/langgraph/chat/stream
│    ├─── /api/v1/langgraph/chat/stream-audio
│    └─── /api/v1/health
│
├─── 🔄 LangGraph Orchestration Engine
│    ├─── StateGraph (RAGState Schema)
│    │    ├─── Input: query, user_id, profile_id, session_id, user_role
│    │    ├─── Analysis: query_features, query_type, complexity, entities
│    │    ├─── Routing: selected_path, routing_confidence, routing_reasoning
│    │    ├─── Retrieval: vector_results, graph_context, memory_results
│    │    ├─── Fusion: fused_results, reranked_results
│    │    ├─── Cognitive: cognitive outputs from 6 layers
│    │    ├─── LLM: llm_response, citations, sources
│    │    └─── State: conversation_history, final_response
│    │
│    ├─── 🚀 Fast Path (< 2s)
│    │    ├─── analyze_query
│    │    ├─── route_query
│    │    ├─── retrieve_unified_fast
│    │    ├─── cognitive_lens_fast (optional)
│    │    └─── generate_fast
│    │
│    ├─── ⚡ Standard Path (< 3s)
│    │    ├─── analyze_query
│    │    ├─── route_query
│    │    ├─── retrieve_graphrag_standard
│    │    ├─── retrieve_parallel_standard
│    │    │    ├─── retrieve_graph_enhanced (parallel)
│    │    │    └─── retrieve_memory (parallel)
│    │    ├─── fuse_results_standard
│    │    ├─── rerank_results_standard
│    │    ├─── 🧠 Cognitive Enhancement Pipeline
│    │    │    ├─── cognitive_lens_standard (Layer 1)
│    │    │    ├─── cognitive_frame_standard (Layer 2)
│    │    │    ├─── situation_analysis_standard (Layer 4)
│    │    │    ├─── relationship_adaptation_standard (Layer 5)
│    │    │    └─── cognitive_prompt_assembly_standard
│    │    └─── generate_standard
│    │
│    └─── 🤖 Agentic Path (< 5s)
│         ├─── analyze_query
│         ├─── route_query
│         ├─── retrieve_graphrag_agentic
│         ├─── retrieve_parallel_agentic
│         ├─── fuse_results_agentic
│         ├─── rerank_results_agentic
│         ├─── 🔁 ReAct Subgraph (Loop)
│         │    ├─── react_think (reasoning)
│         │    ├─── react_act (tool selection)
│         │    ├─── react_observe (tool execution)
│         │    └─── [continue OR finalize]
│         └─── react_finalize
│
├─── 🔍 Hybrid Retrieval System
│    ├─── Vector Search Engine
│    │    ├─── Embedding Generation
│    │    │    ├─── sentence-transformers/all-MiniLM-L6-v2 (1024-dim)
│    │    │    ├─── L1 Cache (In-Memory LRU, 10K queries)
│    │    │    └─── L2 Cache (Redis, TTL: 1h)
│    │    ├─── pgvector Search
│    │    │    ├─── PostgreSQL embeddings table
│    │    │    ├─── IVFFlat index (vector_cosine_ops)
│    │    │    └─── Candidate constraint (from graph)
│    │    ├─── Hybrid Scoring
│    │    │    ├─── 0.6 × vector_similarity
│    │    │    ├─── 0.4 × graph_proximity
│    │    │    └─── 1.2 × person_name_boost
│    │    └─── RBAC Filtering
│    │
│    ├─── Graph Context Provider
│    │    ├─── Entity Extraction
│    │    │    ├─── spaCy NER (English)
│    │    │    └─── GLiNER (Multilingual)
│    │    ├─── Neo4j Graph Traversal
│    │    │    ├─── Match entities to nodes
│    │    │    ├─── Traverse 1-2 hops
│    │    │    └─── Calculate graph_distance
│    │    ├─── Relationship Discovery
│    │    │    ├─── MADE_DECISION
│    │    │    ├─── HAS_POLICY
│    │    │    ├─── SENT_COMMUNICATION
│    │    │    └─── RELATED_TO
│    │    └─── Return candidate_ids + distances
│    │
│    ├─── Memory Search Engine
│    │    ├─── 5-Signal Scoring System
│    │    │    ├─── Semantic Similarity (40%)
│    │    │    ├─── Temporal Decay (25%)
│    │    │    ├─── Importance Score (20%)
│    │    │    ├─── Feedback Quality Multiplier
│    │    │    └─── User Context Multiplier
│    │    ├─── Query conversation_turns table
│    │    │    ├─── Filter by executive_id
│    │    │    ├─── Last 30 days window
│    │    │    └─── Order by memory_score DESC
│    │    └─── Return top 5 memory results
│    │
│    ├─── Result Fusion Engine
│    │    ├─── Query Type Classification
│    │    │    ├─── factual_lookup
│    │    │    ├─── decision
│    │    │    ├─── comparison
│    │    │    ├─── analysis
│    │    │    └─── relationship
│    │    ├─── Adaptive Weighting (from retrieval_weights.yaml)
│    │    │    ├─── factual: V:80% G:15% M:5%
│    │    │    ├─── decision: V:35% G:25% M:40%
│    │    │    ├─── comparison: V:40% G:35% M:25%
│    │    │    ├─── analysis: V:45% G:30% M:25%
│    │    │    └─── relationship: V:30% G:65% M:5%
│    │    ├─── Confidence Blending (if conf < 0.6)
│    │    └─── Deduplication by source_id
│    │
│    └─── Adaptive Reranker
│         ├─── Strategy Selection
│         │    ├─── Lightweight (≤5 results)
│         │    │    └─── Score sorting only
│         │    ├─── Medium (≤15 results)
│         │    │    ├─── Cross-encoder for top-k
│         │    │    └─── 0.7×semantic + 0.3×cross_encoder
│         │    └─── Full (>15 results)
│         │         ├─── Iterative reranking
│         │         └─── Multi-pass refinement
│         └─── Return reranked_results
│
├─── 🧠 Cognitive Twin Architecture (6 Layers)
│    ├─── Layer 0: Conversational Router
│    │    ├─── Detect greetings/small talk
│    │    ├─── Route to generate_conversational
│    │    └─── Skip retrieval entirely
│    │
│    ├─── Layer 1: Cognitive Lens
│    │    ├─── Load executive domain expertise
│    │    ├─── Calculate domain affinity scores
│    │    ├─── Rerank results by relevance
│    │    └─── Boost domain-specific content
│    │
│    ├─── Layer 2: Cognitive Frame
│    │    ├─── Load reasoning patterns
│    │    │    ├─── Red flags to watch
│    │    │    ├─── Decision frameworks
│    │    │    └─── Mental models
│    │    ├─── Inject into context
│    │    └─── Guide LLM reasoning
│    │
│    ├─── Layer 3: Memory Integration
│    │    └─── (Handled in retrieval phase)
│    │
│    ├─── Layer 4: Situation Analyzer
│    │    ├─── Detect emotional tone
│    │    ├─── Assess urgency level
│    │    ├─── Identify context type
│    │    └─── Output calibration hints
│    │
│    ├─── Layer 5: Relationship Adapter
│    │    ├─── Load user role (CEO/Manager/Engineer)
│    │    ├─── Adjust formality level
│    │    ├─── Modify communication style
│    │    └─── Set appropriate tone
│    │
│    └─── Layer 6: Response Generation
│         └─── (Handled by ConversationEngine)
│
├─── 💬 ConversationEngine (5-Stage Pipeline)
│    ├─── Stage 0: Context Loading
│    │    ├─── Load executive profile
│    │    ├─── Retrieve session state
│    │    ├─── Load conversation history
│    │    └─── Set execution mode
│    │
│    ├─── Stage 1: Context Analysis
│    │    ├─── ContextAnalyzer
│    │    │    ├─── Identify theme (technical/business/strategic)
│    │    │    ├─── Detect urgency (low/medium/high)
│    │    │    ├─── Classify emotion (neutral/concerned/excited)
│    │    │    └─── Determine turn_type (greeting/question/followup)
│    │    └─── Output: ContextAnalysis object
│    │
│    ├─── Stage 2: Response Calibration
│    │    ├─── ResponseCalibrator
│    │    │    ├─── Calculate attention_weights
│    │    │    │    ├─── identity_weight
│    │    │    │    ├─── values_weight
│    │    │    │    ├─── style_weight
│    │    │    │    ├─── examples_weight
│    │    │    │    └─── precedents_weight
│    │    │    └─── Determine tone_adjustment
│    │    │         ├─── more_formal / less_formal
│    │    │         ├─── more_direct / more_empathetic
│    │    │         └─── more_concise / more_detailed
│    │    └─── Output: CalibrationResult object
│    │
│    ├─── Stage 3: Example Selection
│    │    ├─── ExampleSelector
│    │    │    ├─── Load communication examples
│    │    │    │    ├─── Slack messages
│    │    │    │    └─── YouTube transcripts
│    │    │    ├─── Semantic similarity search
│    │    │    │    ├─── Generate query embedding
│    │    │    │    ├─── Calculate cosine similarity
│    │    │    │    └─── Rank by relevance
│    │    │    └─── Select best example
│    │    └─── Output: Selected example + similarity score
│    │
│    ├─── Stage 4: Precedent Selection
│    │    ├─── PrecedentSelector
│    │    │    ├─── Check if query_type == 'decision'
│    │    │    ├─── Load decision_cases
│    │    │    ├─── Semantic matching to query
│    │    │    └─── Select most relevant case
│    │    └─── Output: Decision precedent (if applicable)
│    │
│    └─── Stage 5: Prompt Assembly
│         ├─── PromptAssembler
│         │    ├─── Token Budget Allocation
│         │    │    ├─── fast: 4000 tokens
│         │    │    ├─── standard: 8000 tokens
│         │    │    └─── agentic: 12000 tokens
│         │    ├─── Section Construction (10 sections)
│         │    │    ├─── 1. IdentitySection (800 tokens)
│         │    │    │    ├─── Name, title, role
│         │    │    │    ├─── Core expertise areas
│         │    │    │    └─── Background summary
│         │    │    ├─── 2. ValuesSection (600 tokens)
│         │    │    │    ├─── Decision principles
│         │    │    │    ├─── Priorities hierarchy
│         │    │    │    └─── Ethical guidelines
│         │    │    ├─── 3. SpeakingStyleSection (400 tokens)
│         │    │    │    ├─── Tone characteristics
│         │    │    │    ├─── Formality level
│         │    │    │    └─── Communication patterns
│         │    │    ├─── 4. InstructionsSection (400 tokens)
│         │    │    │    ├─── Word limits
│         │    │    │    ├─── Citation format
│         │    │    │    └─── Language preferences
│         │    │    ├─── 5. ReasoningSection (300 tokens, agentic only)
│         │    │    │    ├─── ReAct framework
│         │    │    │    ├─── Tool descriptions
│         │    │    │    └─── Chain-of-thought prompts
│         │    │    ├─── 6. CalibrationSection (200 tokens)
│         │    │    │    ├─── Tone adjustments
│         │    │    │    ├─── Urgency handling
│         │    │    │    └─── Emotion awareness
│         │    │    ├─── 7. ExampleSection (600 tokens)
│         │    │    │    ├─── 1 Slack message OR
│         │    │    │    └─── 1 YouTube transcript snippet
│         │    │    ├─── 8. PrecedentSection (400 tokens, conditional)
│         │    │    │    ├─── Decision case title
│         │    │    │    ├─── Situation context
│         │    │    │    ├─── Decision made
│         │    │    │    └─── Outcome/reasoning
│         │    │    ├─── 9. ConversationContextSection (variable)
│         │    │    │    ├─── Last N turns
│         │    │    │    ├─── Chronological order
│         │    │    │    └─── Role-based formatting
│         │    │    └─── 10. RetrievedContextSection (remaining budget)
│         │    │         ├─── Vector search results
│         │    │         ├─── Graph context
│         │    │         ├─── Memory results
│         │    │         └─── Citations/sources
│         │    └─── Output: (system_prompt, user_prompt)
│         └─── Return assembled prompts
│
├─── 🤖 LLM Integration Layer
│    ├─── LLMOrchestrator
│    │    ├─── Query routing (fast/standard/agentic)
│    │    ├─── Path handler creation (cached)
│    │    ├─── Prompt generation coordination
│    │    ├─── LLM execution
│    │    ├─── Citation extraction
│    │    └─── Quality evaluation
│    │
│    ├─── LLMClientFactory
│    │    ├─── Provider Selection
│    │    │    ├─── Groq (default, fast inference)
│    │    │    │    ├─── llama-3.3-70b-versatile (fast)
│    │    │    │    ├─── llama-3.1-70b-versatile (standard)
│    │    │    │    └─── llama-3.1-8b-instant (agentic)
│    │    │    ├─── OpenAI
│    │    │    │    ├─── gpt-4o (standard)
│    │    │    │    └─── gpt-4o-mini (fast)
│    │    │    ├─── Google Gemini
│    │    │    │    └─── gemini-1.5-pro (multimodal)
│    │    │    └─── GLM (Chinese)
│    │    │         └─── glm-4-plus
│    │    └─── Client instantiation
│    │
│    ├─── Path-Specific Configurations
│    │    ├─── Fast Path
│    │    │    ├─── temperature: 0.3
│    │    │    ├─── max_tokens: 800
│    │    │    └─── timeout: 10s
│    │    ├─── Standard Path
│    │    │    ├─── temperature: 0.5
│    │    │    ├─── max_tokens: 1500
│    │    │    └─── timeout: 15s
│    │    └─── Agentic Path
│    │         ├─── temperature: 0.7
│    │         ├─── max_tokens: 2500
│    │         └─── timeout: 30s
│    │
│    ├─── Response Processing
│    │    ├─── ResponseFormatter
│    │    │    ├─── Citation extraction (regex)
│    │    │    ├─── Source list building
│    │    │    └─── Metadata attachment
│    │    └─── Quality checks
│    │
│    └─── Streaming Support
│         ├─── Text streaming (SSE)
│         └─── Audio streaming (TTS + text)
│
├─── 📊 Query Analysis System
│    ├─── QueryAnalyzer
│    │    ├─── Entity Extraction
│    │    │    ├─── spaCy NER (PERSON, ORG, DATE, etc.)
│    │    │    ├─── GLiNER (multilingual)
│    │    │    └─── Entity normalization
│    │    ├─── Complexity Classification
│    │    │    ├─── Simple (1 entity, short query)
│    │    │    ├─── Medium (2-3 entities, moderate length)
│    │    │    └─── Complex (4+ entities, long/multi-part)
│    │    ├─── Query Type Detection
│    │    │    ├─── factual_lookup (who/what/when/where)
│    │    │    ├─── decision (should/recommend/choose)
│    │    │    ├─── analysis (why/analyze/explain)
│    │    │    ├─── comparison (compare/vs/difference)
│    │    │    └─── relationship (how related/connection)
│    │    └─── Output: QueryFeatures object
│    │
│    └─── QueryRouter
│         ├─── Routing Logic
│         │    ├─── Fast: simple + high_conf + no_entities
│         │    ├─── Standard: has_entities + medium_complexity
│         │    └─── Agentic: complex OR multi_step OR low_conf
│         └─── Output: path + confidence + reasoning
│
├─── 🗄️ Data Layer
│    ├─── PostgreSQL Database
│    │    ├─── Content Tables
│    │    │    ├─── executive_profiles
│    │    │    │    ├─── id (UUID)
│    │    │    │    ├─── name (VARCHAR)
│    │    │    │    ├─── title (VARCHAR)
│    │    │    │    ├─── profile_data (JSONB)
│    │    │    │    ├─── embedding_id (UUID)
│    │    │    │    └─── created_at (TIMESTAMP)
│    │    │    ├─── policies
│    │    │    │    ├─── id (UUID)
│    │    │    │    ├─── name (VARCHAR)
│    │    │    │    ├─── content_markdown (TEXT)
│    │    │    │    ├─── executive_id (UUID)
│    │    │    │    ├─── scope (VARCHAR)
│    │    │    │    ├─── embedding_id (UUID)
│    │    │    │    └─── created_at (TIMESTAMP)
│    │    │    ├─── decision_cases
│    │    │    │    ├─── id (UUID)
│    │    │    │    ├─── title (VARCHAR)
│    │    │    │    ├─── situation (TEXT)
│    │    │    │    ├─── decision_made (TEXT)
│    │    │    │    ├─── outcome (TEXT)
│    │    │    │    ├─── executive_id (UUID)
│    │    │    │    ├─── embedding_id (UUID)
│    │    │    │    └─── created_at (TIMESTAMP)
│    │    │    ├─── communications
│    │    │    │    ├─── id (UUID)
│    │    │    │    ├─── message_text (TEXT)
│    │    │    │    ├─── channel (VARCHAR: slack/youtube/email)
│    │    │    │    ├─── executive_id (UUID)
│    │    │    │    ├─── embedding_id (UUID)
│    │    │    │    ├─── metadata (JSONB)
│    │    │    │    └─── created_at (TIMESTAMP)
│    │    │    └─── document_sections (Semantic Chunking)
│    │    │         ├─── id (UUID)
│    │    │         ├─── parent_document_id (UUID)
│    │    │         ├─── section_title (VARCHAR)
│    │    │         ├─── content (TEXT)
│    │    │         ├─── position (INTEGER)
│    │    │         ├─── embedding_id (UUID)
│    │    │         └─── created_at (TIMESTAMP)
│    │    │
│    │    ├─── Embedding Table (Unified)
│    │    │    ├─── embeddings
│    │    │         ├─── id (UUID PRIMARY KEY)
│    │    │         ├─── source_id (VARCHAR)
│    │    │         ├─── source_type (VARCHAR)
│    │    │         ├─── embedding (vector(1024))
│    │    │         ├─── created_at (TIMESTAMP)
│    │    │         └─── INDEX USING ivfflat (embedding vector_cosine_ops)
│    │    │
│    │    ├─── Session Management
│    │    │    ├─── conversation_sessions
│    │    │    │    ├─── id (UUID)
│    │    │    │    ├─── user_id (VARCHAR)
│    │    │    │    ├─── executive_id (UUID)
│    │    │    │    ├─── created_at (TIMESTAMP)
│    │    │    │    └─── last_activity (TIMESTAMP)
│    │    │    └─── conversation_turns
│    │    │         ├─── id (UUID)
│    │    │         ├─── session_id (UUID)
│    │    │         ├─── query (TEXT)
│    │    │         ├─── response (TEXT)
│    │    │         ├─── sources_used (JSONB)
│    │    │         ├─── importance_score (FLOAT)
│    │    │         ├─── feedback_score (FLOAT)
│    │    │         └─── created_at (TIMESTAMP)
│    │    │
│    │    ├─── LangGraph Checkpointing
│    │    │    └─── checkpoints
│    │    │         ├─── checkpoint_ns (VARCHAR)
│    │    │         ├─── checkpoint_id (VARCHAR)
│    │    │         ├─── parent_checkpoint_id (VARCHAR)
│    │    │         ├─── type (VARCHAR)
│    │    │         ├─── checkpoint (BYTEA)
│    │    │         ├─── metadata (JSONB)
│    │    │         └─── channel_values (JSONB)
│    │    │
│    │    └─── Observability Tables
│    │         ├─── quality_metrics
│    │         │    ├─── id (UUID)
│    │         │    ├─── request_id (UUID)
│    │         │    ├─── executive_id (UUID)
│    │         │    ├─── citation_coverage (FLOAT)
│    │         │    ├─── grounding_rate (FLOAT)
│    │         │    ├─── faithfulness (FLOAT)
│    │         │    ├─── relevancy (FLOAT)
│    │         │    ├─── precision (FLOAT)
│    │         │    └─── created_at (TIMESTAMP)
│    │         └─── user_activity
│    │              ├─── id (UUID)
│    │              ├─── user_id (VARCHAR)
│    │              ├─── activity_type (VARCHAR)
│    │              ├─── session_id (UUID)
│    │              ├─── metadata (JSONB)
│    │              └─── created_at (TIMESTAMP)
│    │
│    ├─── Neo4j Graph Database
│    │    ├─── Node Types
│    │    │    ├─── (:Executive {id, name, title})
│    │    │    ├─── (:DecisionCase {id, title, situation})
│    │    │    ├─── (:Policy {id, name, scope})
│    │    │    ├─── (:Communication {id, channel})
│    │    │    └─── (:Entity {name, type})
│    │    │
│    │    ├─── Relationship Types
│    │    │    ├─── [:MADE_DECISION]
│    │    │    ├─── [:HAS_POLICY]
│    │    │    ├─── [:SENT_COMMUNICATION]
│    │    │    ├─── [:RELATED_TO]
│    │    │    ├─── [:MENTIONED_ENTITY]
│    │    │    └─── [:INFLUENCED_BY]
│    │    │
│    │    └─── Graph Queries
│    │         ├─── Entity-based traversal
│    │         ├─── Community detection
│    │         ├─── Path finding
│    │         └─── Distance calculation
│    │
│    └─── Redis Cache (Optional)
│         ├─── query_embeddings:{hash(query)} → vector
│         ├─── section_results:{query_hash} → results JSON
│         └─── TTL: 1 hour (embeddings), 5 min (results)
│
├─── 📈 Evaluation & Quality System
│    ├─── RAGASEvaluator
│    │    ├─── Faithfulness
│    │    │    ├─── Extract claims from response
│    │    │    ├─── LLM verification against context
│    │    │    └─── Score: verified_claims / total_claims
│    │    ├─── Relevancy
│    │    │    ├─── Context relevance to query
│    │    │    ├─── Semantic similarity scoring
│    │    │    └─── Average across context chunks
│    │    └─── Precision
│    │         ├─── Citation accuracy check
│    │         ├─── Source verification
│    │         └─── Score: correct_citations / total_citations
│    │
│    └─── QualityEvaluator (Sampling-based)
│         ├─── Citation Coverage
│         │    ├─── Extract all citations from response
│         │    ├─── Count unique sources cited
│         │    └─── Rate: citations / response_length
│         └─── Factual Grounding
│              ├─── Identify factual statements
│              ├─── Verify against retrieved context
│              └─── Rate: grounded_facts / total_facts
│
├─── 🎙️ Audio/Video Module (Optional)
│    ├─── Text-to-Speech (Kokoro-TTS)
│    │    ├─── Voice profile loading
│    │    ├─── Natural pause injection
│    │    ├─── Prosody modeling
│    │    └─── Streaming audio generation
│    │
│    ├─── Speech-to-Text (Faster Whisper)
│    │    ├─── Audio preprocessing
│    │    ├─── Transcription
│    │    └─── Text normalization
│    │
│    └─── Audio Streaming Endpoint
│         ├─── Dual stream (text + audio)
│         ├─── Chunk coordination
│         └─── SSE delivery
│
├─── 🔐 Security & RBAC
│    ├─── Role-Based Access Control
│    │    ├─── User role extraction
│    │    ├─── Document permission filtering
│    │    └─── Result filtering by role
│    │
│    ├─── Session Management
│    │    ├─── SessionManager
│    │    │    ├─── create_session()
│    │    │    ├─── get_session()
│    │    │    ├─── store_conversation_turn()
│    │    │    └─── update_last_activity()
│    │    └─── Session persistence in PostgreSQL
│    │
│    └─── API Authentication (if configured)
│         ├─── API key validation
│         └─── Token-based auth
│
├─── 📡 Observability Stack
│    ├─── LangSmith Integration
│    │    ├─── Trace creation with thread_id
│    │    ├─── Run tracking (node executions)
│    │    ├─── Conversation linking
│    │    └─── Performance metrics
│    │
│    ├─── Prometheus Metrics
│    │    ├─── Request counters
│    │    ├─── Latency histograms
│    │    ├─── Path selection distribution
│    │    └─── Error rates
│    │
│    ├─── Grafana Dashboards
│    │    ├─── System overview
│    │    ├─── LangGraph performance
│    │    ├─── Retrieval metrics
│    │    ├─── LLM latency
│    │    └─── Quality scores
│    │
│    └─── Loki Log Aggregation
│         ├─── Structured logging
│         ├─── Query logs
│         └─── Error tracking
│
├─── ⚙️ Configuration Management
│    ├─── config/llm_config.yaml
│    │    ├─── active_provider
│    │    ├─── provider_configs
│    │    ├─── model_mappings (fast/standard/agentic)
│    │    └─── path_settings (temp, max_tokens, timeout)
│    │
│    ├─── config/retrieval_weights.yaml
│    │    ├─── default_weights
│    │    ├─── query_type_weights (5 types)
│    │    └─── config flags
│    │
│    ├─── .env
│    │    ├─── Database credentials
│    │    ├─── API keys
│    │    ├─── LangSmith config
│    │    └─── Optional service configs
│    │
│    └─── docker-compose.yml
│         ├─── PostgreSQL service
│         ├─── Neo4j service
│         ├─── Redis service (optional)
│         ├─── Prometheus
│         ├─── Grafana
│         └─── Loki
│
└─── 🚀 Initialization & Data Loading
     ├─── init-scripts/load_postgres_data.py
     │    ├─── Load JSON data files
     │    ├─── Generate embeddings (1024-dim)
     │    ├─── Insert into PostgreSQL
     │    └─── Create Neo4j relationships
     │
     ├─── init-scripts/setup_database.sql
     │    ├─── Create tables
     │    ├─── Create indexes
     │    ├─── Enable pgvector extension
     │    └─── Set up constraints
     │
     └─── Migration Scripts
          ├─── 768→1024 dimension migration
          ├─── Schema updates
          └─── Data backfill
```

---

## 🔄 DATA FLOW TREE (Query → Response)

```
USER QUERY
│
├─── 1. API Reception (api/main.py)
│    ├─── Receive ChatRequest
│    ├─── Normalize profile_id
│    └─── Create/retrieve session_id
│
├─── 2. LangGraph Initialization (langgraph_endpoints.py)
│    ├─── Create initial RAGState
│    ├─── Restore conversation_history (from checkpointer)
│    └─── Determine ConversationEngine usage
│
├─── 3. Query Analysis (nodes.py:analyze_query)
│    ├─── Entity Extraction
│    │    ├─── spaCy NER → [entities]
│    │    └─── GLiNER → [multilingual entities]
│    ├─── Complexity Classification
│    │    ├─── Count entities
│    │    ├─── Measure query length
│    │    └─── Detect multi-part structure
│    └─── Query Type Detection
│         ├─── Pattern matching (who/what/when → factual)
│         ├─── Keyword detection (should/recommend → decision)
│         └─── Output: query_features
│
├─── 4. Intelligent Routing (nodes.py:route_query)
│    ├─── Evaluate complexity + entities + confidence
│    ├─── Decision Matrix:
│    │    ├─── Fast: simple + no_entities + high_conf
│    │    ├─── Standard: has_entities + medium_complexity
│    │    └─── Agentic: complex + multi_step + low_conf
│    └─── Output: selected_path, confidence, reasoning
│
├─── 5A. FAST PATH RETRIEVAL
│    ├─── retrieve_unified_fast
│    │    ├─── Graph traversal → candidate_ids
│    │    ├─── Vector search (constrained)
│    │    ├─── Hybrid scoring: 0.6v + 0.4g
│    │    └─── Return top 5 results
│    ├─── [Optional] cognitive_lens_fast
│    │    └─── Domain affinity reranking
│    └─── generate_fast
│         ├─── Build simple prompt
│         ├─── LLM execution (temp: 0.3, max: 800)
│         └─── Return response
│
├─── 5B. STANDARD PATH RETRIEVAL
│    ├─── retrieve_graphrag_standard
│    │    ├─── GraphRAGProvider.global_search()
│    │    ├─── Community-based retrieval
│    │    └─── Only if few/no entities
│    │
│    ├─── retrieve_parallel_standard
│    │    ├─── ThreadPoolExecutor (max_workers=2)
│    │    ├─── Future 1: retrieve_graph_enhanced
│    │    │    ├─── Neo4j traversal
│    │    │    │    ├─── Match entities → nodes
│    │    │    │    ├─── Traverse 1-2 hops
│    │    │    │    ├─── Calculate graph_distance
│    │    │    │    └─── Return candidate_ids + distances
│    │    │    ├─── pgvector search
│    │    │    │    ├─── Generate query embedding (with cache)
│    │    │    │    ├─── Search WHERE source_id IN candidate_ids
│    │    │    │    ├─── Calculate: 1 - (embedding <=> query_embedding)
│    │    │    │    └─── Return vector results
│    │    │    └─── Hybrid scoring
│    │    │         ├─── vector_score = similarity
│    │    │         ├─── graph_score = 1 / (1 + graph_distance)
│    │    │         ├─── final = 0.6*vector + 0.4*graph
│    │    │         └─── If person_name_match: final *= 1.2
│    │    │
│    │    └─── Future 2: retrieve_memory
│    │         ├─── Query conversation_turns table
│    │         ├─── Filter: executive_id + last_30_days
│    │         ├─── 5-Signal Scoring
│    │         │    ├─── Semantic: cosine(query_emb, turn_emb)
│    │         │    ├─── Temporal: exp(-age_days / 30)
│    │         │    ├─── Importance: stored importance_score
│    │         │    ├─── Feedback: feedback_score multiplier
│    │         │    ├─── Context: user_role match bonus
│    │         │    └─── final = (0.4*sem + 0.25*temp + 0.2*imp) * fb * ctx
│    │         └─── Return top 5 memory results
│    │
│    ├─── fuse_results_standard
│    │    ├─── Load query-type weights
│    │    │    ├─── factual: {V:0.80, G:0.15, M:0.05}
│    │    │    ├─── decision: {V:0.35, G:0.25, M:0.40}
│    │    │    ├─── comparison: {V:0.40, G:0.35, M:0.25}
│    │    │    ├─── analysis: {V:0.45, G:0.30, M:0.25}
│    │    │    └─── relationship: {V:0.30, G:0.65, M:0.05}
│    │    ├─── Confidence blending
│    │    │    ├─── If confidence >= 0.6:
│    │    │    │    └─── weights = conf*type_weights + (1-conf)*default
│    │    │    └─── Else: weights = default_weights
│    │    ├─── Calculate fused scores
│    │    │    └─── For each result:
│    │    │         └─── fused_score = W_v*v_score + W_g*g_score + W_m*m_score
│    │    ├─── Deduplicate by source_id
│    │    └─── Return fused_results
│    │
│    ├─── rerank_results_standard
│    │    ├─── Select strategy
│    │    │    ├─── If ≤5 results: "lightweight"
│    │    │    ├─── If ≤15 or factual: "medium"
│    │    │    └─── Else: "full"
│    │    ├─── Execute reranking
│    │    │    ├─── Lightweight: sort by fused_score
│    │    │    ├─── Medium:
│    │    │    │    ├─── Load cross-encoder model
│    │    │    │    ├─── For top-k results:
│    │    │    │    │    ├─── score = cross_encoder(query, result.content)
│    │    │    │    │    └─── final = 0.7*fused + 0.3*cross_encoder
│    │    │    │    └─── Re-sort by final scores
│    │    │    └─── Full:
│    │    │         ├─── Iterative multi-pass reranking
│    │    │         └─── Progressive refinement
│    │    └─── Return reranked_results
│    │
│    ├─── COGNITIVE ENHANCEMENT PIPELINE
│    │    ├─── cognitive_lens_standard (Layer 1)
│    │    │    ├─── Load executive domain expertise
│    │    │    ├─── Calculate domain affinity scores
│    │    │    ├─── Boost domain-relevant results
│    │    │    └─── Update state.cognitive.lens_output
│    │    │
│    │    ├─── cognitive_frame_standard (Layer 2)
│    │    │    ├─── Load reasoning patterns
│    │    │    │    ├─── Red flags to watch
│    │    │    │    ├─── Decision frameworks
│    │    │    │    └─── Mental models
│    │    │    ├─── Prepare injection prompts
│    │    │    └─── Update state.cognitive.frame_output
│    │    │
│    │    ├─── situation_analysis_standard (Layer 4)
│    │    │    ├─── Detect emotional tone (neutral/concerned/excited)
│    │    │    ├─── Assess urgency (low/medium/high)
│    │    │    ├─── Identify context type (technical/business/strategic)
│    │    │    └─── Update state.cognitive.situation_analysis
│    │    │
│    │    ├─── relationship_adaptation_standard (Layer 5)
│    │    │    ├─── Load user role (CEO/Manager/Engineer/External)
│    │    │    ├─── Determine formality adjustment
│    │    │    ├─── Set communication style
│    │    │    └─── Update state.cognitive.relationship_adaptation
│    │    │
│    │    └─── cognitive_prompt_assembly_standard
│    │         ├─── Combine all cognitive outputs
│    │         ├─── Prepare cognitive sections for prompt
│    │         └─── Update state.cognitive.assembled_prompts
│    │
│    └─── generate_standard
│         ├─── IF ConversationEngine enabled:
│         │    ├─── Stage 1: ContextAnalyzer
│         │    │    ├─── Analyze query + history + situation
│         │    │    ├─── Identify theme (technical/business/strategic)
│         │    │    ├─── Detect urgency (low/medium/high)
│         │    │    ├─── Classify emotion (neutral/concerned/excited)
│         │    │    └─── Determine turn_type (greeting/question/followup)
│         │    │
│         │    ├─── Stage 2: ResponseCalibrator
│         │    │    ├─── Calculate attention weights
│         │    │    │    ├─── identity_weight (0.0-1.0)
│         │    │    │    ├─── values_weight (0.0-1.0)
│         │    │    │    ├─── style_weight (0.0-1.0)
│         │    │    │    ├─── examples_weight (0.0-1.0)
│         │    │    │    └─── precedents_weight (0.0-1.0)
│         │    │    └─── Determine tone_adjustment
│         │    │         ├─── Formality: more/less/unchanged
│         │    │         ├─── Directness: more/less/unchanged
│         │    │         └─── Detail: more_concise/more_detailed/balanced
│         │    │
│         │    ├─── Stage 3: ExampleSelector
│         │    │    ├─── Load communication examples
│         │    │    │    ├─── Slack messages
│         │    │    │    └─── YouTube transcripts
│         │    │    ├─── Generate query embedding
│         │    │    ├─── Calculate semantic similarity to each example
│         │    │    ├─── Select best match (highest similarity)
│         │    │    └─── Return selected example
│         │    │
│         │    ├─── Stage 4: PrecedentSelector
│         │    │    ├─── Check if query_type == 'decision'
│         │    │    ├─── If yes:
│         │    │    │    ├─── Load decision_cases
│         │    │    │    ├─── Semantic match to query
│         │    │    │    └─── Select most relevant case
│         │    │    └─── Else: skip
│         │    │
│         │    ├─── Stage 5: PromptAssembler
│         │    │    ├─── Token budget allocation (standard: 8000)
│         │    │    │    ├─── IdentitySection: 800
│         │    │    │    ├─── ValuesSection: 600
│         │    │    │    ├─── SpeakingStyleSection: 400
│         │    │    │    ├─── InstructionsSection: 400
│         │    │    │    ├─── CalibrationSection: 200
│         │    │    │    ├─── ExampleSection: 600
│         │    │    │    ├─── PrecedentSection: 400 (if decision)
│         │    │    │    ├─── ConversationContextSection: variable
│         │    │    │    └─── RetrievedContextSection: remaining (~5000)
│         │    │    │
│         │    │    ├─── Build system_prompt
│         │    │    │    ├─── Assemble IdentitySection
│         │    │    │    ├─── Assemble ValuesSection
│         │    │    │    ├─── Assemble SpeakingStyleSection
│         │    │    │    ├─── Assemble InstructionsSection
│         │    │    │    ├─── Assemble CalibrationSection
│         │    │    │    └─── Apply attention weights
│         │    │    │
│         │    │    └─── Build user_prompt
│         │    │         ├─── Assemble ExampleSection
│         │    │         ├─── Assemble PrecedentSection (if applicable)
│         │    │         ├─── Assemble ConversationContextSection
│         │    │         ├─── Assemble RetrievedContextSection
│         │    │         └─── Append current query
│         │    │
│         │    └─── LLMOrchestrator.generate_with_prompts
│         │         ├─── Create messages list
│         │         │    ├─── {"role": "system", "content": system_prompt}
│         │         │    └─── {"role": "user", "content": user_prompt}
│         │         ├─── LLMClient.generate(messages)
│         │         └─── Return response
│         │
│         └─── ELSE (legacy path):
│              ├─── PromptBuilder.build_full_prompt
│              └─── LLMOrchestrator.generate
│
├─── 5C. AGENTIC PATH RETRIEVAL
│    ├─── [Similar to Standard path for retrieval/fusion/rerank]
│    │
│    ├─── ReAct Subgraph (Loop)
│    │    ├─── react_think
│    │    │    ├─── Analyze current state
│    │    │    ├─── Formulate reasoning
│    │    │    └─── Determine next action
│    │    │
│    │    ├─── react_act
│    │    │    ├─── Select tool (search/calculate/verify)
│    │    │    ├─── Prepare tool input
│    │    │    └─── Execute tool call
│    │    │
│    │    ├─── react_observe
│    │    │    ├─── Capture tool output
│    │    │    ├─── Update state
│    │    │    └─── Evaluate: continue OR finalize?
│    │    │
│    │    └─── Loop condition
│    │         ├─── If solution incomplete: → react_think
│    │         └─── If solution complete: → react_finalize
│    │
│    └─── react_finalize
│         ├─── Synthesize multi-step reasoning
│         ├─── Build final response
│         └─── Return with chain-of-thought
│
├─── 6. LLM Execution (llm_integration/)
│    ├─── LLMClientFactory.create
│    │    ├─── Select provider (Groq/OpenAI/Gemini/GLM)
│    │    ├─── Load model config
│    │    ├─── Apply path-specific settings
│    │    │    ├─── Fast: temp=0.3, max=800, timeout=10s
│    │    │    ├─── Standard: temp=0.5, max=1500, timeout=15s
│    │    │    └─── Agentic: temp=0.7, max=2500, timeout=30s
│    │    └─── Instantiate client
│    │
│    ├─── llm_client.generate(messages, stream=False/True)
│    │    ├─── Format messages for provider
│    │    ├─── Execute API call
│    │    ├─── Handle streaming (if enabled)
│    │    └─── Return response
│    │
│    └─── Extract metadata
│         ├─── Token usage
│         ├─── Model name
│         └─── Latency
│
├─── 7. Post-Processing
│    ├─── ResponseFormatter.format_response
│    │    ├─── Extract citations via regex
│    │    │    ├─── Pattern: [Source: ...] or (Source: ...)
│    │    │    └─── Build citation list
│    │    ├─── Build source list
│    │    │    ├─── Link to document IDs
│    │    │    ├─── Include document titles
│    │    │    └─── Add metadata
│    │    └─── Format final response
│    │
│    ├─── RAGAS Evaluation (optional, sampling-based)
│    │    ├─── Faithfulness
│    │    │    ├─── Extract claims from response
│    │    │    ├─── LLM verification: "Is claim X supported by context Y?"
│    │    │    ├─── Count verified vs. unverified
│    │    │    └─── Score = verified / total
│    │    │
│    │    ├─── Relevancy
│    │    │    ├─── For each context chunk:
│    │    │    │    └─── Semantic similarity to query
│    │    │    └─── Average relevancy score
│    │    │
│    │    └─── Precision
│    │         ├─── Verify each citation
│    │         ├─── Check if cited source exists
│    │         └─── Score = correct_citations / total_citations
│    │
│    ├─── QualityEvaluator (sampling-based)
│    │    ├─── Citation Coverage
│    │    │    ├─── Count citations in response
│    │    │    ├─── Calculate: citations / response_length
│    │    │    └─── Rate = coverage_percentage
│    │    │
│    │    └─── Factual Grounding
│    │         ├─── Identify factual statements
│    │         ├─── Verify against retrieved context
│    │         └─── Rate = grounded_facts / total_facts
│    │
│    └─── Store metrics
│         ├─── INSERT INTO quality_metrics
│         └─── INSERT INTO user_activity
│
├─── 8. State Persistence
│    ├─── Update conversation_history in RAGState
│    │    ├─── Append {"role": "user", "content": query}
│    │    └─── Append {"role": "assistant", "content": response}
│    │
│    ├─── LangGraph Checkpointer.save
│    │    ├─── Serialize RAGState to JSONB
│    │    ├─── INSERT INTO checkpoints
│    │    │    ├─── checkpoint_ns = thread_id
│    │    │    ├─── channel_values = state JSONB
│    │    │    └─── metadata = path, timestamp, etc.
│    │    └─── Link to parent checkpoint
│    │
│    └─── SessionManager.store_conversation_turn
│         ├─── INSERT INTO conversation_turns
│         │    ├─── session_id
│         │    ├─── query
│         │    ├─── response
│         │    ├─── sources_used (JSONB)
│         │    └─── importance_score (calculated)
│         └─── UPDATE conversation_sessions.last_activity
│
├─── 9. Observability Logging
│    ├─── LangSmith
│    │    ├─── Create run with thread_id
│    │    ├─── Log each node execution
│    │    ├─── Link to conversation chain
│    │    └─── Track latency per node
│    │
│    ├─── Prometheus
│    │    ├─── Increment request counter
│    │    ├─── Record latency histogram
│    │    ├─── Update path distribution
│    │    └─── Track error rate
│    │
│    └─── Loki
│         ├─── Log structured event
│         ├─── Include request_id, session_id, user_id
│         └─── Store query, path, timing
│
└─── 10. Response Return
     ├─── Build ChatResponse
     │    ├─── response (text)
     │    ├─── sources (list)
     │    ├─── citations (list)
     │    ├─── metadata
     │    │    ├─── path (fast/standard/agentic)
     │    │    ├─── latency_ms
     │    │    ├─── model_used
     │    │    ├─── tokens_used
     │    │    └─── quality_scores (if evaluated)
     │    └─── session_id
     │
     └─── Return to client (HTTP 200)
```

---

## 🧩 MODULE DEPENDENCY TREE

```
RAG System
│
├─── api/
│    ├─── main.py (FastAPI app, depends on all modules)
│    ├─── langgraph_endpoints.py
│    │    ├─── → langgraph_workflow.graph
│    │    ├─── → conversation_engine.engine
│    │    └─── → utils.session_manager
│    └─── schemas.py (Pydantic models)
│
├─── langgraph_workflow/
│    ├─── graph.py
│    │    ├─── → nodes.py
│    │    ├─── → state.py
│    │    ├─── → checkpointer (AsyncPostgresSaver)
│    │    └─── → cognitive_twin/ (if enabled)
│    ├─── nodes.py
│    │    ├─── → hybrid_retrieval.manager
│    │    ├─── → vector_search.search_engine
│    │    ├─── → graph_context.provider
│    │    ├─── → llm_integration.orchestrator
│    │    ├─── → conversation_engine.engine
│    │    ├─── → query_analysis.analyzer
│    │    ├─── → query_analysis.router
│    │    └─── → cognitive_twin.layers.*
│    └─── state.py (RAGState TypedDict)
│
├─── hybrid_retrieval/
│    ├─── manager.py
│    │    ├─── → vector_search.search_engine
│    │    ├─── → graph_context.provider
│    │    ├─── → memory_search.py
│    │    ├─── → fusion.py
│    │    └─── → adaptive_reranker.py
│    ├─── memory_search.py
│    │    └─── → database.postgres_client
│    ├─── fusion.py
│    │    └─── → config.retrieval_weights.yaml
│    └─── adaptive_reranker.py
│         └─── → transformers (cross-encoder)
│
├─── vector_search/
│    ├─── search_engine.py
│    │    ├─── → embedding.embedding_service
│    │    ├─── → database.postgres_client
│    │    └─── → graph_context.provider
│    └─── embedding/
│         ├─── embedding_service.py
│         │    ├─── → sentence_transformers
│         │    └─── → cache (Redis)
│         └─── models/ (local embedding models)
│
├─── graph_context/
│    ├─── provider.py
│    │    ├─── → neo4j_client
│    │    └─── → query_analysis.entity_extractor
│    └─── neo4j_client.py
│         └─── → neo4j driver
│
├─── conversation_engine/
│    ├─── engine.py
│    │    ├─── → context/analyzer.py
│    │    ├─── → context/calibrator.py
│    │    ├─── → examples/selector.py
│    │    ├─── → precedents/selector.py
│    │    └─── → prompt/assembler.py
│    ├─── context/
│    │    ├─── analyzer.py
│    │    └─── calibrator.py
│    ├─── examples/
│    │    └─── selector.py
│    │         ├─── → database.postgres_client
│    │         └─── → embedding.embedding_service
│    ├─── precedents/
│    │    └─── selector.py
│    │         ├─── → database.postgres_client
│    │         └─── → embedding.embedding_service
│    └─── prompt/
│         ├─── assembler.py
│         │    └─── → sections/*.py
│         ├─── budget.py
│         └─── sections/
│              ├─── identity.py
│              ├─── values.py
│              ├─── speaking_style.py
│              ├─── instructions.py
│              ├─── reasoning.py
│              ├─── calibration.py
│              ├─── example.py
│              ├─── precedent.py
│              ├─── conversation_context.py
│              └─── retrieved_context.py
│
├─── cognitive_twin/
│    ├─── layers/
│    │    ├─── conversational_router.py (Layer 0)
│    │    ├─── cognitive_lens.py (Layer 1)
│    │    │    └─── → database.postgres_client
│    │    ├─── cognitive_frame.py (Layer 2)
│    │    │    └─── → database.postgres_client
│    │    ├─── situation_analyzer.py (Layer 4)
│    │    └─── relationship_adapter.py (Layer 5)
│    └─── prompt_assembly.py
│         └─── → layers/*.py
│
├─── llm_integration/
│    ├─── orchestrator.py
│    │    ├─── → client_factory.py
│    │    ├─── → prompt_builder.py
│    │    ├─── → response_formatter.py
│    │    ├─── → conversation_engine.engine
│    │    └─── → evaluation/
│    ├─── client_factory.py
│    │    ├─── → clients/groq_client.py
│    │    ├─── → clients/openai_client.py
│    │    ├─── → clients/gemini_client.py
│    │    └─── → clients/glm_client.py
│    ├─── clients/
│    │    ├─── base_client.py (ABC)
│    │    ├─── groq_client.py (extends base)
│    │    ├─── openai_client.py (extends base)
│    │    ├─── gemini_client.py (extends base)
│    │    └─── glm_client.py (extends base)
│    ├─── prompt_builder.py
│    ├─── response_formatter.py
│    └─── evaluation/
│         ├─── ragas_evaluator.py
│         └─── quality_evaluator.py
│
├─── query_analysis/
│    ├─── analyzer.py
│    │    ├─── → spacy
│    │    └─── → gliner
│    ├─── router.py
│    └─── entity_extractor.py
│         ├─── → spacy
│         └─── → gliner
│
├─── database/
│    ├─── postgres_client.py
│    │    └─── → psycopg2 / asyncpg
│    ├─── neo4j_client.py
│    │    └─── → neo4j driver
│    └─── redis_client.py (optional)
│         └─── → redis
│
├─── utils/
│    ├─── session_manager.py
│    │    └─── → database.postgres_client
│    ├─── config_loader.py
│    ├─── logger.py
│    └─── metrics.py
│         └─── → prometheus_client
│
├─── observability/
│    ├─── langsmith_integration.py
│    │    └─── → langsmith SDK
│    ├─── prometheus_exporter.py
│    │    └─── → prometheus_client
│    └─── grafana_dashboards/ (JSON configs)
│
└─── config/
     ├─── llm_config.yaml
     ├─── retrieval_weights.yaml
     └─── .env
```

---

## 🔗 COMPONENT INTERACTION DIAGRAM

```
┌──────────────┐
│   FastAPI    │
│  (API Layer) │
└──────┬───────┘
       │
       ├─────────────────┬─────────────────┬────────────────┐
       │                 │                 │                │
       ▼                 ▼                 ▼                ▼
┌─────────────┐   ┌────────────┐   ┌────────────┐  ┌──────────┐
│  LangGraph  │   │Conversation│   │  Session   │  │   Auth   │
│  Workflow   │   │   Engine   │   │  Manager   │  │   RBAC   │
└──────┬──────┘   └─────┬──────┘   └─────┬──────┘  └────┬─────┘
       │                │                │              │
       ├────────────────┴────────────────┴──────────────┘
       │
       │ [Orchestrates all components]
       │
       ├──────────┬──────────┬──────────┬──────────┬──────────┐
       │          │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
│  Query   │ │ Hybrid   │ │Cognitive │ │   LLM    │ │Evaluation│
│ Analysis │ │Retrieval │ │  Twin    │ │Integration│ │  System  │
└────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘
     │            │             │            │            │
     │            ├─────────────┼────────────┘            │
     │            │             │                         │
     ▼            ▼             ▼                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │PostgreSQL│  │  Neo4j   │  │  Redis   │  │LangSmith │   │
│  │(Vector+  │  │ (Graph)  │  │ (Cache)  │  │(Tracing) │   │
│  │Sessions) │  │          │  │          │  │          │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 EXECUTION PATH DECISION TREE

```
                            USER QUERY
                                │
                                ▼
                      ┌──────────────────┐
                      │  Query Analysis  │
                      └────────┬─────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
                ▼              ▼              ▼
         ┌──────────┐   ┌──────────┐  ┌──────────┐
         │ Simple?  │   │ Medium?  │  │ Complex? │
         │No entity │   │Has entity│  │Multi-step│
         │High conf │   │Med compl │  │Low conf  │
         └────┬─────┘   └────┬─────┘  └────┬─────┘
              │              │              │
              ▼              ▼              ▼
        ┌─────────┐    ┌─────────┐   ┌─────────┐
        │  FAST   │    │STANDARD │   │ AGENTIC │
        │  PATH   │    │  PATH   │   │  PATH   │
        └────┬────┘    └────┬────┘   └────┬────┘
             │              │              │
             ▼              ▼              ▼
      ┌──────────┐   ┌──────────┐   ┌──────────┐
      │Unified   │   │GraphRAG  │   │GraphRAG  │
      │Retrieval │   │+Parallel │   │+Parallel │
      │(Top 5)   │   │(V+G+M)   │   │(V+G+M)   │
      └────┬─────┘   └────┬─────┘   └────┬─────┘
           │              │              │
           │              ▼              ▼
           │        ┌──────────┐   ┌──────────┐
           │        │  Fusion  │   │  Fusion  │
           │        │ +Rerank  │   │ +Rerank  │
           │        └────┬─────┘   └────┬─────┘
           │             │              │
           │             ▼              ▼
           │        ┌──────────┐   ┌──────────┐
           │        │Cognitive │   │  ReAct   │
           │        │6 Layers  │   │Subgraph  │
           │        └────┬─────┘   │(Loop)    │
           │             │          └────┬─────┘
           │             │               │
           ├─────────────┴───────────────┘
           │
           ▼
    ┌─────────────┐
    │ConversationE│
    │   Engine    │
    │ (5 Stages)  │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │    LLM      │
    │ Generation  │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   Format    │
    │ + Evaluate  │
    └──────┬──────┘
           │
           ▼
    ┌─────────────┐
    │   Response  │
    │   Return    │
    └─────────────┘
```

---

This comprehensive tree visualization shows every component, connection, data flow, and decision point in your RAG system!

