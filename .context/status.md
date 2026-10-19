# Status

**Done (this cleanup)**
- Repo root tidied: `ui-spec` -> `docs/ui-spec`, compose overrides merged into the single `docker-compose.yml` (loopback gateway port, opt-in `test` profile), scaffolder removed (it could only recreate existing services).
- TS packages folded into `apps/web/src/{common,contracts}`; root npm workspace removed; per-page logic in `features/`; private `_page` folders flattened.
- Dead code removed (web exports, CSS classes, server-only TS ports, Python env shells, web-only password score, duplicate formatters). Docstrings and comments shortened; stale "port of ts / Zod" wording removed.
- Backend: shared settings moved into `BaseEnv`; one `FieldCipher.from_keys` (auth now honours key rotation too).
- Fixed a syntax error that stopped the ledger service importing (`transactions.py`).
- UI: scroller no longer clips panels, min-height floors, Now has no CHECK link, auth header height fixed.

**Done (Telegram logging)**
- Removed the iPhone Shortcut (`scripts/make-shortcut.py`, the signed file, its header, `/public-url`, `PHONE_URL`). iOS cannot create the Message automation from a file and its Sender rule accepts only contacts.
- Telegram: `/350 food` (money out, tagged at once), `+1500 salary` (money in), `/350` alone gives the tag buttons. Money out replies with an Open Google Pay button (`/pay` page). Ledger `ManualTransactionReq` has an optional `tag`.
- Setup guide cut to 3 steps; README, ARCHITECTURE and SYSTEM_DESIGN updated. The optional `/ingest/message` route and Devices token page remain.
- Not run on a phone or live bot: the `/pay` Google Pay hand-off and the typed-amount commands. Web typecheck and tests were not run (no Node here); `setup.test.ts` was edited to match.

**Done (security, brand, guide)**
- Telegram: only the chosen account (username or id, set on Setup) can link; the typed-payment confirmation repeats the amount; same-token re-save no longer deletes the webhook; deep link `t.me/<bot>?start=<code>`.
- Web: optional allowed-address list (`users.allowed_ips`) checked at sign-in, refresh and the gateway session check.
- `apps/web/src/brand` + `public/brand`: logo mark, wordmark, icons, BRAND constants; shown in the header, auth pages and tab icon.
- Setup guide and page descriptions shortened; placeholders added to inputs; unused `SectionHead` and `public/.gitkeep` removed.

**Known broken**
- Backend pytest passes per service (auth, gateway, ingest, planning, recurring, reports, telegram, packages `bt`), except: `test_common.py` (`EnvError`), `test_db.py` (`camel_all`), `test_kit.py` (`Paging`) cannot import, `test_queue.py::test_jobs_go_to_their_queue_and_drain_runs_them` (`InMemoryBus.jobs_of`) fails, and `ledger` has no tests. Running all services in one pytest call fails (`pytest_plugins` in nested conftests).
- Web: 224 tests pass in Docker. Not run on a real phone or live bot: the `/pay` hand-off, typed commands and the deep link.

**Next**
- Fix the broken backend tests above and add ledger tests.
- Unused exported contract types in `apps/web/src/contracts` (e.g. `UserDto`, `PlanDto`, `AlertDto`) and a few unused CSS-module classes are dead by the conventions; remove them.
- Menu hint text wraps on "Profile and preferences" at 300px (spec width); the "signed in today" footer line needs a session start time from `/me`.
