# packages/bt (import `bt.*`)

| Module | What it holds |
|---|---|
| `common` | `AppError`/`Errors`, `BaseEnv` + `load_env`, `Ctx`, logger (redacting JSON), money, time (`timeutil`), metrics, tags, cursors, password policy |
| `crypto` | Argon2id (`password`), `FieldCipher` (AES-GCM, `from_keys`), TOTP, token hashing, JWT (access + internal service token) |
| `contracts` | pydantic models for every cross-service request/response, events/jobs (`events.py`), route table (`routes.py`); `base.py` has `Model`, `Opt`, `partial`, `discriminated` |
| `db` | pool + adapters (`$n` placeholders), `Tx`, `Where`, migrations, bootstrap (roles, schemas, `bt.enable_rls`), test database |
| `queue` | `MessageBus` protocol, `Messaging` (outbox -> Postgres queue, retries, cron), `InMemoryBus` |
| `clients` | one typed client per service, signing, retries, error mapping |
| `kit` | `run_service`/`boot_service`, `create_app`, `Deps`, request deps, rate limiter, test fixtures, software WebAuthn |

- `BaseEnv` owns: `DATABASE_URL` (empty for gateway/reports), `QUEUE_DATABASE_URL`, `INTERNAL_SECRET`, `FIELD_KEY(S)`, `PUBLIC_URL`, service URLs. A service only adds an `Env` when it has its own variables (auth, gateway, ingest, telegram).
- Build ciphers with `FieldCipher.from_keys(env.FIELD_KEY, env.FIELD_KEYS)`.
- Password strength meter (score/label) is web-only; Python keeps only the rules.
