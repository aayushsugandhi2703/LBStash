# LBStash

[![Release](https://github.com/aayushsugandhi2703/LBStash/actions/workflows/release.yml/badge.svg)](https://github.com/aayushsugandhi2703/LBStash/actions/workflows/release.yml)
[![Terraform](https://github.com/aayushsugandhi2703/LBStash/actions/workflows/terraform.yml/badge.svg)](https://github.com/aayushsugandhi2703/LBStash/actions/workflows/terraform.yml)
[![Version](https://img.shields.io/github/v/tag/aayushsugandhi2703/LBStash?sort=semver&label=version)](https://github.com/aayushsugandhi2703/LBStash/tags)
[![Docker Hub](https://img.shields.io/docker/v/aayush2703/lbstash-web?sort=semver&label=docker&logo=docker)](https://hub.docker.com/u/aayush2703)
[![Status](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Faayushsugandhi2703%2FLBStash%2Fstatus%2Fstatus.json&cacheSeconds=300)](https://lbstash.site)

A private budget tracker you run from a Telegram chat. Send `/350 food` when you spend, `+1500 salary` when money comes in. It is saved, tagged and shown in the web app. Amounts are in ₹.

## How it works

1. **Log.** `/350` = money out, `+1500` = money in. Add a tag (`/350 food`) or pick one from the buttons.
2. **Save.** The server stores it and deletes your message from the chat.
3. **Tag.** Known payees are tagged for you. Tag a new one once and it is remembered.
4. **Track.** Balance, limits, alerts, trends and repeating payments come from your tagged payments. A payment you forgot to log shows up as "Unaccounted".

You can also log from the web app, or (optionally) let another tool post bank SMS text to `/ingest/message`.

## The three parts

| Part | What it is | Tech | Folders |
|---|---|---|---|
| **Backend** | 8 small services that own the data and rules | Python 3.12, FastAPI, PostgreSQL 17 | `backend/` |
| **Frontend** | The web app you use in the browser | Next.js (TypeScript) | `frontend/` |
| **Infra** | Runs and protects everything | Docker Compose, nginx, certbot / Cloudflare, Terraform (Oracle Cloud) | `infra/`, `docker-compose.yml` |

```mermaid
flowchart LR
  Browser --> Nginx
  Telegram --> Nginx
  Nginx -->|"/"| Web
  Nginx -->|"/api, /ingest, /telegram/webhook"| Gateway
  Gateway --> Auth & Ingest & Transactions & Planning & Recurring & Reports & Tg["Telegram service"]
  Auth & Ingest & Transactions & Planning & Recurring & Tg --> DB[("PostgreSQL")]
```

## Folder structure

```
lbstash/
├── backend/                     Python 3.12 + FastAPI (a uv workspace; also the Docker build folder of every Python image)
│   ├── services/                one folder per service
│   │   ├── gateway/             only door to the backend: login, CSRF, rate limits
│   │   ├── auth/                users, sessions, 2FA, passkeys, audit log
│   │   ├── transactions/        payments, categories, tag rules, balance checks
│   │   ├── ingest/              optional bank-message route
│   │   ├── planning/            monthly plans, limits, alerts
│   │   ├── recurring/           repeating payments
│   │   ├── reports/             dashboard and trends (stores nothing)
│   │   └── telegram/            the bot
│   │       (each has: src/  migrations/  tests/  Dockerfile  pyproject.toml)
│   ├── packages/lbstash/        code shared by every service (money, crypto, db, queue, clients)
│   ├── pyproject.toml, uv.lock  Python workspace and locked versions
│   └── .dockerignore
│
├── frontend/                    Next.js web app
│   ├── src/app/                 pages (sign-in, create-account, reset, pay, the app screens)
│   ├── src/components/          shared UI pieces
│   ├── src/features/            data and logic for each screen
│   ├── src/lib/                 API calls and hooks
│   ├── src/brand/               logo, name, icons
│   ├── src/common/, contracts/  copies of money rules and response types
│   ├── public/                  images and brand SVGs
│   ├── test/                    web tests
│   └── next.config.mjs, package.json, Dockerfile
│
├── infra/
│   ├── docker/base.Dockerfile   shared Python base image
│   ├── nginx/                   public entry: templates/, snippets/, certbot/, entrypoint.sh
│   ├── terraform/               builds the Oracle Cloud server (see its README): modules/, policies.txt
│   └── scripts/                 gen-secrets.py (makes .env), e2e.py (end-to-end test), update-changelog.py (used by Release)
│
├── .github/workflows/           terraform.yml (builds the server), release.yml (builds, deploys, tags), status.yml (live-site badge)
├── docs/                        SECRETS.md, application/ (architecture, service guide, release, brand, changelog), infrastructure/ (server setup)
├── docker-compose.yml           starts the whole stack (kept at the top so `docker compose up` just works)
├── .env, .env.example           secrets and settings (.env is never committed)
└── README.md
```

## Backend

Each service owns its own database schema and login, and never reads another's tables.

| Service | Job |
|---|---|
| gateway | Login check, CSRF, rate limits, security headers, forwards by path |
| auth | Users, sessions, 2FA, passkeys, recovery codes, export, account deletion |
| transactions | Payments, categories, tag rules, credits, balance checks |
| ingest | Optional bank-message route: device tokens, OTP guard, parser |
| planning | Monthly plans, limits, alerts |
| recurring | Repeating payments and the cron that posts them |
| reports | Dashboard and trend views, worked out when read |
| telegram | Logging, tagging, Google Pay button, daily digest |

How they work together:
- **Calls** are typed HTTP clients. Reads may retry; writes are never blindly retried.
- **Events** are saved with the change (outbox), then moved to a Postgres queue. Failed jobs retry; every consumer is safe to run twice.
- **Money** is whole paise as integers, never floats. Months and "today" use your time zone.
- More: [ARCHITECTURE](docs/application/ARCHITECTURE.md) (where the code lives and how the flows work), [SERVICE_GUIDE](docs/application/SERVICE_GUIDE.md).

## Frontend

A Next.js app with these pages: Now · Transactions · Plan · Limits · Repeats · Trends · Add credit · Needs a look · Account · Setup guide. It only talks to the gateway. Logo, name and colours: [BRAND](docs/application/BRAND.md).

## Infra

- **nginx** is the only public entry. `/` goes to the web app; `/api`, `/ingest`, `/telegram/webhook` go to the gateway. Nothing else is exposed.
- **Docker images:** one per service on a shared, slimmed Python base (built from `backend/`; the web image from `frontend/`) (about 240MB each; web about 225MB). The 8 Python images share the same base layers, so together they take roughly one image of disk.
- **Start order:** `db-init` creates roles and schemas, then the services, gateway, web and nginx start.
- **https:** Cloudflare Tunnel or Let's Encrypt (see [Deployment](#deployment)).
- **Server:** a free Oracle Cloud VM, built with [Terraform](infra/terraform/README.md).

## Security

- **Sign-in:** 12+ character password (Argon2id), authenticator app required, passkeys, 10 hashed recovery codes. Optional allowed-IP list.
- **Sessions:** 15-minute access token; refresh token rotates and a reused one revokes the session. `HttpOnly`, `Secure`, `SameSite=Strict` cookies and a CSRF token on every change.
- **Brute force:** 5 wrong passwords lock for 30 s, doubling up to 15 min. Per-IP limits.
- **Data:** AES-256-GCM for secrets, tokens stored as hashes, one Postgres login and schema per service, row-level security on user tables.
- **Between services:** not on the internet; a signed 60-second token on every call.
- **Telegram:** only your account can link; your message is deleted after it is read; sensitive prompts stay hidden until you tap Reveal.
- **Never collected:** bank logins, UPI PINs, card numbers, OTPs. The app never moves money.
- **Yours:** export any time, delete your account (7-day grace), append-only audit log, logs hold ids only.

## Deployment

Pick one. Always **back up `FIELD_KEY`** from the `.env`: encrypted data cannot be read without it. Oracle Cloud creates the `.env` for you; for the other two, run `python3 infra/scripts/gen-secrets.py` first.

### Oracle Cloud (free)

An always-on server for about ₹0/month. Terraform builds it; GitHub Actions builds the images (amd64 + arm64), stores them on Docker Hub and updates the server.

Add the GitHub secrets first ([SECRETS](docs/SECRETS.md), one place for all of them), then follow [server setup](docs/infrastructure/SERVER_SETUP.md) and [release and deploy](docs/application/RELEASE.md).

In short: create the server with **Actions > Terraform**, point your domain at it, then run **Actions > Release** with a version (`x.y.z`) after each merge to `main`.

### Cloudflare Tunnel

No public IP or open ports needed.

1. In Cloudflare, create a tunnel (Network > Tunnels) to `http://nginx:80`. Copy its token.
2. In `.env`, set `TUNNEL_TOKEN`, `COMPOSE_PROFILES=tunnel` and `PUBLIC_URL=https://lbstash.site`.
3. `docker compose up -d --build`

### Locally with Docker

For trying it, and for development and tests.

```bash
python3 infra/scripts/gen-secrets.py
docker compose up --build
```

Open http://localhost:8088. Stop with `docker compose down` (`-v` also wipes the database).

Telegram needs https, so use Oracle Cloud or Cloudflare Tunnel for the bot.

**Run the tests** (optional):

```bash
docker compose --profile test up -d test-db  # throwaway Postgres (run from the top folder)
export TEST_DATABASE_URL=postgres://lbstash_admin:<POSTGRES_PASSWORD from .env>@127.0.0.1:5544/lbstash

cd backend
uv sync                                      # Python environment
uv run pytest services/auth/tests            # backend tests, one service at a time
uv run python ../infra/scripts/e2e.py        # end-to-end test (needs PUBLIC_URL and REGISTRATION=open)

cd ../frontend && npm install && npm test    # web tests
```
