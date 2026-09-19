# FirstWeek roadmap and milestones

Status: authorized for implementation. Begin with M1; progress is recorded in TRACK.md.

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

## Engineering constraints

Use React/Vite, Express auth, Prisma/PostgreSQL, FastAPI and configured embedding/provider clients. Route private data only through project-scoped chat and retrieval. Authorization derives from server identity, never body scope. Keep private content out of bundles, logs and public APIs. Use additive migrations; no database reset. Managed ingestion needs durable state separate from destructive curated rebuilds. Prefer bounded synchronous ingestion only if it is genuinely safe at the supported size, otherwise explicit jobs and recovery. Follow established FirstWeek/Impeccable design patterns.

## Three-agent workflow

Exactly three agents: coder, reviewer, tracker. The primary assistant coordinates the user and performs independent read-only integration checks. Only the coding agent changes application code, tests, migrations, configuration, scripts and implementation documentation after this planning bootstrap.

The reviewer and tracker NEVER edit code, tests, migrations, configuration, generated artifacts, or implementation documents. Their only writable file is TRACK.md. Neither runs autofix, formatters, code generation, builds that mutate the repository, or migrations. Reviewer inspects feasibility, correctness, security, errors and evidence; tracker owns scheduling and status, not code fixes.

Tracker chooses a bounded task, records assignment and acceptance criteria in TRACK.md, and sends it to coder. Coder implements/tests, sends a report to reviewer and tracker with changed files, decisions, evidence, limitations and suggested next work. Reviewer appends a dated review section to TRACK.md (findings, severity, reproduction/evidence, required mitigation, verdict) and informs tracker. Tracker records the verdict, assigns fixes to coder or advances to the next task. Coder never bypasses a failed review. Only tracker marks tasks accepted after reviewer acceptance.

TRACK.md has a single-writer handoff: tracker releases it to reviewer for review entries, then reviewer releases it back. Coder sends reports by agent message and never edits TRACK.md. Each cycle preserves an append-only decision/finding log alongside a current completed/remaining task table. No agent spawns extra agents.
