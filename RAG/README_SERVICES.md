# AI Officer - Onboarding & Embedding Services

A comprehensive multi-service architecture for executive profile generation and AI-powered cognitive twin creation.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Services](#services)
3. [Quick Start](#quick-start)
4. [Database Migrations](#database-migrations)
5. [Document Types: Profile vs Knowledgebase](#document-types-profile-vs-knowledgebase)
6. [Onboarding Service (Port 8002)](#onboarding-service-port-8002)
7. [Embedding Service (Port 8001)](#embedding-service-port-8001)
8. [RAG API (Port 8000)](#rag-api-port-8000)
9. [Database Schema](#database-schema)
10. [API Reference](#api-reference)
11. [Pipeline Deep Dive](#pipeline-deep-dive)
12. [Environment Variables](#environment-variables)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           AI Officer System                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │  Onboarding  │───▶│  Embedding   │───▶│   RAG API    │                  │
│  │   Service    │    │   Service    │    │              │                  │
│  │  (Port 8002) │    │  (Port 8001) │    │  (Port 8000) │                  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                  │
│         │                   │                   │                          │
│         │    ┌──────────────┴───────────────────┘                          │
│         │    │                                                              │
│         ▼    ▼                                                              │
│  ┌──────────────────────────────────────────────────────────┐              │
│  │                    PostgreSQL + pgvector                  │              │
│  │  • executive_profiles  • embeddings  • companies          │              │
│  │  • decision_cases      • documents   • onboarding_jobs    │              │
│  └──────────────────────────────────────────────────────────┘              │
│         │                                                                   │
│         ▼                                                                   │
│  ┌──────────────┐    ┌──────────────┐                                      │
│  │    Neo4j     │    │    Redis     │                                      │
│  │  (Knowledge  │    │   (Cache &   │                                      │
│  │    Graph)    │    │    Queue)    │                                      │
│  └──────────────┘    └──────────────┘                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Services

| Service | Port | Purpose |
|---------|------|---------|
| **Onboarding Service** | 8002 | Company/executive registration, document processing, LLM extraction pipeline |
| **Embedding Service** | 8001 | BGE-M3 multilingual embeddings (1024 dimensions), vector storage |
| **RAG API** | 8000 | Chat endpoint, cognitive twin responses, hybrid retrieval |
| **PostgreSQL** | 5432 | Main database with pgvector for similarity search |
| **Neo4j** | 7474/7687 | Knowledge graph for entity relationships |
| **Redis** | 6379 | Cache and Celery task queue |

---

## Quick Start

### 1. Clone and Configure

```bash
# From the project root (ai officer/)
cp .env.example .env

# Edit .env and add your Groq API key (REQUIRED)
# Get your key from: https://console.groq.com
nano .env  # or use any text editor
```

**Minimum required in `.env` (at project root, NOT in RAG/):**
```bash
GROQ_API_KEY=gsk_your_actual_key_here
```

> **Note:** The `.env` file must be in the project root (`ai officer/.env`), not in `RAG/.env`.

### 2. Start All Services

```bash
docker-compose up -d
```

### 3. Verify Services

```bash
# Check health endpoints
curl http://localhost:8000/api/v1/health  # RAG API
curl http://localhost:8001/health          # Embedding Service
curl http://localhost:8002/health          # Onboarding Service
```

### 4. Onboard Your First Executive

```bash
# 1. Create company
curl -X POST http://localhost:8002/api/v1/companies \
  -H "Content-Type: application/json" \
  -d '{"id": "my_company", "name": "My Company Inc", "industry": "Technology"}'

# 2. Create executive
curl -X POST http://localhost:8002/api/v1/companies/my_company/executives \
  -H "Content-Type: application/json" \
  -d '{"id": "john_doe", "company_id": "my_company", "name": "John Doe", "title": "CTO"}'

# 3. Upload documents
curl -X POST http://localhost:8002/api/v1/companies/my_company/executives/john_doe/documents \
  -F "files=@interview_transcript.pdf" \
  -F "files=@bio.docx"

# 4. Start onboarding pipeline
curl -X POST http://localhost:8002/api/v1/companies/my_company/executives/john_doe/onboard

# 5. Chat with the cognitive twin
curl -X POST http://localhost:8000/api/v1/langgraph/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What is your management philosophy?", "user_id": "user1", "profile_id": "john_doe"}'
```

---

## Database Migrations

Database migrations are located in `RAG/config/`. Run them in order when setting up a new environment or upgrading.

### Migration Files

| Migration | Description |
|-----------|-------------|
| `postgres_schema.sql` | Base schema (tables, views, functions) |
| `onboarding_migration.sql` | Onboarding service tables (companies, jobs, documents) |
| `phase8_migration.sql` | Session management enhancements |
| `phase9_multitenant_migration.sql` | Multi-tenant company support |
| `phase10_ocr_metadata_migration.sql` | OCR parsing metadata |
| `phase11_knowledgebase_migration.sql` | **Knowledgebase vs Profile document separation** |

### Running Migrations

**Using Docker (recommended):**

```bash
# Run all migrations
cat RAG/config/postgres_schema.sql | docker exec -i ai-officer-postgres psql -U postgres -d ai_officer_dev
cat RAG/config/onboarding_migration.sql | docker exec -i ai-officer-postgres psql -U postgres -d ai_officer_dev
cat RAG/config/phase11_knowledgebase_migration.sql | docker exec -i ai-officer-postgres psql -U postgres -d ai_officer_dev
```

**Using psql directly:**

```bash
psql -h localhost -U postgres -d ai_officer_dev -f RAG/config/phase11_knowledgebase_migration.sql
```

**Using Python (if Docker is not available):**

```python
import asyncio
import asyncpg

async def run_migration():
    pool = await asyncpg.create_pool(
        host="localhost", port=5432,
        database="ai_officer_dev",
        user="postgres", password="postgres"
    )

    # Add doc_type column
    await pool.execute("""
        ALTER TABLE executive_documents
        ADD COLUMN IF NOT EXISTS doc_type VARCHAR(20) DEFAULT 'profile'
    """)

    # Make executive_id nullable
    await pool.execute("""
        ALTER TABLE executive_documents
        ALTER COLUMN executive_id DROP NOT NULL
    """)

    # Add indexes
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS idx_exec_docs_doc_type
        ON executive_documents(doc_type)
    """)
    await pool.execute("""
        CREATE INDEX IF NOT EXISTS idx_company_knowledgebase
        ON executive_documents(company_id, doc_type)
        WHERE executive_id IS NULL
    """)

    await pool.close()
    print("Migration complete!")

asyncio.run(run_migration())
```

### Verifying Migration

```sql
-- Check doc_type column exists
SELECT column_name, is_nullable
FROM information_schema.columns
WHERE table_name = 'executive_documents';

-- Should show: doc_type (nullable: YES), executive_id (nullable: YES)
```

---

## Document Types: Profile vs Knowledgebase

The system supports two types of documents with different processing pipelines:

```
+-----------------------------------------------------------------------------+
|                         DOCUMENT TYPES                                       |
+-----------------------------------------------------------------------------+
|                                                                             |
|  PROFILE DOCUMENTS                      KNOWLEDGEBASE DOCUMENTS             |
|  (Executive-specific)                   (Company-wide, Shared)              |
|  -------------------------              -------------------------           |
|  - Interviews                           - Company policies                  |
|  - Speeches                             - Procedures & guidelines           |
|  - Biographies                          - Handbooks                         |
|  - Articles by executive                - Compliance documents              |
|                                                                             |
|  Endpoint:                              Endpoint:                           |
|  POST /companies/{cid}/                 POST /companies/{cid}/              |
|       executives/{eid}/documents             knowledgebase                  |
|                                                                             |
|  Processing:                            Processing:                         |
|  Parse -> 7 LLM Extractors ->           Parse -> Chunk -> Embed directly    |
|  Profile + Voiceprint -> Embed          (NO LLM extraction)                 |
|                                                                             |
|  Storage:                               Storage:                            |
|  executive_id = "{eid}"                 executive_id = NULL                 |
|  doc_type = "profile"                   doc_type = "knowledgebase"          |
|                                                                             |
|  RAG Access:                            RAG Access:                         |
|  Only for this executive                Shared by ALL executives in company |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### How RAG Queries Work

When querying for executive `john_doe`:

```sql
WHERE executive_id = 'john_doe' OR executive_id IS NULL
```

This returns:
1. **Personal profile embeddings** (from interviews, speeches, etc.)
2. **Company knowledgebase** (policies shared by all executives)

### Example Workflow

```bash
# 1. Upload company-wide policies (shared by all executives)
curl -X POST "http://localhost:8002/api/v1/companies/my_company/knowledgebase" \
  -F "files=@company_policy.pdf" \
  -F "files=@employee_handbook.pdf"

# 2. Upload executive-specific documents
curl -X POST "http://localhost:8002/api/v1/companies/my_company/executives/john_doe/documents" \
  -F "files=@john_interview.pdf" \
  -F "files=@john_keynote_speech.pdf"

# 3. Run calibration to generate profile from executive documents
curl -X POST "http://localhost:8002/api/v1/companies/my_company/executives/john_doe/calibrate" \
  -H "Content-Type: application/json" \
  -d '{"mode": "full"}'

# 4. Chat - AI has access to BOTH personal profile AND company policies
curl -X POST "http://localhost:8000/api/v1/langgraph/chat" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the company leave policy?", "profile_id": "john_doe"}'
```

---

## Onboarding Service (Port 8002)

The onboarding service handles the complete executive profile generation pipeline.

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ONBOARDING PIPELINE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐ │
│  │  Upload  │──▶│  Parse   │──▶│ Extract  │──▶│ Assemble │──▶│ Validate │ │
│  │Documents │   │Documents │   │  (7 LLM) │   │ Profile  │   │ Profile  │ │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘ │
│                                                      │                      │
│                                                      ▼                      │
│                                ┌──────────┐   ┌──────────┐                 │
│                                │  Deploy  │──▶│ Generate │                 │
│                                │   to DB  │   │Embeddings│                 │
│                                └──────────┘   └──────────┘                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7 LLM Extractors

The extraction phase runs 7 concurrent LLM extractors via Groq API:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           7 CONCURRENT EXTRACTORS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ 1. Background       │  │ 2. Thinking         │  │ 3. Communication    │ │
│  │    Identity         │  │    Patterns         │  │    Style            │ │
│  │ ─────────────────── │  │ ─────────────────── │  │ ─────────────────── │ │
│  │ • Education         │  │ • Problem approach  │  │ • Tone & formality  │ │
│  │ • Roles & expertise │  │ • Frameworks used   │  │ • Language prefs    │ │
│  │ • Company info      │  │ • Typical questions │  │ • Response patterns │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                                                             │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐ │
│  │ 4. Values &         │  │ 5. Domain &         │  │ 6. Red Flags &      │ │
│  │    Decisions        │  │    Tech Opinions    │  │    Inference        │ │
│  │ ─────────────────── │  │ ─────────────────── │  │ ─────────────────── │ │
│  │ • Core values       │  │ • Primary domains   │  │ • Never approve     │ │
│  │ • Decision cases    │  │ • Tech preferences  │  │ • Always do         │ │
│  │ • Trade-off scales  │  │ • AI/market views   │  │ • Escalation rules  │ │
│  └─────────────────────┘  └─────────────────────┘  └─────────────────────┘ │
│                                                                             │
│  ┌─────────────────────┐                                                    │
│  │ 7. Speaking         │  ──────────────────────────────────────────────▶  │
│  │    Patterns         │              VOICEPRINT GENERATION                 │
│  │ ─────────────────── │                                                    │
│  │ • Casual responses  │                                                    │
│  │ • Lexicon/phrases   │                                                    │
│  │ • Humor style       │                                                    │
│  └─────────────────────┘                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Document Parsing

Supported formats with automatic OCR fallback for scanned documents:

| Format | Parser | OCR Fallback |
|--------|--------|--------------|
| `.pdf` | pdfplumber | MinerU (for scanned PDFs) |
| `.docx` | python-docx | N/A |
| `.txt` | UTF-8 text | N/A |
| `.json` | JSON parser | N/A |
| `.png/.jpg` | MinerU OCR | Always OCR |

### API Endpoints Summary

#### Companies
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/companies` | Create company |
| `GET` | `/api/v1/companies` | List all companies |
| `GET` | `/api/v1/companies/{id}` | Get company with executives |
| `PATCH` | `/api/v1/companies/{id}` | Update company |

#### Executives
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/companies/{cid}/executives` | Create executive |
| `GET` | `/api/v1/companies/{cid}/executives` | List executives |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}` | Get executive details |
| `PATCH` | `/api/v1/companies/{cid}/executives/{eid}` | Update executive |
| `DELETE` | `/api/v1/companies/{cid}/executives/{eid}` | Soft delete executive |

#### Profile Documents (Executive-specific)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/companies/{cid}/executives/{eid}/documents` | Upload profile documents (goes through LLM extraction) |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/documents` | List executive's documents |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/documents/{did}` | Get document with text |
| `DELETE` | `/api/v1/companies/{cid}/executives/{eid}/documents/{did}` | Soft delete document |
| `POST` | `/api/v1/companies/{cid}/executives/{eid}/documents/{did}/restore` | Restore document |

#### Knowledgebase Documents (Company-wide, Shared)
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/companies/{cid}/knowledgebase` | Upload knowledgebase docs (bypasses LLM, direct embed) |
| `GET` | `/api/v1/companies/{cid}/knowledgebase` | List company's knowledgebase documents |
| `GET` | `/api/v1/companies/{cid}/knowledgebase/{did}` | Get knowledgebase document with text |
| `DELETE` | `/api/v1/companies/{cid}/knowledgebase/{did}` | Soft delete knowledgebase document |

#### Profiles & Voiceprints
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/profile` | Get profile + voiceprint |
| `PATCH` | `/api/v1/companies/{cid}/executives/{eid}/profile` | Edit profile sections |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/voiceprint` | Get voiceprint |
| `PATCH` | `/api/v1/companies/{cid}/executives/{eid}/voiceprint` | Edit voiceprint sections |

#### Onboarding & Calibration
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/companies/{cid}/executives/{eid}/onboard` | Start onboarding pipeline |
| `POST` | `/api/v1/companies/{cid}/executives/{eid}/calibrate` | Re-run extraction |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/jobs/{jid}` | Get job status |
| `GET` | `/api/v1/companies/{cid}/executives/{eid}/jobs/{jid}/result` | Get job result |

---

## Embedding Service (Port 8001)

Generates and stores multilingual embeddings using BAAI/bge-m3 (1024 dimensions).

### Embedding Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    EMBEDDING GENERATION                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Profile JSON                                                  │
│        │                                                        │
│        ▼                                                        │
│   ┌─────────────┐                                               │
│   │  Chunk by   │  (background, communication_style,           │
│   │  Section    │   decision_cases, etc.)                       │
│   └──────┬──────┘                                               │
│          │                                                      │
│          ▼                                                      │
│   ┌─────────────┐    ┌─────────────┐                           │
│   │  BGE-M3     │───▶│  1024-dim   │                           │
│   │  Encoder    │    │  Vectors    │                           │
│   └─────────────┘    └──────┬──────┘                           │
│                             │                                   │
│                             ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                PostgreSQL + pgvector                     │  │
│   │  ┌─────────────────────────────────────────────────────┐│  │
│   │  │ embeddings table                                    ││  │
│   │  │ ─────────────────────────────────────────────────── ││  │
│   │  │ id | source_id | source_type | company_id |         ││  │
│   │  │    | executive_id | embedding (vector 1024) |       ││  │
│   │  │    | metadata (JSONB)                               ││  │
│   │  └─────────────────────────────────────────────────────┘│  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/embeddings/documents` | Embed single document |
| `POST` | `/embeddings/batch` | Batch embed documents |
| `POST` | `/embeddings/incremental` | Incremental update |
| `GET` | `/embeddings/version` | Get version history |
| `POST` | `/embeddings/rollback` | Rollback to previous version |
| `GET` | `/tasks/{task_id}` | Get async task status |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Processing metrics |

---

## RAG API (Port 8000)

Main API for chatting with cognitive twins using hybrid retrieval.

### Chat Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CHAT PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   User Query: "What's your approach to hiring?"                             │
│        │                                                                    │
│        ▼                                                                    │
│   ┌─────────────┐                                                           │
│   │  Identify   │  profile_id: "john_doe"                                   │
│   │  Executive  │  company_id: "my_company"                                 │
│   └──────┬──────┘                                                           │
│          │                                                                  │
│          ▼                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    HYBRID RETRIEVAL                                  │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │  │
│   │  │   Vector    │  │   Graph     │  │  Episodic   │                  │  │
│   │  │   Search    │  │   Context   │  │   Memory    │                  │  │
│   │  │ (pgvector)  │  │  (Neo4j)    │  │ (sessions)  │                  │  │
│   │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │  │
│   │         │                │                │                          │  │
│   │         └────────────────┴────────────────┘                          │  │
│   │                          │                                           │  │
│   │                          ▼                                           │  │
│   │                  ┌─────────────┐                                     │  │
│   │                  │   Fusion    │  RRF (Reciprocal Rank Fusion)       │  │
│   │                  │   Layer     │                                     │  │
│   │                  └──────┬──────┘                                     │  │
│   └─────────────────────────┼───────────────────────────────────────────┘  │
│                             │                                               │
│                             ▼                                               │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    LLM ORCHESTRATION                                 │  │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                  │  │
│   │  │   Profile   │  │  Retrieved  │  │ Voiceprint  │                  │  │
│   │  │   Context   │  │   Context   │  │   Style     │                  │  │
│   │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                  │  │
│   │         │                │                │                          │  │
│   │         └────────────────┴────────────────┘                          │  │
│   │                          │                                           │  │
│   │                          ▼                                           │  │
│   │                  ┌─────────────┐                                     │  │
│   │                  │    Groq     │  openai/gpt-oss-120b                │  │
│   │                  │     LLM     │                                     │  │
│   │                  └──────┬──────┘                                     │  │
│   └─────────────────────────┼───────────────────────────────────────────┘  │
│                             │                                               │
│                             ▼                                               │
│   Response: "I believe in hiring for potential over credentials..."        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Chat Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/langgraph/chat` | Main chat endpoint (recommended) |
| `POST` | `/api/v1/chat` | Legacy chat endpoint |
| `GET` | `/api/v1/health` | Health check |

### Chat Request Example

```json
{
  "query": "What's your approach to hiring?",
  "user_id": "user_123",
  "profile_id": "john_doe",
  "session_id": "optional_session_id",
  "language": "en"
}
```

---

## Database Schema

### Multi-Tenant Data Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATABASE SCHEMA                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │    companies     │                                                       │
│  │ ──────────────── │                                                       │
│  │ id (PK)          │◀──────────────────────┐                              │
│  │ name             │                       │                              │
│  │ industry         │                       │                              │
│  │ metadata (JSONB) │                       │                              │
│  └──────────────────┘                       │                              │
│                                             │                              │
│  ┌──────────────────┐                       │                              │
│  │executive_profiles│                       │                              │
│  │ ──────────────── │                       │                              │
│  │ id (PK)          │◀───────────┐          │                              │
│  │ company_id (FK)  │────────────┼──────────┘                              │
│  │ name             │            │                                          │
│  │ title            │            │                                          │
│  │ profile_data     │            │  (JSONB - full profile)                 │
│  │ voiceprint_data  │            │  (JSONB - voiceprint)                   │
│  │ hierarchy_level  │            │                                          │
│  │ reports_to (FK)  │────────────┘  (self-reference for org chart)         │
│  └──────────────────┘                                                       │
│           │                                                                 │
│           │                                                                 │
│  ┌────────┴─────────┐         ┌──────────────────┐                         │
│  │                  │         │                  │                         │
│  ▼                  ▼         ▼                  │                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐         │
│  │executive_documents│  │ onboarding_jobs  │  │   embeddings     │         │
│  │ ──────────────── │  │ ──────────────── │  │ ──────────────── │         │
│  │ id (PK, UUID)    │  │ id (PK, UUID)    │  │ id (PK)          │         │
│  │ company_id       │  │ company_id       │  │ company_id       │         │
│  │ executive_id     │  │ executive_id     │  │ executive_id     │         │
│  │ (NULL for KB)    │  │ status           │  │ (NULL for KB)    │         │
│  │ doc_type         │  │ progress         │  │ source_type      │         │
│  │ filename         │  │ assembled_profile│  │ embedding (1024) │         │
│  │ extracted_text   │  │ validation_report│  │ metadata (JSONB) │         │
│  │ parsing_method   │  └──────────────────┘  └──────────────────┘         │
│  │ ocr_applied      │                                                      │
│  └──────────────────┘                                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Tables

| Table | Purpose |
|-------|---------|
| `companies` | Company registration |
| `executive_profiles` | Executive info + profile JSON + voiceprint JSON |
| `executive_documents` | Uploaded documents with extracted text (profile + knowledgebase) |
| `onboarding_jobs` | Pipeline job tracking |
| `embeddings` | Vector embeddings for RAG retrieval |
| `decision_cases` | Individual decision cases for learning |

### Document Types in executive_documents

| doc_type | executive_id | Description |
|----------|--------------|-------------|
| `profile` | `{executive_id}` | Executive-specific docs (interviews, bios) - go through LLM extraction |
| `knowledgebase` | `NULL` | Company-wide docs (policies, procedures) - direct embedding, shared by all |

---

## Pipeline Deep Dive

### Job Status Flow

```
pending → parsing → extracting → assembling → validating → deploying → embedding → completed
                                                                                      │
                                                                              (on error)
                                                                                      ▼
                                                                                   failed
```

### Calibration Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| `full` | Re-runs all 7 extractors | Major document changes |
| `incremental` | Runs only specified extractors | Minor updates |

```bash
# Full calibration
curl -X POST http://localhost:8002/api/v1/companies/my_company/executives/john_doe/calibrate \
  -H "Content-Type: application/json" \
  -d '{"mode": "full", "regenerate_embeddings": true}'

# Incremental calibration (only values and communication)
curl -X POST http://localhost:8002/api/v1/companies/my_company/executives/john_doe/calibrate \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "incremental",
    "extractors": ["values_decisions", "communication_style"],
    "merge_strategy": "replace"
  }'
```

### Profile Editing with Dot Notation

```bash
# Edit nested fields using dot notation
curl -X PATCH http://localhost:8002/api/v1/companies/my_company/executives/john_doe/profile \
  -H "Content-Type: application/json" \
  -d '{
    "sections": {
      "core_values": ["integrity", "innovation", "teamwork"],
      "communication_style.formality_scale": 7,
      "decision_making.risk_tolerance": 6
    }
  }'
```

---

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key for LLM | `gsk_xxx...` |

### Optional (with defaults)

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `ai_officer_dev` | Database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres123` | Database password |
| `NEO4J_USER` | `neo4j` | Neo4j user |
| `NEO4J_PASSWORD` | `12341234` | Neo4j password |
| `REDIS_PASSWORD` | `redis123` | Redis password |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Embedding model |
| `EMBEDDING_DIMENSION` | `1024` | Vector dimensions |
| `LLM_MODEL` | `openai/gpt-oss-120b` | LLM model for chat |

### Onboarding-Specific

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_EXTRACTION_API_KEY` | `${GROQ_API_KEY}` | Separate key for extraction (rate limits) |
| `GROQ_SYNTHESIS_API_KEY` | `${GROQ_API_KEY}` | Separate key for synthesis |
| `ONBOARDING_SERVICE_PORT` | `8002` | Onboarding service port |
| `EMBEDDING_SERVICE_URL` | `http://embedding-service:8001` | Embedding service URL |

### OCR (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `OCR_BACKEND` | `mineru` | OCR backend: `mineru` or `olmocr2` |
| `OCR_MIN_TEXT_LENGTH` | `100` | Min chars before triggering OCR |
| `MINERU_TIMEOUT` | `600` | OCR timeout in seconds |

---

## Swagger Documentation

Each service provides interactive API documentation:

- **Onboarding Service**: http://localhost:8002/docs
- **Embedding Service**: http://localhost:8001/docs
- **RAG API**: http://localhost:8000/docs

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| `Executive not found` | Ensure company exists first, then create executive |
| `No documents found` | Upload documents before starting onboarding |
| `Embedding dimension mismatch` | Run migrations: schema expects 1024-dim vectors |
| `Groq rate limit` | Use separate API keys for extraction/synthesis |

### Logs

```bash
# View service logs
docker-compose logs -f onboarding-service
docker-compose logs -f embedding-service
docker-compose logs -f rag-api
```

### Database Reset

```bash
# Full reset (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
```

---

## Contributing

1. Create feature branch from `onboarding-pipeline`
2. Follow existing code patterns
3. Update this README if adding endpoints
4. Test with `docker-compose up`

---

## License

Internal use only - Example Company
