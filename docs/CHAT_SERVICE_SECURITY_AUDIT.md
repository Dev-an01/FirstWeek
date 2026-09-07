# Chat Service — Security & Production Audit Checklist

**Target:** `backend/chat-service/` (~5,600 LOC)
**Stack:** Express 5, Socket.IO 4.8, Prisma 6 / Postgres, JWT, axios → RAG service. Multi-tenant SaaS.
**Audited:** 2026-06-26 · **Method:** manual code trace, every item cites `file:line`.

> Status legend: `[ ]` open · `[~]` in progress · `[x]` fixed (not committed/pushed).
> Severity: **Critical** must block release; **High** block release; **Medium** fix before GA; **Low** hardening.

---

## Critical

- [x] **C1 — Real-streaming `chat:message` skips conversation ownership check (cross-tenant write / IDOR)** — **FIXED (this session, not committed)**
  - Location: `websocket/chatHandlers.js` (real-streaming branch, gated by `ENABLE_REAL_STREAMING`)
  - Threat: An authenticated user emits `chat:message` with another tenant's `conversationId`. The real-streaming branch wrote a user message, generated + persisted an assistant reply, bumped `updateLastMessageAt`, and streamed to the victim's room — **with no ownership check**. The legacy path checks ownership via `messageService.sendMessage` → `conversationRepository.getConversationById({conversationId,userId})` (`messageService.js:93-101`); the new path did not.
  - Re-verified: no `getConversation`/ownership/room-membership check existed anywhere in the handler; `messageRepository.createMessage` filters on `conversationId` only. Confirmed genuine.
  - Fix applied: added `await conversationService.getConversation({ conversationId, userId })` after input validation and before any write — mirrors `chat:join`. Unowned conversations throw `NotFoundError` → returned to client as a failed callback, no write performed.

## High

- [x] **H1 — `/rag/query` & `/rag/chat` reachable unauthenticated (LLM cost abuse + null-tenant RAG)** — **FIXED (this session, not committed)**
  - Location: `routes/chatRoutes.js:127,182`; `controllers/chatController.js:430-539`
  - Threat: With no user, `ragService` forwards `user_id:"anonymous"`, `user_role:"guest"`, `company_id:null` (`ragService.js:113-118,192-201`). Anyone on the network could drive LLM generation and issue null-tenant RAG queries. Routes were labeled "public for testing."
  - Re-verified: both routes used `optionalAuth`; controllers read `req.user?` optionally (never required). Frontend calls them via `chatAxiosInstance` with `withCredentials:true` (`frontend/src/services/api.js:464,528,536`), so authenticated users send the cookie and are unaffected. Confirmed genuine and safe to gate.
  - Fix applied: `optionalAuth` → `authenticateUser` on `/rag/query` and `/rag/chat`. Now `req.user` (incl. real `companyId`) is always populated, so RAG calls are properly tenant-scoped.
  - Out of scope (not part of H1, still open): `/rag/profiles` uses `optionalAuth` (unauth → null company → all profiles) and `/rag/health` has no auth — tighten separately if desired.

- [x] **H2 — No per-event rate limiting on Socket.IO; HTTP limiter does not cover sockets** — **FIXED (this session, not committed)**
  - Location: all handlers in `websocket/chatHandlers.js`; `server.js:128-160` (`generalLimiter` is Express-only)
  - Threat: A single authenticated socket can flood `chat:message` (expensive LLM/RAG path) → unbounded cost / DoS.
  - Re-verified: no `socket.use`/`onAny`/`rateLimit`/`throttle` anywhere in `websocket/`, `services/`, `server.js`; the only `io.use` is connect-time auth. Confirmed genuine.
  - Fix applied: per-socket sliding-window limiter (`checkRateLimit`) held in the handler closure (GC'd on disconnect — no global leak), applied to `chat:message` (default 30 / 60s) and `chat:interrupt` (default 60 / 60s). Limits configurable via `WS_MESSAGE_RATE_MAX`, `WS_MESSAGE_RATE_WINDOW_MS`, `WS_INTERRUPT_RATE_MAX`, `WS_INTERRUPT_RATE_WINDOW_MS`. Exceeding the limit returns a `RATE_LIMIT_EXCEEDED` callback; no work is performed.
  - Scope note: low-cost events (`chat:typing`, `chat:join`, `chat:leave`, `chat:get-online-users`, `chat:stop-streaming`) were intentionally left unthrottled to avoid UX regressions (typing fires rapidly). Add a high-ceiling limit there later if flood-DoS of broadcasts becomes a concern.

- [ ] **H3 — Sensitive data logged unredacted (`sanitizeLogData` exists but is never called)**
  - Location: `shared/utils/logger.js:237-254` (logs full `req.body`/`params`/`query`), `:290-310` (unused redactor); `websocket/auth.js:49-54` (logs full handshake `auth`/`query`/`cookies` — all carry the JWT)
  - Threat: Tokens / PII written to `*-combined.log` in plaintext.
  - Fix: wire `sanitizeLogData` into error + handshake logging; drop the handshake debug dump.

## Medium

- [ ] **M1 — `chat:interrupt` cancels any session by client-supplied `sessionId`, no ownership check**
  - Location: `websocket/chatHandlers.js:536-580` → `ragService.interruptSession` (`ragService.js:669-706`)
- [ ] **M2 — `chat:get-online-users` discloses userId/username of arbitrary conversation rooms**
  - Location: `websocket/chatHandlers.js:587-642`
- [ ] **M3 — Raw Prisma/internal error messages leak to client via `metadata` spread**
  - Location: `shared/utils/errors.js:184-194,224-228`; controllers spread `...(transformed.metadata && {metadata})` (e.g. `chatController.js:104-107`)
- [ ] **M4 — `trust proxy` never set, but service runs behind Caddy → `req.ip` is the proxy for all clients (rate-limit bucket collapses; security logs useless)**
  - Location: `server.js` (no `app.set('trust proxy')`); `Caddyfile` present — *verify deploy topology before changing.*
- [ ] **M5 — Hardcoded fallback DB credentials in source**
  - Location: `repositories/userDbClient.js:11-13` (`postgres:postgres123@avatar-user-db`)
- [ ] **M6 — No content-length cap on `chat:message` real-streaming path (REST/legacy cap at 10k)**
  - Location: `websocket/chatHandlers.js:158-166` vs `services/messageService.js:83-91`
- [ ] **M7 — Streaming `fetch` to RAG has no timeout/AbortController (axios path has 60s) → hung-socket resource leak**
  - Location: `services/ragService.js:510-517`

## Low / Hardening

- [ ] **L1 — Swagger UI + spec served unconditionally (all environments)** — `server.js:163-180`
- [ ] **L2 — JWT verified without `algorithms`/`issuer`/`audience` pinning; no startup check that `JWT_ACCESS_SECRET` is set** — `middleware/authMiddleware.js:65`; `websocket/auth.js:72,128`
- [ ] **L3 — `onLimitReached` is a no-op in express-rate-limit v7 → rate-limit security logging never fires** — `server.js:145-152`
- [ ] **L4 — Auth token accepted via query string (logged/cached by proxies)** — `websocket/auth.js:21-23`
- [ ] **L5 — Spoofable `chat:typing` / `chat:stop-streaming` broadcasts to arbitrary rooms (no membership check)** — `websocket/chatHandlers.js:474-498,505-529`

## Informational

- [ ] **I1 — Message content stored/returned without sanitization — stored-XSS risk depends on frontend rendering** — `repositories/messageRepository.js:24-48` (verify frontend does not render as raw HTML)

---

## Verified safe (checked, correctly implemented)

- [x] REST conversation/message/preferences access consistently scoped by `userId` at the Prisma layer (`conversationRepository.js:106-110,164-168,203-208`; `messageService.js:93-101,398-406`).
- [x] No raw SQL / `$queryRaw` interpolation — all DB access via Prisma query builder (no SQL injection).
- [x] Preferences updates are field-whitelisted (`preferencesService.js:119-183`) — no mass assignment.
- [x] JWT failures fail closed (invalid/missing → 401; `authMiddleware.js:58-69`); `alg:none` rejected by jsonwebtoken v9 defaults.
- [x] Helmet, CORS allowlist with logging, compression, graceful shutdown, non-root Docker user (`Dockerfile:35-39`), multi-stage build with `npm prune --production`.
- [x] RAG base URL is env-fixed, not user-controlled → no classic SSRF via URL.

## Follow-ups owed

- [ ] Run `npm audit` for Express 5 / socket.io / axios CVEs (needs network).
- [ ] Verify frontend message rendering for I1.

---

## Change log (this session)

- **C1 fixed** — ownership check added to `chat:message` before any write (`websocket/chatHandlers.js`).
- **H2 fixed** — per-socket rate limiter added for `chat:message` and `chat:interrupt` (`websocket/chatHandlers.js`).
- **H1 fixed** — `optionalAuth` → `authenticateUser` on `/rag/query` and `/rag/chat` (`routes/chatRoutes.js`).
- Each issue re-verified against source before editing (no assumptions); `node --check` passed on every modified file.
- Changed: `backend/chat-service/websocket/chatHandlers.js`, `backend/chat-service/routes/chatRoutes.js` (plus this doc). **No commits or pushes made.**
