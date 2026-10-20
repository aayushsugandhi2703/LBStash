"""End-to-end check against the REAL running stack, through the gateway.

    docker compose up -d --build
    REGISTRATION=open ... (a second sign-up must be allowed, see .env.example)
    PUBLIC_URL=<the stack's PUBLIC_URL> uv run python scripts/e2e.py   # GATEWAY=http://127.0.0.1:3010 by default
    PROXY=http://127.0.0.1:8088 uv run python scripts/e2e.py   # also checks the web app via the proxy

Signs up a throwaway user, drives the money flows from README section 10 and checks the numbers. HTTP only.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import struct
import sys
import time
import urllib.parse
import uuid
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
from lbstash.kit.softauth import SoftAuthenticator

BASE = os.environ.get("GATEWAY", "http://127.0.0.1:3010")
PROXY = os.environ.get("PROXY")
jar: dict[str, str] = {}
failures = 0
http = httpx.Client(timeout=30)


def log(ok: bool, name: str, extra: str = "") -> None:
    global failures
    if not ok:
        failures += 1
    print(f"{'  ok ' if ok else ' FAIL'}  {name}{f'  ({extra})' if extra else ''}", flush=True)


def eq(name: str, got, want) -> None:
    same = json.dumps(got, sort_keys=True) == json.dumps(want, sort_keys=True)
    log(same, name, "" if same else f"got {json.dumps(got)}, want {json.dumps(want)}")


def until(fn, seconds: float = 30):
    end = time.time() + seconds
    while time.time() < end:
        v = fn()
        if v:
            return v
        time.sleep(0.5)
    return None


class Reply:
    def __init__(self, status: int, body):
        self.status, self.json = status, body


def call(method: str, path: str, body=None, *, headers: dict | None = None, cookies: bool = True) -> Reply:
    h = dict(headers or {})
    if body is not None:
        h["content-type"] = "application/json"
    if cookies and jar:
        h["cookie"] = "; ".join(f"{k}={v}" for k, v in jar.items())
    if method != "GET" and jar.get("lbstash_csrf") and "x-csrf-token" not in h:
        h["x-csrf-token"] = urllib.parse.unquote(jar["lbstash_csrf"])
    res = http.request(method, BASE + path, headers=h, content=json.dumps(body) if body is not None else None)
    for c in res.headers.get_list("set-cookie"):
        kv = c.split(";", 1)[0]
        k, _, v = kv.partition("=")
        if "max-age=0" in c.lower() or "expires=thu, 01 jan 1970" in c.lower() or v == "":
            jar.pop(k, None)
        else:
            jar[k] = v
    try:
        data = res.json() if res.content else None
    except ValueError:
        data = res.text
    return Reply(res.status_code, data)


def ok(method: str, path: str, body=None, **kw):
    r = call(method, path, body, **kw)
    if r.status >= 300:
        raise RuntimeError(f"{method} {path} -> {r.status} {json.dumps(r.json)}")
    return r.json


# TOTP (RFC 6238), kept here so the script depends on none of the code under test
def totp_code(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    h = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    off = h[-1] & 15
    return str((struct.unpack(">I", h[off:off + 4])[0] & 0x7FFFFFFF) % 10**6).zfill(6)


def totp_step(now: float | None = None) -> int:
    return int((now or time.time()) // 30)


last_step = 0
secret = ""


def code() -> str:
    """A code for a time step nobody has used yet (the server accepts each step once)."""
    global last_step
    s = totp_step()
    if s <= last_step:
        s = last_step + 1
    last_step = s
    return totp_code(secret, s)


def wait_step() -> None:
    while totp_step() <= last_step:
        time.sleep(1)


stamp = int(time.time() * 1000)
email = f"e2e+{stamp}@example.com"
password = f"correct horse battery {stamp}"
tz = "Asia/Kolkata"
today = datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d")
month = today[:7]
yy, mm, dd = today.split("-")
msg_date = f"{dd}-{mm}-{yy[2:]}"
nonce = lambda: f"n-{uuid.uuid4()}"


def ingest(token: str, text: str, n: str | None = None) -> Reply:
    body = {"text": text, "receivedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"), "nonce": n or nonce()}
    return call("POST", "/ingest/message", body, headers={"authorization": f"Bearer {token}"}, cookies=False)


print(f"gateway {BASE}, user {email}\n")

# health
eq("gateway /health", call("GET", "/health").status, 200)
eq("no session -> 401", call("GET", "/me").status, 401)

# sign-up and mandatory setup (README 10.7, 15.1)
reg = ok("POST", "/auth/register", {"email": email, "password": password, "name": "E2E", "timezone": tz})
eq("register gives a setup-limited session", reg["setup"]["complete"], False)
eq("limited session cannot reach the transactions", call("GET", "/transactions").status, 403)
secret = ok("POST", "/auth/2fa/enable", {})["secret"]
ok("POST", "/auth/2fa/enable/confirm", {"code": code()})
public_url = os.environ.get("PUBLIC_URL") or sys.exit("set PUBLIC_URL to the stack's PUBLIC_URL (the passkey origin)")
authenticator = SoftAuthenticator(urllib.parse.urlsplit(public_url).hostname or "", public_url)
pk = ok("POST", "/auth/passkey/register/options", {})
ok("POST", "/auth/passkey/register/verify", {"response": authenticator.register(pk["options"]), "label": "e2e key"})
rc = ok("POST", "/auth/recovery-codes", {})
eq("authenticator + passkey + 10 recovery codes: setup complete", [len(rc["codes"]), rc["setup"]["complete"]], [10, True])
me = ok("GET", "/me")
eq("/me composed", [me["email"], me["timezone"], me["untaggedCount"]], [email, tz, 0])

# settings composed from three services
ok("PATCH", "/settings", {"openingBalanceMinor": 10_000_000, "alertLevel": 80, "reconcileGraceHours": 0})
st = ok("GET", "/settings")
eq("settings merged (transactions + planning + telegram)",
   [st["openingBalanceMinor"], st["alertLevel"], st["reconcileGraceHours"], st["currency"], isinstance(st["allowReveal"], bool)],
   [10_000_000, 80, 0, "INR", True])

# bank-message capture (optional route; README 4.6, 15.3)
dev = ok("POST", "/devices", {})
token = dev["token"]
log(isinstance(token, str) and len(token) > 30, "ingest token issued once")
debit = f"Rs.450.00 debited from a/c XX1234 on {msg_date} to VPA ramesh@okaxis (UPI Ref 123456789012)"
n1 = nonce()
eq("debit captured 201", ingest(token, debit, n1).status, 201)
eq("same message again -> duplicate 200", ingest(token, debit).status, 200)
eq("replayed nonce -> 409", ingest(token, debit, n1).status, 409)
eq("OTP dropped 202", ingest(token, "Your OTP is 482913. Do not share it with anyone. Rs.450.00").status, 202)
eq("bad token -> 401", ingest("ledg_nope", debit).status, 401)
eq("unreadable -> 422", ingest(token, "debited something odd without any amount").status, 422)
eq("empty text (sender run by hand) -> device test 200", ingest(token, "").status, 200)
eq("/unparsed shows 1 open", ok("GET", "/unparsed")["open"], 1)

# transactions, tagging, payee memory (README 10.2)
led = ok("GET", "/transactions?limit=20")
eq("one pending payment, counted as Needs a tag", [len(led["items"]), led["counts"]["needsTag"]], [1, 1])
eq("balance counts the pending debit", led["balanceMinor"], 10_000_000 - 45_000)
tx = led["items"][0]
tagged = ok("PATCH", f"/transactions/{tx['id']}", {"tag": "#Food"})
eq("tag creates the category and confirms", [tagged["transaction"]["categoryName"], tagged["transaction"]["status"]], ["food", "confirmed"])
again = ok("PATCH", f"/transactions/{tx['id']}", {"tag": "travel"})
eq("first write wins", [again["changed"], again["transaction"]["categoryName"]], [False, "food"])
ingest(token, f"Rs.320.00 debited from a/c XX1234 on {msg_date} to VPA ramesh@okaxis (UPI Ref 223456789012)")
led = ok("GET", "/transactions?limit=20")
eq("payee memory auto-tags the next payment",
   len([i for i in led["items"] if i["status"] == "confirmed" and i["categoryName"] == "food"]), 2)

# credits and plan (README 10.3)
cr = ok("POST", "/credits", {"amountMinor": 5_000_000, "date": today, "tag": "salary", "addToPlan": True})
eq("credit: new balance returned", cr["balanceMinor"], 10_000_000 - 45_000 - 32_000 + 5_000_000)
eq("credit raised the plan total", cr["planTotalMinor"], 5_000_000)
ok("PUT", f"/plans/{month}", {"totalMinor": 5_000_000, "lines": [{"tag": "food", "allocatedMinor": 800_000}, {"tag": "rent", "allocatedMinor": 2_000_000}]})
plan = ok("GET", f"/plans/{month}")
eq("plan: assigned / unassigned", [plan["assignedMinor"], plan["unassignedMinor"]], [2_800_000, 2_200_000])
eq("plan: food spent comes from the transactions", next((l["spentMinor"] for l in plan["lines"] if l["categoryName"] == "food"), None), 77_000)

# budgets and alerts (README 10.5)
log(bool(ok("POST", "/budgets", {"tag": "food", "limitMinor": 100_000, "period": "monthly"})), "limit created for food (₹1,000)")
ingest(token, f"Rs.100.00 debited from a/c XX1234 on {msg_date} to VPA ramesh@okaxis (UPI Ref 323456789012)")  # 87%
alert = until(lambda: next((a for a in ok("GET", "/alerts")["items"] if a["level"] == "alert"), None))
log(bool(alert), "alert row appears after crossing 80% (event → job → row)", f"{alert['categoryName']} {alert['level']}" if alert else "timeout")
eq('limit status is "close"', ok("GET", f"/budgets?month={month}")["items"][0]["status"], "close")
ingest(token, f"Rs.200.00 debited from a/c XX1234 on {msg_date} to VPA ramesh@okaxis (UPI Ref 423456789012)")  # 107%
log(bool(until(lambda: next((a for a in ok("GET", "/alerts")["items"] if a["level"] == "exceeded"), None))), "exceeded alert fires once")
time.sleep(2.5)
eq("exactly two alerts (one per level)", len(ok("GET", "/alerts")["items"]), 2)

# recurring
rule = ok("POST", "/recurring", {"name": "Rent", "tag": "rent", "amountMinor": 2_000_000, "schedule": {"kind": "monthly", "day": int(dd)}, "startsOn": today})
log(bool(rule), "repeating payment created", f"next {rule.get('rule', {}).get('nextDue')}")
eq("committed per month", ok("GET", "/recurring")["committedMinor"], 2_000_000)

# dashboard and reports (derived, never stored)
dash = ok("GET", f"/dashboard?month={month}")
spent = 45_000 + 32_000 + 10_000 + 20_000
eq("dashboard spent / income", [dash["balance"]["spent"], dash["balance"]["income"]], [spent, 5_000_000])
eq("dashboard available = opening + in − out", dash["balance"]["available"], 10_000_000 + 5_000_000 - spent)
months = ok("GET", "/reports/months?range=6")
log(isinstance(months.get("months", months.get("items")), list), "reports/months answers")
log(call("GET", f"/reports/daily?month={month}").status == 200, "reports/daily answers")
log(call("GET", "/reports/category-matrix?range=6").status == 200, "reports/category-matrix answers")

# balance check → Unaccounted (README 3.6, 10.9)
transactions_now = dash["balance"]["available"]
bc = ok("POST", "/balance-check", {"bankBalanceMinor": transactions_now - 18_000})
eq("check finds a ₹180 gap", bc["check"]["gapMinor"], -18_000)
def unaccounted():
    page = ok("GET", "/transactions?src=unaccounted")
    return page if page["items"] else None


un = until(unaccounted)
log(bool(un), "grace 0 → one Unaccounted entry booked (job ran)")
if un:
    u0 = un["items"][0]
    eq("Unaccounted is a debit of ₹180", [u0["type"], u0["amountMinor"], u0["source"]], ["debit", 18_000, "unaccounted"])
    eq("balance now matches the bank", ok("GET", "/transactions")["balanceMinor"], transactions_now - 18_000)
    split = ok("POST", f"/transactions/{u0['id']}/split", {"parts": [{"amountMinor": 10_000, "tag": "food"}, {"amountMinor": 8_000}]})
    log(bool(split), "split 100 + 80 (parts add up)")

# security: sessions, 2FA-gated actions, audit, export
eq("sessions list shows this browser", any(s["current"] for s in ok("GET", "/sessions")["sessions"]), True)
au = ok("GET", "/audit?limit=20")
log(len(au["entries"]) > 0 and all("Rs." not in json.dumps(e) for e in au["entries"]), "audit log has entries, no amounts")
wait_step()
exp = ok("POST", "/account/export", {"code": code()})
log(len(exp.get("parts", [])) >= 5, "export composes every service", f"{len(exp.get('parts', []))} parts")
eq("wrong code on a sensitive action", call("DELETE", f"/devices/{dev['device']['id']}", {"code": "000000"}).status, 401)

# csrf, sign-out
eq("bad CSRF token -> 403", call("POST", "/credits", {"amountMinor": 100, "date": today, "tag": "x"}, headers={"x-csrf-token": "wrong"}).status, 403)
ok("POST", "/auth/logout", {})
eq("after sign-out the session is dead", call("GET", "/me").status, 401)

# sign back in the real way (password → authenticator)
l1 = ok("POST", "/auth/login", {"email": email, "password": password})
wait_step()
l2 = ok("POST", "/auth/2fa/verify", {"twoFactorToken": l1["twoFactorToken"], "code": code()})
eq("login: password then authenticator", l2["user"]["email"], email)
eq("and the data is all still there", ok("GET", "/transactions")["matching"] > 0, True)

# passkey sign-in (the software authenticator enrolled above)
ok("POST", "/auth/logout", {})
l3 = ok("POST", "/auth/login", {"email": email, "password": password})
po = ok("POST", "/auth/passkey/login/options", {"twoFactorToken": l3["twoFactorToken"]})
pv = call("POST", "/auth/passkey/login/verify", {"twoFactorToken": l3["twoFactorToken"], "response": authenticator.assert_(po["options"])})
log(pv.status < 300 and pv.json["user"]["email"] == email, "passkey sign-in (software authenticator)", f"status {pv.status}")

# the public edge: web app and API via the reverse proxy (only with PROXY)
if PROXY:
    page = http.get(PROXY + "/sign-in")
    log(page.status_code == 200 and "<html" in page.text.lower(), "proxy serves the web app (/sign-in)", f"status {page.status_code}")
    # a bare request: `http` still carries the signed-in cookie (cookies ignore the port, so the proxy would see it too)
    eq("proxy routes /api/* to the gateway (401 without a session)", httpx.get(PROXY + "/api/me").status_code, 401)
    eq("proxy exposes the ingest endpoint without /api", httpx.post(PROXY + "/ingest/message", json={}).status_code, 401)

print(f"\n{failures} check(s) FAILED" if failures else "\nall checks passed")
sys.exit(1 if failures else 0)
