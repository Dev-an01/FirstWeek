# M1 acceptance evidence

Date: 2026-09-09. Scope: the private local onboarding workspace on `v1`. Reviewer verdict: ACCEPT M1-05 and overall local M1, with no blocking findings. The full sign-off is recorded in TRACK.md. This report is not approval for public deployment.

## Milestone checklist

- [x] M1-01: company-admin project creation; explicit maintainer/member access; member add/change/remove; final-maintainer protection; settings and revocations survive restart.
- [x] M1-02: maintained responsibilities and status; same-project owners; removal leaves assignments unassigned; current ownership reaches answers with provenance.
- [x] M1-03: UTF-8 Markdown/plain-text uploads; bounded size/chunks/count; durable scoped PostgreSQL text and chunks; read/search/delete; curated rebuild and service restart retention.
- [x] M1-04: private saved conversations; server-owned history; bounded turns; duplicate-request handling; concurrent/expired worker fencing; failed-draft recovery; deletion and knowledge-change invalidation.
- [x] M1-05 verification: refreshed source guide and architecture, matching evidence hashes, successful index rebuild, final regression suite and browser checks.
- [x] Final M1 reviewer sign-off: accepted on 2026-09-09.

## Reproducible automated evidence

From the repository root, use the existing isolated `firstweek_demo` on loopback port 5547. Tests create and remove scoped disposable records; never substitute a production database.

```sh
NODE_ENV=test FIRSTWEEK_TEST_DATABASE=1 node --test backend/auth-service/tests/projectAccess.test.js backend/auth-service/tests/firstweekRoutes.test.js backend/auth-service/tests/projectAdministration.integration.test.js backend/auth-service/tests/projectResponsibilities.integration.test.js backend/auth-service/tests/projectDocuments.integration.test.js backend/auth-service/tests/projectConversations.integration.test.js backend/auth-service/tests/conversationRoutes.integration.test.js
.firstweek/venv/bin/python -m unittest RAG.firstweek.test_api RAG.firstweek.test_index RAG.firstweek.test_profile_mapping -q
.firstweek/venv/bin/python -m RAG.firstweek.index check
git diff --check
```

Final results: 15 Node checks passed; 20 Python checks passed; no changed source hashes; clean diff whitespace. Intentional missing-record and provider-failure cases print error messages while their assertions pass. Prisma validation/client generation and the frontend production build passed during M1-04 acceptance; M1-05 changes only documentation and corpus metadata.

The cached semantic rebuild was repeated with `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, using `.firstweek/models` and `sentence-transformers/all-MiniLM-L6-v2`. Result: five projects, 45 chunks, hybrid index. Managed uploads reside in PostgreSQL and are separate from this rebuild.

## Browser and persistence evidence

M1-01 through M1-04 reviewer handoffs in TRACK.md record authenticated creation, membership changes, ownership changes, upload/read/answer/delete, ordinary-member read-only controls, conversation reload/restart and failure recovery. These include actual PostgreSQL and service operations, not only mock assertions.

The final refreshed architecture and source reader were opened through the authenticated UI. At 390px viewport width, document width was 390px. The diagram has a keyboard-focusable scroll region and a textual SVG description; the page also lists its data flows as text.

Screenshots retained locally for review:

- `/private/tmp/firstweek-m1-final-architecture.png`
- `/private/tmp/firstweek-m1-final-mobile.png`
- `/private/tmp/firstweek-m1-final-diagram.png`
- `/private/tmp/firstweek-m1-conversations-recovery.png`
- `/private/tmp/firstweek-m1-conversations-mobile.png`
- Earlier administration/ownership/upload evidence is referenced in TRACK.md.

M1-04's deleted conversation returned HTTP 404 after UI deletion/reload. Final M1-05 database checks additionally found zero rows for that exact conversation and zero documents named `firstweek-upload-acceptance.md`; five active local projects remain. The auth service was restarted with the reviewed code for final integration.

## Limits of acceptance

The latest browser conversation checks used offline source excerpts. Automatic approval review blocked a fresh live-provider question; provider generation was verified in earlier milestones but was not revalidated for saved conversations. The local RAG process remains in `FIRSTWEEK_GENERATE=false FIRSTWEEK_SEMANTIC=false` mode. The on-disk semantic index remains available.

Uploads support text only, at most 256 KiB/file, 240 chunks/document and 100 documents/project. Conversations allow 20 turns and 50 conversations/user/project. Conservative knowledge changes can clear history; offline/failed knowledge lookup withholds saved content. Text already copied outside the application cannot be recalled.

Public deployment remains M6: production static serving, domain/TLS, internal-only service exposure, secrets/index configuration, migration baselining and backup/restore verification are outstanding. Public push remains paused separately; no deployment or publication is part of this acceptance.
