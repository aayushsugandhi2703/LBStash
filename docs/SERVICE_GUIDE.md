# Building a service

Read `docs/ARCHITECTURE.md` first. This is the how-to every service follows. Services are Python 3.12 / FastAPI; the shared
code is the library in `packages/bt` (import `bt.*`).

## Layout

```
services/<name>/
  Dockerfile                 # ARG BASE_IMAGE=budget-base; FROM it, add this service's source and own dependencies
  pyproject.toml             # depends on `bt`; add only service-specific dependencies, then `uv sync`
  migrations/001_init.sql    # forward-only; ends each user table with SELECT bt.enable_rls('table')
  src/bt_<name>/
    main.py                  # run_service(name, register=…, migrations_dir=…, workers=…): nothing else
    env.py                   # optional: class Env(BaseEnv) when the service has its own variables (pass env_model=Env)
    routes.py                # register(app, deps): declares routes; thin, calls the domain code
    <domain>.py              # business logic; takes `deps` and `ctx`, no FastAPI types
    workers.py               # async start_workers(deps): deps.bus.on_event / on_job / schedule
  tests/
    conftest.py              # pytest_plugins = ['bt.kit.pytest_plugin'] + the two session fixtures
    test_*.py
```

Dev loop: `uv sync`, then `uv run pytest services/<name> -q` and `uv run ruff check services/<name>`. Postgres for tests:
`docker compose --profile test up -d test-db` (port 5544; set `TEST_DATABASE_URL` to its superuser URL).

## Writing routes

```python
def register(app: FastAPI, deps: Deps) -> None:
    @app.get("/budgets", response_model=BudgetsRes)
    async def list_budgets(ctx: UserCtx, query: Annotated[BudgetsQuery, Query()]):
        return await budgets.list_(deps, ctx, query)

    @app.post("/internal/plans/{month}/credit", response_model=PlanCreditRes)
    async def plan_credit(claims: ServiceClaims, month: Annotated[MonthParam, Path()], body: PlanCreditReq): ...
```

- `ctx: UserCtx` needs a user on the token (401 otherwise). `ServiceClaims` needs a valid internal token only (webhooks, ingest, system
  calls); `OptionalCtx` gives the user when there is one.
- Input is validated by FastAPI against pydantic models from `bt.contracts` (put new shared models there, in your own service's file).
  A failure answers `400 validation_failed` with `details` per field.
- Raise `Errors.*` from `bt.common`; never craft error JSON by hand.
- Every mutating endpoint returns the updated row **and** the figures the page shows beside it (README 11). Always serialise with
  `bt.contracts.dump(model)` or return the model with `response_model` (by alias, camelCase on the wire).
- Public routes are mounted on the README paths (`/budgets`, `/ledger`, …). Routes only other services call live under `/internal/`
  (the app refuses any request the gateway forwarded from outside).

## Database

```python
async with deps.as_user(ctx) as tx:
    row = await tx.maybe_one("SELECT … WHERE id = $1", [id])
    await deps.bus.emit(tx, "transaction.changed", payload)   # commits with the row
```

- `Tx` offers `query`, `many`, `maybe_one`, `one`, `execute`, `savepoint()`; `Where` builds dynamic filters; `camel(row)` renames keys.
  `bigint` columns come back as `int`, `date` columns as `'YYYY-MM-DD'` strings, `uuid` as `str`, `timestamptz` as aware UTC `datetime`.
- Parameterised SQL only, with `$1, $2 …` placeholders (the wrapper rewrites them). Schema is the default `search_path`, so use
  unqualified table names.
- Add the constraints the README lists (unique keys, `amount_minor > 0`, …) in the migration.

## Calling other services

`await deps.clients.ledger.tag(ctx, id, body)`. Add a method to your own client class in `packages/bt/src/bt/clients/clients.py`
if another service needs to call you (and its models to `packages/bt/src/bt/contracts/<you>.py`). Do not edit another service's
client or contract except to add something you were told is missing; report it instead.

## Events

Producers: `await deps.bus.emit(tx, "name", payload)` / `enqueue`. Consumers: `await deps.bus.on_event("name", handler)` in
`workers.py` for events listed under your service in `SUBSCRIPTIONS`. Handlers get the validated pydantic payload. At-least-once:
make handlers idempotent (unique keys, "first write wins").

## Testing

- `docker compose --profile test up -d test-db` gives Postgres on 5544; export `TEST_DATABASE_URL=postgres://<POSTGRES_USER>:<POSTGRES_PASSWORD>@127.0.0.1:5544/<POSTGRES_DB>`.
- DB tests: the `db` fixture is a throwaway database per test module, connected as the service's own least-privilege role, so RLS is real.
- HTTP tests: `app_factory(register=register, pool=db.pool, clients={"ledger": FakeLedger()})` gives a harness with an `httpx` client over
  ASGI and `headers_for(user_id)`. Messages go to an `InMemoryBus` (`bus.events_of("…")`, `await bus.drain()`).
- Run only your own tests: `uv run pytest services/<name>`.
- Cover: happy path, validation, ownership (user A cannot see user B), idempotency, and each edge case the README lists for your area.
- End to end: `docker compose up -d --build` (with `REGISTRATION=open`), then
  `uv run python scripts/e2e.py`.

## Definition of done

- [ ] Every endpoint in README section 9/11 that belongs to you exists, validated, with the response shape the page needs (read `docs/ui-spec/*/SKILL.md` for the page).
- [ ] Migration has the constraints, indexes, RLS (`bt.enable_rls`) and revokes the README lists.
- [ ] Idempotent consumers; outbox used for every write that triggers work.
- [ ] No amounts, payees, message text, tokens or e-mail addresses in logs.
- [ ] Money is integer paise; time-zone aware month logic uses `bt.common`.
- [ ] Tests pass; `uv run ruff check services/<name>` is clean; `docker build -f services/<name>/Dockerfile -t budget-<name> .` works (after `docker build -f docker/base.Dockerfile -t budget-base .`).
- [ ] No logic copied from another service or from `bt`: reuse it.
