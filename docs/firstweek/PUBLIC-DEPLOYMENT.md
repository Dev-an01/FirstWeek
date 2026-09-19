# Public FirstWeek showcase

## Scope

Anonymous visitors can browse the six published project summaries, architecture and guides, and ask grounded questions. The sixth project, Movie Enquirer, is published as a completed, self-coded learning project. No account is required. Public APIs have no create, edit, upload, membership, company, onboarding-profile or saved-conversation operations. The private workspace remains at `/projects` in the normal local/private build; the Vercel build uses a public-only entry point.

This is a deliberately small M5/M6 slice. The personal-site integration API, embedded widget, publication admin UI and full production acceptance remain deferred. The existing M2 work is preserved, not declared complete.

## Data boundary and publication

`frontend/server/publicCollection.js` is the sole public corpus. It contains separately authored summaries, not copies of the private manifest or runtime data. It imports no private guides, databases, uploads, company records, user profiles or saved conversations. No private credentials are required by this deployment. Review this file before publishing; change/remove a project there and redeploy to update publication. Never automatically synchronize private uploads into it.

The basic Node endpoint performs keyword ranking over the selected project's public sections, then sends numbered passages, the system prompt and at most six short history messages to a generation provider. It does not run the private Python semantic retriever. OpenAI is tried first, then Groq when explicitly enabled, then a free OpenRouter model. A failed provider may therefore receive the question before the next provider is tried. Chat is held in browser memory, not a server database, and resets on leaving Ask or reloading. Visitors are told not to submit private information. Provider processing is subject to each provider's policies; this is not a promise of zero provider retention. Redis stores counters with hashed visitor identifiers, not questions.

Removing content and redeploying prevents new requests to that deployment from retrieving it. It cannot erase material already read, copied, retained in an open browser, or present in an older preview deployment. Delete/protect obsolete deployments separately when withdrawing public content. Treat publication as irreversible disclosure.

## Vercel setup

Import the repository only when publication is approved. Select the `public-showcase` branch and Root Directory **frontend**. Framework: **Vite**. The included `frontend/vercel.json` selects **npm run build:public**, output **dist**, and the Node function at `api/public.js`. Use Node.js 22 or newer. `/showcase/...` deep links rewrite to the SPA; `/api/public` is a function, not an SPA rewrite. No private API proxy is configured.

The public build needs no Postgres, JWT secrets, internal service token, Python service or embedding model. Do not copy the root/private `.env` into Vercel. The previous deployment advice listed the full private stack; this isolated implementation deliberately needs less.

### Server variables

| Variable | Value / purpose |
| --- | --- |
| `FIRSTWEEK_PUBLIC_ORIGIN` | Exact visitor origin, e.g. `https://your-project.vercel.app`, no trailing slash or path. Set the matching preview origin separately when testing previews. |
| `FIRSTWEEK_PUBLIC_GENERATE` | `true` for normal retrieval → LLM answers (also the default when unset). Set explicitly to `false` only for offline source excerpts. |
| `OPENAI_API_KEY` | Server-only primary provider key. Recommended for the normal path. Never expose it through a `VITE_*` variable. |
| `FIRSTWEEK_PUBLIC_OPENAI_MODEL` | Optional OpenAI model override. Default: `gpt-5.6-luna`. |
| `GROQ_API_KEY` | Optional server-only first fallback key. This preserves the existing Groq path. |
| `FIRSTWEEK_PUBLIC_GROQ_FALLBACK` | Exact `true` opts into Groq fallback; `false` or unset skips it. Other values fail configuration closed. |
| `FIRSTWEEK_PUBLIC_GROQ_MODEL` | Optional Groq model override. Default: `openai/gpt-oss-120b`. |
| `OPENROUTER_API_KEY` | Optional server-only final fallback key. Recommended for free fallback after OpenAI or Groq failure. |
| `FIRSTWEEK_PUBLIC_OPENROUTER_MODEL` | Optional OpenRouter model. Default: `openrouter/free`. Only `openrouter/free` or IDs ending in `:free` are accepted. |
| `UPSTASH_REDIS_REST_URL` | HTTPS Redis REST endpoint, required for generated chat limits. |
| `UPSTASH_REDIS_REST_TOKEN` | Redis write-capable REST token; server only. Use a dedicated database for this demo. |
| `FIRSTWEEK_PUBLIC_RATE_SECRET` | Stable random secret of at least 32 characters for hashing visitor addresses. |
| `FIRSTWEEK_PUBLIC_IP_DAILY_LIMIT` | Per-visitor generated-question limit per UTC day. Default `10`; allowed 1–10,000. |
| `FIRSTWEEK_PUBLIC_GLOBAL_DAILY_LIMIT` | Shared generated-question limit per UTC day. Default `30`; allowed 1–10,000. |
| `FIRSTWEEK_PUBLIC_OPENAI_TOTAL_LIMIT` | Persistent maximum OpenAI call reservations for this Redis database. Default `100`; allowed 1–1,000,000. |

Generated chat requires the Redis variables and at least one enabled provider key. For the intended order, set all three provider keys and set `FIRSTWEEK_PUBLIC_GROQ_FALLBACK=true`. `VITE_FIRSTWEEK_PUBLIC_ONLY=true` is supplied by `.env.public` during `build:public`. It is not a security boundary: the deployed function itself has no access to private data. Never put provider, Redis or private-service credentials in `VITE_*` variables.

Do not set `OPENAI_BASE_URL`. The public function uses fixed official endpoints for OpenAI, Groq and OpenRouter. The local `caveman` skill only reduces assistant output tokens; `gw.caveman.so` is not part of this deployment.

Each generated question atomically reserves all three general counters before any provider call: five per visitor per fixed minute, ten per visitor per UTC day, and thirty globally per UTC day by default. Every provider attempt for that question uses the same reservation. Falling back never consumes a second general reservation. Failed model requests still consume the reservation.

Immediately before an OpenAI request, a separate atomic counter reserves one of the default 100 lifetime paid attempts. This key is `fw-public:openai:total` and has no expiry. An OpenAI failure still consumes that reservation. When the cap is exhausted, the request skips OpenAI and tries explicitly enabled Groq, then OpenRouter. Delete that Redis key only when deliberately resetting the paid budget. A missing or failed general limiter fails closed before any provider call. A failed paid-counter reservation skips OpenAI and can use a fallback already covered by the general reservation. The function uses Vercel's client-IP header; unsupported hosts share a local bucket rather than trusting visitor-supplied forwarding headers. IP limits are imperfect on shared networks or with rotating addresses, so the global cap is essential. Every provider output is bounded to 600 completion tokens.

The OpenAI cap limits calls, not exact dollars. At the current `gpt-5.6-luna` Standard price of $0.20 per million input tokens and $1.20 per million output tokens, 100 fully used 600-token outputs cost about $0.072 for output, plus input. Your $4.80 balance still needs an OpenAI dashboard budget/alert because prompts, retries, pricing and model overrides can change the total. Lower `FIRSTWEEK_PUBLIC_OPENAI_TOTAL_LIMIT` if that balance must last. Groq currently lists `openai/gpt-oss-120b` on its free plan, but exact account limits vary. OpenRouter free-model capacity is not guaranteed.

These limits bound model calls, not all infrastructure spending or denial-of-service traffic. Set provider spending alerts/limits and Vercel traffic protections before opening to broad traffic. Origin checks constrain browsers; nonbrowser clients can forge Origin, so they are not authentication or the cost control.

After changing environment settings, redeploy. Open the configured exact origin to avoid the origin-mismatch error. Browsing works without keys; explicitly selected excerpt chat needs only the matching origin. Normal Ask runs retrieval followed by LLM generation and needs Redis plus at least one provider. Missing configuration or failed generation returns an honest error, not a response labeled as AI that merely repeats search excerpts. Successful responses include only safe provider/model names, citations and public evidence; keys and provider error bodies remain server-side.

## Local checks

From `frontend`:

```sh
# Explicit offline preview (no provider call):
FIRSTWEEK_PUBLIC_ORIGIN=http://127.0.0.1:5173 FIRSTWEEK_PUBLIC_GENERATE=false npm run dev -- --mode public
# Open http://127.0.0.1:5173/showcase
npm run test:public
npm run build:public
```

The Vite development and preview middleware serve the same public handler, without starting private services. For real local generation, put the server variables above in the ignored `frontend/.env.local`, or supply them through the launching environment; restart the local server afterward. The middleware loads only `FIRSTWEEK_PUBLIC_*`, the three provider keys and `UPSTASH_REDIS_REST_*`; process settings take precedence. The private root `.env` is not automatically imported. Do not paste secrets into commands saved in shell history. A normal private build still uses `npm run build`.

### Generation verification

The provider-order migration was verified with mocked OpenAI, Groq, OpenRouter and Redis responses. No live provider request or hosted deployment was made. Public Ask cannot be activated until its shared Redis limits and server credentials are configured; do not bypass those limits to enable it.

Gauss accepted the local provider migration and cost controls on 2026-09-17 at 100/100 with no material findings. Independent checks passed all 16 public tests plus syntax/whitespace; primary also passed public and private production builds. Acceptance covers local code and mocked limiter contracts only. It excludes live providers, real Redis Lua/concurrency, Vercel and publication.

## Acceptance before public launch

The provider migration passed 16 public API checks and the public build locally on 2026-09-17. Model and Redis responses were mocked; no browser, private build, hosted service or public-launch acceptance was performed for this change.

- Review every public summary and architecture; confirm the disclosure is intended.
- Deploy a protected preview; verify direct project/architecture URLs and inspectable citations.
- Enable Redis and the intended provider chain in that preview; verify OpenAI success, provider fallback, daily quota exhaustion and paid-cap exhaustion.
- Verify missing/wrong origin, arbitrary project IDs and mutation attempts are denied.
- Verify `/api/users`, `/api/firstweek`, `/internal/firstweek`, and private upload paths are unavailable on this public deployment.
- Configure cost alerts, rotate any exposed keys, and approve publication separately.

Local mocked-provider checks do not establish live OpenAI, Groq, OpenRouter, Upstash or Vercel acceptance. No site is published merely by adding this configuration.

References: [OpenAI API pricing](https://developers.openai.com/api/docs/pricing), [Groq rate limits](https://console.groq.com/docs/rate-limits), [OpenRouter free models](https://openrouter.ai/openrouter/free), [Vercel Vite](https://vercel.com/docs/frameworks/frontend/vite), [Vercel request headers](https://vercel.com/docs/headers/request-headers), [Upstash Redis REST API](https://upstash.com/docs/redis/features/restapi).
