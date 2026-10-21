# Demo

A read-only demo account with six months of believable sample data, so visitors can press **Try the demo** on the About page and look around before making an account. It lives in this folder; the app itself only has two small opt-in hooks (below).

## What it is

| Piece | Where | What it does |
|---|---|---|
| Sample data | `dataset.py` | Builds the account's rows without a database: salary, UPI payments with real-looking merchants, Telegram-style entries, repeats (rent, SIP, gym, ...), a plan and limits with alerts, one Unaccounted gap, a few payments waiting for a tag, two messages in Needs a look. The same moment always gives the same rows, and nothing is dated after "now". |
| Loader | `seed.py` | Writes it into Postgres with the admin connection and repeats every `DEMO_REFRESH_HOURS` (6), so "this month" stays current. Only the one demo user is touched. |
| Overlay | `docker-compose.demo.yml` | Adds the `demo-seed` service and turns `DEMO_MODE` on for auth and the gateway. The main compose file is not changed. |
| Secrets | `setup.py`, `totp.py` | `demo/.env` (git-ignored) with the demo email, password and authenticator secret; `totp.py` prints the current code. |
| Tests | `tests/` | Check that the data follows the schema rules (balance never negative, one post per due day, alerts match the limits, ...). |

## How the demo login works

`DEMO_MODE=true` (set only by the overlay) does two things in the backend:

1. `POST /api/auth/demo` starts a normal session for the demo user (`DEMO_USER_ID` in `lbstash.common`) with no password or second step. It can sign in nobody else. With `DEMO_MODE` off it answers 404.
2. The gateway refuses every write by that user (`403`: "This is a demo, so it is read-only. Create an account to make changes."). Sign-out and token renewal still work.

The demo user's real password and authenticator secret are random and only in `demo/.env`: the normal sign-in form works for you (password, then `python3 demo/totp.py`), and nobody else can use it.

## Run it

From the `lbstash` folder:

```bash
python3 infra/scripts/gen-secrets.py            # once, if there is no .env yet
python3 demo/setup.py                           # once: demo/.env
docker compose --env-file .env --env-file demo/.env \
  -f docker-compose.yml -f demo/docker-compose.demo.yml up -d --build
```

Open http://localhost:8088 (the About page), press **Try the demo**. To look at the data as an account owner instead: sign in as `demo@lbstash.site` with the password in `demo/.env` and the code from `python3 demo/totp.py`.

On the server, set the GitHub variable `DEMO_ENABLED=true` and run **Release**: [Release and deploy](../docs/application/RELEASE.md).

## Reseed or remove

```bash
# reseed now
docker compose --env-file .env --env-file demo/.env -f docker-compose.yml -f demo/docker-compose.demo.yml run --rm demo-seed python /demo/seed.py
# remove the demo user and all its data
docker compose --env-file .env --env-file demo/.env -f docker-compose.yml -f demo/docker-compose.demo.yml run --rm demo-seed python /demo/seed.py --remove
```

Then start the stack without the overlay to switch the demo off.

## Notes

- The demo user does not count as "the app's account": with `REGISTRATION=first-only` you can still create your own.
- Sample amounts, merchants and people are made up. Nothing here comes from a real account.
- The current month runs hot on purpose (shopping, fun and food are above pace) so the Limits and Forecast pages have something to show. See `HOT_THIS_MONTH` in `dataset.py`.
- Run the data tests inside the backend image: `pytest demo/tests`.
