# Services (`services/<name>/src/bt_<name>/`)

| Service | Port | Key files |
|---|---|---|
| gateway | 3000 | `guard.py` (session, CSRF, rate limits), `routes.py` (catch-all proxy), `compose.py` (`/me`, `/settings`), `proxy.py`, `paths.py` |
| auth | 3001 | `signin.py`, `factors.py`, `passkeys.py`, `sessions.py`, `account.py`, `lifecycle.py`, `throttle.py`, `mailer.py`, `cookies.py` |
| ledger | 3002 | `transactions.py`, `ingest.py`, `classify.py`, `categories.py`, `credits.py`, `balance.py` (Unaccounted), `aggregates.py`, `settings.py` |
| ingest | 3003 | `routes.py` (`/ingest/message`), `devices.py`, `unparsed.py`, `parser/` (pure parser, templates as data) |
| planning | 3004 | `plans.py`, `budgets.py`, `alerts.py`, `evaluate.py`, `jobs.py` |
| recurring | 3005 | `rules.py`, `schedule.py`, `posting.py` |
| reports | 3006 | `dashboard.py`, `trends.py`, `fixed.py`, `common.py` (no database) |
| telegram | 3007 | `webhook.py`, `prompts.py`, `messages.py`, `link.py`, `store.py`, `botapi.py`, `runtime.py` |

Every service: `main.py` -> `run_service(...)`, `routes.py` `register(app, deps)`, domain modules take `deps` and `ctx`, `workers.py` registers consumers/cron, `migrations/` per schema. Each service has its own `Dockerfile`.
