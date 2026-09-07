# Database Initialization Scripts

This directory contains scripts for setting up and managing the PostgreSQL and Neo4j databases with sample executive data.

## Quick Start for Teammates

**Just run this - data loads automatically!**

```bash
docker-compose up -d
```

The `rag-api` service will:
1. Wait for PostgreSQL and Neo4j to be ready
2. Check if database is empty
3. **Auto-load sample data if empty** (profile, decisions, policies, embeddings)
4. Start the API server

No manual steps needed for first-time setup!

## Scripts

| Script | Description |
|--------|-------------|
| `load_postgres_data.py` | Loads PostgreSQL data (profile, decisions, policies, docs) |
| `load_neo4j_data.py` | Loads Neo4j graph data (entities, relationships) |
| `generate_embeddings.py` | Generates embeddings for all data + Slack messages |
| `quick-start.sh` | Interactive menu for all database operations |
| `01-init.sql` | Creates pgvector extension and schemas (auto-runs) |

## Usage

### From Host Machine (Local Development)

```bash
cd RAG/init-scripts

# For Docker database (port 5433)
python load_postgres_data.py --docker --confirm
python load_neo4j_data.py --docker --confirm
python generate_embeddings.py --docker

# For Local database (port 5432)
python load_postgres_data.py --local --confirm
python load_neo4j_data.py --local --confirm
python generate_embeddings.py --local
```

### Via Docker Compose (Automated)

```bash
# Load data (first time setup)
docker-compose --profile init up load-sample-data

# Reset and reload all data
docker-compose --profile reset up reset-databases

# Skip embeddings for faster reset
SKIP_EMBEDDINGS=true docker-compose --profile reset up reset-databases
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTO_LOAD_DATA` | `true` | Auto-load data if database is empty on startup |
| `SKIP_EMBEDDINGS` | `false` | Skip embedding generation (faster loading) |
| `POSTGRES_HOST` | `localhost` / `rag-postgres` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5433` (Docker) / `5432` (Local) | PostgreSQL port |
| `POSTGRES_DB` | `ai_officer` | Database name |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |

To disable auto-loading:
```bash
AUTO_LOAD_DATA=false docker-compose up -d
```

## Data Sources

The data loader loads from these locations:

| Data Type | Source Path |
|-----------|-------------|
| Executive Profile | `test_data/executive_profiles/sample_profile.json` |
| Voiceprint | `test_data/voiceprints/sample_profile_voiceprint.json` |
| Policies | `test_data/policies/*.md` |
| Meeting Notes | `test_data/documents/meeting_notes/*.md` |
| Presentations | `test_data/documents/presentations/*.md` |
| Entities | `test_data/entities/*.json` |
| Slack Messages | `docs/sample_data/slack messages.md` |

## Docker Services

| Service | Profile | Description |
|---------|---------|-------------|
| `load-sample-data` | `init` | Loads sample data with embeddings |
| `reset-databases` | `reset` | Resets both databases and loads fresh data |
| `rag-postgres` | (default) | PostgreSQL with pgvector |
| `neo4j` | (default) | Neo4j graph database |
| `rag-api` | (default) | FastAPI server |

Run with profiles:
```bash
# Load data
docker-compose --profile init up load-sample-data

# Reset and load
docker-compose --profile reset up reset-databases
```

## Troubleshooting

### Databases not starting

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs rag-postgres
docker-compose logs neo4j
```

### Data not loading

```bash
# Check if databases are healthy
./quick-start.sh status

# View load-sample-data logs
docker-compose logs load-sample-data
```

### Reset if something goes wrong

```bash
# Nuclear option: remove all volumes and start fresh
docker-compose down -v
docker-compose up -d rag-postgres neo4j redis
# Wait 30 seconds for databases to initialize
docker-compose --profile init up load-sample-data
```

## Notes

- The `load-sample-data` and `reset-databases` services use Docker profiles
- All init services have `restart: "no"` to prevent repeated execution
- Scripts are idempotent - safe to run multiple times
- Embedding generation requires GPU for best performance (~5-10 min with GPU, longer on CPU)
