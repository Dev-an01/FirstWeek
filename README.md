# FirstWeek

FirstWeek is a source-grounded onboarding workspace for software projects. It helps new team members understand what a project does, how it is built, what to read next, and who owns each responsibility without inventing answers that are not present in the project knowledge base.

The repository contains two deliberately separate experiences:

- **Private workspace:** authenticated project onboarding with membership-scoped knowledge, managed documents, saved conversations, company context, reading paths, and personal progress.
- **Public showcase:** an anonymous, read-only portfolio demo built from a separately authored six-project collection. Visitors can inspect project guides and architecture, then ask questions grounded only in the selected public project.

> **Current status:** the private M1 milestone is accepted locally. M2-01 through M2-03 are accepted locally, while M2-04 integration acceptance remains in progress. The public showcase and its cost controls are accepted locally, but hosted provider, Redis, Vercel, and public-launch verification are still pending.

## Contents

- [Why FirstWeek](#why-firstweek)
- [What is implemented](#what-is-implemented)
- [Architecture](#architecture)
- [Run the public showcase](#run-the-public-showcase)
- [Run the private workspace](#run-the-private-workspace)
- [Environment files](#environment-files)
- [Tests and verification](#tests-and-verification)
- [Project structure](#project-structure)
- [Roadmap](#roadmap)
- [Documentation](#documentation)

## Why FirstWeek

Project onboarding information is usually scattered across repositories, documents, chat history, and individual memory. A generic chatbot can produce a fluent answer while using the wrong project, stale information, or an invented owner.

FirstWeek treats project boundaries and evidence as product requirements:

- Project membership determines which private evidence a user may access.
- Answers show their supporting sources.
- Missing knowledge is reported instead of fabricated.
- Company assignments and responsibility owners are explicitly maintained.
- Public portfolio content is separately authored and never synchronized from private uploads.

## What is implemented

### Private workspace

- Project creation, membership, roles, invitations, and removal safeguards
- Maintained responsibilities and same-project ownership assignments
- Private document upload, indexing, retrieval, source reading, and deletion
- Persistent project conversations with bounded server-owned history
- Per-member onboarding focus and experience preferences
- Company teams and explicit assignments with provenance
- Maintainer-authored reading paths and private completion progress
- English and Japanese interface support

### Public showcase

- Six explicitly published project summaries, guides, and architecture views
- Anonymous read-only browsing with no create, edit, upload, or membership APIs
- Project-scoped keyword retrieval with typo-tolerant matching
- Retrieval-first generation using numbered public evidence
- OpenAI primary generation, optional Groq fallback, and free-model OpenRouter fallback
- Upstash-backed visitor, global, and paid-attempt limits
- Browser-memory-only conversations that reset on reload
- Public-only Vite/Vercel entry point with no private database or private RAG import

The published projects are FirstWeek, AI PR Review Agent, RAG-Builder, MoneyPlant, Personal Site, and Movie Enquirer.

## Architecture

### Private workspace

```text
React/Vite workspace
        |
        v
Express authentication and project-membership gateway
        |                         |
        v                         v
PostgreSQL workspace data     Python RAG API
                                  |
                         retrieval + graph context
                                  |
                         cited, scoped response
```

The private application stores users, companies, memberships, managed knowledge, conversations, profiles, assignments, reading paths, and progress in PostgreSQL. Retrieval is scoped by server-derived company and project identity. Neo4j, Redis, and the embedding service support the broader RAG stack.

### Public showcase

```text
Anonymous visitor
        |
        v
React public-only workspace
        |
        v
Node public API -> authored public collection -> project-scoped retrieval
                                                |
                                                v
                                  OpenAI -> Groq -> OpenRouter
                                                |
                                                v
                                    cited public-only answer
```

`frontend/server/publicCollection.js` is the sole public corpus. The public function does not import the private manifest, PostgreSQL data, uploads, user profiles, teams, or saved conversations.

## Run the public showcase

### Prerequisites

- Node.js 22 or newer
- npm

### Offline local demo

The offline mode exercises the public UI and retrieval without calling an LLM or requiring Redis.

```bash
git clone https://github.com/Dev-an01/FirstWeek.git
cd FirstWeek
git switch public-showcase
cd frontend
npm ci
FIRSTWEEK_PUBLIC_ORIGIN=http://127.0.0.1:5173 FIRSTWEEK_PUBLIC_GENERATE=false npm run dev -- --mode public
```

Open [http://127.0.0.1:5173/showcase](http://127.0.0.1:5173/showcase).

### Local generated answers

Create `frontend/.env.local`:

```dotenv
FIRSTWEEK_PUBLIC_ORIGIN=http://127.0.0.1:5173
FIRSTWEEK_PUBLIC_GENERATE=true

OPENAI_API_KEY=replace_me
FIRSTWEEK_PUBLIC_OPENAI_MODEL=gpt-5.6-luna

UPSTASH_REDIS_REST_URL=https://replace-me.upstash.io
UPSTASH_REDIS_REST_TOKEN=replace_me
FIRSTWEEK_PUBLIC_RATE_SECRET=replace_with_at_least_32_random_characters

FIRSTWEEK_PUBLIC_IP_DAILY_LIMIT=10
FIRSTWEEK_PUBLIC_GLOBAL_DAILY_LIMIT=30
FIRSTWEEK_PUBLIC_OPENAI_TOTAL_LIMIT=100
```

Then restart the public development server:

```bash
cd frontend
npm run dev -- --mode public --host 127.0.0.1
```

Groq and OpenRouter are optional fallbacks. See the [public deployment guide](docs/firstweek/PUBLIC-DEPLOYMENT.md) for the complete provider order, accepted values, rate limits, and Vercel setup.

## Run the private workspace

### Prerequisites

- Node.js 22 or newer
- Python 3.10 or newer
- Docker with Docker Compose

### Full local stack

```bash
git clone https://github.com/Dev-an01/FirstWeek.git
cd FirstWeek
git switch main
cp .env.example .env
```

Update `.env` with your database credentials and provider keys, then start the services:

```bash
docker compose up --build
```

The development Compose file starts the frontend, authentication service, chat service, onboarding service, RAG API, embedding service, PostgreSQL databases, Neo4j, and Redis.

For the private data model, migrations, isolated test database, authorization boundaries, and recovery behavior, follow the [FirstWeek runbook](docs/firstweek/RUNBOOK.md).

### Frontend only

Use this when working on UI that does not require a complete authenticated backend flow:

```bash
cd frontend
npm ci
npm run dev
```

The private application expects its API services to be available through the Vite development proxies. Frontend-only mode does not provide working authentication, persistence, or private RAG by itself.

### Local knowledge index

```bash
python3 -m RAG.firstweek.index build --company local-workspace
python3 -m RAG.firstweek.index search --company local-workspace --project moneyplant "transaction categorization"
python3 -m RAG.firstweek.index check
```

Add `--semantic` when a supported embedding provider is configured.

## Environment files

| File or location | Purpose |
| --- | --- |
| Root `.env` | Private Docker/full-stack database, service, embedding, and provider configuration |
| `frontend/.env.public` | Non-secret public-only Vite entry flag |
| `frontend/.env.local` | Ignored local server secrets for generated public chat |
| Vercel Environment Variables | Production public-chat keys, Upstash credentials, origin, models, and limits |

Never place provider keys or Redis credentials in variables beginning with `VITE_`; Vite exposes those variables to browser code. The public deployment intentionally does not load the root private `.env`.

## Tests and verification

### Public showcase

```bash
cd frontend
npm run test:public
npm run build:public
```

### Frontend

```bash
cd frontend
npm test -- --runInBand
npm run build
```

### Local RAG index

```bash
python3 -m unittest RAG.firstweek.test_index
```

Some private integration tests require the isolated PostgreSQL test database described in the runbook. Local mocked-provider tests do not establish that OpenAI, Groq, OpenRouter, Upstash, or Vercel work in a hosted environment.

## Project structure

```text
FirstWeek/
├── frontend/                  React/Vite private and public interfaces
│   ├── api/                   Vercel public function entry
│   ├── server/                Public collection, retrieval, limits, providers
│   └── src/firstweek/         Workspace UI and project views
├── backend/
│   ├── auth-service/          Identity, membership, workspace APIs, Prisma
│   ├── chat-service/          Project chat service
│   └── onboarding-service/    Profile extraction and synthesis
├── RAG/                       Python retrieval, graph, embeddings, and API
├── knowledge/                 Curated private project guides and manifest
├── docs/firstweek/            Roadmap, runbooks, acceptance, deployment notes
├── TRACK.md                   Current status and acceptance evidence
├── PRODUCT.md                 Product scope and principles
└── docker-compose*.yml        Local and production-oriented service definitions
```

## Roadmap

| Milestone | Status | Remaining outcome |
| --- | --- | --- |
| **M1: Private onboarding workspace** | Accepted locally | No remaining work in the accepted local M1 scope |
| **M2: Company context and personalization** | In progress | M2-01 through M2-03 are accepted; M2-04 must verify the combined profile, company-context, reading-progress, and grounded-answer flows |
| **M3: Maintainable knowledge and evaluated RAG** | Planned | Repository import and refresh lifecycle, source deletion propagation, golden evaluations, citation precision, prompt-injection cases, and curated-source reading paths |
| **M4: Complete frontend and account experience** | Planned | Finish signup, recovery, account, and admin screens; verify accessibility, responsive layouts, and error recovery |
| **M5: Public portfolio assistant** | Partial local slice accepted | Add an explicit publication workflow, personal-site integration, and embeddable assistant while preserving the private/public boundary |
| **M6: Deployment-ready demo** | Partial preparation complete | Run live provider and Upstash checks, deploy and verify Vercel, validate health/monitoring, secrets, backups and restore, then produce an explicit readiness report |

### Immediate next work

1. Complete M2-04 combined integration and independent acceptance.
2. Deploy a protected public preview and verify live OpenAI, fallback, Upstash quota, origin, and private-route denial behavior.
3. Complete M3 ingestion lifecycle and retrieval-quality evaluation.
4. Finish the remaining account and accessibility work in M4.
5. Add the publication/admin and embedded-widget work needed to complete M5.
6. Complete the operational and restore evidence required for M6 production readiness.

Progress is tracked in [TRACK.md](TRACK.md). Acceptance criteria and milestone definitions are in the [roadmap](docs/firstweek/MILESTONES.md).

## Deployment

### Public demo

The public demo is designed for Vercel with:

- Branch: `public-showcase`
- Root directory: `frontend`
- Build command: `npm run build:public`
- Output directory: `dist`

Do not publish until the protected-preview checks in the [public deployment guide](docs/firstweek/PUBLIC-DEPLOYMENT.md) pass.

### Private application

The repository contains Docker Compose definitions, but the roadmap does not claim production readiness. M6 still requires reviewed static serving, private networking, controlled migrations, secrets, monitoring, backup/restore evidence, and an explicit readiness decision.

## Documentation

| Document | Purpose |
| --- | --- |
| [Product](PRODUCT.md) | Users, product purpose, constraints, and principles |
| [Current tracker](TRACK.md) | Live milestone status, verification evidence, and next work |
| [Roadmap](docs/firstweek/MILESTONES.md) | M1-M6 outcomes and acceptance criteria |
| [Project map](docs/firstweek/PROJECT-MAP.md) | Current components and repository navigation |
| [Runbook](docs/firstweek/RUNBOOK.md) | Private setup, operations, tests, and recovery behavior |
| [Public deployment](docs/firstweek/PUBLIC-DEPLOYMENT.md) | Public environment variables, limits, Vercel setup, and launch checklist |
| [M2 acceptance](docs/firstweek/M2-ACCEPTANCE.md) | Current combined M2 integration evidence and pending checks |
| [RAG architecture](docs/AI-OFFICER_RAG_COMPLETE_GUIDE.md) | Detailed RAG subsystem guide |

## Security and disclosure

Do not add secrets, private uploads, user records, company data, or saved conversations to the public collection. Treat publication as irreversible disclosure: removing a project later cannot erase copies already viewed or retained by visitors or providers.

If you discover a security issue, do not include credentials or private data in a public issue.

## License

This project is licensed under the [MIT License](LICENSE).
