# FirstWeek implementation plan

Status: initial foundation and frontend slice implemented; this is not a production-readiness sign-off.

## Current delivery checkpoint

- Complete: 5 source-backed private project guides; 45 chunks with full-text and local semantic vectors; atomic rebuild and source freshness checks.
- Complete in code: membership models/migration, authenticated gateway, internal scoped RAG API, and opt-in existing embedding/LLM adapters.
- Complete initial frontend: FirstWeek sign-in, project directory, overview, Ask, source reader, knowledge and people views; development-only fictional preview.
- Verified: frontend production build, Prisma schema validation, isolation/input tests, browser question-to-source flow, desktop/mobile overview and sign-in review.
- Live-verified on an isolated PostgreSQL 16 database: original-schema migration, real login and logout, five memberships, question-to-source retrieval, client scope spoofing ignored, immediate membership revocation and restoration, and internal service-token enforcement.
- Verified locally: MiniLM semantic model loading and retrieval for natural-language stack questions; bounded conversational context, provider-failure handling, and generation integration using a test double.
- User approved Groq processing of selected private guide passages and recent chat turns. Live Groq tests passed for the exact deployment/technology question, a contextual bot-architecture follow-up, and a greeting.
- Not yet live-verified: production infrastructure.
- Still planned: managed ingestion, editable responsibilities/membership administration, durable project conversations/checklists, remaining account-screen work, published portfolio collection and deployment.

## Product and access contract

FirstWeek is a project onboarding workspace for people who belong to a project. Members learn what a project does, how it is built, where to start, and who owns each area. Every answer must be supported by accessible sources. A company role alone does not grant access to private projects, including administrators: administrators manage membership, and must also be members to read project content. Public portfolio chat uses a separately published collection and is a later delivery surface.

The initial local corpus is private. The requested `/User/projects` does not exist; the source root is `/Users/dev_an/projects`. Reading repositories does not establish personal authorship, current maintenance, deployment status, or team responsibilities. Missing ownership is shown as unknown.

## System component plan

| Component | Decision | Reason / required work |
|---|---|---|
| `frontend/` React, Vite, React Router, Zustand, Markdown, Lucide | Build FirstWeek product surfaces | Keep authentication state and HTTP helpers aligned with project-scoped routes. |
| Auth service, sessions, company model | Extend with project access | Add projects and membership. Validate membership on every project request; company membership is insufficient. |
| Chat service and persistent conversations | Add mandatory project scope | Bind conversation to project and member; guard history, sockets, citations and interruption. |
| RAG embedding model and provider clients | Configure for onboarding answers | Use the embedding manager and configurable LLM factory without personas. |
| Vector, graph and memory retrieval | Enforce scope before integration | All retrieval paths must require project filters before private FirstWeek data is indexed. |
| Onboarding document parsers and chunking | Propagate project scope | Uploads, jobs, chunks, deletion and status must carry immutable project and company IDs. |
| Docker, Caddy, observability, evaluation | Adapt | Docker unavailable on this machine; frontend currently serves Vite dev. Replace production serving and verify service boundaries before deployment. |

## Corpus and provenance

Start with curated Markdown about documents rather than an indiscriminate source dump. Each document contains purpose, implemented mechanics, architecture, reading path, limitations, ownership status, and evidence paths. A manifest records project ID, source SHA-256 hashes and snapshot date. Regeneration detects source drift; refresh requires re-analysis rather than silently treating old summaries as current. No `.env`, databases, backups, private learning logs, questionnaire data, dependency trees, binaries or credentials enter the corpus.

Active projects: FirstWeek, AI PR Review Agent, MoneyPlant, RAG-Builder and Personal Site. WasmEdge, riscV, random_exp and OopsC++ are excluded at the owner’s request. Learning RAG and C++ Shell are deferred until the owner publishes them. Source repositories remain untouched. Each active project has a source-backed architecture diagram and an indexed text equivalent.

## Phase 1 — Concrete foundation (current implementation)

- Document component boundaries and source-backed project guides with a private manifest.
- Build a reproducible local project-scoped full-text index; parameterized queries, immutable per-document project scope, content hashes and atomic replacement.
- Add opt-in semantic indexing using the existing RAG embedding model and rank fusion; never silently call lexical retrieval semantic RAG.
- Use the RAG LLM provider for optional sourced generation. Without a configured model, return clearly labelled source excerpts, not simulated AI answers.
- Introduce Project and ProjectMember in auth Prisma schema with a reviewed additive migration.
- Add authenticated FirstWeek API gateway: project list, overview, documents, source reading and questions. Require active, verified company membership plus explicit project membership; no administrator read bypass.
- Internal RAG routes require a dedicated service token and exact company/project scope. No corpus JSON or Markdown in the browser bundle or public directory.
- Add runnable negative tests for cross-project retrieval, wrong-company reads, missing membership and source paths.

## Phase 2 — Complete frontend revamp with Impeccable

Primary surface mode: Operate; project guides and source readers use Read. Keep React/Vite and existing dependencies.

Routes: `/projects`, `/projects/:projectId`, `/projects/:projectId/ask`, `/projects/:projectId/knowledge`, `/projects/:projectId/team`, `/projects/:projectId/start`, plus workspace membership management and revised sign-in/account flows.

Project home: project purpose and architecture, source freshness, next reading steps, named ownership only when entered by an authorized maintainer. Project switcher lists memberships only. Ask view: scoped conversation, accessible composer, source panel with document provenance. Knowledge view: search, document reader, ingestion status and deletion. Team view: responsibilities and contact path. Getting started: actual setup instructions and per-user completion state. Admin: create project, invite/remove members, assign responsibilities and manage sources.

Interaction states: initial loading, no memberships, no sources, no evidence, stale documents, model unavailable, index unavailable, request timeout, membership removed, document deleted, small-screen navigation and keyboard focus. Clear old project content immediately on switching; discard stale responses and clear private state on sign-out. Unknown owners remain unknown.

Visual direction is chosen through Impeccable's design round before UI code. No invented metrics, customer claims, synthetic teammates or fake working buttons. Desktop/mobile browser verification uses gstack browse, followed by one batched correction pass and bounded finish review.

## Phase 3 — Production retrieval and ownership

Extend PostgreSQL/pgvector document tables with non-null company/project keys and composite foreign keys. Persist ingestion jobs and document versions. Move local index behind the same scoped repository contract when multi-worker writes or corpus size requires it. Strict filters apply before vector ranking, graph expansion, memory retrieval and reranking. Include scope, membership version and index version in cache keys. No shared-company source union until that explicit sharing model exists.

Store responsibilities as maintained records with owner membership, area, status and reviewed date. Do not infer live task ownership from Git authors. Add project-scoped conversations and durable checklists; reconcile member removal across active sockets and in-flight answers. Generated answers treat source text as evidence, not instructions; enforce a citation allowlist and avoid unsupported claims.

## Phase 4 — Demo, portfolio API and deployment

Use an explicitly published collection, never the private index. Public API has a collection-specific token, bounded input, rate limits, cost budget, allowed origins and citations restricted to published sources. Portfolio embed is a consumer of this API, not a privileged key in JavaScript.

Serve static frontend build. Keep internal RAG routes off public proxies. Configure production secrets, backups, health checks, TLS, logs without tokens/content, and retention. Resolve existing audit findings for exposed routes. Test authenticated end-to-end flow with real databases and a configured model, adversarial isolation cases, first-response time and a small golden question set before describing it as production-ready.

## Acceptance checks

1. A member can list only assigned projects; the same URL/API called by a nonmember reveals no project metadata.
2. Identical keywords in two projects never produce cross-project documents or citations.
3. Member removal takes effect on subsequent reads and before an in-flight answer is returned.
4. Missing or mismatched service token fails closed; client-supplied company/user/role never defines authorization.
5. Index rebuild is reproducible, atomic, excludes symlink escapes, and removes deleted documents.
6. An unknown question produces an honest no-evidence state; an unconfigured model returns labelled excerpts.
7. Each about document has inspectable evidence and never invents a personal contribution or owner.
8. UI remains usable with keyboard and at 390px; project switches cannot flash another project's answer.
9. No deployment occurs until live integration, isolation and operational checks pass.

## Current review boundary

Complete this scoped change: visual architecture for five projects, curated directory/index exclusions, and the FirstWeek product/repository rename. Do not start the remaining product areas until the user confirms.
