# MoneyPlant

Telegram-first finance tracking with a private dashboard.

## About
MoneyPlant is a personal finance and investment tracker whose primary capture interface is a Telegram bot. Its README describes turning short messages into categorized transactions, leaving a five-minute correction window, and presenting spending and investment information in a private web dashboard.

## Technology stack

TypeScript, Next.js, PostgreSQL, Drizzle, grammY.

## Architecture
The Bun workspace separates `apps/web`, `apps/bot`, and shared packages. The web application uses Next.js and Auth.js. The bot uses grammY. PostgreSQL and Drizzle form the documented persistence layer. Shared TypeScript packages hold database access, types and core behavior.

## Transaction flow
A person sends a message containing an expense or investment. The documented design parses amounts deterministically, applies keyword categorization first, and uses a Claude fallback for ambiguous categorization with the amount masked. Pending entries may be edited or cancelled before committing. Dashboard views include transactions, spending, monthly insights, portfolio, pending items and settings.

## Where to start
Read the root README for the user flow, then `packages/core` for business logic, `packages/db` for persistence, `apps/bot` for message handling and `apps/web` for dashboard routes. The manifest establishes the workspace package boundaries.

## Current limitations
The README positions Phase 1 as self-hosted and single-user. Do not describe the checkout as a verified multi-tenant commercial service. Financial calculations, external valuation feeds, account linking and production deployment have not been tested for this corpus. No personal transactions or database contents were inspected or indexed.

## Ownership
No current team or responsibility map was supplied. Repository presence is not proof of exclusive authorship.

## Architecture flow
The documented transaction flow. Ambiguous categorization can use Claude; this diagram does not imply the project is currently deployed.

- Telegram message → Telegram bot: message.
- Telegram bot → Core logic: parse.
- Core logic → Claude fallback: when ambiguous.
- Core logic → Shared database: after correction window.
- Shared database → Private dashboard: read transactions.

## Evidence
- `MoneyPlant/README.md`
- `MoneyPlant/package.json`
- `MoneyPlant/packages/core/package.json`
- `MoneyPlant/apps/web/package.json`
- `MoneyPlant/apps/bot/package.json`
