# FirstWeek roadmap and milestones

Status: M1 accepted for the local private workspace on 2026-09-09. M2-01 private onboarding profiles accepted on 2026-09-10; full M2-02 company structure and assignments accepted on 2026-09-15. M2-03 managed reading paths and private progress accepted locally by Gauss on 2026-09-16 at 100/100; M2-04 and M2 overall acceptance remain outstanding. Progress and acceptance limits are recorded in TRACK.md and docs/firstweek/M1-ACCEPTANCE.md.

Priority update (2026-09-15): user resumed M2 while handling public deployment settings. PUBLIC-01 brings forward a bounded M5/M6 slice: explicitly published summaries, anonymous project/architecture/source browsing, grounded chat, distributed generation limits and Vercel configuration. Public launch remains pending; personal-site integration and embed remain deferred. This does not complete M5 or M6. See `PUBLIC-DEPLOYMENT.md` for the public-only deployment and remaining launch checks.

## Baseline

Five private projects and 45 indexed sections, source-backed architecture diagrams, session and project membership checks, local hybrid retrieval, and Groq-generated cited answers. This is a local prototype, not a production-readiness sign-off. Existing unrelated working-tree changes must be preserved. Repository: /Users/dev_an/projects/FirstWeek.

## Milestones

| ID | Outcome | Included work | Completion evidence |
| --- | --- | --- | --- |
| M1 | Usable private onboarding workspace | Create projects; add/invite/remove members and manage project roles; edit responsibility/ownership records; upload, index and delete documents; persist private conversations per user/project; complete corresponding UI | Real authenticated flows, persistence across reload/restart, upload-to-answer evidence, negative authorization tests, reviewer acceptance |
| M2 | Maintained company context and personalized onboarding | Company structure, assignments, role/experience profiles, relevant reading paths and durable onboarding progress | Explicit maintained records, role-appropriate answers, progress persistence, no inferred owners |
| M3 | Maintainable knowledge and evaluated RAG | Repository imports, refresh/version/index-job lifecycle, source deletion propagation, retrieval/answer evaluation, citation precision, prompt injection and ambiguous-question cases | Reproducible ingestion/refresh, golden question set, documented quality results and failure limits |
| M4 | Complete frontend and account experience | Revamp remaining signup, recovery, account and admin screens; accessibility, responsive states and error recovery | Browser checks of actual supported flows at desktop/mobile widths |
| M5 | Public portfolio assistant | Explicit publication workflow, separate public collection, bounded API, embeddable widget, origin and cost controls | No private corpus access from public endpoints; publication/removal checks; working embed |
| M6 | Deployment-ready demo | Static production serving, internal networking, secrets, backups, health/monitoring, rate/cost limits and deployment verification | Reviewed deployment artifact, operational checks, restore exercise and explicit readiness report |

Production publishing and external messaging are separate external actions: prepare concrete artifacts first. No email/Slack/invitation message is sent automatically. Invite creation in M1 means a shareable, expiring invitation or explicit same-company membership action in the UI, with no outbound message delivery.

## M1 task sequence and acceptance

1. M1-01 Membership and project administration: examine existing auth and membership contracts; implement project creation and scoped management UI/API, invitation/acceptance if needed, roles and removal. Only an authorized same-company actor can manage; company role alone is not permission to read project sources. Prevent last-maintainer removal/demotion and self-escalation. Removed access must fail closed. New projects must show honest empty knowledge states.
2. M1-02 Editable ownership: maintain project responsibility areas, current assignments/status and owner membership. No invented ownership. Validate owner belongs to the same project. Removal must unassign or invalidate ownership safely. Expose maintained context to answers with provenance, not stale copied facts.
3. M1-03 Document uploads: support clearly declared formats with size/type/text limits; store privately, index in exact project/company scope, show status/errors, read sources and delete uploaded content. Reindex/restart must not discard managed documents. Generated filenames and safe parser behavior; no arbitrary server path ingestion or remote URL fetching. Existing curated sources must remain intact.
4. M1-04 Persistent conversations: private user/project conversation list, create/open/delete, durable messages and sources; server-owned history, bounded model context, concurrency/idempotency protection and pending/error recovery. Reload and server restart preserve successful turns. Membership removal and document removal must not leak stale source contents through saved conversations.
5. M1-05 Integration and acceptance: apply additive migrations only to isolated firstweek_demo; run live member/nonmember flows, ownership changes, upload-index-answer-delete, conversation reload and restart checks; browser UX/accessibility checks; update source guides and runbook. Resolve reviewer findings before accepting M1.

## M2 task sequence and acceptance

1. M2-01 Private onboarding profiles: members explicitly choose an onboarding focus and experience preference per project. Nullable defaults, self-only reads/writes, no authorization or ownership implications. Server-owned answer style and profile-version fencing; changes reset only that member's project conversations. Verify isolation, null reset, revocation, restart durability and accessible UI.
2. M2-02 Company structure and assignments: company-admin-maintained teams and explicit assignments, with company isolation and project-source membership remaining independent. Show provenance and unassigned states; do not infer owners.
3. M2-03 Reading paths and progress: maintained project reading sequences relevant to explicit profiles, durable private completion records, scoped source links and safe deletion handling.
4. M2-04 Integration and acceptance: role-appropriate grounded answer checks, maintained context freshness, reload/restart progress checks, browser evidence and reviewer sign-off.

## M2-03 independent review — 2026-09-15 — Gauss

Verdict: **CHANGES REQUESTED, 88/100** for the bounded managed-source reading-path implementation. Database and browser acceptance remain blocking. This is not acceptance of M2-03 or M2 overall.

- Context read: PROJECT-MAP.md, TRACK.md, this roadmap, M2-03-PLAN.md and relevant RUNBOOK sections; reviewed only the mapped reading-path, membership, managed-document, schema, route and frontend paths.
- Resolved preflight findings: append now uses the greatest surviving position after source-deletion cascades; reorder validates the complete project list and moves through temporary negative positions inside the project lock; maintainers can edit/reorder; personal progress uses profile-matching steps with an explicitly labelled management list. Material edits increment revision and the form explains the completion reset. Curated-source reading paths are explicitly deferred to M3 in the revised plan; this review covers managed sources only.
- Independently run: focused ReadingPath frontend test passed (one test); Node syntax checks and git diff whitespace check passed. The database test was deliberately invoked with its database guard disabled and reported zero passes/one skip. No migration, fixture mutation, database restart or browser flow was performed by the reviewer.
- Primary-reported evidence: all three FirstWeek frontend suites/six tests, private Vite build and Prisma validation passed. These do not establish database or browser acceptance.
- Blocking evidence gap: M2-03-PLAN.md:28 requires actual completion persistence through reload/auth restart, and lines 29–30 require browser/regression evidence. The prior isolated PostgreSQL cluster is absent; this review does not authorize recreating or overwriting a database.
- Important test gap: readingPaths.integration.test.js:5 contains one sequential service test, without HTTP origin/JSON/no-store and scope-injection checks, actual second-company/project source fixtures, or competing quota/reorder/edit/delete/completion writes. Its reconnect at line 57 occurs after the completed member was removed, so it verifies surviving steps rather than completion persistence. Follow-up completion-reset-after-edit and source-to-progress cascade assertions were inspected but remain unexecuted. Add the remaining focused cases; run them against an authorized isolated database once available.
- Next action: primary completes safe test/documentation work, resolves the database target with the user, then supplies migration, concurrency, persistence, desktop/mobile browser and exact-fixture-cleanup evidence for a new independent review. TRACK.md remains primary-owned.

| Factor | Weight | Score | Evidence |
| --- | ---: | ---: | --- |
| Correctness and regressions | 30 | 30/30 | Original ordering/editing defects resolved in inspected code; no new verified implementation defect |
| Security and authorization | 20 | 20/20 | Scoped membership, server-owned completion identity, composite ownership and write guards inspected |
| Tests and verification | 15 | 3/15 | Focused UI test passes; backend coverage incomplete and database/browser acceptance absent |
| Reliability and data integrity | 15 | 15/15 | Locked ordering, safe append, revision fencing and cascades inspected; runtime proof remains in the verification gap |
| Maintainability and scope discipline | 10 | 10/10 | Bounded existing-stack implementation; managed-source limitation explicit |
| UX, accessibility, and error states | 10 | 10/10 | Edit/reorder controls, reset explanation and separate personal counts inspected; live browser proof remains outstanding |
| **Overall combined review score** | **100** | **88/100** | weighted total; blocking acceptance evidence requires CHANGES REQUESTED |

## M2-03 verification follow-up — 2026-09-16 — primary coordinator

The historical 88/100 review above is retained, not superseded by implementer claims. Correction: the old `.firstweek/local/postgres` directory exists; an earlier check used the wrong working directory. The user authorized a separate `.firstweek/m203/postgres` cluster on loopback 5548, database `firstweek_demo`; its baseline and eight additive migrations are applied without overwriting the original cluster.

Follow-up database checks now assert completion before member removal and after reconnect. Expanded tests cover profile counts, real-service scope-injection rejection, source isolation and competing quota/edit-completion/reorder-deletion writes. Authenticated browser verification demonstrates upload/index, maintained-step CRUD/reorder, edit-reset and 1/1 completion persisting through reload and actual auth restart at desktop/390px. Corrected screenshots are under `.firstweek/m203/`. Fresh server permissions now drive UI controls; row-specific CSS prevents control overflow while preserving existing Overview reading links.

Primary independently passed 11 public API tests, 22 offline RAG tests, 129 frontend tests (one skipped) and the private build before the final follow-up additions. Sol's final rerun passed two expanded database, three HTTP and two focused UI tests; the full frontend suite (129 passed, one skipped, 11 snapshots), private build and six index tests also passed. Member browser controls were read-only for maintenance, with self-completion working. Exact cleanup retained five active projects and left zero temporary companies, fixture documents/users, reading steps or progress. The refreshed guide has 18 matching FirstWeek evidence hashes; offline hybrid rebuild now contains five projects/46 sections and no changed sources. Gauss's final verdict remains pending; M2-03 and overall M2 are not yet accepted by this follow-up record.

## M2-03 final independent review — 2026-09-16 — Gauss

Verdict: **ACCEPT, 100/100** for the bounded local managed-source reading-path and private-progress scope. No remaining blocking or important findings. This supersedes the historical 88/100 verdict above; that record and the dated correction to the earlier cluster-absence claim are preserved. It does not accept M2 overall, curated-source reading paths, a new live-provider evaluation, publication or production readiness.

- Context and scope: reread PROJECT-MAP.md, TRACK.md, M2-03-PLAN.md and relevant runbook/roadmap entries; inspected the reading-path service, scoped schema/migration, routes, managed-document/member deletion paths, UI/CSS and focused tests.
- Correctness and authorization: project-locked writes preserve the 50-step quota and exact complete-list ordering; append safely tolerates source-deletion gaps. Material edits advance revisions; stale completions fail closed and only the requesting member's progress is returned. Foreign-company and same-company/other-project sources are rejected. Source and membership foreign keys cascade dependent progress. The public workspace excludes the private reading-path capability.
- Review fixes closed: fresh response permissions drive management controls; row-specific styles prevent overflow; direct-child Overview reading-link styles are restored. Real-service scope-injection assertions complement the deliberately mocked HTTP tests. Final race assertions cover the surviving step ID and nonnegative unique positions. Profile-matching personal counts remain distinct from the maintained list.
- Independently run by Gauss: both focused ReadingPath UI tests passed; reading-path service/test syntax and diff whitespace checks passed; all 18 FirstWeek evidence hashes independently matched current files. Independently opened four artifacts: `.firstweek/m203/reading-path-desktop-complete.png`, `reading-path-mobile-complete.png`, `reading-path-member-mobile.png` and `overview-desktop.png`. Completed desktop/mobile layouts fit their content; the member view shows private completion without maintenance controls; Overview styling is preserved.
- Inspected tests and implementer/coordinator evidence: two real-PostgreSQL tests passed on the authorized isolated 5548 database, covering reconnect persistence, revision reset, cascades, scope/profile cases and the three bounded races; three HTTP tests and two focused UI tests passed. Reported authenticated browser checks cover upload/source opening, maintainer create/edit/reorder/remove, member self-completion, reload and actual auth-server restart. The reviewer did not repeat database fixture writes, migrations, browser interactions or runtime restarts.
- Regression and cleanup evidence supplied by the team: full frontend suite 129 passed/one skipped, private build passed, public API 11/11, offline RAG 22/22 and six index tests passed. Exact fixture cleanup retained five active projects and left zero temporary companies, fixture documents/users, reading steps or progress. Refreshed offline hybrid index contains five projects/46 sections with no changed sources. Guide, runbook and plan now document the supported managed-only behavior and isolated runtime.
- Remaining gaps in this submitted scope: none requiring another implementation loop. Next action: primary records M2-03 acceptance in TRACK/plan/map and proceeds to the separate M2-04 integration acceptance task. No commit, push or deployment is authorized by this verdict. Gauss edited only this milestone record.

| Factor | Weight | Score | Evidence |
| --- | ---: | ---: | --- |
| Correctness and regressions | 30 | 30/30 | Scoped CRUD/order/revision behavior and restored Overview styles reviewed; focused and adjacent regressions passed |
| Security and authorization | 20 | 20/20 | Fresh maintainer checks, self-only completion, exact source scope, composite foreign keys and write guards |
| Tests and verification | 15 | 15/15 | Focused database/HTTP/UI evidence, browser/restart walkthrough, independent UI/hash/artifact verification |
| Reliability and data integrity | 15 | 15/15 | Quota, edit/completion and reorder/deletion races; reconnect/restart retention; cascade and cleanup evidence |
| Maintainability and scope discipline | 10 | 10/10 | Bounded existing-stack implementation, explicit managed-only boundary and refreshed operational documentation |
| UX, accessibility, and error states | 10 | 10/10 | Fresh permission UI, labelled controls, revision-reset warning, profile counts and corrected desktop/390px layouts |
| **Overall combined review score** | **100** | **100/100** | weighted total; no verified issue remains in the submitted scope |

## Engineering constraints

Reuse React/Vite, Express auth, Prisma/PostgreSQL, FastAPI and existing embeddings/provider clients. Avoid routing private data through legacy unscoped chat/retrieval. Authorization derives from server identity, never body scope. Keep private content out of bundles, logs and public APIs. Use additive migrations; no database reset. Managed ingestion needs durable state separate from destructive curated rebuilds. Prefer bounded synchronous ingestion only if it is genuinely safe at the supported size, otherwise explicit jobs and recovery. Reuse established FirstWeek/Impeccable design patterns.

## Implementation workflow

GPT-5.6-Sol implements, debugs and verifies each bounded task. The primary assistant coordinates, reviews and maintains TRACK.md. Gauss independently inspects correctness, security, errors and evidence without editing application code; Sol addresses review findings. A task advances only after reviewer acceptance. No publication or main-branch change is authorized by acceptance alone.
