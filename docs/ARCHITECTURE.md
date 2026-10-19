# Architecture: modular microservices

This is how the README's design is built. The README says *what* the product does; this file says *where the code lives*.
Where this file and README section 7/8/16 differ, this file wins (the differences are listed at the end).

## Services

| Service | Port | Database schema | Owns | Calls |
|---|---|---|---|---|
| **gateway** | 3000 | none | the only door: cookie session check, CSRF, rate limits, security headers, proxy by path (`ROUTE_TABLE`), `GET /me`, `GET\|PATCH /settings` | every service |
| **auth** | 3001 | `auth` | users, sessions, auth factors (TOTP, passkeys, recovery codes), audit log, export, account deletion | – |
| **ledger** | 3002 | `ledger` | transactions, categories, tag rules, classification, balance checks / Unaccounted, credits, ledger settings, spend aggregates | planning (credit → plan total) |
| **ingest** | 3003 | `ingest` | devices (ingest tokens), ingest events (nonces), the bank-message parser, unparsed messages | ledger, auth |
| **planning** | 3004 | `planning` | monthly plans, budgets (limits), alerts, planning settings | ledger |
| **recurring** | 3005 | `recurring` | recurring rules and the posting cron | ledger |
| **reports** | 3006 | none | dashboard, daily, months, category matrix: read models composed from other services, nothing stored | ledger, planning, recurring, ingest |
| **telegram** | 3007 | `telegram` | links, pairings, bot sessions, prompts, bot token (encrypted), webhook handling, digest | ledger, auth |
| **web** | 3000 (container) | – | Next.js app, 16 screens from `docs/ui-spec/` | gateway only |

Every backend service is Python 3.12 + FastAPI (async, pydantic, psycopg). The web app is the only TypeScript left.

Shared backend code is one installable library, `packages/bt` (import `bt.*`), and is the only thing services have in common:

| Module | What it gives every service |
|---|---|
| `bt.common` | money (paise ints, `format_inr`), time-zone/month helpers, derived metrics (`pace_projection`, `limit_status`, `safe_per_day` …), tag normalisation, cursors, password policy, `AppError`, env loading, redacting JSON logger, `Ctx` |
| `bt.crypto` | Argon2id, AES-256-GCM `FieldCipher`, TOTP, token hashing, recovery codes, JWT (access + internal service tokens) |
| `bt.contracts` | pydantic models for every cross-service request/response, every event/job payload, the route table |
| `bt.db` | pool + type adapters, `Tx` (`$n` placeholders kept as written), `deps.as_user` (RLS) / `as_system`, migration runner, bootstrap (roles, schemas, `bt.enable_rls`), `Where`, `camel`, test database |
| `bt.queue` | `MessageBus` protocol; `Messaging` (transactional outbox → Postgres `SKIP LOCKED` queue with retries and cron); `InMemoryBus` for tests |
| `bt.clients` | one typed client per service (`deps.clients.ledger.tag(...)`), signing, timeouts, retries, error mapping |
| `bt.kit` | `run_service` (boot), `create_app`, request dependencies (`user_ctx`, `service_claims`), `MemoryRateLimiter`, test fixtures, a software WebAuthn authenticator |

Logo, name and icons are in `apps/web/src/brand` (import from `@/brand`; SVG files in `apps/web/public/brand`). The web app keeps its own browser-side copy of what it needs: `apps/web/src/common` (money formatting, month maths, tag and password rules, so what a page promises is what the server enforces) and `apps/web/src/contracts` (the response types). They mirror `bt.common` / `bt.contracts`; the Python models are the source of truth and `scripts/e2e.py` keeps the two honest.

## Rules of the road

1. **A service owns its data.** One Postgres instance, one schema and one login role per service (`svc_ledger` owns schema `ledger`). A service never reads another service's tables; it calls its API. Joins across services happen in code (usually `reports`).
2. **Every user table has RLS.** Migration ends with `SELECT bt.enable_rls('table')`; queries run in `async with deps.as_user(ctx) as tx:` (sets `app.user_id`). Scheduler scans use `deps.as_system()`.
3. **Writes that cause work use the outbox.** `await deps.bus.emit(tx, event, payload)` / `await deps.bus.enqueue(tx, job, payload)` inside the same transaction as the change. Delivery is at-least-once: consumers must be idempotent.
4. **Events, not polling.** Budget evaluation is triggered by `transaction.changed`, never a timer. Catalogue in `packages/bt/src/bt/contracts/events.py`.
5. **Auth between services.** Every request carries `x-internal-token` (60-second HS256 JWT: calling service, user id, time zone). `/internal/*` routes refuse requests the gateway forwarded from outside. Services are not published on the host; only the proxy is.
6. **Money is integer paise.** Never floats. Format only at the edge (`format_inr`). Month boundaries and "today" use the user's time zone (`month_range`, `month_progress`).
7. **Derive, don't duplicate.** Balance, per-category spend, pace, trends are computed on read. No cached totals. The metric functions live in `bt.common` and are used by every service.
8. **No sensitive data in logs.** Ids and outcome codes only (the logger also redacts common fields).
9. **Reuse before writing.** If two services need the same logic it belongs in `packages/bt` (see table above), not copied. If you find yourself writing the same ten lines a third time, extract them.

## Request paths

```
Browser ──/api/*──► proxy ──► gateway ──(cookie → JWT → session check)──► service
Telegram ──/telegram/webhook/<secret>──► proxy ──► gateway ──► telegram ──► ledger (save tagged payment, tag) ──(outbox)──► transaction.changed
Telegram button ──/pay──► proxy ──► web (hands the phone to Google Pay)
Optional sender ──/ingest/message──► proxy ──► gateway ──► ingest ──► ledger
```

## Internal API (service → service)

Typed in `bt.clients`; payloads in `bt.contracts`. Paths are the contract.

| Caller → Callee | Endpoint | Purpose |
|---|---|---|
| ingest → ledger | `POST /internal/transactions/ingest` | save a parsed message (dedupe, classify, link, merge, reverse) |
| ingest → ledger | `POST /internal/transactions/manual` | resolve a "Needs a look" message into a transaction |
| telegram → ledger | `POST /internal/transactions/manual` | `/350 food` or `+1500 salary`: save a payment, with the tag when one is given |
| recurring → ledger | `POST /internal/transactions/recurring` | post a due rule or link a captured debit |
| telegram → ledger | `GET /internal/transactions/:id`, `POST /internal/transactions/:id/tag`, `GET /internal/transactions/pending`, `GET /internal/categories`, `POST /internal/categories/resolve` | Reveal, tag, held prompts, buttons |
| planning/reports → ledger | `GET /internal/spend/by-category`, `/internal/aggregates/{summary,months,category-months,daily}` | spend, balance, trends |
| planning → ledger | `POST /internal/categories/resolve` | a limit or plan line created from a new tag |
| ledger → planning | `POST /internal/plans/:month/credit` | add a hand-added credit to the plan total (idempotent per transaction) |
| ingest/telegram → auth | `POST /internal/totp/verify` | a fresh authenticator code (once per time step) |
| gateway → auth | `POST /internal/sessions/check` (`sid`, `ip`) | is this browser session alive, and is the caller's address allowed |
| auth → ledger, planning, recurring, ingest, telegram | `GET /internal/export` | each service's rows for the user (no secrets); auth composes the data export |
| gateway → ledger/planning/telegram | `GET\|PATCH /internal/settings` | composed `GET\|PATCH /settings` |
| gateway/reports → * | `GET /me`-style reads: `auth /internal/me`, `ingest /internal/unparsed/count`, `planning /alerts`, `recurring /recurring`, `planning /budgets`, `planning /plans/:month` | composition |

## Events and jobs (`bt.contracts` → `EVENTS`, `JOBS`)

| Name | From → To | Meaning |
|---|---|---|
| `transaction.changed` (event) | ledger → planning, telegram | insert / update / tag / delete; carries affected category ids |
| `credit.added` (event) | ledger → planning | hand-added credit with "add to plan" |
| `alert.created` (event) | planning → telegram | a limit crossed its level (once per budget, period, level) |
| `unparsed.created` (event) | ingest → telegram | a message could not be read |
| `account.deleted` (event) | auth → all data services | purge the user's rows |
| `audit.record` (event) | any → auth | append to the audit log |
| `budget.evaluate` (job) | planning → planning | recompute one budget, insert alert once |
| `balance.reconcile` (job) | ledger → ledger | gap check, grace period, book/merge Unaccounted |
| `recurring.post` (job, cron) | recurring | post due rules |
| `telegram.send`, `telegram.sync_prompt`, `telegram.digest` (jobs) | telegram | messages out |
| `retention.sweep.<service>` (job, nightly) | each service | expire its own old rows |

## Docker

- `docker/base.Dockerfile` is the **common image** (`budget-base`): Python 3.12 slim, `uv`, the locked dependencies (`uv.lock`) and the shared library `bt`. It also runs the one-shot `db-init` job (`python -m bt.db.init`).
- Each `services/<name>/Dockerfile` is the **service image**, so it can be built and pushed on its own: `ARG BASE_IMAGE=budget-base`, `FROM ${BASE_IMAGE}`, adds that service's source, installs only its own dependencies, runs as a non-root user with a health check (`python -m bt_<name>.main`). Push `budget-base` first, then each service; point a service at a registry copy of the base with `--build-arg BASE_IMAGE=<registry>/budget-base:<tag>`.
- `apps/web/Dockerfile` is self-contained (Node 24, Next.js standalone build, build context `apps/web`); it does not use the base image.
- `docker-compose.yml` is the only compose file and wires everything: `db` → `db-init` → services → `gateway` → `proxy`, plus `web`. `docker compose up --build` starts it all. Published to the host: `proxy` (`PUBLIC_PORT`, default 8088) and the gateway on `127.0.0.1` only (`GATEWAY_PORT`, default 3010, where `scripts/e2e.py` talks to it). Image names are `${REGISTRY}budget-<name>:${IMAGE_TAG}`, so `REGISTRY=... docker compose build && docker compose push` publishes every image.
- The `test` profile adds `test-db`, a throwaway Postgres on `127.0.0.1:5544` for the backend tests (`docker compose --profile test up -d test-db`).

## Where this differs from the README

| README | Built as | Why |
|---|---|---|
| One deployable API, many modules (7.3, 8) | Eight services plus web | the requested modular microservice architecture |
| One shared `user_settings` table | Each field lives with the service that uses it; the gateway composes `/settings` | data ownership |
| Worker container (7.3, 16) | Each service runs its own consumers and cron | no cross-service worker to deploy; same queue (the `queue` schema in Postgres, `bt.queue`) |
| Telegram bot token in a secret manager | Encrypted in the telegram schema (AES-256-GCM, `FIELD_KEY`); `FIELD_KEY` comes from the environment / secret store | the Setup guide has the user save the bot token in the app |
