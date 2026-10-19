"""Auth test harness: the real routes and workers on a throwaway database, plus a `Browser` that acts like a browser
behind the gateway (keeps cookies, checks the session with auth, forwards the user)."""

import base64
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import FastAPI

from bt.common import COOKIES
from bt.crypto import TokenError, totp_code, totp_step, verify_access_token
from bt.db.testing import TempDatabase
from bt.kit.testing import build_test_app, headers_for
from bt_auth.env import Env
from bt_auth.routes import make_routes
from bt_auth.workers import start_workers

ACCESS_SECRET = 'a' * 40
FIELD_KEY = base64.b64encode(os.urandom(32)).decode()
ORIGIN = 'http://localhost:8088'
STRONG = 'correct horse battery staple 42'
MAC_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'


@dataclass
class Mail:
    to: str
    subject: str
    text: str


@dataclass
class Res:
    status: int
    body: Any
    set_cookie: list[str]
    headers: httpx.Headers | dict[str, str]


class FakeMailer:
    """Collects mail instead of sending it."""

    def __init__(self) -> None:
        self.mails: list[Mail] = []

    async def send(self, to: str, subject: str, text: str) -> None:
        self.mails.append(Mail(to, subject, text))


@dataclass
class Account:
    user_id: str
    secret: str
    recovery_codes: list[str]


@dataclass
class Harness:
    t: TempDatabase
    app: FastAPI
    deps: Any
    mailer: FakeMailer
    clients: dict[str, Any]
    _extra: list[Any] = field(default_factory=list)

    @property
    def mails(self) -> list[Mail]:
        return self.mailer.mails

    async def app_with(self, **env: Any) -> FastAPI:
        """Another app on the same database with different env."""
        built = await build_test_app(
            service='auth', register=make_routes(self.mailer), pool=self.t.pool, env=_base_env() | env, env_model=Env,
            clients=self.clients,
        )  # fmt: skip
        self._extra.append(built)
        return built.app

    def browser(self, ip: str | None = None, ua: str | None = None, app: FastAPI | None = None) -> 'Browser':
        b = Browser(app or self.app, ip=ip, ua=ua)
        self._extra.append(b)
        return b

    async def code(self, user_id: str, secret: str, drift: int = 0) -> str:
        """A TOTP code for the secret; resets the replay guard first."""
        await self.t.admin_pool.execute('UPDATE auth.users SET last_totp_step = NULL WHERE id = $1', [user_id])
        return totp_code(secret, totp_step(datetime.now(UTC)) + drift)

    async def close(self) -> None:
        for x in self._extra:
            await x.close()


def _base_env() -> dict[str, Any]:
    return {
        'ACCESS_TOKEN_SECRET': ACCESS_SECRET, 'FIELD_KEY': FIELD_KEY, 'PUBLIC_URL': ORIGIN, 'WEBAUTHN_RP_NAME': 'Ledger',
        'MAIL_TRANSPORT': 'log', 'REGISTRATION': 'open',
    }  # fmt: skip


async def make_harness(t: TempDatabase, clients: dict[str, Any] | None = None) -> Harness:
    """The auth app (all routes, workers on an in-memory bus) over `t`, with fake clients for other services."""
    mailer = FakeMailer()
    clients = clients or {}
    built = await build_test_app(
        service='auth', register=make_routes(mailer), pool=t.pool, env=_base_env(), env_model=Env, clients=clients
    )
    await start_workers(built.deps)
    h = Harness(t, built.app, built.deps, mailer, clients)
    h._extra.append(built)
    return h


class Browser:
    """Keeps cookies and does what the gateway does per request: verify the access cookie, ask auth if the session is
    alive, forward cookies and the user id."""

    def __init__(self, app: FastAPI, ip: str | None = None, ua: str | None = None) -> None:
        self.jar: dict[str, str] = {}
        self._ua = ua or MAC_UA
        self._http = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, client=(ip or '10.0.0.1', 50000)), base_url='http://test'
        )

    async def close(self) -> None:
        await self._http.aclose()

    @property
    def access(self) -> str | None:
        return self.jar.get(COOKIES.access)

    @property
    def refresh(self) -> str | None:
        return self.jar.get(COOKIES.refresh)

    @property
    def csrf(self) -> str | None:
        return self.jar.get(COOKIES.csrf)

    def sid(self) -> str:
        assert self.access
        return verify_access_token(ACCESS_SECRET, self.access).sid

    async def call(
        self, method: str, url: str, body: Any = None, *, skip_gateway: bool = False, no_cookies: bool = False
    ) -> Res:
        user_id: str | None = None
        if self.access and not no_cookies:
            try:
                claims = verify_access_token(ACCESS_SECRET, self.access)
            except TokenError:
                pass
            else:
                chk = await self._http.post(
                    '/internal/sessions/check', json={'sid': claims.sid}, headers=headers_for(None, 'gateway')
                )
                if not skip_gateway and not chk.json()['valid']:
                    return Res(401, {'error': {'code': 'unauthorized'}}, [], {})
                user_id = claims.sub
        return await self._send(method, url, body, user_id, no_cookies)

    async def internal(self, method: str, url: str, user_id: str | None, body: Any = None) -> Res:
        """As another service would: internal token with a user, no cookies."""
        res = await self._http.request(method, url, json=body, headers=headers_for(user_id, 'telegram'))
        return Res(res.status_code, res.json() if res.content else None, [], res.headers)

    async def _send(self, method: str, url: str, body: Any, user_id: str | None, no_cookies: bool) -> Res:
        headers = {**headers_for(user_id, 'gateway', 'Asia/Kolkata', True), 'user-agent': self._ua}
        if self.jar and not no_cookies:
            headers['cookie'] = '; '.join(f'{k}={v}' for k, v in self.jar.items())
        res = await self._http.request(method, url, json=body, headers=headers)
        set_cookie = res.headers.get_list('set-cookie')
        for c in set_cookie:
            pair, *attrs = [s.strip() for s in c.split(';')]
            name, _, value = pair.partition('=')
            if 'Max-Age=0' in attrs:
                self.jar.pop(name, None)
            else:
                self.jar[name] = value
        return Res(res.status_code, res.json() if res.content else None, set_cookie, res.headers)

    async def create_account(self, h: Harness, email: str, password: str = STRONG) -> Account:
        """Register, enable the authenticator, make recovery codes: a complete, signed-in account."""
        reg = await self.call('POST', '/auth/register', {'email': email, 'password': password})
        if reg.status != 201:
            raise AssertionError(f'register failed {reg.status} {reg.body}')
        user_id = reg.body['user']['id']
        start = await self.call('POST', '/auth/2fa/enable', {})
        secret = start.body['secret']
        conf = await self.call('POST', '/auth/2fa/enable/confirm', {'code': await h.code(user_id, secret)})
        if conf.status != 200:
            raise AssertionError(f'confirm failed {conf.body}')
        rc = await self.call('POST', '/auth/recovery-codes', {})
        if rc.status != 200:
            raise AssertionError(f'recovery failed {rc.body}')
        return Account(user_id, secret, rc.body['codes'])

    async def sign_in(self, h: Harness, who: Account, email: str, password: str = STRONG) -> Res:
        """Two-step sign-in with an authenticator code."""
        step1 = await self.call('POST', '/auth/login', {'email': email, 'password': password})
        if step1.status != 200:
            return step1
        return await self.call(
            'POST', '/auth/2fa/verify', {'twoFactorToken': step1.body['twoFactorToken'], 'code': await h.code(who.user_id, who.secret)}
        )
