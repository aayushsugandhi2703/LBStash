# Status

**Done**
- Repo tidy: one `docker-compose.yml`, TS packages folded into `apps/web/src/{common,contracts}`, per-page logic in `features/`, dead code and long comments cut, shared settings in `BaseEnv`, one `FieldCipher.from_keys`.
- Telegram logging: `/350 food`, `+1500 salary`, `/350` for tag buttons, Open Google Pay button (`/pay`). iPhone Shortcut removed (iOS cannot create the automation from a file). Typed payments are confirmed with the amount.
- Telegram lock: only the account set on Setup (username or id) can link; deep link `t.me/<bot>?start=<code>`; saving the same token twice no longer deletes the webhook.
- Web: optional allowed addresses (`users.allowed_ips`), checked at sign-in, refresh and the gateway session check.
- Brand: `apps/web/src/brand` + `public/brand` (logo, icons, `BRAND`), shown in the header, auth pages and tab icon.
- Setup guide cut to 3 steps; copy shortened across the app; placeholders on inputs; unused `SectionHead` removed.

**Known broken**
- Backend tests pass per service. Exceptions: `test_common.py` (`EnvError`), `test_db.py` (`camel_all`), `test_kit.py` (`Paging`) cannot import; `test_queue.py::test_jobs_go_to_their_queue_and_drain_runs_them` (`InMemoryBus.jobs_of`) fails; `ledger` has no tests. One pytest call over all services fails (`pytest_plugins` in nested conftests).
- Web: 224 tests pass in Docker.
- Not checked on a real phone or live bot: the `/pay` hand-off, typed commands, the deep link.

**Next**
- Fix those backend tests; add ledger tests.
- Remove unused contract types in `apps/web/src/contracts` (`UserDto`, `PlanDto`, `AlertDto`, ...) and unused CSS-module classes.
- Menu hint wraps on "Profile and preferences" at 300px; the "signed in today" footer needs a session start time from `/me`.
