# Infra and local running

- Root: `docker-compose.yml` is the only compose file (whole stack; `docker compose up --build`). `pyproject.toml` + `uv.lock` (uv workspace), `.env.example`. Opt-in `test` profile adds `test-db` (Postgres on 5544).
- Images: `docker/base.Dockerfile` (Python base + `bt`), `services/<name>/Dockerfile` (one per service, `ARG BASE_IMAGE`), `apps/web/Dockerfile` (Node, context `apps/web`). Names `${REGISTRY}budget-<name>:${IMAGE_TAG}`; `docker compose build && docker compose push` publishes them.
- Scripts: `scripts/gen-secrets.py` (writes `.env`), `scripts/e2e.py` (end-to-end over HTTP against a running gateway).
- Without Docker: Postgres on 127.0.0.1:5544 (user `bt_admin`, db `budget`), run `python -m bt.db.init` with `ADMIN_DATABASE_URL` and `DB_PASSWORD_*`, then start each `bt_<service>.main` with `PORT`, `SERVICE_NAME`, `DATABASE_URL`, `QUEUE_DATABASE_URL`, `INTERNAL_SECRET`, `ACCESS_TOKEN_SECRET`, `FIELD_KEY` and the `*_URL` addresses on 127.0.0.1. Use `REGISTRATION=open` and `PUBLIC_URL=http://localhost:8088` for the e2e script.
- Run e2e: `PUBLIC_URL=http://localhost:8088 GATEWAY=http://127.0.0.1:3000 .venv/bin/python scripts/e2e.py` (PUBLIC_URL must equal the stack's).
