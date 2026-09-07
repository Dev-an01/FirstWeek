<![CDATA[# FirstWeek

> **AI-powered project onboarding platform** — helps new team members understand codebases, ask grounded questions, and find the right people, backed by inspectable sources and explicit access boundaries.

---

## Overview

FirstWeek is a membership-protected onboarding workspace that combines a conversational RAG (Retrieval-Augmented Generation) system with curated project knowledge. Instead of inventing answers, it retrieves evidence from indexed project documentation and makes sources visible alongside every response.

### Key Features

- **Project Onboarding Workspace** — Browse project overviews, reading guides, architecture diagrams, and team structure
- **Conversational Ask** — Ask questions about any project you're assigned to; answers cite their sources
- **Source Reader** — Inspect the exact documents and repository evidence behind every answer
- **Project Membership Access Control** — Knowledge access is scoped to assigned projects, not global roles
- **Visual Architecture** — SVG-based architecture diagrams generated from source-backed component data
- **Multi-tenant Isolation** — Company and project-level data boundaries
- **Internationalization** — English and Japanese language support

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, Vite, i18n (en/ja) |
| **Backend Services** | Node.js, Express |
| **RAG Engine** | Python, LangGraph, LangChain |
| **Databases** | PostgreSQL, Neo4j (knowledge graph), Redis (cache) |
| **Embeddings** | Configurable embedding models via provider factory |
| **LLM Integration** | Groq, configurable LLM provider factory |
| **Avatar Interface** | WebRTC, Socket.IO |
| **Infrastructure** | Docker Compose, Kubernetes (GCP), Caddy |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React/Vite)                     │
│   Login · Project Directory · Workspace · Ask · Architecture     │
└──────────────┬──────────────────────────────────┬───────────────┘
               │                                  │
      ┌────────▼────────┐               ┌────────▼────────┐
      │  Auth Service    │               │  Chat Service    │
      │  (Express)       │               │  (Express + WS)  │
      └────────┬────────┘               └────────┬────────┘
               │                                  │
               │              ┌───────────────────▼───────────┐
               │              │       Recall Service           │
               │              └───────────────────┬───────────┘
               │                                  │
      ┌────────▼────────┐               ┌────────▼────────┐
      │   PostgreSQL     │               │   RAG Engine     │
      │   (Users, ACL)   │               │   (Python)       │
      └─────────────────┘               ├──────────────────┤
                                         │ · LangGraph      │
                                         │ · Hybrid Search  │
                                         │ · Graph Context  │
                                         │ · Cognitive Twin  │
                                         └──┬──────────┬───┘
                                            │          │
                                    ┌───────▼──┐  ┌───▼───────┐
                                    │  Neo4j    │  │ Embedding │
                                    │  (Graph)  │  │ Service   │
                                    └──────────┘  └───────────┘
```

---

## Getting Started

### Prerequisites

- **Node.js** ≥ 18
- **Python** ≥ 3.10
- **Docker & Docker Compose** (for full stack)
- **PostgreSQL**, **Neo4j**, **Redis** (or use Docker)

### Quick Start — Frontend Only

```bash
cd frontend
npm install
npm run dev
```

### Quick Start — Full Stack (Docker)

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your API keys and database credentials

# Start all services
docker compose up --build
```

### Local RAG Index

Build and search the local project knowledge index without any network calls:

```bash
# Build the index
python3 -m RAG.firstweek.index build --company local-workspace

# Search a project
python3 -m RAG.firstweek.index search --company local-workspace --project moneyplant 'transaction categorization'

# Health check
python3 -m RAG.firstweek.index check
```

Add `--semantic` to enable embedding-model-backed retrieval (requires a configured embedding provider).

---

## Project Structure

```
FirstWeek/
├── frontend/              # React/Vite workspace UI
│   └── src/
│       ├── firstweek/     # Onboarding workspace components
│       ├── components/    # Shared UI components
│       ├── pages/         # Route pages
│       ├── services/      # API clients
│       └── i18n/          # Translations (en, ja)
├── frontend-avatar/       # WebRTC avatar interface
├── backend/
│   ├── auth-service/      # Authentication, project membership
│   ├── chat-service/      # WebSocket chat, conversation management
│   ├── recall-service/    # RAG integration bridge
│   └── db-init/           # Database initialization scripts
├── RAG/                   # Python RAG engine
│   ├── firstweek/         # FirstWeek-specific indexing & retrieval
│   ├── langgraph_workflow/# LangGraph orchestration
│   ├── hybrid_retrieval/  # Vector + full-text search
│   ├── graph_context/     # Neo4j knowledge graph
│   ├── cognitive_twin/    # Personality-aware response generation
│   ├── embedding_*/       # Embedding generation & serving
│   ├── llm_integration/   # LLM provider factory
│   └── onboarding/        # Profile & voiceprint onboarding
├── knowledge/             # Curated project guides & manifests
├── docs/                  # Architecture docs, runbooks, audits
├── kubernetes/            # K8s manifests & deployment scripts
├── scripts/               # Utility & setup scripts
├── docker-compose.yml     # Development environment
├── docker-compose.prod.yml# Production environment
└── Caddyfile              # Reverse proxy configuration
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [Implementation Plan](docs/firstweek/IMPLEMENTATION_PLAN.md) | Full implementation scope and reuse assessment |
| [Runbook](docs/firstweek/RUNBOOK.md) | Setup, API contracts, and operational limits |
| [Milestones](docs/firstweek/MILESTONES.md) | Development milestones and progress |
| [Product Requirements](PRODUCT.md) | Product purpose, users, and principles |
| [Design System](DESIGN.md) | Visual design tokens, components, and guidelines |
| [API Documentation](API_DOCUMENTATION.yaml) | OpenAPI specification |
| [RAG Architecture](docs/AI-OFFICER_RAG_COMPLETE_GUIDE.md) | Complete RAG system guide |
| [Security Audit](docs/SECURITY_AUDIT.md) | Security review and findings |
| [Kubernetes Guide](kubernetes/README.md) | Deployment to GCP/GKE |

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Key variables include database credentials, API keys for LLM/embedding providers, JWT secrets, and service URLs. See [`.env.example`](.env.example) for the full list.

---

## Deployment

### Docker Compose (Production)

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

### Kubernetes (GCP/GKE)

Step-by-step scripts are provided in `kubernetes/scripts/`:

```bash
./kubernetes/scripts/1-setup-gcp.sh
./kubernetes/scripts/2-create-cluster.sh
./kubernetes/scripts/3-build-images.sh
./kubernetes/scripts/4-deploy-secrets.sh
./kubernetes/scripts/5-deploy-app.sh
./kubernetes/scripts/6-health-check.sh
```

See the [Kubernetes README](kubernetes/README.md) for details.

---

## License

This project is licensed under the [MIT License](LICENSE).
]]>
