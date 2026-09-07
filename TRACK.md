# FirstWeek milestone tracker

## Current state

- Active milestone: M1 — Usable private onboarding workspace.
- Roadmap: docs/firstweek/MILESTONES.md.
- Baseline: 5 projects, 45 indexed sections; local authenticated conversational RAG and architecture views.
- Workflow: coder → reviewer → tracker → coder. Only coder edits code. Reviewer and tracker may edit ONLY this file.
- TRACK.md write owner: tracker (reviewer must receive explicit handoff).
- Status: feasibility preflight complete; coder assigned priority legacy-term cleanup before M1-01.

## Task board

| Task | Status | Acceptance / next action |
| --- | --- | --- |
| M1-00 Feasibility and sequence | Accepted | Reviewer feasibility preflight approved with guardrails below |
| M1-CLEAN Legacy-term cleanup | In progress — coder | Remove user-specified legacy names and related branding from maintained project text, identifiers and assets; preserve working behavior; reviewer verifies residual search and relevant checks |
| M1-01 Project and membership administration | Pending | Create/manage through UI; secure scope, roles, invitations and revocation |
| M1-02 Editable ownership | Pending | Maintained responsibilities and valid member owners; usable in assistant context |
| M1-03 Document uploads | Pending | Private durable upload/index/read/delete; rebuild safety and size limits |
| M1-04 Persistent conversations | Pending | User/project history, reload/restart persistence, safe history and deletion |
| M1-05 Integration and acceptance | Pending | Live flows, regression evidence, browser checks and final reviewer acceptance |

## Completed

- Planning bootstrap: roadmap, milestone acceptance criteria, strict role boundaries and review handoff protocol documented.
- M1-00 feasibility and sequence: reviewer approved membership-first implementation with the recorded security, concurrency and durability guardrails.

## Remaining milestones

M1 tasks above, then M2 company context/personalization; M3 managed knowledge and RAG quality; M4 frontend/account completion; M5 public portfolio collection/widget; M6 production deployment readiness.

## Decisions and activity log

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

No milestone review has been performed yet.

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
