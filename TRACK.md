# FirstWeek milestone tracker

## Current state

- Active milestone: M1 — Usable private onboarding workspace.
- Roadmap: docs/firstweek/MILESTONES.md.
- Baseline: 5 projects, 45 indexed sections; local authenticated conversational RAG and architecture views.
- Workflow: primary assistant implements and tracks; one reviewer agent independently reviews. This supersedes the earlier three-agent workflow by user instruction on 2026-09-08.
- TRACK.md write owner: primary assistant. Reviewer supplies findings by agent message and does not edit application code.
- Status: M1-03 accepted; M1-04 persistent conversations is next.

## Task board

| Task | Status | Acceptance / next action |
| --- | --- | --- |
| M1-00 Feasibility and sequence | Accepted | Reviewer feasibility preflight approved with guardrails below |
| M1-CLEAN Legacy-term cleanup | Accepted | Reviewer accepted maintained-source cleanup; exclusions and recoverable archive recorded below |
| M1-01 Project and membership administration | Accepted | Reviewer accepted scoped administration, concurrency/restart safety and authenticated desktop/mobile flows |
| M1-02 Editable ownership | Accepted | Reviewer accepted scoped responsibility maintenance, safe unassignment, cited answers, stale-evidence rejection and member read-only UI |
| M1-03 Document uploads | Accepted | Reviewer accepted scoped uploads, Unicode/size limits, cited retrieval, restart/rebuild durability and deletion |
| M1-04 Persistent conversations | Pending | User/project history, reload/restart persistence, safe history and deletion |
| M1-05 Integration and acceptance | Pending | Live flows, regression evidence, browser checks and final reviewer acceptance |

## Completed

- Planning bootstrap: roadmap, milestone acceptance criteria, strict role boundaries and review handoff protocol documented.
- M1-00 feasibility and sequence: reviewer approved membership-first implementation with the recorded security, concurrency and durability guardrails.
- M1-CLEAN maintained-source cleanup: reviewer accepted requested-term removal, runtime corrections and documented exclusions; original corpus preserved in a private recoverable archive.
- M1-01 project and membership administration: reviewer accepted project creation/settings and secure member add/role/remove flows with real concurrency, restart and browser evidence.
- M1-02 editable ownership: reviewer accepted maintained responsibilities, same-project assignments, safe removal-to-unassigned behavior, sourced answers and read-only member access.
- M1-03 document uploads: reviewer accepted durable PostgreSQL text/chunk storage, project-scoped access, bounded ingestion, cited answers and deletion.

## Remaining milestones

M1 tasks above, then M2 company context/personalization; M3 managed knowledge and RAG quality; M4 frontend/account completion; M5 public portfolio collection/widget; M6 production deployment readiness.

## Decisions and activity log

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
