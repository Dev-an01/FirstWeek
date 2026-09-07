# FirstWeek foundation runbook

## Available now

Five private project guides, a reproducible local full-text index, strict company/project retrieval, internal RAG endpoints, and an authenticated membership gateway. The initial Impeccable frontend now includes sign-in, a project directory, project overview, sourced questions, a source reader, knowledge and people views. This is not the completed production deployment. The standalone local wrapper now defaults to semantic retrieval and conversational generation using the existing provider code; the core API retains explicit environment flags.

The generated index stays in ignored `.firstweek/` with owner-only file permissions. The Markdown corpus stays server-side in `knowledge/firstweek/`; never copy it to `frontend/public` or import it into browser code. The guides are curated summaries, not a raw repository-code index. Evidence is hashed but source file content is not automatically uploaded.

## Local indexing, no services required

From the repository root:

```sh
python3 -m RAG.firstweek.index build --company local-workspace
python3 -m RAG.firstweek.index search --company local-workspace --project moneyplant 'transaction categorization'
python3 -m RAG.firstweek.index check
python3 -m unittest RAG.firstweek.test_index -v
node --test backend/auth-service/tests/projectAccess.test.js backend/auth-service/tests/firstweekRoutes.test.js
```

`check` exits nonzero when an evidence file changes or disappears. Re-read changed evidence and edit the affected guide before updating its manifest hash. It does not rewrite guides or bless changed evidence automatically.

The importer rebuilds the complete single-company corpus atomically. It is intended for the small local demo corpus, not concurrent multi-tenant ingestion. An old process can finish reading its old snapshot while new requests open the new one. Future managed uploads belong in PostgreSQL with job/version state, as described in the implementation plan.

## Frontend preview

Start `npm run dev` from `frontend/` and open `http://localhost:5173/preview/northstar-api`. This explicit development-only route contains a fictional project; it exercises navigation, excerpt answers and source reading without private data or a database. The preview module is excluded from production output. The real workspace is `/projects`, requires sign-in, and reads only the authenticated API. There is no mock fallback on private routes.

Actual company/project data requires the identities and index setup below. Conversation turns are currently in-memory and reset when leaving the Ask view. Uploads, editable ownership, persistent conversations and interactive project administration remain planned. The older signup, password recovery and account/admin screens are retained during migration.

## Connect to actual identities

1. Install the existing auth-service dependencies and generate Prisma with `npm run generate` from `backend/auth-service`.
2. Apply the additive project migration using the repository's established database migration workflow. Do not run `db:reset`. Existing databases not managed by Prisma migrations must be baselined before `prisma migrate deploy`; inspect migration history first. The migration was tested against an isolated local database created from the original schema; it has not been applied to any preexisting or production database.
3. Choose a real existing company ID and an active verified user ID. Run `node scripts/firstweek-register-projects.js --company COMPANY_ID --member USER_ID`. This grants that explicit user membership in the five imported projects; it has not been run automatically.
4. Rebuild the knowledge index with `--company COMPANY_ID`. `local-workspace` is an offline test identifier, not a real authorization bypass.
5. Supply an identical random server-only `FIRSTWEEK_SERVICE_TOKEN` (at least 32 characters) to auth and RAG. Set `FIRSTWEEK_INDEX_PATH` to the private generated SQLite file in the RAG environment. Set `FIRSTWEEK_RAG_URL` in auth when not using the existing `RAG_API_URL`.

## Internal service

The router is mounted in the existing RAG application. For isolated development with FastAPI and Uvicorn installed, run from the repository root:

```sh
python -m uvicorn RAG.firstweek.api:app --host 127.0.0.1 --port 8003
```

Set `FIRSTWEEK_RAG_URL=http://127.0.0.1:8003` in the auth service for that mode. Keep the internal endpoint private. The browser uses `/api/firstweek/projects`, `/api/firstweek/projects/:id`, `/api/firstweek/projects/:id/documents/:documentId` and `POST /api/firstweek/projects/:id/ask` with `{"question":"..."}` and the existing session cookie.

Every request requires current project membership; super-admin/company-admin roles do not bypass it. A response is rechecked after generation so revocation during a slow request withholds the answer. Gateway responses are `no-store`. Missing database schema, service configuration or index returns an unavailable state rather than unscoped legacy results.

## Existing RAG integrations

`python3 -m RAG.firstweek.index build --company COMPANY_ID --semantic` uses the existing shared Sentence Transformer model. It requires the RAG Python environment and may download model weights. Set `FIRSTWEEK_SEMANTIC=true` on the internal API only after building with the same model. Semantic retrieval performs exact similarity inside the selected project's chunks and combines ranks with lexical retrieval. Move this scan to pgvector when corpus size justifies it.

Set `FIRSTWEEK_GENERATE=true` to use the existing `RAG/config/llm_config.yaml` provider and its configured credentials. This can make paid model calls. Tracing is disabled for this path to avoid sending private evidence to a second telemetry provider. With generation off, responses are labelled `source-excerpts`; when generation is enabled but fails, the request returns 503 with a retryable error rather than substituting excerpts. Citation ID validation is not a factual-entailment guarantee; the deployment evaluation must test groundedness.

## Remaining before launch

The remaining legacy auth/account surface revamp, interactive membership administration, editable responsibilities, durable project conversations, managed ingestion, public publication/API widget and production deployment remain in later plan phases. The isolated migration, real sessions and immediate revocation passed locally; in-flight revocation is covered by the gateway tests. Verify provider generation, RAG model indexing and production proxy isolation before exposing the service. No private project sources are published by this work.

## Working authenticated local demo

The tested demo uses PostgreSQL 16 on `127.0.0.1:5547`, database `firstweek_demo`, role `firstweek_local`. Its isolated cluster is `.firstweek/local/postgres`. No preexisting database was changed. The original checked-in Prisma schema was converted to baseline SQL, then `202609070001_firstweek_projects/migration.sql` was applied successfully. Local trust authentication is for this loopback development cluster only.

To restart the existing cluster, from the repository root:

```sh
pg_ctl -D .firstweek/local/postgres -l .firstweek/local/postgres.log -o "-h 127.0.0.1 -p 5547 -k $PWD/.firstweek/local/socket" start
```

Do not run this if the cluster is already running (`pg_ctl -D .firstweek/local/postgres status`). This command requires the existing local cluster; on another machine create a separate empty development database and apply a baseline matching the original schema before the additive migration. Never point the local scripts at a production database.

Run each service in its own terminal:

```sh
# Repository root; seeds only firstweek_demo and creates local secrets.
node scripts/firstweek-local-server.js

# Repository root; Python environment needs FastAPI and Uvicorn.
python scripts/firstweek-local-rag.py

# frontend/ directory
AUTH_SERVICE_URL=http://127.0.0.1:3003 VITE_API_BASE_URL=/api/users VITE_FIRSTWEEK_API_URL=/api/firstweek npm run dev -- --host 127.0.0.1 --port 5174
```

Open `http://127.0.0.1:5174`. Credentials are in owner-readable `.firstweek/local/access.json`; service secrets are in `.firstweek/local/runtime.json`. Both are ignored by Git. The account is a local test identity with access to all five projects, not evidence of real project ownership. Restarting the auth script restores its seeded memberships. Other existing backend integrations are not started by this local wrapper.

During this task the Python environment is `/tmp/firstweek-test-env`; use `/tmp/firstweek-test-env/bin/python scripts/firstweek-local-rag.py` while it exists. The local RAG wrapper defaults to Groq generation plus the compact `sentence-transformers/all-MiniLM-L6-v2` embedding model for these English guides. It reads only provider credentials from the root `.env`. Local vectors remain on disk; generated answers send selected passages, the question and up to six recent chat messages to the configured provider. The user approved this transfer and live Groq verification passed: the original stack/deployment question returned a cited stack and an honest unconfirmed deployment status; a contextual follow-up and greeting also generated successfully. A real browser session verified sign-in, project navigation, MoneyPlant questions and source reading at desktop and mobile widths. Separate live API checks verified anonymous rejection, ignored client scope, `no-store`, immediate member removal, restored membership, service-token enforcement and logout invalidation.

Stop the service terminal processes with Ctrl-C, then stop this isolated database with `pg_ctl -D .firstweek/local/postgres stop`. Nothing here deploys or publishes the private corpus.

## Conversational RAG setup

Install the tested standalone dependencies and build embeddings with the same model used by the local wrapper:

```sh
python -m pip install -r RAG/firstweek/requirements.txt
HF_HOME="$PWD/.firstweek/models" FIRSTWEEK_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 python -m RAG.firstweek.index build --company local-workspace --semantic
python scripts/firstweek-local-rag.py
```

The global legacy RAG model remains BGE-M3. `FIRSTWEEK_EMBEDDING_MODEL` changes only this process; rebuild the index when changing models. A lexical-only rebuild will not work with `FIRSTWEEK_SEMANTIC=true`. For explicit offline excerpt mode use both `FIRSTWEEK_GENERATE=false FIRSTWEEK_SEMANTIC=false` when starting the local wrapper.

The browser sends the last three completed turns within the selected project, with a six-message/4,000-character-per-message limit enforced again at the gateway and internal API. History supports follow-ups but is not evidence, and cannot supply system messages, membership or company scope. New conversation clears this context. Enter sends; Shift+Enter adds a line. Turns remain in memory and clear when leaving the Ask view.

Deployment instructions are not proof of current deployment. The assistant is instructed to answer supported parts of a multi-part question and explicitly identify undocumented facts. Generated citation IDs are validated, but this is not an entailment check. A provider timeout or invalid citation produces an error, never a fabricated response.

## Curated collection and repository name

The repository directory is `/Users/dev_an/projects/FirstWeek`. Five projects are active: FirstWeek, MoneyPlant, AI PR Review Agent, RAG-Builder and Personal Site. Each has a private visual architecture plus an indexed text equivalent. The index contains 45 sections. The local seed and explicit registration script deactivate only the retired IDs in the manifest; they do not delete repositories or unrelated database projects. Removed guides are absent from the rebuilt index, so their old document URLs no longer resolve.

WasmEdge, riscV, random_exp and OopsC++ are excluded. Learning RAG and C++ Shell remain excluded until the owner publishes them. Remaining product phases await the owner’s confirmation.
