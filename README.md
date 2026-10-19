# Budget Tracker

A private budget tracker run from a Telegram chat. Send `/350 food` when you spend, `+1500 salary` when money comes in, and it is saved, tagged and shown in the web app. Amounts are in INR (₹).

## About and how it works

You decide how much to plan each month and split it across categories. The app does the rest:

1. **Log.** Send the bot `/350` for money out or `+1500` for money in. Add a tag to file it at once (`/350 food`); without one the bot replies with category buttons. Money out also gets an **Open Google Pay** button, so you can pay whoever you need there. (iPhone apps cannot read SMS, so you log each payment yourself.)
2. **Save.** The server records the amount, direction and time. Your typed message is deleted from the chat.
3. **Tag.** Untagged payments arrive in Telegram with category buttons. Known payees are tagged automatically; tag once and the payee is remembered.
4. **Track.** Balance, limits, alerts, trends and recurring payments are worked out from your tagged payments.

Where a payment can come from:

| Source | Used for |
|---|---|
| Telegram bot | Logging payments (`/350 food`, `+1500 salary`) and tagging them (main route) |
| Web app | Everything, plus hand-added credits |
| Bank-message token (optional) | Another tool that posts bank SMS text to `/ingest/message` |

A payment you forget to log is caught by the balance check, which books the gap as "Unaccounted" for you to tag.

### Web app pages

Now · Ledger · Plan · Limits · Repeats · Trends · Add credit · Needs a look · Account (profile, security, devices) · Setup guide

## Architecture

**Stack:** Python 3.12 + FastAPI services, PostgreSQL 17, a Next.js web app, Caddy as the public proxy, all run by Docker Compose. Each service owns its own database schema and never reads another service's tables.

```mermaid
flowchart LR
  Browser --> Proxy
  Sender["Optional bank-message sender"] -.-> Proxy
  Telegram --> Proxy
  Proxy -->|"/"| Web["web (Next.js)"]
  Proxy -->|"/api, /ingest, /telegram/webhook"| Gateway
  Gateway --> Auth
  Gateway --> Ingest
  Gateway --> Ledger
  Gateway --> Planning
  Gateway --> Recurring
  Gateway --> Reports
  Gateway --> Tg["telegram service"]
  Ingest -->|save parsed payment| Ledger
  Ledger -.->|events via outbox| Q[("Job queue<br/>in Postgres")]
  Q -.-> Planning
  Q -.-> Tg
  Recurring -->|post due payments| Ledger
  Auth & Ingest & Ledger & Planning & Recurring & Tg --> DB[("PostgreSQL<br/>one schema + login role per service")]
```

| Service | Job |
|---|---|
| proxy (Caddy) | The only public entry. Routes `/` to the web app and `/api`, `/ingest`, `/telegram/webhook` to the gateway |
| gateway | The only door to the backend: checks login, CSRF and rate limits, adds security headers, forwards by path |
| auth | Users, sessions, 2FA, passkeys, recovery codes, optional allowed addresses, audit log, data export, account deletion |
| ingest | Optional bank-message route: device tokens, the OTP guard and the message reader |
| ledger | Transactions, categories, tag rules, credits, balance checks |
| planning | Monthly plans, limits, alerts |
| recurring | Repeating payments and the cron that posts them |
| reports | Dashboard and trend views, built on read from other services (stores nothing) |
| telegram | The bot, `/350` and `+1500` logging, tagging prompts, the Google Pay button, daily digest, the encrypted bot token, who may link (one Telegram account) |

### How services work together

- **Calls:** services talk over typed HTTP clients. Reads may retry; writes are never blindly retried.
- **Events and jobs:** a change and its event are saved in the same database transaction (outbox pattern). A relay moves them into a Postgres queue (`SKIP LOCKED`). Failed jobs retry with backoff (2 s up to 10 min, 5 tries) before being marked failed. Delivery is at-least-once, so every consumer is idempotent.
- **Cron:** nightly cleanup per service, recurring-payment posting, balance checks and the Telegram digest run from the same queue. Only one replica fires each tick.
- **Events used:** `transaction.changed` (planning re-checks limits, Telegram updates prompts), `credit.added`, `alert.created`, `unparsed.created`, `account.deleted` (every service purges that user), `audit.record`.
- **Derived, not stored:** balance, spend per category, pace and trends are calculated when read, so there are no cached totals to drift out of date.
- **Money:** whole paise as integers, never floats. Months and "today" use your time zone.
- **Shared code:** `packages/bt` holds what every service needs (money, crypto, contracts, DB access, queue, HTTP clients). Details: [ARCHITECTURE](docs/ARCHITECTURE.md). Colours: [COLOURS](docs/COLOURS.md). Logo, icons and the name live in `apps/web/src/brand` (SVG files in `apps/web/public/brand`).
- **Deploy:** one Docker image per service on a shared base image. A one-shot `db-init` job creates roles and schemas, then services start, then the gateway, then the proxy.

### What happens to one logged payment

```mermaid
sequenceDiagram
  participant You
  participant Telegram
  participant Bot as telegram service
  participant Ledger
  participant Q as Queue
  participant Planning
  You->>Telegram: "/350 food"
  Telegram->>Bot: webhook (secret header, your id, signed-in session)
  Bot->>Ledger: save manual transaction with tag "food"
  Ledger->>Q: transaction.changed (same DB transaction)
  Bot->>Telegram: delete your message, reply "Money out · ₹350 · Food ✓" + Open Google Pay
  Q->>Planning: re-check limits, raise alert once if crossed
  Note over You,Telegram: With no tag ("/350") the bot sends category buttons and tagging is one tap
  You->>Telegram: tap Open Google Pay
  Telegram->>You: opens the /pay page, which opens Google Pay
```

## System design

Built for one person's money data, so correctness and privacy come before scale: one Postgres database, small services that own their data, safe retries, and a balance check that catches anything lost. Details: [SYSTEM_DESIGN](docs/SYSTEM_DESIGN.md).

## Security

| Area | What we do |
|---|---|
| **Sign-in** | • 12+ character password, common ones rejected<br>• Hashed with Argon2id<br>• Authenticator app is mandatory<br>• Passkeys and 10 recovery codes (hashed) |
| **Sessions** | • Access token lasts 15 min, refresh token rotates<br>• A reused refresh token means it was copied, so the session is revoked<br>• Ends after 12 h idle or 30 days |
| **Allowed addresses (optional)** | • Account > Security: list the IPs or ranges that may use the web app<br>• Sign-in, token refresh and every page refuse other addresses<br>• Needs a fresh authenticator code; a list without your own address is refused<br>• Does not apply to the Telegram bot (Telegram never reveals your address; the bot is locked to your Telegram account instead) |
| **Cookies and CSRF** | • `HttpOnly`, `Secure`, `SameSite=Strict`<br>• CSRF token on every change |
| **Brute force** | • 5 wrong passwords lock 30 s, doubling to 15 min<br>• Per-IP rate limits on login, reset, phone and webhook<br>• Generic errors, so emails cannot be guessed |
| **Idempotency (safe to repeat)** | • Each Telegram update is processed once, even if Telegram retries<br>• Optional bank-message route: one-time `nonce`, 5-min window, unique dedupe key<br>• Queue jobs can run twice with the same result: alerts fire once, credits count once<br>• Telegram taps and sign-in codes work once |
| **Encryption** | • AES-256-GCM for 2FA secrets, bot token, unreadable messages<br>• Tokens stored only as hashes<br>• Key comes from the environment |
| **Data isolation** | • One Postgres login and schema per service<br>• Row-level security on every user table |
| **Between services** | • Not exposed to the internet<br>• Signed 60-second token on every call<br>• Internal routes refuse outside requests |
| **Edge** | • HSTS, `nosniff`, `no-referrer`, strict CSP, Permissions-Policy<br>• Strict input validation, parameterised queries<br>• Constant-time secret checks |
| **Bank-message token (optional)** | • Per-device token: ingest-only, shown once, revocable<br>• OTP-like text dropped unread (`202`), nothing stored<br>• Parsed messages are not kept |
| **Telegram** | • Setup asks for your Telegram username or id first; only that account can link, anyone else sending a valid code is ignored<br>• After linking, only your Telegram id, private chat<br>• `/signin` with an authenticator code before any `/350` is accepted<br>• Your typed message is deleted; its confirmation repeats the amount you typed<br>• Bank-message prompts carry no amount, payee or balance unless you tap Reveal<br>• Webhook secret header, stored hashed |
| **Never collected** | • Bank logins, UPI PINs, card numbers, OTPs<br>• The app never moves money |
| **Logs and audit** | • Logs hold ids and outcome codes only<br>• Append-only audit log |
| **Your data** | • Export any time<br>• Delete account (7-day grace)<br>• Old rows cleaned nightly |

## Run it

You need Docker.

```bash
python3 scripts/gen-secrets.py   # once: writes .env with random secrets
docker compose up --build        # db, services, gateway, web and proxy
```

Open http://localhost:8088 and create your account. Back up `FIELD_KEY` from `.env`; encrypted data cannot be read without it. Registration allows one account unless you set `REGISTRATION=open`.

Then follow the in-app **Setup guide** (Account menu): create your bot in @BotFather, paste its token, enter your Telegram username, and send the code to your bot (or tap the link under the code). For the Open Google Pay button, set `PUBLIC_URL` to an address your phone can reach.

### Put it on a domain (https)

`docker compose up -d` also starts **nginx** (config in `nginx/`), which forwards to the app and serves it at `http://localhost`. Two ways to get `https://aegios.co.in`:

- **Cloudflare Tunnel (home machine, no public IP, no open ports).** Cloudflare Zero Trust > Networks > Tunnels: create a tunnel, add the public hostname `aegios.co.in` -> `http://nginx:80`, delete any A record for the name. Put the tunnel token in `.env` as `TUNNEL_TOKEN` and set `COMPOSE_PROFILES=tunnel`, then `docker compose up -d`. Cloudflare provides the certificate; turn on "Always Use HTTPS" there to redirect http to https. nginx reads the visitor address from Cloudflare's header.
- **Let's Encrypt on a machine with a public IP.** Point the DNS A record at it, open ports 80 and 443, set `LETSENCRYPT_EMAIL` in `.env`, and `docker compose up -d`. **certbot** requests the certificate into `nginx/certs` (never committed) and nginx switches to https and redirects http to `https://aegios.co.in` by itself. Use `LETSENCRYPT_STAGING=1` first for a dry run.

Either way `PUBLIC_URL` must be `https://aegios.co.in` (set in `.env`). To use another domain, set `DOMAIN`. Telegram needs the https address for its webhook, so save your bot token in the Setup guide once it is live.

Stop with `docker compose down` (add `-v` to wipe the database).

### Develop and test

```bash
uv sync                                      # Python environment
docker compose --profile test up -d test-db  # throwaway Postgres for tests
TEST_DATABASE_URL=postgres://postgres:test@127.0.0.1:55432/postgres uv run pytest services/auth/tests   # backend tests: one service at a time
cd apps/web && npm install && npm test       # web tests
uv run python scripts/e2e.py                     # end-to-end check against the running stack
```

Backend tests need a throwaway Postgres superuser in `TEST_DATABASE_URL` (the `test-db` service above, or any scratch Postgres) and run per service, since each has its own `conftest.py`; `ledger` has no tests yet. `scripts/e2e.py` needs `PUBLIC_URL` set and `REGISTRATION=open`; see the header of the script.
