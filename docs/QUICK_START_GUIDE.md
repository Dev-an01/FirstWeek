# AI Officer - Quick Start Guide for New Developers

## Prerequisites

- **Docker Desktop** (with WSL2 on Windows)
- **NVIDIA GPU + Drivers** (for embeddings - or set `EMBEDDING_DEVICE=cpu`)
- **Git**

---

## Step 1: Clone & Setup Environment

```bash
# Clone the repository
git clone <repo-url>
cd ai-officer

# Copy environment template
cp .env.example .env
```

---

## Step 2: Configure API Keys in `.env`

Open `.env` and fill in these **REQUIRED** keys:

```env
# LLM Provider (at least one required)
GROQ_API_KEY=your-groq-api-key          # Get from https://console.groq.com
OPENAI_API_KEY=your-openai-api-key      # Get from https://platform.openai.com

# LangSmith (for query tracing - highly recommended)
LANGCHAIN_API_KEY=your-langsmith-key    # Get from https://smith.langchain.com
LANGSMITH_API_KEY=your-langsmith-key    # Same key
LANGCHAIN_TRACING_V2=true

# Neo4j Password (change from default)
NEO4J_PASSWORD=neo4j123

# PostgreSQL Password (change from default)
RAG_POSTGRES_PASSWORD=postgres123
DB_PASSWORD=postgres123
```

**Optional but recommended:**
```env
# Google Cloud TTS (for Japanese voice)
GCP_PROJECT_ID=your-gcp-project

```

---

## Step 3: Start Everything

```bash
# Start all services (first run takes 5-10 minutes to build)
docker compose up -d

# Watch the logs
docker compose logs -f
```

**What happens on first run:**
1. PostgreSQL, Neo4j, Redis containers start
2. Database schemas are created automatically
3. **sample data is auto-loaded** (profiles, documents, embeddings)
4. RAG API, Auth Service, Chat Service, Frontend start

---

## Step 4: Verify Everything is Running

```bash
# Check all services are healthy
docker compose ps

# Test RAG API health
curl http://localhost:8000/api/v1/health

# Test a query
curl -X POST http://localhost:8000/api/v1/langgraph/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What are sample-san priorities?", "user_id": "test", "profile_id": "sample_profile"}'
```

---

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:5173 | Main UI |
| **RAG API** | http://localhost:8000 | AI chat endpoint |
| **RAG API Docs** | http://localhost:8000/docs | Swagger documentation |
| **Neo4j Browser** | http://localhost:7474 | Graph database UI |
| **Auth Service** | http://localhost:3001 | Authentication |
| **Chat Service** | http://localhost:3002 | Chat history |

---

## Common Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# View logs (all services)
docker compose logs -f

# View logs (specific service)
docker compose logs -f rag-api

# Restart a specific service
docker compose restart rag-api

# Rebuild after code changes
docker compose up -d --build rag-api

# Reset databases and reload data
docker compose --profile reset up reset-databases

# Shell into RAG container
docker compose exec rag-api bash
```

---

## Troubleshooting

### "Database is empty" or "No executive profiles found"
```bash
# Manually trigger data load
docker compose --profile init up load-sample-data
```

### Neo4j won't start (license error)
Make sure this is in docker-compose.yml:
```yaml
NEO4J_ACCEPT_LICENSE_AGREEMENT: "yes"
```

### GPU not detected for embeddings
```bash
# Check if Docker can see GPU
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi

# If no GPU, use CPU mode in .env:
EMBEDDING_DEVICE=cpu
```

### Port already in use
```bash
# Find what's using the port
netstat -ano | findstr :8000

# Or change ports in .env:
RAG_POSTGRES_PORT=5434
NEO4J_HTTP_PORT=7475
```

### Windows: Line ending issues
```bash
# If scripts fail with "bad interpreter"
git config --global core.autocrlf input
```

---

## Development Workflow

### Working on RAG code locally (without Docker)

```bash
# 1. Keep databases running in Docker
docker compose up -d rag-postgres neo4j redis

# 2. Create Python virtual environment
cd RAG
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Update .env for local development
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
NEO4J_URI=bolt://localhost:7687
REDIS_HOST=localhost

# 5. Run the server locally
python -m api.main
```

### After making code changes

```bash
# If running in Docker - rebuild the container
docker compose up -d --build rag-api

# If running locally - just restart
# (Ctrl+C then python -m api.main)
```

---

## LangSmith Query Tracing

1. Go to https://smith.langchain.com
2. Create a project (or use default)
3. Add to `.env`:
   ```env
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_API_KEY=your-key
   LANGCHAIN_PROJECT=AI-Officer-Dev
   ```
4. Restart the RAG API
5. Send a query - trace appears in LangSmith dashboard

---

## Next Steps

1. Read `docs/AI-OFFICER_RAG_COMPLETE_GUIDE.md` for architecture deep-dive
2. Watch the onboarding video (if available)
3. Try the Swagger docs at http://localhost:8000/docs
4. Explore LangSmith traces to understand query flow

---

## Quick Test Commands

```bash
# English query
curl -X POST http://localhost:8000/api/v1/langgraph/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is sample working on?", "user_id": "test", "profile_id": "sample_profile"}'

# Japanese query (base64 encoded)
curl -X POST http://localhost:8000/api/v1/langgraph/chat \
  -H "Content-Type: application/json" \
  -d '{"query_base64": "5LuK5b6M44Gu5oim55Wl44Gr44Gk44GE44Gm5pWZ44GI44Gm44GP44Gg44GV44GE", "user_id": "test", "profile_id": "sample_profile", "language": "ja"}'

# Multi-turn (use session_id from previous response)
curl -X POST http://localhost:8000/api/v1/langgraph/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Tell me more about the first one", "user_id": "test", "profile_id": "sample_profile", "session_id": "YOUR_SESSION_ID"}'
```

---

**Questions?** Check LangSmith traces first - they show exactly what's happening!
