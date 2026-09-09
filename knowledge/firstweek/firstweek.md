# FirstWeek

Private project onboarding with conversational, source-backed answers.

## About
FirstWeek helps project members understand a codebase, its architecture and its documented context. The workspace includes project guides, visual architecture, a source reader and a conversational assistant. It reuses identity and model-provider components from an earlier avatar application; avatars and executive personas are not part of the FirstWeek question flow.

## Technology stack
React and Vite, Express, FastAPI and Python, PostgreSQL with Prisma, SQLite FTS5, Sentence Transformers and Groq. The local English demo uses all-MiniLM-L6-v2 embeddings and Groq's configured openai/gpt-oss-120b model.

## Architecture
The browser sends a question and up to three recent conversation turns to the Express auth gateway. The gateway checks an active, verified company identity and explicit project membership in PostgreSQL. Only then does it forward the server-derived project/company scope to the internal FastAPI service using a server-only service token. Retrieval combines SQLite full-text ranking with local vector similarity inside that project. The existing LLM factory sends the selected passages and conversation to Groq, which generates an answer with source citations. Membership is checked again before the response is delivered.

## Knowledge ingestion
Curated Markdown project guides and their evidence hashes live on the server. An atomic index build splits guides into sections and computes local embeddings. The browser never receives the whole private corpus. A freshness check identifies changed repository evidence. Managed uploads and automatic repository synchronization remain planned.

## Where to start
Read `frontend/src/firstweek/Workspace.jsx` for project navigation and chat, `backend/auth-service/routes/firstweekRoutes.js` for the access gateway, `RAG/firstweek/api.py` for generation, and `RAG/firstweek/index.py` for retrieval. The local setup is documented in `docs/firstweek/RUNBOOK.md`.

## Current limitations
The local authenticated flow, hybrid retrieval and Groq generation have been verified. This does not establish a production deployment. Conversations remain in memory. Membership administration is implemented, with PostgreSQL concurrency, authorization, restart and authenticated desktop/mobile browser checks. Editable responsibilities, managed uploads and a separately published portfolio collection remain planned. New projects start with no indexed sources. Legacy avatar services are preserved in the repository but are not the active FirstWeek retrieval path.

## Ownership
The workspace owner selected this project for their portfolio. A current team responsibility map has not been supplied; do not invent individual component owners.

## Architecture flow
The active FirstWeek request path. PostgreSQL authorizes access; the local index retrieves evidence. Groq generates the final answer.

- Project workspace → Membership gateway: question.
- Membership gateway → Identity database: access check.
- Membership gateway → Scoped retrieval: verified scope.
- Scoped retrieval → Generative model: evidence.
- Generative model → Cited response: generated answer.

## Evidence
- `FirstWeek/README.md`
- `FirstWeek/frontend/src/firstweek/Workspace.jsx`
- `FirstWeek/backend/auth-service/routes/firstweekRoutes.js`
- `FirstWeek/RAG/firstweek/api.py`
- `FirstWeek/RAG/firstweek/index.py`
- `FirstWeek/backend/auth-service/shared/prisma/schema.prisma`
