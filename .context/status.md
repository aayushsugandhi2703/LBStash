# Status

**Done (this cleanup)**
- Repo root tidied: `ui-spec` -> `docs/ui-spec`, compose overrides merged into the single `docker-compose.yml` (loopback gateway port, opt-in `test` profile), scaffolder removed (it could only recreate existing services).
- TS packages folded into `apps/web/src/{common,contracts}`; root npm workspace removed; per-page logic in `features/`; private `_page` folders flattened.
- Dead code removed (web exports, CSS classes, server-only TS ports, Python env shells, web-only password score, duplicate formatters). Docstrings and comments shortened; stale "port of ts / Zod" wording removed.
- Backend: shared settings moved into `BaseEnv`; one `FieldCipher.from_keys` (auth now honours key rotation too).
- Fixed a syntax error that stopped the ledger service importing (`transactions.py`).
- UI: scroller no longer clips panels, min-height floors, Now has no CHECK link, auth header height fixed.

**Known broken (not touched, tests were out of scope)**
- Backend pytest: `test_db.py` imports removed `camel_all`; `test_kit.py` imports removed `Paging`; nested `conftest.py` files define `pytest_plugins` (pytest 8+ needs it at the rootdir); `bt.common` exports trimmed in this cleanup (`password_score`, `password_label`, `round_to`, `encode_cursor`, ...) may need test imports updated. `test_contracts.py` still describes a Zod corpus.
- Dockerfiles, compose and the registry-push flow are untested here (no Docker available).

**Next**
- Fix and rerun the backend tests, then add tests for the new `BaseEnv` fields.
- Menu hint text wraps on "Profile and preferences" at 300px (spec width); the "signed in today" footer line needs a session start time from `/me`.
