# FirstWeek foundation runbook

## Project administration (M1-01)

Company administrators create projects from the directory and become the first maintainer. Only assigned maintainers edit Settings or manage People. Add an active, company-verified and email-verified person by exact username. Membership writes serialize on the project row and retain an active maintainer. New projects start without indexed knowledge; maintainers add sources through Knowledge.

Management writes require JSON and the exact browser Origin. Set `FIRSTWEEK_ORIGIN` when a proxy changes the request host; the local host defaults to `http://127.0.0.1:5173`. Existing project settings, roles and revocations survive restart. Bootstrap grants membership only when creating a project for the first time.

The additive migration `202609080001_project_knowledge_origin/migration.sql` adds `hasCuratedKnowledge`. The isolated `firstweek_demo` had no Prisma migration history (Prisma deploy reported P3005); this exact SQL was applied directly after schema inspection, without reset. Do not apply baseline migrations blindly to an existing database. Regenerate Prisma client after applying the column.

Run `FIRSTWEEK_TEST_DATABASE=1 node --test backend/auth-service/tests/projectAdministration.integration.test.js` for concurrency and authorization checks against disposable records in the fixed local `firstweek_demo` database. The test cleans its records. Live browser checks covered create, empty knowledge, add, promotion, settings save, last-maintainer rejection, confirmed removal and reload persistence at desktop/mobile sizes. Milestone acceptance is recorded in TRACK.md.

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

The importer rebuilds the complete single-company corpus atomically. It is intended for the small local demo corpus, not concurrent multi-tenant ingestion. An old process can finish reading its old snapshot while new requests open the new one. Managed uploads live in PostgreSQL and are unaffected by this SQLite rebuild.

## Managed documents (M1-03)

Maintainers upload UTF-8 `.md` and `.txt` files through Knowledge. Limits are 256 KiB per file, 240 chunks per document and 100 documents per project. Unsupported formats, binary control characters, invalid Unicode and unsafe filenames are rejected. Browser file decoding is strict; the authenticated JSON API validates the decoded text independently. Raw files, PDFs, remote URLs and arbitrary server paths are not ingested. Markdown links and images do not trigger external requests from the source reader.

The additive `202609080003_project_documents/migration.sql` creates scoped PostgreSQL document and chunk tables. It was applied only to the isolated `firstweek_demo`; regenerate the auth Prisma client afterward. Document text and chunks commit together, so a successful upload is immediately searchable without a background worker. Deletion cascades to chunks. A failed transaction leaves no partial document. Back up these PostgreSQL tables together with projects and memberships; the curated SQLite file is not a backup of uploads.

Members read sources and maintainers create/delete them. All operations use server-derived company/project scope. Uploads are searched lexically within the bounded project collection, including recent user questions for follow-ups; curated guides keep their hybrid retrieval. Managed evidence is forwarded only by the authenticated gateway and carries document IDs/timestamps. Documents changing while an answer is generated cause a retry response, withholding the old evidence. Deleting an upload clears saved conversation content for every user in that project, including titles, questions, answers, source copies and pending requests. Text already seen or copied outside the app cannot be recalled.

Run `NODE_ENV=test FIRSTWEEK_TEST_DATABASE=1 node --test backend/auth-service/tests/projectDocuments.integration.test.js backend/auth-service/tests/firstweekRoutes.test.js` for disposable PostgreSQL authorization, Unicode, quota concurrency, retrieval, deletion and pending-answer checks. Use `.firstweek/venv/bin/python -m unittest RAG.firstweek.test_api RAG.firstweek.test_index -q` for the local RAG regression suite. The local auth wrapper accepts up to 2 MiB JSON to accommodate escaped text; the document byte limit is enforced after parsing.

## Frontend preview

Start `npm run dev` from `frontend/` and open `http://localhost:5173/preview/northstar-api`. This explicit development-only route contains a fictional project; it exercises navigation, excerpt answers and source reading without private data or a database. The preview module is excluded from production output. The real workspace is `/projects`, requires sign-in, and reads only the authenticated API. There is no mock fallback on private routes.

Actual company/project data requires the identities and index setup below. Project administration, maintained responsibilities, text uploads and private saved conversations are implemented. Saved conversations survive navigation, reload and auth-service restart. The older signup, password recovery and account/admin screens are retained during migration.

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

M1 integration acceptance, broader imports and refresh workflows, the legacy account-screen revamp, public publication/widget and production deployment remain in later phases. Project administration, editable responsibilities, bounded text uploads and private saved conversations are implemented locally. Production migration baselining, backups and proxy isolation still need deployment verification. No private project sources are published by this work.

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
AUTH_SERVICE_URL=http://127.0.0.1:3003 VITE_API_BASE_URL=/api/users VITE_FIRSTWEEK_API_URL=/api/firstweek node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173`. Credentials are in owner-readable `.firstweek/local/access.json`; service secrets are in `.firstweek/local/runtime.json`. Both are ignored by Git. The account is a local test identity initially assigned to all five projects, not evidence of real project ownership. Restarting the auth script preserves revoked memberships and edited roles/settings. Other existing backend integrations are not started by this local wrapper.

The local Python environment is `.firstweek/venv`; run `.firstweek/venv/bin/python scripts/firstweek-local-rag.py` from the repository root. The wrapper defaults to Groq generation and the cached `sentence-transformers/all-MiniLM-L6-v2` embedding model. It reads provider credentials from the root `.env`. Vectors remain local; selected passages, questions and bounded chat context are sent to the configured provider under the user's existing authorization. Local browser verification covered sign-in, project navigation, cited answers, source reading and managed uploads at desktop/mobile sizes. API checks covered anonymous rejection, ignored client scope, `no-store`, revocation and service-token enforcement.

Stop the service terminal processes with Ctrl-C, then stop this isolated database with `pg_ctl -D .firstweek/local/postgres stop`. Nothing here deploys or publishes the private corpus.

## Conversational RAG setup

Install the tested standalone dependencies and build embeddings with the same model used by the local wrapper:

```sh
python -m pip install -r RAG/firstweek/requirements.txt
HF_HOME="$PWD/.firstweek/models" FIRSTWEEK_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2 python -m RAG.firstweek.index build --company local-workspace --semantic
python scripts/firstweek-local-rag.py
```

The global legacy RAG model remains BGE-M3. `FIRSTWEEK_EMBEDDING_MODEL` changes only this process; rebuild the index when changing models. A lexical-only rebuild will not work with `FIRSTWEEK_SEMANTIC=true`. For explicit offline excerpt mode use both `FIRSTWEEK_GENERATE=false FIRSTWEEK_SEMANTIC=false` when starting the local wrapper.

The authenticated Ask screen uses persisted conversations. The browser sends only the current question and a request ID to the selected conversation's turn endpoint. The server derives context from its last three completed turns; browser-supplied history is rejected on this endpoint. Context supports follow-ups but is not evidence. The development preview and older stateless `/ask` endpoint retain their separate compatibility behavior. Enter sends; Shift+Enter adds a line.

## Saved conversations (M1-04)

The additive `202609090001_project_conversations/migration.sql` creates `project_conversations` and adds the project's knowledge version. It was applied only to isolated `firstweek_demo`. Generate the auth Prisma client after applying it. Conversations reference the exact company/project/user membership and are deleted when that membership is removed. Company administrators cannot read another user's conversations.

Ask supports new, select/open and delete actions. The selected conversation ID is preserved in the page URL. Limits are 50 conversations per user/project, 20 completed turns per conversation and 300,000 serialized bytes per answer including sources. Completed request IDs are idempotent while their turns remain in that conversation; reusing an ID with a different question is rejected. Knowledge invalidation clears that replay history too.

Short project-row transactions reserve a pending turn and validate current membership. Model calls run outside the transaction. A version fence prevents expired or superseded workers from saving late answers. Pending requests become retryable after 60 seconds; failed or expired questions remain available as drafts until retried or invalidated. The UI reloads authoritative history after a failure and keeps an explicit error and retry draft. A successful response replaces displayed history, so it cannot append stale turns from before an invalidation.

Before returning saved titles/content or generating another turn, the server checks current curated document hashes, managed-source metadata, maintained ownership and project version. Changed knowledge conservatively resets the conversation rather than displaying possibly stale private copies. An unavailable knowledge service returns an error, not saved content with an assumed-valid snapshot. Upload deletion additionally clears all project conversations inside its transaction. Ownership and other knowledge changes invalidate conversations on their next checked access.

Verification includes real PostgreSQL isolation, competing sends, completed replay, timeout/late-worker fencing, deletion invalidation and membership cascade. HTTP tests prove server-owned history, replay without another provider call and failure/retry recovery. Browser checks covered two turns retained through reload and auth restart, authoritative replacement after a second-tab source change, failed-draft recovery with deleted content absent, mobile layout and conversation deletion returning 404.

The M1-04 browser checks used local source excerpts: automatic approval review blocked a fresh external generation call. The running local RAG process was restarted with `FIRSTWEEK_GENERATE=false FIRSTWEEK_SEMANTIC=false`; live provider generation was not revalidated for this milestone. Source-excerpt responses are visibly labelled. Restore the appropriate generation configuration only under authorized provider use.

Run `NODE_ENV=test FIRSTWEEK_TEST_DATABASE=1 node --test backend/auth-service/tests/projectConversations.integration.test.js backend/auth-service/tests/conversationRoutes.integration.test.js` for the disposable database and HTTP checks. Include the conversation table when backing up project data. Local M1 integration is accepted in `M1-ACCEPTANCE.md`; this is not deployment approval.

## Private onboarding profiles (M2-01)

Migration `202609090002_onboarding_profiles/migration.sql` adds nullable onboarding focus/experience and a profile version to project membership, with database allowlist constraints. Applied only to isolated `firstweek_demo`; regenerate the auth Prisma client after applying. There are no inferred job titles, experience levels, owners or permission changes.

Members use the Onboarding tab to set or clear their own project preferences. `GET/PUT /api/firstweek/projects/:projectId/onboarding-profile` derives company and user from the session, requires current membership, and accepts exactly `onboardingRole` (null, ENGINEERING, PRODUCT, DESIGN, OPERATIONS) and `onboardingExperience` (null, NEW, EXPERIENCED) on same-origin JSON writes. Other members' profiles are not returned by the member directory. Membership removal deletes the preferences; re-adding starts with null defaults.

Saving changed preferences increments only the member's profile version and immediately clears that member's saved questions, answers, titles and pending drafts for this project. Other members' history remains unchanged; same-value saves do nothing. The form warns about this reset before saving. Existing default-profile conversations retain their prior hash on upgrade. A later reset to null still advances the version and clears outdated history.

Saved conversations check profile version inside the project lock, and the older stateless ask endpoint checks it after generation. Both use server-loaded preferences, never browser-supplied profile claims. RAG maps the enums to bounded explanation guidance; preferences are not evidence or verified biography. Offline source excerpts are unchanged. Mocked-provider tests verify all focus/experience guidance combinations; a fresh external-provider quality evaluation remains outside this local acceptance.

Checks: `NODE_ENV=test FIRSTWEEK_TEST_DATABASE=1 node --test backend/auth-service/tests/onboardingProfiles.integration.test.js backend/auth-service/tests/conversationRoutes.integration.test.js backend/auth-service/tests/firstweekRoutes.test.js`. The complete suite passes 18 Node and 21 Python checks. Browser verification covers ordinary-member access, save/reload/auth-restart persistence, null reset and per-user conversation clearing. Desktop/390px captures: `/private/tmp/firstweek-m2-onboarding-desktop.png` and `/private/tmp/firstweek-m2-onboarding-mobile.png`. The disposable acceptance company, project, users and conversations were removed.

Deployment instructions are not proof of current deployment. The assistant is instructed to answer supported parts of a multi-part question and explicitly identify undocumented facts. Generated citation IDs are validated, but this is not an entailment check. A provider timeout or invalid citation produces an error, never a fabricated response.

## Company teams and maintained answer context (M2-02)

The additive `202609100001_company_teams/migration.sql` creates `company_teams` and `team_assignments` in isolated `firstweek_demo`. Regenerate the auth Prisma client after applying. From All projects, open Company teams to read the directory; company administrators also get create/edit team, assign/edit member and explicit removal confirmation controls. This directory is available even when the verified company member has no project memberships.

Teams are explicitly company-shared records, visible to current active verified company members even without a project assignment. Only a current COMPANY_ADMIN can maintain them. Team membership grants no project permissions. These routes derive company scope from the session and never accept a body company/user ID:

- `GET /api/firstweek/company/teams`: maintained team names/descriptions, assignment text, timestamps and member display names/usernames; `canManage` comes from the current database role. No emails, onboarding profiles or project memberships are exposed.
- `POST /api/firstweek/company/teams` and `PATCH /api/firstweek/company/teams/:teamId`: exact JSON `{name, description}`. Names are required (120 characters), descriptions may be empty (2,000 characters). Duplicate names are rejected case-insensitively within a company.
- `DELETE /api/firstweek/company/teams/:teamId`: empty JSON object; cascades only that team's assignments, not users or projects.
- `PUT /api/firstweek/company/teams/:teamId/assignments`: exact JSON `{username, assignment}`; resolves an existing active, email/company-verified same-company user. Required assignment text is capped at 500 characters; repeat writes update the existing assignment.
- `DELETE /api/firstweek/company/teams/:teamId/assignments`: exact JSON `{username}`; also permits removing assignments for now-inactive users.

All mutations require same-origin JSON. Company-row locking serializes quota and duplicate checks: 100 teams/company and 200 assignments/team, with existing assignments still editable at capacity. Company projects are then locked in deterministic order; the change increments their knowledge versions and clears saved conversations atomically, preventing retained stale team answers. Inactive or unverified users' assignments are omitted from reads. Company inactivity and stale administrator authority fail closed.

Both assignment foreign keys include companyId. User deletion cascades assignments; company transfers are restricted while team assignments exist, so an authorized transfer must explicitly remove those assignments first. They are never silently moved into another company's team. Existing project-membership constraints remain separate.

Private Ask selects at most eight matching company-team/assignment records from the current server-owned directory. Numbered evidence exposes maintained text and timestamps; assignment evidence explicitly does not prove project ownership or membership. Both saved and stateless answers compare fresh company context before completing. Member names and eligible assignment changes invalidate the context hash. The public showcase has no company directory endpoint or source connection.

Run `NODE_ENV=test FIRSTWEEK_TEST_DATABASE=1 node --test backend/auth-service/tests/companyTeams.integration.test.js` for the real PostgreSQL and HTTP checks, including two-company isolation, validation, fresh permissions, no implicit project access, persistence across client reconnect, transfer protection, deletion cascades, competing quota writes and company-wide pending-response fencing. Fixtures are disposable and cleaned up at the end. Browser acceptance covers member read-only access, auth restart persistence, administrator edits/removals, saved-answer invalidation and removed evidence; see TRACK.md for the dated verdict and exact limits. The private browser checks use offline excerpts, not a new live-provider evaluation.

## Reading paths and private progress (M2-03)

The additive `202609150001_reading_paths/migration.sql` is applied to the newly authorized local cluster `.firstweek/m203/postgres`, database `firstweek_demo`, role `firstweek_local`, loopback port 5548. The older `.firstweek/local/postgres` is preserved. Do not reset either cluster. Regenerate the Prisma client after schema changes. For this runtime, set `FIRSTWEEK_DATABASE_URL=postgresql://firstweek_local@127.0.0.1:5548/firstweek_demo` and `FIRSTWEEK_ORIGIN=http://127.0.0.1:5175` when starting `scripts/firstweek-local-server.js`; auth listens on 3003 and Vite on 5175. The browser origin must match exactly for writes. RAG verification uses `FIRSTWEEK_GENERATE=false FIRSTWEEK_SEMANTIC=false`, without new provider calls.

The private Reading path tab uses managed project sources only. Current maintainers create/edit/remove up to 50 steps and reorder the complete list. Members mark their own steps complete; completion grants no permissions and is never exposed to another member. Profile filters affect personal counts, not access. Maintainers see a separately labelled full management list. Material edits advance a revision and reset effective completion; stale completion requests return 409 and require reload. Source deletion cascades its steps/progress; membership deletion removes that member's progress. Curated-source reading paths remain deferred to M3.

Routes under `/api/firstweek/projects/:projectId/reading-path`: GET reads private progress; POST creates; PATCH/DELETE `/:stepId` edits/removes; PUT `/order` takes exactly `{stepIds}`; PUT `/:stepId/completion` takes exactly `{revision}`. Write guards require same-origin JSON. Session identity supplies company/user scope, and current project membership/maintainer authority is checked server-side. Responses are no-store.

Run the focused checks against this explicitly isolated target:

```sh
NODE_ENV=test FIRSTWEEK_TEST_DATABASE=1 FIRSTWEEK_DATABASE_URL=postgresql://firstweek_local@127.0.0.1:5548/firstweek_demo node --test backend/auth-service/tests/readingPaths.integration.test.js backend/auth-service/tests/readingPathRoutes.test.js
```

Database fixtures use unique company IDs and exact cleanup. HTTP guard tests mock services; database tests separately cover real validation, isolation, cascades, profiles and bounded write races. Browser evidence under `.firstweek/m203/` includes desktop/390px completion and actual auth-restart persistence. Latest acceptance/cleanup and independent review are recorded in TRACK.md; these instructions do not establish production readiness.

## Curated collection and repository name

The repository directory is `/Users/dev_an/projects/FirstWeek`. Five projects are active: FirstWeek, MoneyPlant, AI PR Review Agent, RAG-Builder and Personal Site. Each has a private visual architecture plus an indexed text equivalent. The index contains 46 sections after the 2026-09-16 reading-path guide refresh. The local seed and explicit registration script deactivate only the retired IDs in the manifest; they do not delete repositories or unrelated database projects. Removed guides are absent from the rebuilt index, so their old document URLs no longer resolve.

WasmEdge, riscV, random_exp and OopsC++ are excluded. Learning RAG and C++ Shell remain excluded until the owner publishes them. Remaining product phases await the owner’s confirmation.
