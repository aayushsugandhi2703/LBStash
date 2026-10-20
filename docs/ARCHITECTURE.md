# Architecture: modular microservices

The README says *what* the product does; this file says *where the code lives*. Where they differ, this file wins (listed at the end).

## Services

| Service | Port | Database schema | Owns | Calls |
|---|---|---|---|---|
| **gateway** | 3000 | none | the only door: cookie session check, CSRF, rate limits, security headers, proxy by path (`ROUTE_TABLE`), `GET /me`, `GET\|PATCH /settings` | every service |
| **auth** | 3001 | `auth` | users, sessions, auth factors (TOTP, passkeys, recovery codes), audit log, export, account deletion | – |
| **transactions** | 3002 | `transactions` | transactions, categories, tag rules, classification, balance checks / Unaccounted, credits, transactions settings, spend aggregates | planning (credit → plan total) |
| **ingest** | 3003 | `ingest` | devices (ingest tokens), ingest events (nonces), the bank-message parser, unparsed messages | transactions, auth |
| **planning** | 3004 | `planning` | monthly plans, budgets (limits), alerts, planning settings | transactions |
| **recurring** | 3005 | `recurring` | recurring rules and the posting cron | transactions |
| **reports** | 3006 | none | dashboard, daily, months, category matrix: read models composed from other services, nothing stored | transactions, planning, recurring, ingest |
| **telegram** | 3007 | `telegram` | links, pairings, bot sessions, prompts, bot token (encrypted), webhook handling, digest | transactions, auth |
| **web** | 3000 (container) | – | Next.js app, 16 screens from `docs/ui-spec/` | gateway only |

Every backend service is Python 3.12 + FastAPI. The web app is the only TypeScript. Services share one library, `backend/packages/lbstash` (import `lbstash.*`), and nothing else:

| Module | What it gives every service |
|---|---|
| `lbstash.common` | money (paise ints, `format_inr`), time-zone/month helpers, derived metrics (`pace_projection`, `limit_status`, `safe_per_day` …), tag normalisation, cursors, password policy, `AppError`, env loading, redacting JSON logger, `Ctx` |
| `lbstash.crypto` | Argon2id, AES-256-GCM `FieldCipher`, TOTP, token hashing, recovery codes, JWT (access + internal service tokens) |
| `lbstash.contracts` | pydantic models for every cross-service request/response, every event/job payload, the route table |
| `lbstash.db` | pool + type adapters, `Tx` (`$n` placeholders kept as written), `deps.as_user` (RLS) / `as_system`, migration runner, bootstrap (roles, schemas, `lbstash.enable_rls`), `Where`, `camel`, test database |
| `lbstash.queue` | `MessageBus` protocol; `Messaging` (transactional outbox → Postgres `SKIP LOCKED` queue with retries and cron); `InMemoryBus` for tests |
| `lbstash.clients` | one typed client per service (`deps.clients.transactions.tag(...)`), signing, timeouts, retries, error mapping |
| `lbstash.kit` | `run_service` (boot), `create_app`, request dependencies (`user_ctx`, `service_claims`), `MemoryRateLimiter`, test fixtures, a software WebAuthn authenticator |

Web code: logo, name and icons in `frontend/src/brand` (import from `@/brand`; SVGs in `frontend/public/brand`). The web app keeps browser-side copies in `src/common` (money, month maths, tag and password rules, so pages promise what the server enforces) and `src/contracts` (response types). The Python models are the source of truth; `infra/scripts/e2e.py` keeps the two honest.

## Rules of the road

1. **A service owns its data.** One Postgres, one schema and one login role per service (`svc_transactions` owns `transactions`). Never read another service's tables; call its API. Cross-service joins happen in code (usually `reports`).
2. **Every user table has RLS.** Migration ends with `SELECT lbstash.enable_rls('table')`; queries run in `async with deps.as_user(ctx) as tx:` (sets `app.user_id`). Scheduler scans use `deps.as_system()`.
3. **Writes that cause work use the outbox.** `deps.bus.emit(tx, event, payload)` or `enqueue(tx, job, payload)` in the same transaction as the change. Delivery can repeat: consumers must be idempotent.
4. **Events, not polling.** Budget evaluation is triggered by `transaction.changed`, never a timer. Catalogue in `backend/packages/lbstash/src/lbstash/contracts/events.py`.
5. **Auth between services.** Every request carries `x-internal-token` (60-second JWT: service, user id, time zone). `/internal/*` refuses requests forwarded from outside. Only nginx is published on the host.
6. **Money is integer paise.** Never floats. Format only at the edge (`format_inr`). Month boundaries and "today" use the user's time zone (`month_range`, `month_progress`).
7. **Derive, don't duplicate.** Balance, spend, pace and trends are computed on read, with no cached totals. The metric functions live in `lbstash.common`.
8. **No sensitive data in logs.** Ids and outcome codes only (the logger also redacts common fields).
9. **Reuse before writing.** Logic two services need goes in `backend/packages/lbstash`, not copied.

## Request paths

```
Browser ──/api/*──► nginx ──► gateway ──(cookie → JWT → session check)──► service
Telegram ──/telegram/webhook/<secret>──► nginx ──► gateway ──► telegram ──► transactions (save tagged payment, tag) ──(outbox)──► transaction.changed
Telegram button ──/pay──► nginx ──► web (hands the phone to Google Pay)
Optional sender ──/ingest/message──► nginx ──► gateway ──► ingest ──► transactions
```

## Internal API (service → service)

Typed in `lbstash.clients`; payloads in `lbstash.contracts`. Paths are the contract.

| Caller → Callee | Endpoint | Purpose |
|---|---|---|
| ingest → transactions | `POST /internal/transactions/ingest` | save a parsed message (dedupe, classify, link, merge, reverse) |
| ingest → transactions | `POST /internal/transactions/manual` | resolve a "Needs a look" message into a transaction |
| telegram → transactions | `POST /internal/transactions/manual` | `/350 food` or `+1500 salary`: save a payment, with the tag when one is given |
| recurring → transactions | `POST /internal/transactions/recurring` | post a due rule or link a captured debit |
| telegram → transactions | `GET /internal/transactions/:id`, `POST /internal/transactions/:id/tag`, `GET /internal/transactions/pending`, `GET /internal/categories`, `POST /internal/categories/resolve` | Reveal, tag, held prompts, buttons |
| planning/reports → transactions | `GET /internal/spend/by-category`, `/internal/aggregates/{summary,months,category-months,daily}` | spend, balance, trends |
| planning → transactions | `POST /internal/categories/resolve` | a limit or plan line created from a new tag |
| transactions → planning | `POST /internal/plans/:month/credit` | add a hand-added credit to the plan total (idempotent per transaction) |
| ingest/telegram → auth | `POST /internal/totp/verify` | a fresh authenticator code (once per time step) |
| gateway → auth | `POST /internal/sessions/check` (`sid`, `ip`) | is this browser session alive, and is the caller's address allowed |
| auth → transactions, planning, recurring, ingest, telegram | `GET /internal/export` | each service's rows for the user (no secrets); auth composes the data export |
| gateway → transactions/planning/telegram | `GET\|PATCH /internal/settings` | composed `GET\|PATCH /settings` |
| gateway/reports → * | `GET /me`-style reads: `auth /internal/me`, `ingest /internal/unparsed/count`, `planning /alerts`, `recurring /recurring`, `planning /budgets`, `planning /plans/:month` | composition |

## Events and jobs (`lbstash.contracts` → `EVENTS`, `JOBS`)

| Name | From → To | Meaning |
|---|---|---|
| `transaction.changed` (event) | transactions → planning, telegram | insert / update / tag / delete; carries affected category ids |
| `credit.added` (event) | transactions → planning | hand-added credit with "add to plan" |
| `alert.created` (event) | planning → telegram | a limit crossed its level (once per budget, period, level) |
| `unparsed.created` (event) | ingest → telegram | a message could not be read |
| `account.deleted` (event) | auth → all data services | purge the user's rows |
| `audit.record` (event) | any → auth | append to the audit log |
| `budget.evaluate` (job) | planning → planning | recompute one budget, insert alert once |
| `balance.reconcile` (job) | transactions → transactions | gap check, grace period, book/merge Unaccounted |
| `recurring.post` (job, cron) | recurring | post due rules |
| `telegram.send`, `telegram.sync_prompt`, `telegram.digest` (jobs) | telegram | messages out |
| `retention.sweep.<service>` (job, nightly) | each service | expire its own old rows |

## Docker

- `infra/docker/base.Dockerfile` is the common image (`lbstash-base`, two stages): a builder installs every backend dependency from `uv.lock` into one venv; the final image is Python 3.12 slim plus that venv and `lbstash`. No `uv` at runtime. It also runs the one-shot `db-init` job (`python -m lbstash.db.init`).
- Each `backend/services/<name>/Dockerfile` builds on it (`ARG BASE_IMAGE=lbstash-base`), copies that service's source, sets `PYTHONPATH` and runs as a non-root user with a health check (`python -m lbstash_<name>.main`). No per-service install, so all services share the same layers on disk. Push `lbstash-base` first; use `--build-arg BASE_IMAGE=<registry>/lbstash-base:<tag>` for a registry copy.
- `frontend/Dockerfile` is self-contained (Node 24, Next.js standalone build, context `frontend`).
- `docker-compose.yml` is the only compose file: `db` → `db-init` → services → `gateway` → `nginx`, plus `web`. `docker compose up --build` starts it all. On the host: `nginx` (80 and 443, plus plain http on `PUBLIC_PORT`, default 8088) and the gateway on `127.0.0.1` only (`GATEWAY_PORT`, default 3010, used by `infra/scripts/e2e.py`). Images are `${REGISTRY}lbstash-<name>:${IMAGE_TAG}`, so `docker compose build && docker compose push` publishes them all.
- The `test` profile adds `test-db`: throwaway Postgres on `127.0.0.1:5544` (`docker compose --profile test up -d test-db`).

## Where this differs from the README

| README | Built as | Why |
|---|---|---|
| One deployable API, many modules (7.3, 8) | Eight services plus web | the requested modular microservice architecture |
| One shared `user_settings` table | Each field lives with the service that uses it; the gateway composes `/settings` | data ownership |
| Worker container (7.3, 16) | Each service runs its own consumers and cron | no cross-service worker to deploy; same queue (the `queue` schema in Postgres, `lbstash.queue`) |
| Telegram bot token in a secret manager | Encrypted in the telegram schema (AES-256-GCM, `FIELD_KEY`); `FIELD_KEY` comes from the environment / secret store | the Setup guide has the user save the bot token in the app |
