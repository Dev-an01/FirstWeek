# RAG System Quick Reference Card

> Print this for quick reference during development

---

## Architecture At-A-Glance

```
Query → ConversationalRouter → QueryAnalyzer → QueryRouter
                                    ↓
        ┌───────────────────────────┼───────────────────────────┐
        ↓                           ↓                           ↓
     [FAST]                   [STANDARD]                   [AGENTIC]
     <1.5s                      <2.5s                        <5s
   Top 5 docs                Top 10 + graph               Full + ReAct
        ↓                           ↓                           ↓
     Generate               CognitiveLayers              ReAct Loop
        ↓                           ↓                           ↓
        └───────────────────────────┼───────────────────────────┘
                                    ↓
                              LLM Generation
                                    ↓
                                Response
```

---

## Key Files

| Purpose | File |
|---------|------|
| **Entry Point** | `api/main.py` |
| **Workflow Nodes** | `langgraph_workflow/nodes.py` |
| **SINGLE SOURCE OF TRUTH** | `conversation_engine/prompt/rules.py` |
| **Prompt Assembly** | `conversation_engine/prompt/assembler.py` |
| **Retrieval Config** | `hybrid_retrieval/config.py` |
| **Small-talk Detection** | `cognitive_twin/conversational_router.py` |
| **Opinion Formation** | `cognitive_twin/inference_engine.py` |
| **LLM Config** | `config/llm_config.yaml` |
| **Profiles** | `test_data/executive_profiles/*.json` |

---

## Word Limits (from rules.py)

| Path | Target | Soft Max | Hard Max |
|------|--------|----------|----------|
| Fast | 15 | 25 | 40 |
| Standard | 35 | 50 | 80 |
| Agentic | 60 | 100 | 150 |

---

## Retrieval Weights

```
Composite = 0.60×Vector + 0.30×Graph + 0.10×Memory
Multi-source boost: +10% (2 sources), +15% (3 sources)
```

---

## Hybrid Score Formula

```
graph_score = 1.0 / distance
hybrid = 0.60×vector_similarity + 0.40×graph_score
```

---

## Reranking Distribution

| Strategy | Usage | Latency | Trigger |
|----------|-------|---------|---------|
| Lightweight | 40% | ~50ms | top_score>0.85, gap>0.25 |
| Medium | 35% | ~100ms | top_score 0.70-0.85 |
| Full | 25% | ~200ms | top_score<0.70 |

---

## Prompt Section Order

```
1. ReasoningSection      ← ALWAYS FIRST (System 2 thinking)
2. IdentitySection
3. ConversationContext   ← If has_session
4. ExampleSection
5. CalibrationSection
6. ValuesSection         ← Standard/agentic only
7. PrecedentSection      ← If has_precedent
8. InstructionsSection   ← ALWAYS LAST (recency bias)
```

---

## Cognitive Twin Layers

| Layer | Component | Purpose |
|-------|-----------|---------|
| 0 | ConversationalRouter | Detect small-talk |
| 1 | CognitiveLens | Rerank by domain |
| 2 | CognitiveFrame | Inject thinking |
| 3 | SituationAnalyzer | Detect urgency |
| 4 | RelationshipAdapter | Adjust tone |
| 5 | InferenceEngine | Form opinions |

---

## Core Principles

1. **Database is Brain** - Data from PostgreSQL/Neo4j, not hardcode
2. **Graph Constrains Vector** - Narrow before search
3. **Never "I Don't Know"** - Form opinions from values
4. **Recency Bias** - Instructions LAST
5. **Soft Targets** - Limits are targets, not ceilings
6. **Guardrails Sacred** - Red flags never overridden

---

## Forbidden Phrases (Anti-AI)

❌ "I'd be happy to"
❌ "Let me help you"
❌ "Certainly!"
❌ "That's a great question"
❌ "Here's a breakdown"
❌ "As an AI"
❌ "synergy", "leverage", "circle back"

---

## Common Commands

```bash
# Start services
docker-compose up -d

# Start API (dev)
uvicorn api.main:app --reload --port 8000

# Run tests
pytest RAG/tests/ -v

# Load data
python init-scripts/load_postgres_data.py

# Health check
curl http://localhost:8000/api/v1/health
```

---

## Database Ports

| Service | Port |
|---------|------|
| PostgreSQL | 5433 |
| Neo4j HTTP | 7474 |
| Neo4j Bolt | 7687 |
| Redis | 6379 |
| RAG API | 8000 |

---

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/chat` | Chat (non-streaming) |
| `POST /api/v1/chat/stream` | Chat (streaming) |
| `POST /api/v1/langgraph/chat` | LangGraph workflow |
| `GET /api/v1/profiles` | List profiles |
| `GET /api/v1/health` | Health check |

---

## Request Example

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What should we do about the pricing?",
    "profile_id": "sample_profile",
    "language": "en"
  }'
```

---

## Environment Variables

```
POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD
NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
REDIS_HOST, REDIS_PORT
OPENAI_API_KEY, GROQ_API_KEY, GEMINI_API_KEY
LANGSMITH_API_KEY, LANGSMITH_PROJECT
```

---

## Debugging

```python
# Enable debug logging
import logging
logging.getLogger("RAG").setLevel(logging.DEBUG)

# Check state
state = await workflow.aget_state(config)
print(state.values)
```

---

## Git Workflow

```bash
git checkout -b feature/your-feature
# make changes
pytest RAG/tests/ -v
black RAG/
git commit -m "feat: description"
git push origin feature/your-feature
```

---

*Keep this card handy during development!*
