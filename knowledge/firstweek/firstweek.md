# FirstWeek

Private project onboarding with conversational, source-backed answers.

## About
FirstWeek helps project members understand a codebase, its architecture and its documented context. The private workspace includes project administration, maintained responsibilities, company teams and assignments, document uploads, visual architecture, source reading, managed reading paths with private progress, saved conversations and private onboarding preferences. Existing identity and model-provider components support the FirstWeek flow.

## Technology stack
React and Vite, Express, FastAPI and Python, PostgreSQL with Prisma, SQLite FTS5, Sentence Transformers and a configurable model-provider factory. The demo supports all-MiniLM-L6-v2 embeddings and Groq generation. Local source-excerpt mode disables generation and returns labelled passages instead of generated answers.

## Architecture
The browser sends the current question and a request ID for a selected private conversation. Express verifies the session and explicit project membership in PostgreSQL, then derives recent history from saved turns. Maintained ownership, matching company-team assignments and matching uploaded passages are server-owned evidence. Company context is shared only inside the verified company and never grants project membership. A server-only token protects the scoped internal FastAPI request. Curated retrieval uses SQLite full-text search and optional local vectors; generation optionally sends selected evidence and bounded history to the configured provider. The gateway rechecks membership, knowledge and company-context snapshots and the pending turn's version before saving and returning the answer.

## Knowledge ingestion
Curated Markdown guides and repository evidence hashes stay server-side. An atomic SQLite build creates searchable sections and optional embeddings. Maintainers can also upload UTF-8 Markdown or plain text: at most 256 KiB per file, 240 chunks per document and 100 documents per project. PostgreSQL stores uploaded text and chunks together, independently of curated rebuilds. Members can read sources; only maintainers can upload or delete. Deletion removes chunks and conservatively clears saved conversation copies throughout that project. Automatic repository synchronization remains planned.

## Where to start
Read `frontend/src/firstweek/Workspace.jsx` for the workspace and saved-chat UI, `backend/auth-service/routes/firstweekRoutes.js` for project access, `backend/auth-service/routes/conversationRoutes.js` for server-owned conversation context, and `backend/auth-service/services/projectConversations.js` for persistence and retry fencing. `projectDocuments.js` handles uploads; `onboardingProfiles.js` stores private focus/experience preferences. `readingPaths.js` owns reading-path management, profile matching and private completion, while `frontend/src/firstweek/ReadingPath.jsx` renders the member and maintainer workflow. `companyTeams.js` maintains teams and `companyContext.js` selects bounded company evidence. `frontend/src/firstweek/CompanyTeams.jsx` provides the company directory and administrator controls. `RAG/firstweek/api.py` and `index.py` handle internal answers and curated retrieval. Local setup is documented in `docs/firstweek/RUNBOOK.md`.

## Current limitations
Project/membership administration, maintained responsibilities, text uploads, managed reading paths and private conversations are implemented and reviewed locally. Reading paths currently use managed project sources; curated-source reading-path support remains deferred. Conversations survive reload/restart, with limits of 20 turns and 50 conversations per user/project. Interrupted requests become retryable after 60 seconds. Changed knowledge can reset saved history to avoid exposing stale private copies. New projects start with no sources. Private networking, migration baselining, backups and hosted deployment verification remain outstanding. The latest private conversation browser checks used offline excerpts. A separate public snapshot and public-only Vercel build are implemented, but not deployed; personal-site embedding remains deferred. Automatic repository synchronization remains planned.

## Ownership
Members explicitly select or clear their private onboarding focus and explanation level through Onboarding. These preferences guide generated explanations only; they do not establish actual job roles, experience, ownership or permissions. Saving changed preferences clears only that member's project conversations. Profile version checks reject pending answers using outdated preferences. Offline excerpts are unchanged. Company teams and explicit assignments are available from All projects, even to verified company members with no project memberships. Only current company administrators can maintain them. Matching current team/assignment records can support private answers with timestamps and a disclaimer: company assignment is not proof of project ownership or access. Team changes clear saved conversations across company projects and reject stale in-flight responses. Team assignments grant no project access.

Project maintainers order reading steps backed by managed project sources and can target steps with explicit focus and experience filters. Each member sees a personal matching path and self-owned completion state; maintainers also receive the complete management list separately. Completion is revision-fenced so a material step edit resets stale progress, while unchanged saves and reordering preserve it. Source deletion and membership removal cascade the corresponding steps or private progress.

Project maintainers record responsibility areas, status and owners through People. An owner must be a current project member; removal safely leaves the responsibility unassigned. Answers receive current maintained records with provenance. This static guide does not establish individual owners or assignments; use current maintained evidence and state when an owner is unassigned.

## Architecture flow
The active FirstWeek request path. PostgreSQL authorizes access and stores private workspace data. Project-scoped retrieval supplies evidence; the configured provider optionally generates an answer.

- Project workspace → Membership gateway: question and request ID.
- Membership gateway → Workspace database: membership, saved history and maintained evidence.
- Membership gateway → Scoped retrieval: verified scope and server-owned context.
- Scoped retrieval → Generative model: evidence.
- Generative model → Saved response: optional generated answer; excerpt mode returns local passages.
- Saved response → Workspace database: validated turn, after membership and knowledge rechecks.

## Evidence
- `FirstWeek/README.md`
- `FirstWeek/frontend/src/firstweek/Workspace.jsx`
- `FirstWeek/backend/auth-service/routes/firstweekRoutes.js`
- `FirstWeek/RAG/firstweek/api.py`
- `FirstWeek/RAG/firstweek/index.py`
- `FirstWeek/backend/auth-service/shared/prisma/schema.prisma`
- `FirstWeek/backend/auth-service/routes/conversationRoutes.js`
- `FirstWeek/backend/auth-service/services/projectConversations.js`
- `FirstWeek/backend/auth-service/services/projectDocuments.js`
- `FirstWeek/backend/auth-service/services/projectResponsibilities.js`
- `FirstWeek/backend/auth-service/services/projectAdministration.js`
- `FirstWeek/backend/auth-service/services/onboardingProfiles.js`
- `FirstWeek/frontend/src/firstweek/OnboardingProfile.jsx`
- `FirstWeek/backend/auth-service/services/companyTeams.js`
- `FirstWeek/backend/auth-service/services/companyContext.js`
- `FirstWeek/frontend/src/firstweek/CompanyTeams.jsx`
- `FirstWeek/backend/auth-service/services/readingPaths.js`
- `FirstWeek/frontend/src/firstweek/ReadingPath.jsx`
