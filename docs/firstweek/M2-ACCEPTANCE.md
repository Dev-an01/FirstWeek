# M2 integration and acceptance evidence

Started: 2026-09-16; resumed: 2026-09-17. Status: M2-04 in progress; overall M2 is not yet accepted. M2-01, M2-02 and M2-03 have individual local acceptance. This report consolidates their interaction checks, not production or publication approval.

## Scope and gates

- Explicit self-only onboarding preferences affect explanation guidance and reading relevance, never permissions or inferred job/ownership facts.
- Maintained company teams/assignments can supply scoped answer evidence with provenance; edits/deletion invalidate stale saved or pending answers without granting project access.
- Profile-matched reading counts and durable revision-fenced completion remain private across integrated flows, reload and restart.
- Combined local regression/browser evidence, exact disposable-fixture cleanup and Gauss independent final acceptance are required.

## Environment and evidence boundaries

Use only the user-authorized `.firstweek/m203/postgres` cluster on loopback 5548, database `firstweek_demo`. Preserve the original `.firstweek/local/postgres`. Existing local auth/Vite/RAG ports are 3003/5175/8003; verify listeners before restarting anything. Database tests must explicitly target the isolated database and clean their scoped fixtures.

M2-03 accepted evidence includes actual completion persistence across reload/auth restart, desktop/390px maintainer/member flows, three bounded write races, scoped sources and exact cleanup. Reuse where implementation is unchanged, and label it as carried-forward evidence.

Current live browser RAG uses offline source excerpts. Mocked-provider tests may verify controlled prompt guidance, evidence injection and freshness fencing; neither establishes fresh live-provider answer quality. No new external-provider call, deployment or publication is part of this acceptance run.

## Results

Primary reran adjacent regressions on 2026-09-17: 22 offline RAG tests and 11 public API tests passed. Commands: `.firstweek/venv/bin/python -m unittest RAG.firstweek.test_api RAG.firstweek.test_index RAG.firstweek.test_profile_mapping -q` with generation/semantics disabled, and `node --test server/public.test.js` from `frontend`.

Primary also passed all 11 frontend suites: 129 tests passed, one skipped, 11 snapshots passed (`node node_modules/jest/bin/jest.js --runInBand` from `frontend`). Private production build passed, 1,702 modules (`node node_modules/vite/bin/vite.js build`). These checks do not substitute for the new cross-feature database/browser scenario.

Sol ran the new `backend/auth-service/tests/m2Acceptance.integration.test.js` against explicit port 5548: one test passed. The relevant M2 integration/route set passed 19 checks, and four remaining legacy suites passed four checks. Seven existing suites now honor `FIRSTWEEK_DATABASE_URL` rather than forcing the preserved port-5547 cluster. Gauss inspected the combined test and found no blocking defect.

The combined test uses real PostgreSQL/services/HTTP gateway, synthetic test identities and a stub RAG server. It verifies profile hide/restore with private completion, own-history invalidation, assignment-change invalidation preserving profiles/progress, and current server-owned profile/company/managed-source forwarding. Its unsupported-question assertion establishes empty forwarded evidence and the stub fallback, not real generated-answer quality or session authentication.

Primary independently checked the source index: `changedSources: []`; diff whitespace is clean. Real browser verification is running with exact fixture company `m2-acceptance-browser`, project `p-25dcbde5-fdf0-4e7d-bf8c-7f794365c320`, users `m204_admin_fixture`/`m204_member_fixture`. Real login succeeded; combined offline Ask/profile/progress/company-context flow, restart, exact cleanup and final independent acceptance remain pending.
