# M2-03 reading paths and private progress

Status: accepted locally by Gauss on 2026-09-16, 100/100, with no remaining blockers. The historical 88/100 CHANGES REQUESTED review and final scorecard are preserved in MILESTONES.md. Overall M2 and deployment acceptance remain separate.

## Scope

- A project maintainer authors a bounded, ordered reading sequence referencing existing **managed** sources in that same project. Curated sources do not have a database source identity compatible with the durable foreign key, so curated-path support is explicitly deferred to M3's source lifecycle work. Reuse the source-reader UI; no arbitrary URL fetching, new ingestion pipeline or recommendation service.
- Optional focus and experience filters use the explicit M2-01 preference enums. Null means generally relevant. Preferences affect presentation, never access permissions or ownership claims.
- Each member records their own completion durably in PostgreSQL. No other member, including maintainers/company admins, receives another person's completion records.
- Reuse the private workspace design and existing authenticated project API. Public showcase, generated answers, email notifications and analytics are outside this submilestone.

## Implemented decisions

1. Additive reading-step and self-only progress tables use composite company/project/source/member foreign keys and deletion cascades.
2. Only existing managed documents in the exact project are accepted. Source deletion removes dependent steps and progress; curated support is deferred to M3.
3. Existing project locks serialize edits, reordering, completion and document deletion. Material edits advance revision; completion requires the displayed revision and stale requests fail with 409.
4. Limit each project to 50 steps, title to 120 characters and description to 800. Reorder accepts exactly the current unique step-ID set and uses temporary negative positions atomically. Appends use the greatest surviving position after deletion gaps.
5. Only profile-matching steps contribute to personal progress; maintainers separately see all maintained steps. Material edits reset effective completion; unchanged saves and reordering do not change revisions. No inferred completion or progress access for other users.

## Acceptance checklist

- [x] Maintainer create/edit/reorder/remove; ordinary members cannot manage steps (self-completion remains allowed).
- [x] Fresh membership and current authority checks; cross-company/project IDs and body-scope injection denied.
- [x] Same-origin JSON write guards and private no-store responses.
- [x] Self-only progress reads/writes; revocation and membership removal fail closed.
- [x] Source deletion/change and concurrent edits cannot leak stale source content or preserve misleading completion.
- [x] Explicit profile filtering with honest empty states and stable progress counts.
- [x] Completion survives reload and auth-server restart in isolated firstweek_demo.
- [x] Desktop/mobile browser checks using disposable fixtures; exact fixture cleanup preserves maintained projects.
- [x] Backend/frontend regression tests, build, refreshed guide/evidence and independent reviewer acceptance.

M2-04 remains the separate overall M2 integration and acceptance step.

## Verification follow-up — 2026-09-16

The user-authorized new isolated cluster is `.firstweek/m203/postgres`, loopback port 5548, database `firstweek_demo`. Baseline plus eight additive migrations through `202609150001_reading_paths` were applied; the pre-existing `.firstweek/local/postgres` was preserved. Earlier reports that the old directory was absent were incorrect.

Two real-database tests pass, covering revision reset/reconnect, self-only progress, source/member cascades, profile counts, injected-field rejection, foreign source denial and three bounded races: competing quota appends, edit/completion and reorder/source deletion. Three HTTP tests cover authentication, same-origin JSON/no-store and server-derived scope; their mocked services are not evidence of real-service validation. Two focused UI tests cover maintenance and fresh server permissions.

Authenticated desktop/390px browser checks cover upload/index, step creation, ordering, material-edit reset, completion, removal and persistence after reload and an actual auth restart. Primary inspected corrected `reading-path-desktop-complete.png` and `reading-path-mobile-complete.png` under `.firstweek/m203/`; both show 1/1 progress without the original control overflow. An ordinary-member browser session showed source/self-completion controls without management controls and reached its own 1/1; capture `reading-path-member-mobile.png` has no page overflow. Exact fixture cleanup reports five active projects and zero temporary companies, fixture documents/users, reading steps or progress. Guide/evidence refreshed: 18 matching FirstWeek evidence hashes, offline hybrid index five projects/46 sections, no changed sources. Gauss accepted this bounded scope at 100/100 after independent code/artifact review and the separately attributed verification evidence.
