"""Test doubles for the gateway: a fake for each service, a network that routes to them, and a signed-in browser."""

import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from http.cookiejar import DefaultCookiePolicy
from typing import Any

import httpx
from bt.clients import create_clients
from bt.common import create_logger
from bt.crypto import InternalClaims, sign_access_token, verify_internal_token
from bt.kit import create_app, make_deps
from bt.kit.testing import TEST_SECRET, test_env_values
from bt.queue import InMemoryBus
from bt_gateway.env import Env
from bt_gateway.routes import make_register
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Receive, Scope, Send

ACCESS_SECRET = 'test-access-secret-test-access-secret!!'
USER = '8f14e45f-ceea-467a-9575-0a3b1f3f0c11'
NAMES = ('auth', 'ledger', 'ingest', 'planning', 'recurring', 'reports', 'telegram')


@dataclass
class Seen:
    method: str
    url: str
    headers: dict[str, str]
    body: str


@dataclass
class Reply:
    status: int = 200
    body: Any = None
    cookies: list[str] = field(default_factory=list)
    headers: dict[str, str] = field(default_factory=dict)


Handler = Callable[[Seen], Reply | None]


class FakeService:
    """A stand-in for one service: records every request it gets and answers from `handler` (default `{ok: true}`)."""

    def __init__(self) -> None:
        self.seen: list[Seen] = []
        self.handler: Handler = lambda _seen: None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        request = Request(scope, receive)
        query = scope['query_string'].decode()
        seen = Seen(
            request.method, scope['raw_path'].decode() + (f'?{query}' if query else ''),
            {k.lower(): v for k, v in request.headers.items()}, (await request.body()).decode(),
        )  # fmt: skip
        self.seen.append(seen)
        r = self.handler(seen) or Reply()
        response = Response(json.dumps({'ok': True} if r.body is None else r.body), r.status, r.headers, 'application/json')
        for c in r.cookies:
            response.headers.append('set-cookie', c)
        await response(scope, receive, send)

    def last(self) -> Seen:
        return self.seen[-1]

    def clear(self) -> None:
        self.seen.clear()

    def json(self, i: int = -1) -> Any:
        return json.loads(self.seen[i].body or 'null')

    def claims(self, i: int = -1) -> InternalClaims:
        return verify_internal_token(TEST_SECRET, self.seen[i].headers['x-internal-token'])

    def non_check(self) -> list[Seen]:
        """Everything but the gateway's session checks."""
        return [s for s in self.seen if s.url != '/internal/sessions/check']


class Fakes(dict[str, FakeService]):
    """The seven services by name (`fakes['ledger']`, `fakes.ledger`)."""

    def __getattr__(self, name: str) -> FakeService:
        return self[name]

    def clear(self) -> None:
        for f in self.values():
            f.clear()


class Network(httpx.AsyncBaseTransport):
    """Routes `http://<service>.test` to the fake of that name; a service in `down` refuses connections."""

    def __init__(self, fakes: Fakes) -> None:
        self.down: set[str] = set()
        # seconds a service takes before it answers
        self.slow: dict[str, float] = {}
        self._asgi = {name: httpx.ASGITransport(app=fake) for name, fake in fakes.items()}

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        name = request.url.host.removesuffix('.test')
        if name in self.down or name not in self._asgi:
            raise httpx.ConnectError('connection refused', request=request)
        if name in self.slow:
            await asyncio.sleep(self.slow[name])
        return await self._asgi[name].handle_async_request(request)


def start_fakes() -> Fakes:
    return Fakes({n: FakeService() for n in NAMES})


async def _no_sleep(_seconds: float) -> None:
    return None


class Gateway:
    """The gateway app, wired to the fakes, plus a client that talks to it in process."""

    def __init__(self, fakes: Fakes, **extra: Any) -> None:
        self.network = Network(fakes)
        values = {
            'ACCESS_TOKEN_SECRET': ACCESS_SECRET, 'UPSTREAM_TIMEOUT_MS': 2000, 'RATE_LIMIT_PER_MINUTE': 1000,
            'RATE_LIMIT_AUTH_PER_15_MIN': 5, 'RATE_LIMIT_INGEST_PER_MINUTE': 60, 'RATE_LIMIT_WEBHOOK_PER_MINUTE': 120, **extra,
        }  # fmt: skip
        env = Env.model_validate(test_env_values('gateway', **values))
        clients = create_clients('gateway', env, transport=self.network, sleep=_no_sleep)
        deps = make_deps(env=env, log=create_logger('gateway', 'silent'), bus=InMemoryBus(), clients=clients)
        self.app = create_app(deps, make_register(transport=self.network), edge=True)
        # A browser's cookie jar would feed Set-Cookie answers back into later requests; the tests send cookies themselves.
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://gateway.test')
        self.client.cookies.jar.set_policy(DefaultCookiePolicy(allowed_domains=[]))

    async def request(self, method: str, url: str, **kw: Any) -> httpx.Response:
        return await self.client.request(method, url, **kw)

    async def get(self, url: str, **kw: Any) -> httpx.Response:
        return await self.client.get(url, **kw)

    async def aclose(self) -> None:
        await self.client.aclose()
        await self.app.state.proxy_client.aclose()


def make_gateway(fakes: Fakes, **extra: Any) -> Gateway:
    return Gateway(fakes, **extra)


@dataclass
class Login:
    sid: str
    cookie: str
    csrf: str
    headers: dict[str, str]


def login(sub: str = USER, sid: str | None = None, tz: str = 'Asia/Kolkata', ttl: int = 15 * 60) -> Login:
    """A signed-in browser: valid access cookie + CSRF cookie and header. The auth fake must call its session `valid`."""
    sid = sid or str(uuid.uuid4())
    csrf = f'csrf-{uuid.uuid4()}'
    jwt = sign_access_token(ACCESS_SECRET, sub=sub, sid=sid, tz=tz, ttl_seconds=ttl)
    cookie = f'bt_access={jwt}; bt_csrf={csrf}'
    return Login(sid, cookie, csrf, {'cookie': cookie, 'x-csrf-token': csrf})


def auth_fake(
    auth: FakeService, alive: set[str], extra: Handler = lambda _s: None, limited: set[str] | None = None
) -> None:
    """Make the auth fake answer the gateway's session check from a set of live session ids."""

    def handler(s: Seen) -> Reply | None:
        if s.url == '/internal/sessions/check':
            sid = json.loads(s.body)['sid']
            return Reply(body={'valid': sid in alive, 'limited': sid in (limited or set())})
        return extra(s)

    auth.handler = handler


async def raw_status(app: Any, raw_path: bytes, headers: dict[str, str]) -> int:
    """GET with the request target exactly as written, like a socket would deliver it (an HTTP client would normalise it)."""
    from urllib.parse import unquote

    scope = {
        'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'GET', 'scheme': 'http',
        'path': unquote(raw_path.decode()), 'raw_path': raw_path, 'query_string': b'', 'root_path': '',
        'headers': [(k.lower().encode(), v.encode()) for k, v in headers.items()], 'client': ('127.0.0.1', 1),
        'server': ('gateway.test', 80),
    }  # fmt: skip
    status: list[int] = []

    async def receive() -> dict[str, Any]:
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(message: dict[str, Any]) -> None:
        if message['type'] == 'http.response.start':
            status.append(message['status'])

    await app(scope, receive, send)
    return status[0]
