# Building a service

Read [Architecture](ARCHITECTURE.md) first. Services are Python 3.12 and FastAPI. Shared code is the library in `backend/packages/lbstash` (`import lbstash.*`).

## Layout

```
backend/services/<name>/
  Dockerfile                 # ARG BASE_IMAGE=lbstash-base; FROM it, add this service's source
  pyproject.toml             # depends on `lbstash`; add only service-specific packages, then `uv sync`
  migrations/001_init.sql    # forward-only; end each user table with SELECT lbstash.enable_rls('table')
  src/lbstash_<name>/
    main.py                  # run_service(name, register=…, migrations_dir=…, workers=…): nothing else
    env.py                   # optional: class Env(BaseEnv) for the service's own variables
    routes.py                # register(app, deps): declares routes; thin, calls the domain code
    <domain>.py              # business logic: takes `deps` and `ctx`, no FastAPI types
    workers.py               # async start_workers(deps): deps.bus.on_event / on_job / schedule
  tests/
    conftest.py              # pytest_plugins = ['lbstash.kit.pytest_plugin'] + the two session fixtures
```

## Routes

```python
def register(app: FastAPI, deps: Deps) -> None:
    @app.get("/budgets", response_model=BudgetsRes)
    async def list_budgets(ctx: UserCtx, query: Annotated[BudgetsQuery, Query()]):
        return await budgets.list_(deps, ctx, query)
```

- `UserCtx` needs a user on the token (401 otherwise). `ServiceClaims` needs only a valid internal token (webhooks, system calls). `OptionalCtx` gives the user when there is one.
- Input is validated against pydantic models from `lbstash.contracts` (put new shared models in your own service's file there). A failure answers `400 validation_failed`.
- Raise `Errors.*` from `lbstash.common`. Never write error JSON by hand.
- A write returns the updated row and the figures the page shows beside it. Use `response_model` (camelCase on the wire).
- Routes only other services call live under `/internal/`. The app refuses them if the gateway forwarded them from outside.

## Database

```python
async with deps.as_user(ctx) as tx:
    row = await tx.maybe_one("SELECT … WHERE id = $1", [id])
    await deps.bus.emit(tx, "transaction.changed", payload)   # commits with the row
```

- `Tx` has `query`, `many`, `maybe_one`, `one`, `execute`, `savepoint()`. `Where` builds filters; `camel(row)` renames keys.
- Parameterised SQL only (`$1, $2 …`). The schema is the default `search_path`, so use plain table names.
- Put constraints in the migration (unique keys, `amount_minor > 0`, …).

## Other services and events

- Call another service: `await deps.clients.transactions.tag(ctx, id, body)`. To let others call you, add a method to your client in `backend/packages/lbstash/src/lbstash/clients/clients.py` and your models in `contracts/<you>.py`. Do not edit another service's client or contract; report what is missing.
- Producers: `deps.bus.emit(tx, "name", payload)` or `enqueue`. Consumers: `deps.bus.on_event("name", handler)` in `workers.py`, for events listed under your service in `SUBSCRIPTIONS`. Delivery is at-least-once, so make handlers idempotent.

## Testing

From `backend/`: `uv sync`, `uv run pytest services/<name>`, `uv run ruff check services/<name>`.

- Start Postgres: `docker compose --profile test up -d test-db`, then `export TEST_DATABASE_URL=postgres://<POSTGRES_USER>:<POSTGRES_PASSWORD>@127.0.0.1:5544/<POSTGRES_DB>`.
- DB tests: the `db` fixture is a throwaway database per module, connected as the service's own least-privilege role, so RLS is real.
- HTTP tests: `app_factory(register=register, pool=db.pool, clients={...})` gives an `httpx` client over ASGI and `headers_for(user_id)`. Events go to an `InMemoryBus`.
- Cover: happy path, validation, ownership (user A cannot see user B), idempotency, and each edge case.
- End to end: `docker compose up -d --build` with `REGISTRATION=open`, then `cd backend && uv run python ../infra/scripts/e2e.py`.

## Done means

- Endpoints exist, validated, with the response shape the page needs.
- The migration has constraints, indexes and RLS.
- Consumers are idempotent; every write that triggers work uses the outbox.
- No amounts, payees, message text, tokens or emails in logs.
- Money is integer paise; month logic uses `lbstash.common`.
- Tests and `ruff` pass, and the image builds: `docker build -f infra/docker/base.Dockerfile -t lbstash-base backend`, then `docker build -f backend/services/<name>/Dockerfile -t lbstash-<name> backend`.
- No logic copied from another service or from `lbstash`: reuse it.
