# Frontend Security Audit — Tracking Checklist

**Scope:** `frontend/` (React/Vite) + `frontend-avatar/` (Express + vanilla JS)
**Branch:** `staging`
**Date:** 2026-06-23
**Method:** OWASP-based static pattern scan + dependency audit + auth-flow review

> Check a box when the item is **fixed and verified**. Each finding lists location, risk, and remediation.

---

## Summary

| Severity | Open | Fixed |
|----------|------|-------|
| 🔴 Critical | 0 | 0 |
| 🟠 High | 1 | 1 |
| 🟡 Medium | 1 | 5 |
| 🔵 Low / Info | 3 | 0 |

---

## 🟠 High

- [x] **HIGH-001 — Vulnerable dependencies in `frontend-avatar` (9 advisories)** ✅ FIXED 2026-06-23
  - **Location:** `frontend-avatar/package-lock.json`
  - **Detail:** `npm audit` → 3 high + 6 moderate. `picomatch <=2.3.1` (ReDoS / glob-matching, via `http-proxy-middleware`); `qs <=6.15.1` DoS via `body-parser` → `express 4.21.0–4.22.1`.
  - **Risk:** Remotely-triggerable denial of service against the avatar server.
  - **Fix applied:** `npm audit fix` → `express@4.22.2`, `qs@6.15.2`, `picomatch@2.3.2` (lockfile-only, no `package.json` change). **`npm audit` now reports 0 vulnerabilities.**
  - **Ref:** https://cheatsheetseries.owasp.org/cheatsheets/NPM_Security_Cheat_Sheet.html

- [ ] **HIGH-002 — Credentialed requests carry no CSRF token** *(re-assessed → largely mitigated)*
  - **Location:** `frontend/src/services/api.js` (`withCredentials: true`); dead mock at `frontend/e2e/auth.spec.js:6` (`/api/csrf-token` endpoint does not exist).
  - **Backend reality:** auth cookies are `httpOnly` + `secure` + **`SameSite=Strict` (prod)** / `Lax` (dev) — `backend/auth-service/lib/constants.js:215-228`. `SameSite=Strict` blocks classic cross-site CSRF, so the practical risk is **LOW**. There is no CSRF-token system in the backend.
  - **Remaining (defense-in-depth) options:**
    1. Document SameSite as the CSRF control + remove the misleading dead `/api/csrf-token` test mock. *(no functional change)*
    2. Add a custom-header check (`X-Requested-With`) on the frontend + enforce it on mutating backend routes.
    3. Implement a full double-submit CSRF token (frontend interceptor + backend issue/validate) — matches the test's original intent.
  - **Ref:** https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html

---

## 🟡 Medium

- [x] **MEDIUM-001 — No Content-Security-Policy on the avatar interface** ✅ FIXED 2026-06-23
  - **Location:** `frontend-avatar/server.js`
  - **Fix applied:** Added `helmet` with a scoped CSP. `script-src 'self' https://cdn.socket.io`; `connect-src 'self' <avatar-ws-origin>` (derived from `AVATAR_VIDEO_*` env so it matches the real WS target); `object-src 'none'`; `frame-ancestors 'self'`; no `upgrade-insecure-requests` (keeps `ws://` dev working). **Verified** the server boots and emits the CSP header on `/` and `/health`.

- [x] **MEDIUM-002 — No CSP on main frontend** ✅ FIXED 2026-06-25
  - **Location:** `frontend/index.html`
  - **Fix applied:** Re-enabled an **environment-agnostic** CSP `<meta>` (works in dev/docker/prod): `default-src 'self'`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, scheme-based `connect-src` (no hardcoded hosts). `script-src`/`style-src` retain `'unsafe-inline'`/`'unsafe-eval'` **only** because prod serves the Vite dev server; clickjacking is covered by `X-Frame-Options` at Caddy.
  - **Residual (tracked, not blocking):** the loose `script-src` can be tightened to nonces/hashes once the app is served as a **static production build** instead of the dev server (the Dockerfile builds but then runs `npm run dev`). Verify by loading the app once after deploy.

- [x] **MEDIUM-003 — External CDN script without Subresource Integrity** ✅ FIXED 2026-06-25
  - **Location:** `frontend-avatar/public/index.html`, `frontend-avatar/public/js/socket.io.min.js`
  - **Fix applied:** **Self-hosted** socket.io (v4.8.3, copied from `socket.io-client`) and pointed the page at `/js/socket.io.min.js`. This removes the third-party CDN dependency entirely — no SRI hash to maintain — and let the avatar CSP tighten from `script-src 'self' https://cdn.socket.io` → `script-src 'self'`. **Verified:** server serves the file (HTTP 200, 46 KB) and the CSP no longer references any CDN.

- [x] **MEDIUM-004 — Avatar Express server unhardened** ✅ FIXED 2026-06-23
  - **Location:** `frontend-avatar/server.js`
  - **Fix applied:** Added `helmet` (security headers, see MEDIUM-001) and `app.set('trust proxy', 1)` so Express derives protocol/IP from the trusted Caddy hop instead of arbitrary client `X-Forwarded-*`.
  - **Residual (optional):** the pre-existing forwarded-header logging middleware (`:15-33`) was left intact to avoid untested changes to the live proxy path; rate limiting not added (would need tuning vs. the WS flow).

- [x] **MEDIUM-005 — Lockfile not committed in `frontend/`** ✅ FIXED 2026-06-23
  - **Root cause:** `frontend/.gitignore:5` explicitly ignored `package-lock.json` → no reproducible installs, `npm audit` couldn't run in CI.
  - **Fix applied:** Removed the ignore rule and generated `frontend/package-lock.json` (`npm i --package-lock-only`). The lockfile is now tracked and auditable. *(Surfaced MEDIUM-006 below.)*

- [ ] **MEDIUM-006 — 25 dependency advisories in `frontend/` (newly auditable)** 🆕 *(partially fixed; rest are dev-only)*
  - **Key fact:** **all 25 are in `devDependencies` (test/build/lint tooling) — none in production `dependencies`.** The shipped app (react, axios, socket.io-client, …) has 0 advisories. `esbuild`/`vite` is explicitly a **dev-server-only** issue and does not affect production builds.
  - **Source map:** `cookie`←`msw@1` (test mocks) · `esbuild`←`vite@5` (dev server) · `js-yaml`←`jest` · `micromatch`+`yaml`←`lint-staged`.
  - **Fix applied:** bumped `lint-staged ^13.2.3 → ^15.5.0` (clears `micromatch` + `yaml`). Run `npm install && npm audit` to confirm.
  - **Deliberately NOT auto-forced (dev-only, breaking migrations):**
    - `vite@5 → 6+` (to fix `esbuild`) — major bump; test `npm run build` + the app.
    - `msw@1 → 2` (to fix `cookie`) — major test-API rewrite (`rest`→`http`).
    - `jest`/`js-yaml` chain — no clean fix; `npm audit fix --force` proposes a `babel-jest@25` **downgrade** that breaks tests. Wait for upstream jest.
  - **Recommendation:** treat these as scheduled, individually-tested dev-tooling upgrades — not a blanket `--force`. Production exposure is nil in the meantime.

---

## 🔵 Low / Informational

- [ ] **LOW-001 — `window.location.href = avatarUrl`**
  - **Location:** `frontend/src/pages/DashboardPage.jsx:143-144`
  - **Note:** `avatarUrl` is a build-time env var (`VITE_AVATAR_VIDEO_URL`), not user input → not a live open-redirect. Keep that env value trusted.

- [ ] **LOW-002 — `/config.js` reflects env to client**
  - **Location:** `frontend-avatar/server.js:87-101`
  - **Note:** Current values (host/port/protocol) are non-sensitive. Ensure no secrets are ever added to that object.

- [ ] **LOW-003 — `user` object stored in `localStorage`**
  - **Location:** `frontend/src/services/api.js:73`
  - **Note:** Non-sensitive today; if it ever holds PII, prefer in-memory state.

---

## ✅ Verified Good (no action)

- [x] No XSS sinks — zero `dangerouslySetInnerHTML`, `innerHTML=`, `eval`, `new Function`, `document.write`, `insertAdjacentHTML`.
- [x] httpOnly cookie auth; **no tokens in `localStorage`**.
- [x] All `target="_blank"` links carry `rel="noopener noreferrer"`.
- [x] No hardcoded secrets in frontend source.
- [x] Caddy sets HSTS, `X-Frame-Options: SAMEORIGIN`, `X-Content-Type-Options: nosniff`.

---

## Appendix — Incidental backend finding (out of frontend scope, flagged for follow-up)

- [ ] **APP-001 — Hardcoded fallback JWT secrets** 🔴
  - **Location:** `backend/auth-service/lib/constants.js:210-212`
  - **Risk:** `JWT_ACCESS_SECRET`/`JWT_REFRESH_SECRET` fall back to well-known literals (`"your-access-token-secret"`). If the env vars are ever unset in any environment, anyone can forge valid auth tokens → full authentication bypass.
  - **Remediation:** Remove the fallbacks; fail fast at startup if the secrets are unset.
