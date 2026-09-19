# FirstWeek milestone tracker

## Current state

- Completed milestone: M1 — Usable private onboarding workspace. Active priority: M2, resumed at the user's request on 2026-09-15; the user is handling public deployment settings.
- Roadmap: docs/firstweek/MILESTONES.md.
- Current corpus: 5 projects, 46 indexed sections after the 2026-09-16 guide refresh; local authenticated conversational RAG and architecture views.
- Workflow (user update 2026-09-16): GPT-5.6-Sol implements and debugs; primary assistant coordinates, reviews and maintains this tracker; Gauss provides independent review and scoring. Publication requires separate explicit user direction.
- TRACK.md write owner: primary assistant. Reviewer supplies findings by agent message and does not edit application code.
- Status: M2-01, full M2-02 and M2-03 accepted locally. Gauss accepted M2-03 at 100/100 on 2026-09-16 after isolated migrations, expanded tests, desktop/mobile/member flows, restart persistence and cleanup. M2-04 overall integration/acceptance is next; M2 overall remains incomplete. PUBLIC-01 implementation and deployment preparation accepted locally; public launch still requires credentials and hosted verification.
- Follow-up: PUBLIC-02 OpenAI-first Ask with bounded Groq/OpenRouter fallbacks and cost controls accepted locally at 100/100. Live provider, Redis/Lua, Vercel and publication verification remain pending.

## Task board

| Task | Status | Acceptance / next action |
| --- | --- | --- |
| PUBLIC-01 Read-only showcase and Vercel preparation | Accepted locally | Reviewer accepted implementation and UI; 9 public API + 33 frontend/auth tests, public/private builds and anonymous browser checks passed. Live Groq/Redis/Vercel acceptance and publication remain separate. |
| PUBLIC-02 Generated answers after public retrieval | Accepted locally; activation pending | Gauss ACCEPT 100/100 on 2026-09-17. OpenAI primary, opt-in Groq and free-only OpenRouter fallback; 5/IP/min, 10/IP/day, 30 global/day, persistent 100 OpenAI attempts and 600 output tokens. Live provider/Redis/Vercel checks remain. |
| M1-00 Feasibility and sequence | Accepted | Reviewer feasibility preflight approved with guardrails below |
| M1-CLEAN Legacy-term cleanup | Accepted | Reviewer accepted maintained-source cleanup; exclusions and recoverable archive recorded below |
| M1-01 Project and membership administration | Accepted | Reviewer accepted scoped administration, concurrency/restart safety and authenticated desktop/mobile flows |
| M1-02 Editable ownership | Accepted | Reviewer accepted scoped responsibility maintenance, safe unassignment, cited answers, stale-evidence rejection and member read-only UI |
| M1-03 Document uploads | Accepted | Reviewer accepted scoped uploads, Unicode/size limits, cited retrieval, restart/rebuild durability and deletion |
| M1-04 Persistent conversations | Accepted | Reviewer accepted persisted private history, server-owned context, retry fencing, recovery and conservative deletion invalidation |
| M1-05 Integration and acceptance | Accepted | Reviewer accepted refreshed guide/evidence, final regressions, browser checks and overall local M1 |
| M2-01 Private onboarding profiles | Accepted | Reviewer accepted self-only preferences, permissions isolation, stale-answer fencing, upgrade compatibility and desktop/mobile persistence |
| M2-02 Company structure and assignments | Accepted | Reviewer accepted backend, read-only/admin UI, company evidence, restart persistence, invalidation and fixture cleanup |
| M2-03 Reading paths and progress | Accepted locally | Gauss ACCEPT, 100/100 on 2026-09-16. Isolated migration, expanded HTTP/concurrency/profile tests, authenticated desktop/mobile/member flows, auth-restart persistence and exact cleanup pass. |
| M2-04 Integration and acceptance | In progress | User requested next milestone. Verify combined profiles/company context/reading progress and grounded-answer boundaries; full local regressions, exact cleanup and Gauss acceptance. |

## Completed

- Planning bootstrap: roadmap, milestone acceptance criteria, strict role boundaries and review handoff protocol documented.
- M1-00 feasibility and sequence: reviewer approved membership-first implementation with the recorded security, concurrency and durability guardrails.
- M1-CLEAN maintained-source cleanup: reviewer accepted requested-term removal, runtime corrections and documented exclusions; original corpus preserved in a private recoverable archive.
- M1-01 project and membership administration: reviewer accepted project creation/settings and secure member add/role/remove flows with real concurrency, restart and browser evidence.
- M1-02 editable ownership: reviewer accepted maintained responsibilities, same-project assignments, safe removal-to-unassigned behavior, sourced answers and read-only member access.
- M1-03 document uploads: reviewer accepted durable PostgreSQL text/chunk storage, project-scoped access, bounded ingestion, cited answers and deletion.
- M1-04 persistent conversations: reviewer accepted scoped durable history, idempotency, failed/expired turn recovery and invalidation of saved private content.
- M1-05 integration and overall local M1: reviewer accepted the consolidated report, refreshed knowledge/architecture, final automated checks and browser evidence.

## Remaining milestones

M2 company context/personalization; M3 managed knowledge and RAG quality; M4 frontend/account completion; M5 public portfolio collection/widget; M6 production deployment readiness.

## Decisions and activity log

### Public project snapshot refresh — 2026-09-17 — primary coordinator

- Publication was paused before commit after the final staged-scope check found unrelated private-M2 frontend changes without their backend dependencies. Main and the remote remain unchanged.
- Refreshed all public project status metadata from their current local repository documentation. Added Movie Enquirer as the sixth public project with status `Completed`.
- Learning RAG's guide distinguishes manual code authorship from its intentional runtime use of OpenRouter for query enhancement, reranking and grounded generation. The private five-project RAG corpus remains unchanged; this is a public snapshot addition only.
- Release scope is now one coherent product snapshot: the previously accepted private workspace routes/services/schema/migrations plus the public-only Vercel entry. This avoids publishing frontend calls without their backend dependencies; it does not mark M2-04 complete. Fresh checks passed: public API 16/16, frontend 129 passed/one skipped with 11 snapshots, gateway HTTP 13/13, RAG API 15/15, public/private builds, Prisma validation, evidence hashes and diff whitespace.
- Gauss found no security or public/private boundary blocker in the corrected staged scope. Its only evidence-hash finding was refreshed and rechecked clean. Publication still requires the final reviewer verdict, commit and explicit `origin/public-showcase` push; main remains unchanged.

### Public RAG provider and cost controls — 2026-09-17 — primary coordinator

- User selected OpenAI as default public generator, optional Groq fallback and free OpenRouter final fallback. Caveman is a local communication skill, not an API gateway; `OPENAI_BASE_URL` is deliberately unused. Public calls use fixed official endpoints and server-only keys.
- Added Redis-backed limits: five questions per hashed visitor per fixed minute, ten per visitor per UTC day and thirty globally per UTC day. One reservation covers all provider attempts for a question. OpenAI has a separate persistent 100-attempt cap with no expiry; exhausted or unavailable OpenAI moves to enabled fallbacks. Every provider output is capped at 600 tokens. Groq requires exact opt-in and OpenRouter model IDs must be `openrouter/free` or end in `:free`.
- Primary independently passed 16 public API/config tests, public build (1,516 modules), private build (1,702 modules), syntax and whitespace checks. Gauss independently passed the 16 tests, inspected quota scripts and accepted the local migration at 100/100 with no material findings. Public publication snapshot updated to 2026-09-17. Full environment/deployment guidance is in `docs/firstweek/PUBLIC-DEPLOYMENT.md`.
- Limits: tests use stateful Redis mocks; no live provider request, real Redis Lua/concurrency run, Vercel deployment, commit or push occurred. The call cap is not an exact wallet guarantee and does not cover other applications using the same provider account. Branch is `public-showcase`; public launch still needs keys, protected-preview verification and explicit publication action.

### M2-04 resumed — 2026-09-17 — primary coordinator

- User explicitly resumed milestone work after discussing public deployment and chat cost controls. Public-chat hardening was later implemented and accepted separately as recorded above; no deployment or live provider call was authorized by the milestone resumption.
- Retried Sol after the previous usage-limit failure; Gauss is inspecting the bounded cross-feature interactions. Primary freshly passed 22 offline RAG and 11 public API regression checks. Combined database/browser verification and final review remain outstanding.

### M2-04 integration started — 2026-09-16 — primary coordinator

- User requested the next milestone after M2-03 acceptance. Sol owns implementation/debug/verification; primary coordinates and owns this tracker and `docs/firstweek/M2-ACCEPTANCE.md`; Gauss independently defines the bounded acceptance checks and supplies final review.
- Reuse the authorized isolated PostgreSQL database on port 5548 and current local services. Carry forward unchanged M2-03 browser/restart evidence, adding combined-flow checks across profiles, company context, answers and reading progress. Do not infer a fresh external-provider evaluation from offline excerpts or mocked-provider tests.
- No M3 feature expansion, database reset, publication, deployment or main-branch change. Overall M2 remains incomplete until final evidence and independent acceptance.

### M2-03 runtime recovery and workflow correction — 2026-09-16 — primary coordinator

- Final independent verdict: Gauss ACCEPT M2-03 locally, 100/100, no remaining blockers or important findings. Reviewer confirmed PROJECT-MAP context, independently reran two UI tests, syntax/whitespace and all 18 evidence hashes, and opened corrected desktop/mobile/member/Overview artifacts. Database/HTTP/browser/restart/cleanup and broader regression evidence is attributed to Sol/primary, not misrepresented as reviewer reruns. Full scorecard is in MILESTONES.md. M2-04 remains separate; this is not overall M2 or deployment acceptance.
- Final implementation checkpoint: Sol reran two real-database tests (including same-company/different-project and foreign-company source denial), three HTTP tests, two focused UI tests, full frontend (129 passed/one skipped, 11 snapshots), private build and six index tests successfully. Sandbox-denied loopback attempts were rerun with permission; only successful actual runs count. Primary's adjacent public 11/11 and offline RAG 22/22 checks passed. Gauss's permission and CSS sibling-regression findings were addressed; final review is pending.
- Browser closure: ordinary MEMBER saw source/self-completion controls but no management form/Edit/Settings, completed its own step to 1/1 at 390px without overflow (`.firstweek/m203/reading-path-member-mobile.png`). Maintainer CRUD, source opening, revision reset, reload/auth-restart persistence and desktop/mobile checks passed. Only disposable fixture records were removed through document deletion and exact fixture-user cleanup; counts afterward: five active projects, zero temporary companies, fixture documents/users, reading steps and progress. Test data is deleted; maintained projects and both database clusters are preserved.
- Guide/evidence refreshed with 18 matching FirstWeek hashes. Offline cached hybrid rebuild retains five projects and now 46 sections; changed-sources check is empty. Plan, project map, runbook and roadmap corrected to current workflow and verified scope; historical 88/100 review is preserved with dated corrections. No commit, push, deployment or main-branch change.
- User authorized a fresh isolated database. Created `.firstweek/m203/postgres` on loopback port 5548 with database `firstweek_demo`; applied the recorded baseline and eight additive migrations through reading paths. The focused reading-path integration test passed, including reconnect and disposable-fixture cleanup.
- Correction to earlier absence reports: `.firstweek/local/postgres` exists. An earlier check used the frontend working directory and incorrectly concluded the cluster was absent. The new cluster uses a separate path and port; the existing cluster was preserved.
- Browser project loading recovered after starting local RAG in offline mode. Subsequent upload initially failed its origin guard because auth expected port 5173 while Vite served 5175. Auth now uses the matching origin. Later five-byte proxy 500s coincided with absent auth; neither an upload-schema defect nor execution-environment process reaping was established.
- Sol now retains the auth process session and verified expected HTTP 401 from the unauthenticated health request. Primary independently observed listeners on ports 3003, 5175 and 5548. Browser/test verification continues under the user-requested Sol implementation, primary coordination and Gauss review arrangement. Prior agent usage errors cleared on retry; no new acceptance score is claimed.
- Verification follow-up: primary independently passed 11 public API tests, 22 offline RAG tests, the complete frontend suite (129 passed, one skipped, 11 snapshots), and the private production build. Sol subsequently passed the added fresh-permission UI regression (two focused tests) and three reading-path HTTP checks. Sol reports authenticated upload/index/create/complete success and 1/1 progress surviving browser reload and an actual auth-server restart; desktop evidence is `.firstweek/m203/reading-path-desktop.png`. Database race/profile checks, mobile verification, fixture cleanup and final Gauss acceptance are still pending.
- Later checkpoint: Sol reports both expanded database tests passing, including competing quota appends, edit/completion and reorder/source-deletion races, scope-injection rejection, foreign-company source denial and profile counts. Primary spotted desktop control overflow in the initial capture; Sol narrowed the overbroad button styling and added wrapping. Primary opened corrected `reading-path-desktop-complete.png` and `reading-path-mobile-complete.png` in the same artifact directory: controls fit and both show 1/1 progress. Sol verified browser create/reorder/edit-reset/re-complete/remove at desktop and 390px. Member-only browser verification, final fixture cleanup, documentation and independent acceptance remain pending; a further worker usage error cleared on retry.

### M2-02 final acceptance and M2 resumption — 2026-09-15 — primary assistant

- User resumed milestones while handling public deployment settings. Reviewer verdict: ACCEPT full M2-02, no blocking findings. Primary codes and tracks; only Gauss supplies independent review. M2 as a whole is not complete.
- Fresh authenticated browser checks verified a company member with zero project memberships can read maintained teams without editing controls; company-admin edits remain scoped. Team and assignment survived an auth-server restart. Ask cited maintained company records with timestamps and an explicit disclaimer that assignments do not establish project responsibility or access.
- Editing an assignment cleared its saved answer without granting project membership. Confirmed assignment removal and team deletion; the same question then returned no evidence. Exact disposable company, project and two users were removed from isolated firstweek_demo; zero fixture users remained and all five maintained projects were preserved.
- Verification: 20 Node tests, 21 Python tests and 33 frontend/auth tests passed; private Vite production build and diff whitespace check passed. Guide/runbook updated; reviewer independently verified all 16 FirstWeek evidence hashes. Cached offline semantic rebuild retained five projects/45 chunks. Browser RAG used honest offline excerpts, not a new live-provider acceptance test.
- Opened desktop/mobile evidence: .impeccable/review/m2-company-member-mobile.png, m2-company-answer-desktop.png and m2-company-admin-desktop.png. Member layout had no horizontal page overflow at 390px. Reviewer deferred the source-pane label "No sources yet" → "No project documents yet" as nonblocking M4 copy polish.
- Started M2-03 preflight for maintained reading sequences and private completion records. The implementation is now under independent review: maintained managed-source steps, profile-filtered private progress, revisions and an additive migration are present but not accepted. Current branch is public-showcase; accumulated changes remain uncommitted, main unchanged. No push, deployment or new external account provisioning.

### M2-03 implementation follow-up — 2026-09-15 — primary assistant

- Gauss confirmed it read `PROJECT-MAP.md` and returned preflight CHANGES REQUESTED, 63/100. Implemented the requested safe append after source-deletion cascade, atomic complete-list reorder, maintainer edit/reorder UI, revision-fenced completion reset, and distinct personal-progress/maintained-step counts. The plan explicitly records a managed-source-only boundary; curated source identities are deferred to M3.
- Added focused backend and frontend regression coverage. The frontend test, private production build, Prisma schema validation, diff whitespace and JavaScript syntax checks pass. The database integration test is intentionally skipped because `FIRSTWEEK_TEST_DATABASE` is not enabled and the documented isolated cluster directory is gone.
- No migration was applied; no database was recreated or overwritten; no service restart or authenticated browser run occurred. M2-03 remains incomplete pending user direction for an isolated database plus migration, persistence, browser and reviewer acceptance evidence.
- Gauss final review: CHANGES REQUESTED, 88/100. The original implementation defects are resolved. It requires actual database/browser evidence and broader HTTP, tenant-scope and concurrency coverage before acceptance; its review record is in `docs/firstweek/MILESTONES.md`. The reconnect assertion was tightened afterward to assert a still-existing completion after reconnect; it remains unexecuted until an authorized isolated database is available.

### Complete public Ask RAG flow — 2026-09-15 — primary assistant

- User requested generated LLM responses after retrieval, rather than raw search excerpts. Reused the existing scoped retrieval, system prompt, bounded history and Groq generation function. Unset/true `FIRSTWEEK_PUBLIC_GENERATE` now selects normal generation; explicit false selects offline excerpts. Invalid flags and missing/failed services produce errors, never silently labeled generated answers.
- Local Vite development/preview now reads public-chat server settings from ignored frontend env files; launching process variables take precedence. These settings are not added to the browser bundle. The private root `.env` is not automatically loaded.
- A single bounded live generation check used the existing local Groq key and only the authored public FirstWeek guide. Retrieval → prompt/evidence → Groq returned mode `generated` with numbered citations. No Redis reservation/public endpoint bypass was added; this check did not establish live end-to-end public Ask readiness.
- Verification: eleven Node public API/config tests, four public UI tests and public production build passed. The environment-loading check exposed legacy CommonJS `__dirname` in the ESM Vite config; replaced with standard `fileURLToPath(new URL(..., import.meta.url))`. No new dependencies or UI redesign.
- Public activation still requires Redis REST URL/token, a rate-hashing secret, and the server-side Groq/origin settings. Credential presence was checked without printing values. No Redis account was provisioned; no quota controls disabled; no deployment, commit or push occurred.
- Reviewer follow-up failed due to the reviewer account usage limit. This follow-up has primary verification but no independent acceptance; PUBLIC-01 acceptance is not extended to these changes. M2 progression remains paused.

### Public showcase implementation — 2026-09-14 — primary assistant

- Final reviewer verdict: ACCEPT the bounded public showcase implementation and deployment preparation; not public-launch approval. No remaining material findings at this scope. All four desktop/mobile captures preserve the inherited UI; no new visual system or assets were introduced.
- Verification: nine Node public API checks and 33 frontend/auth tests passed; public production build and normal private production build passed. Browser checked anonymous five-project listing, read-only tabs, excerpt answers, opening a numbered source, unpublished-project denial, and zero private API requests after load and an auth broadcast. Mobile width 390 had no horizontal page overflow. JSX detector returned no findings; diff whitespace passed.
- Preview: `http://127.0.0.1:5184/showcase`, served from the public production build with the same handler through Vite preview middleware. Generation remains off locally. Screenshots: `.impeccable/review/public-desktop.png`, `public-mobile.png`, `public-chat-mobile.png`, `public-architecture-desktop.png` (opened and reviewed).
- Remaining launch evidence: protected Vercel preview/function packaging, live Groq/Upstash generation and quota checks, deployed private-route denial and cost controls. The local tests use provider/Redis mocks and do not establish those hosted results. Source and deployment changes remain uncommitted on `v1`; `main` is unchanged.

- User requested anonymous browsing and chat within FirstWeek, with no project creation, edits or uploads. Personal-site API/embed remains deferred. This supersedes automatic M2 progression; it does not mark M2, M5 or M6 complete.
- Added a separately authored five-project publication snapshot and a standalone Node public handler under `frontend/server`. There are no imports of the private manifest, database, uploads, company directory, profiles, or saved conversations. Snapshot review/edit plus redeploy is the bounded v1 publication workflow.
- Reused the existing workspace/architecture/source-reader UI with explicit public labels and only Overview, Architecture, Ask and Knowledge. Public browser requests omit credentials. Chat is ephemeral; default excerpt mode is honest about not using an LLM.
- Optional server-side Groq generation uses scoped keyword retrieval, a system prompt and at most six bounded history messages. Redis Lua reservations enforce five generated requests per visitor/minute and a global daily cap. Missing/failed configuration denies generation; no in-memory production limiter or private backend fallback.
- Reviewer identified module-import private auth requests. Moved initialization and broadcast subscription into a private-app lifecycle; public imports and auth broadcasts no longer trigger private API calls. Added regression checks while preserving private auth tests.
- Vercel public build/root/function configuration and `docs/firstweek/PUBLIC-DEPLOYMENT.md` explain server secrets, origins, quotas, publication/withdrawal limits and launch checks. Existing private services and dirty M2 changes were preserved. No commit, push, deployment, account provisioning or outbound provider request occurred during implementation.

### M2-02 backend foundation acceptance — 2026-09-10 — primary assistant

- Reviewer verdict: ACCEPT M2-02 backend foundation, no blocking findings. This is not full M2-02 acceptance: workspace team UI, maintained company context in answers and their browser/freshness evidence remain next.
- Added company-shared flat teams and explicit assignment records with composite company/team/user foreign keys. Current verified company members can read maintained display data; only a freshly verified current COMPANY_ADMIN can mutate. Assigning a team member does not create project membership or change permissions.
- Same-origin JSON endpoints validate exact fields, names, assignment text and eligible exact usernames. Company-row locks serialize case-insensitive name uniqueness and quotas (100 teams/company, 200 assignments/team); existing assignments remain editable at capacity. Inactive/unverified assignments are omitted from reads and can be removed explicitly.
- User/team deletion cascades assignments. User company transfers are restricted until assignments are explicitly removed; even a matching destination team ID cannot silently move an assignment across companies. No invitations, external messages or publication were performed.
- Verification: 19 Node regression checks passed, including real PostgreSQL/HTTP company isolation, stale-admin denial, scope injection, no-store/origin/JSON guards, persistence across client reconnect, foreign keys, cascades and competing quota writes. Prisma validation/client generation passed. Additive `202609100001_company_teams` applied only to isolated `firstweek_demo`.
- Cleanup verified zero company-team and assignment rows; five active maintained projects remain. Auth restarted with reviewed endpoints. Guide explicitly distinguishes the API foundation from unimplemented UI/RAG integration; 14 FirstWeek evidence records refreshed, cached offline hybrid rebuild retains five projects/45 chunks.
- Primary implemented with the existing stack and no new dependencies; only reviewer supplied feedback. Latest changes remain uncommitted on `v1`, `main` unchanged, public push paused. Local RAG remains offline excerpt mode.

### M2-01 final acceptance — 2026-09-10 — primary assistant

- Reviewer verdict: ACCEPT M2-01, no blocking findings. Primary implemented; only the reviewer supplied independent feedback. M2-02 company structure and assignments is next; M2 as a whole is not complete.
- Members explicitly choose nullable onboarding focus and explanation level per project. These private preferences are separate from permissions, verified job roles and maintained ownership. RAG receives only server-loaded controlled style guidance, not profile claims from the browser.
- Changed preferences clear only the member's own saved project questions, answers and pending drafts; unchanged saves are no-ops. Profile versions fence stale saved/stateless answers. The reviewer approved preserving the pre-M2 hash at version zero so the upgrade itself does not discard history; regression covers later changes and null reset.
- Checks passed: all 18 Node and 21 Python tests, Prisma validation/client generation, frontend production build and diff whitespace. The additive profile migration was applied only to isolated `firstweek_demo`. Refreshed 13 FirstWeek evidence hashes and the cached offline hybrid index; five projects and 45 chunks retained.
- Browser: ordinary EMPLOYEE/MEMBER saw Onboarding but no Settings, saved ENGINEERING/NEW, retained values on reload and actual auth restart, then reset to null and reloaded. DB confirmed unchanged member permission, own saved turns reset from one to zero and the other user's one turn unaffected. Prior question/answer absent from Ask. Desktop/390px UI passed review with no page overflow; captures `/private/tmp/firstweek-m2-onboarding-desktop.png` and `/private/tmp/firstweek-m2-onboarding-mobile.png`.
- Exact disposable company/project/two users/conversations removed; follow-up read returned no fixture memberships or conversations. No real user profile was changed. Fixture setup initially hit existing username/ID format validation; corrected synthetic identifiers without changing auth behavior.
- Impeccable kept the established form/navigation design; detector returned no findings. Reviewer noted nonblocking mobile active-tab auto-scroll polish for M4. No new dependencies or visual identity changes.
- Local RAG remains offline excerpts. Mocked-provider tests cover guidance for every supported focus/experience pair; external generation quality was not newly validated. Latest changes remain uncommitted on `v1`; `main` untouched and public push remains paused.

### M1-05 and local M1 final sign-off — 2026-09-09 — primary assistant

- Reviewer verdict: ACCEPT M1-05 and overall local M1, with no blocking findings. Reviewer inspected the acceptance report, guide, architecture metadata and desktop/mobile screenshots, independently verified all 11 FirstWeek evidence hashes and clean diff whitespace.
- Report: `docs/firstweek/M1-ACCEPTANCE.md`. All M1 task checklist entries are accepted. This sign-off covers the private local workspace, not public deployment or a fresh live-provider check for saved conversations.
- Final checks passed: 15 Node checks and 20 Python checks; all recorded corpus evidence hashes match; cached offline semantic rebuild retains five projects and 45 chunks. Auth was restarted with reviewed code. Local RAG remains in explicit offline excerpt mode.
- Refreshed guide and architecture now describe persisted server-owned history, maintained responsibilities, durable uploads and optional generation. Mobile width 390px matches document width; diagram supports keyboard scrolling and textual descriptions. Full diagram screenshot: `/private/tmp/firstweek-m1-final-diagram.png`.
- Final database cleanup verification succeeded: zero exact acceptance conversations and zero acceptance-upload documents; five active local projects. This supersedes the earlier unavailable count check without changing its historical record.
- Next milestone is M2. Latest M1-04/M1-05 changes remain uncommitted on `v1`; earlier accepted work is in local commit `4d35bca`. Public push remains paused separately.

### M1-04 final acceptance — 2026-09-09 — primary assistant

- Reviewer verdict: ACCEPT M1-04. Prior UI findings were resolved by preserving failed drafts/errors and replacing displayed saved history with authoritative server results. Runbook now matches persistence and server-owned history.
- Final verification: 15 Node gateway/real PostgreSQL/HTTP checks and frontend production build passed; Prisma validation/client generation passed; diff whitespace clean. Tests cover cross-user/company access, concurrent starts, completed replay, altered-payload rejection, timeout/late-worker fencing, provider failure/retry, source invalidation and membership cascade.
- Browser acceptance: first turn survived reload and two turns survived auth restart. A second-tab source change caused the original tab to replace old history with one new turn. Following source deletion and a controlled service outage, recovery retained the retry draft/error while old turns and deleted beacon content were absent. Mobile 390px viewport had no horizontal overflow.
- Disposable conversation `11edb32c-ac3d-472f-aec9-beb9ebe2c44e` and the uploaded acceptance document were deleted through the UI. Subsequent conversation GET returned 404. An additional database-count check was blocked by the approval service's usage limit; no zero-count claim is made.
- Acceptance used offline source excerpts. Automatic approval review blocked a fresh external provider question; live generation was not revalidated. Local RAG is running with generation and semantic retrieval disabled for this verification. Screenshots: `/private/tmp/firstweek-m1-conversations-recovery.png` and `/private/tmp/firstweek-m1-conversations-mobile.png`.
- M1-05 remains next. Read-only evidence audit found four stale FirstWeek hashes (Workspace, gateway, RAG API and Prisma schema); the curated guide also needs its old memory-only/planned-upload language and architecture metadata updated before refreshing those hashes and rebuilding the index. All other recorded project evidence hashes matched.

### M1-04 implementation — 2026-09-09 — primary assistant

- User directed continuation of development. Public push remains paused after automatic approval review required explicit authorization for public visibility; local commit `4d35bca` contains accepted M1-01 through M1-03 on `v1`.
- Implementing private saved conversations through a composite membership foreign key, bounded JSON turns, pending request/version fencing and server-owned history. Membership removal cascades conversations; source changes conservatively invalidate saved content before reads.
- Added the conversation table and project knowledge version through additive migration `202609090001_project_conversations` on isolated `firstweek_demo`. Prisma validation/client generation and initial frontend build pass. Real PostgreSQL checks cover privacy, concurrency, retry, timeout fencing and deletion invalidation. Acceptance awaits reviewer and live browser/HTTP evidence.

### Commit preparation and deployment assessment — 2026-09-09 — primary assistant

- User authorized committing and pushing the reviewed changes on `v1`, preserving `main` separately. Included scope: cleanup follow-ups, FirstWeek favicon, M1-01 administration, M1-02 responsibilities, M1-03 uploads and their tests/documentation.
- Pre-commit verification: 13 Node checks and 20 Python checks passed; frontend production build passed in the M1-03 review. Local credentials, runtime state and generated data remain ignored.
- Public deployment is not accepted yet. `frontend/Dockerfile` starts the Vite development server; production Compose lacks explicit FirstWeek service-token/index configuration and still runs database push/seed commands on startup. A reviewed static-serving artifact, private service networking, durable knowledge volumes, controlled migration baseline and backup/restore verification remain M6 work.
- No deployment was requested or performed by this commit/push operation. M1-04 persistent conversations and M1-05 integration acceptance remain pending.

### M1-03 final acceptance — 2026-09-09 — primary assistant

- Reviewer verdict: ACCEPT M1-03; no remaining blocking findings. The primary implemented all changes and used only the reviewer agent for feedback.
- Maintainers upload UTF-8 Markdown/plain text through Knowledge; members read sources. Limits: 256 KiB/file, 240 chunks/document and 100 documents/project. Generated IDs and composite company/project foreign keys keep uploaded text/chunks private and independent of curated SQLite rebuilds.
- Fixed the reviewer's Unicode boundary finding with code-point chunking and a real PostgreSQL emoji test. Invalid binary text/surrogates, unsafe names and excessive sections are rejected. Managed retrieval uses recent questions for follow-ups; pending answers are withheld if project documents change.
- Verification passed: eight Node gateway/real PostgreSQL checks, 19 Python API/index checks, Prisma validation/client generation, frontend production build and clean diff whitespace. Cases include member/cross-project/cross-company denial, concurrent quota enforcement, forged evidence rejection and document deletion during generation.
- Browser flow passed: upload, source reading, Groq answer citing uploaded beacon instructions, regular member read-only controls, mobile 390px layout without overflow, delete/reload and deleted-source GET 404. Screenshots: `/private/tmp/firstweek-m1-upload-desktop.png` and `/private/tmp/firstweek-m1-upload-mobile.png`.
- Actual cached semantic rebuild retained five curated projects/45 chunks; uploaded text survived that rebuild and auth/RAG process restarts. The exact disposable upload and member account were removed; database checks confirmed zero remaining fixtures and five active projects.
- Additive migration `202609080003_project_documents/migration.sql` applied only to isolated `firstweek_demo`; runbook updated. M1-04 remains next: server-owned private conversation persistence, concurrent turn handling and conservative deletion invalidation.

### Workflow change and M1-02 start — 2026-09-08 — primary assistant

- User replaced the three-agent workflow with direct primary implementation plus one reviewer agent. The primary assistant now owns code, verification and TRACK.md; the reviewer remains read-only for application code and provides an independent verdict.
- M1-02 starts with persisted responsibility records, same-project member assignment, safe unassignment when membership is removed, UI maintenance, and server-owned answer context with provenance.
- Reviewer accepted the M1-02 code after fixes for inactive owners, complete stale-answer snapshots, maintained-only retrieval, inspectable citations and targeted authorization/concurrency tests. Final acceptance awaits browser evidence against restarted local backend processes.
- Replaced the inherited browser-tab icon with a project-local FirstWeek layered mark and aligned both HTML titles/theme metadata. The reviewer approved the asset; SVG validation and the frontend production build pass.

### M1-02 acceptance and M1-03 start — 2026-09-08 — primary assistant

- Reviewer verdict: ACCEPT M1-02 with no remaining blocking findings. Scoped ownership, current-owner validation, safe unassignment and stale generated-evidence rejection were independently reviewed.
- Browser acceptance completed: a maintainer created and assigned `Release readiness`; Ask returned the maintained owner with numbered provenance containing status, owner, description and timestamp; removing the member preserved the responsibility as unassigned after reload.
- A regular project member could read the responsibility but had no add-member, create, edit, save or delete controls. Exact disposable browser fixtures were deleted afterward and database counts verified zero.
- Automated evidence: Prisma validation, frontend production build, 12 RAG API tests (18 Python checks total), 10 Node gateway/administration/ownership checks and diff whitespace validation passed.
- M1-03 is now active. Managed uploads must remain durable outside the curated-index rebuild lifecycle, retain exact company/project authorization, enforce bounded type/size/text validation, and propagate deletion to retrieval.

### Bootstrap — 2026-09-07 — primary assistant

- User authorized implementation, with planning and milestones before tracking and coding.
- The current source collection has five projects, correcting the older ten-project scope text.
- Reviewer and tracker never touch code. All fixes return to coder.
- Isolated database and existing local Groq configuration can be used for verification. Do not send outbound invitations or publish anything as a side effect.
- Preserve the existing dirty working tree; no reset, commit, push or deployment is part of this milestone by default.

### Priority cleanup assignment — 2026-09-07 — tracker

- Latest user instruction prioritizes removing the specified legacy names and related branding across the project before continuing the milestone sequence. Coder owns this bounded cleanup and all implementation changes.
- Acceptance: case-insensitive residual search of maintained files and filenames finds no requested legacy terms; linked references, imports and scripts remain valid; relevant checks pass or pre-existing limitations are explicitly documented. Preserve user changes and do not rewrite Git history or remove dependency internals to satisfy a textual scan.
- Tracker will hand TRACK.md to reviewer after coder's evidence report. Only reviewer acceptance allows advancement to M1-01. TRACK.md remains owned by tracker until that explicit handoff.
- Next bounded task after cleanup acceptance: M1-01 project and membership administration, using exact-username additions of active verified same-company users and the preflight guardrails below; no outbound invitations.

## Review findings

### Cleanup evidence and review handoff — 2026-09-08 — tracker

- Coder reports M1-CLEAN implemented: startup autoseeding removed, unsupported seed flows fail early, stale fallback removed, mapper documentation corrected, retired identifiers removed after database verification, and evidence hash refreshed. Detailed implementation report supplied directly to reviewer.
- Reported checks: 18 Python and 8 Node checks pass; frontend build passes; three Compose configurations validate; embedded shell syntax checks pass; diff whitespace check clean. Maintained-content and filename scans report no requested terms, with ignored credentials/assets, legal license attribution and unrelated standalone names excluded; reviewer must assess these exclusions explicitly.
- Tracker hands sole TRACK.md write ownership to reviewer for dated findings and verdict. Reviewer must return ownership explicitly. M1-CLEAN remains unaccepted and M1-01 has not started.

Full M1 acceptance remains pending.

### M1-00 feasibility review — 2026-09-07 — reviewer

- Scope inspected: current projectScope/findProjectMembership, FirstWeek gateway routes, Project/ProjectMember schema, RAG index/API, and local bootstrap seeder. Read-only inspection; no code or generated files changed.
- Verdict: FEASIBLE WITH GUARDRAILS. Proceed with M1-01; this is not acceptance of unimplemented functionality.
- Decision: company admins may create projects and become their initial MAINTAINER. All subsequent project reads and management still require explicit project membership. A company admin does not gain source access by role alone. MAINTAINER manages exact-username additions of existing active, verified same-company users; this satisfies the roadmap's explicit membership alternative without outbound invitations. Separate external invitation lifecycle remains deferred.
- High / M1-01 concurrency: membership count followed by independent delete/demotion can remove both final maintainers. Required mitigation: serialize mutations on the project row inside a transaction, recheck actor there, validate role allowlist, and reject final-maintainer removal/demotion. Evidence required: simultaneous competing mutations against real PostgreSQL, plus member/cross-company denial.
- High / M1-01 restart revocation: scripts/firstweek-local-server.js:48 upserts the local user's project membership every startup, recreating removed access. Required mitigation: one-time explicit bootstrap semantics that do not restore removed memberships on subsequent starts; demonstrate restart persistence of revocation and roles.
- High / M1-03 durability: RAG/firstweek/index.py:114 atomically replaces the entire curated database. Writing managed uploads into that file loses them on rebuild. Required mitigation: durable managed storage outside curated rebuild lifecycle, exact company/project retrieval scope, bounded content/format validation, safe generated IDs and deletion propagation. Demonstrate rebuild and restart retention.
- High / M1-04 saved-content isolation: current /ask accepts client history; saved conversations must instead derive context from server-owned user/project records. Required mitigation: bounded DB history, ownership checks on every conversation/message operation, pending-call membership recheck, concurrent-turn/idempotency handling and failed-turn recovery. Removed documents must not remain exposed through saved sources or generated answer copies; define and test conservative invalidation/redaction.
- Medium / M1-02 maintained ownership: owner references must point to current same-project membership and become unassigned on removal. Answers must receive current maintained records with provenance rather than copied static guide facts.
- Medium / M1-01 browser mutations: apply same-origin/CSRF defense and strict JSON validation to new cookie-authenticated writes; keep gateway scope server-derived. New projects must have genuine empty knowledge states, not missing-index errors masquerading as success or copied fixture content.
- Existing strength retained: composite company/project membership predicate and post-generation recheck already constrain private retrieval. New routes must preserve that contract.
- Sequence approved: membership administration → editable ownership → durable managed knowledge → server-owned conversations → live integration. Reviewer releases TRACK.md ownership back to tracker after this entry; tracker schedules work and tracks remediation.

### M1-CLEAN final review — 2026-09-08 — reviewer

- Verdict: ACCEPT cleanup; no unresolved blocking findings in the maintained project cleanup scope. Tracker may mark M1-CLEAN accepted and assign M1-01. This is not acceptance of M1 functionality or production deployment.
- Independent evidence: case-insensitive maintained-content and filename scans find none of the requested full terms or the removed persona's Japanese surname. Auth cookie constants, HTTP middleware and WebSocket authentication agree; Git diff whitespace check is clean. Reviewed changes against the existing dirty tree without modifying implementation files.
- High / resolved: mechanical renaming created invalid uppercase deployment identifiers and normal Compose startup still invoked removed fixtures. Identifiers are now lowercase, all three Compose variants omit automatic persona loading, and retired init/reset/loader entry points fail before their database or installation commands. Normal startup no longer depends on the archived corpus.
- Medium / resolved: invented API/mail domains and cloud project defaults, stale persona mapping/prompt rules and voice fallback, and a renamed retirement identifier. Documentation uses reserved example domains, mail uses configured sender, cloud project IDs require configuration, voice cloning returns 503 before external work when unconfigured, persona mappings/rules/fallback were removed, and the bogus tombstone was removed after primary assistant verified the original database row was inactive.
- Corpus handling: coder reports source documents, binary derivatives and person-specific fixtures archived recoverably at /private/tmp/firstweek-persona-archive-UvVO2u; reviewer confirmed the archive directory exists with owner-only access. Git history was not rewritten. Reported offline semantic rebuild retains five projects and 45 chunks with no changed source hashes.
- Exclusions assessed: ignored credentials, credential tutorial/assets and local runtime state were not mechanically rewritten or exposed; dependency internals and Git history are outside maintained-source cleanup. Required LICENSE copyright attribution remains intact. The separate fictional person with the same given name is not the requested full-name identity and remains. Acceptance does not claim erasure from credentials, Git history, backups or external databases.
- Validation evidence supplied by coder: 18 Python checks, eight Node checks, frontend production build, three Compose configuration validations, embedded shell syntax, retired loader exit checks, and targeted cloud configuration precedence/missing-config checks passed. Reviewer independently inspected final fixes and scan/whitespace results; did not run builds, migrations or mutations outside TRACK.md.
- Nonblocking maintenance note: retired seed commands retain unreachable historical implementation behind an immediate explanatory exit. They no longer supply a supported seed workflow; use the FirstWeek runbook. Existing M1-00 guardrails remain mandatory for subsequent work.
- Reviewer returns sole TRACK.md write ownership to tracker now.

### Cleanup acceptance and M1-01 assignment — 2026-09-08 — tracker

- Received reviewer ACCEPT verdict and explicit TRACK.md ownership return; tracker marks M1-CLEAN accepted within the recorded maintained-source scope. No whole-history, credential or external-database erasure claim is made.
- Assign coder the bounded M1-01 task only: company-admin project creation with creator MAINTAINER membership; project settings and exact-username additions of active verified same-company users; member listing, allowlisted role changes and removal. All project reads/management require explicit membership, including company admins. No outbound invitations.
- Required integrity: serialize member mutations by locking the project row within a transaction, recheck actor permissions inside it, prevent final-maintainer removal/demotion and self-escalation, and retain server-derived company/project scope. Apply strict JSON validation and same-origin/CSRF defense to cookie-authenticated mutations.
- Required persistence/UX: bootstrap must not recreate revoked memberships or overwrite roles on restart; newly created projects show an honest empty knowledge state. Preserve existing source access checks and the post-generation membership recheck. Ownership, uploads and saved conversations remain separate later tasks.
- Acceptance evidence: real PostgreSQL simultaneous competing final-maintainer mutations; member/nonmember and cross-company denial; role/last-maintainer/invalid-body/origin checks; reload and server-restart persistence of revocation and roles; authenticated UI create/add/change/remove flows and empty knowledge state. Apply only necessary additive migrations to isolated firstweek_demo; no reset.
- Local PostgreSQL was observed on port 5547; coder must verify current availability and start required auth/RAG/frontend services for validation, then provide URLs and evidence to primary assistant for independent read-only integration checks. Coder performs test mutations; browser interactions use the required browsing skill.
- Working tree remains main with existing user changes preserved. No branch operations, commits, pushes or deployment. Coder sends changed files, decisions, check results and limitations to reviewer/tracker; tracker will explicitly hand TRACK.md to reviewer for the next verdict.

### M1-01 evidence and review handoff — 2026-09-08 — tracker

- Received coder report that backend/UI implementation and tests are complete; detailed implementation report sent to reviewer. Coder reports eight access regression checks and real PostgreSQL integration checks passed, including simultaneous competing final-maintainer mutations; frontend build and diff whitespace checks passed.
- Reported actual auth restart verification preserved role demotion and revoked membership through authenticated API reads; all temporary fixture changes were restored or removed. Exact additive migration SQL was applied only to the isolated database because Prisma migration history was absent; reviewer must assess the resulting schema and migration evidence.
- Browser evidence completed: actual login/project creation and honest empty project overview. Browser member addition, role change, removal and visual captures remain incomplete after the browsing session reset and primary assistant requested handoff. API/DB checks do not replace this missing UI acceptance evidence.
- Tracker transfers sole TRACK.md write ownership to reviewer now for a dated verdict, findings and required remediation, including disposition of the UI evidence gap. M1-01 is unaccepted; M1-02 remains pending. Reviewer must explicitly return ownership when its entry is complete; implementation or browser mutation fixes return to coder.

### M1-01 final review — 2026-09-08 — reviewer

- Verdict: ACCEPT M1-01. No unresolved blocking findings in project/membership administration. Tracker may record acceptance and assign M1-02; this does not accept the remaining M1 tasks or production readiness.
- Independent code review: company-admin creation reads current account authority in its transaction; management requires explicit MAINTAINER membership, locks the exact company/project row, then rechecks membership. Role allowlist, exact-username active/verified same-company target lookup, composite foreign keys and final-active-maintainer protection preserve scope. Cookie-authenticated management writes validate JSON and browser origin; private retrieval retains its post-generation membership check.
- High guardrails resolved: real PostgreSQL test code exercises competing self-demotions and reciprocal removals and asserts one maintainer remains. Bootstrap creates initial membership only alongside a new project; existing projects use an empty update, preserving edited settings, roles and revocations. Coder reports an actual authenticated restart check passed with temporary changes restored.
- Medium / resolved documentation defect: the runbook previously launched the browser on a different port from the permitted origin and described restoring memberships on restart. Reviewer verified the final runbook consistently uses port 5173, explains FIRSTWEEK_ORIGIN and preserves-revocations behavior, and documents the exact additive migration plus isolated-database P3005/history limitation.
- Migration assessment: the checked-in SQL adds only the non-null hasCuratedKnowledge boolean with default true, matching Prisma and preserving existing curated projects. API creation explicitly sets false and returns honest empty knowledge/answer states. Exact SQL application to the isolated database is acceptable for this prototype; deployment to existing databases still requires migration baselining and is not accepted here.
- Browser evidence gap resolved: coder reports actual login, project creation/empty overview, sole-maintainer rejection, exact-username addition, promotion, Settings save, mobile confirmed removal and reload persistence all passed. Reviewer opened /private/tmp/firstweek-m1-people-desktop.png and /private/tmp/firstweek-m1-people-mobile.png and independently verified loaded desktop/mobile content and usable layouts. Coder reports no page overflow and cleanup of exact browser fixtures, restoring five active curated projects.
- Validation: coder reports nine Node checks including the real PostgreSQL integration pass, prior frontend production build pass, and clean source hash/index state at five projects/45 chunks. Reviewer inspected implementation/tests/screenshots and independently verified clean diff whitespace. No reviewer code, database, build or browser mutations were performed.
- M1-02 handoff guardrails: responsibility owners must reference current same-project membership and become unassigned safely when a member is removed; maintained records must reach assistant context with provenance. Preserve the project-row serialization contract when removal begins changing ownership records.
- Reviewer returns sole TRACK.md write ownership to tracker now.
