"""The gateway's door: one dependency every proxied and composed route runs before it reads a body."""

import hashlib
import hmac
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final
from urllib.parse import unquote

from bt.common import COOKIES, HEADERS, AppError, Ctx, Errors
from bt.crypto import AccessClaims, TokenError, verify_access_token, verify_internal_token
from bt.kit import Deps, MemoryRateLimiter
from fastapi import Request
from fastapi.responses import JSONResponse

from .env import Env
from .paths import STRICT_BUCKETS, Bucket, bucket_of, is_csrf_exempt, is_public_path, normalize_path, query_of
from .session_cache import SessionCache

_MUTATING: Final = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})
_MINUTE: Final = 60.0


@dataclass(frozen=True, slots=True)
class GatewayInfo:
    """What the guard learned about a request (`request.state.gw`); routes and the proxy read it instead of re-parsing."""

    # Without `/api` prefix and query.
    path: str
    # The query string with its `?`, forwarded untouched.
    query: str
    # Reachable without a session (PUBLIC_PATHS).
    public: bool
    # Verified `bt_access` claims, if the cookie held a valid token (the session itself is checked separately).
    access: AccessClaims | None
    # The caller's address (leftmost `x-forwarded-for`, set by the reverse proxy; else the socket peer).
    ip: str


class RateLimited(AppError):
    """429 that also tells the client when to come back (`retry-after`, seconds)."""

    def __init__(self, retry_after: int) -> None:
        super().__init__('too_many_requests', 'Too many requests, try again later')
        self.retry_after = retry_after


async def on_rate_limited(_request: Request, exc: Exception) -> JSONResponse:
    """The standard error body plus `retry-after`."""
    assert isinstance(exc, RateLimited)
    return JSONResponse(exc.to_json(), status_code=exc.status, headers={'retry-after': str(exc.retry_after)})


class Limiter(MemoryRateLimiter):
    """`MemoryRateLimiter` that can also say how long until a refused key may try again."""

    def retry_after(self, key: str) -> int:
        hits = self._hits.get(key)
        if not hits:
            return 1
        return max(1, math.ceil(hits[0] + self._window - self._now()))


def safe_equal(a: str | None, b: str | None) -> bool:
    """Constant-time string compare (hashing first so lengths do not leak). Empty never matches."""
    if not a or not b:
        return False
    return hmac.compare_digest(hashlib.sha256(a.encode()).digest(), hashlib.sha256(b.encode()).digest())


def client_ip(request: Request) -> str:
    """The caller's address: the reverse proxy puts it first in `x-forwarded-for` (and uvicorn does the same for the socket)."""
    forwarded = request.headers.get('x-forwarded-for', '').split(',', 1)[0].strip()
    if forwarded:
        return forwarded[:64]
    return request.client.host if request.client else 'unknown'


def cookie(request: Request, name: str) -> str | None:
    """A cookie value, percent-decoded: the browser sends the CSRF cookie back through `decodeURIComponent`."""
    value = request.cookies.get(name)
    return None if value is None else unquote(value)


def raw_url(request: Request) -> str:
    """The request target as the client wrote it (not the decoded `scope["path"]`), query included."""
    scope = request.scope
    path = scope.get('raw_path') or scope['path'].encode()
    query = scope.get('query_string') or b''
    return path.decode('latin-1') + ('?' + query.decode('latin-1') if query else '')


def _is_internal(secret: str, request: Request) -> bool:
    token = request.headers.get(HEADERS.internal_token)
    if token is None:
        return False
    try:
        verify_internal_token(secret, token)
    except TokenError:
        return False
    return True


def build_guard(deps: Deps[Env]) -> Callable[[Request], Awaitable[None]]:
    """The guard dependency, in order: path check, who is this (cookie -> JWT), rate limits, session alive (cached ~10 s), setup-limited sessions, CSRF. Anything outside PUBLIC_PATHS must pass all of it."""
    env = deps.env
    sessions = SessionCache(10.0)
    general = Limiter(env.RATE_LIMIT_PER_MINUTE, _MINUTE)
    strict: dict[Bucket, Limiter] = {
        'login': Limiter(env.RATE_LIMIT_AUTH_PER_15_MIN, 15 * _MINUTE),
        '2fa': Limiter(env.RATE_LIMIT_AUTH_PER_15_MIN, 15 * _MINUTE),
        'reset': Limiter(env.RATE_LIMIT_AUTH_PER_15_MIN, 15 * _MINUTE),
        'ingest': Limiter(env.RATE_LIMIT_INGEST_PER_MINUTE, _MINUTE),
        'webhook': Limiter(env.RATE_LIMIT_WEBHOOK_PER_MINUTE, _MINUTE),
    }
    assert set(strict) == set(STRICT_BUCKETS)

    def enforce(limiter: Limiter, key: str) -> None:
        if not limiter.allow(key):
            raise RateLimited(limiter.retry_after(key))

    async def guard(request: Request) -> None:
        url = raw_url(request)
        path = normalize_path(url)
        if path is None:
            raise Errors.bad_request('Bad path')
        public = is_public_path(path)

        access: AccessClaims | None = None
        token = cookie(request, COOKIES.access)
        if token:
            try:
                access = verify_access_token(env.ACCESS_TOKEN_SECRET, token)
            except TokenError:
                access = None
        ip = client_ip(request)
        gw = GatewayInfo(path, query_of(url), public, access, ip)
        request.state.gw = gw

        # Rate limits first, so a flood of bad cookies or bad logins is counted too. Signed in: per user; otherwise per IP.
        enforce(general, f'u:{access.sub}' if access else f'ip:{ip}')
        bucket = bucket_of(path)
        if bucket:
            enforce(strict[bucket], f'ip:{ip}')

        if not public:
            # `/health/deps` is also open to other services (a valid internal token), for operators and probes.
            internal = path == '/health/deps' and access is None and _is_internal(env.INTERNAL_SECRET, request)
            if not internal:
                if access is None:
                    raise Errors.unauthorized()
                session = sessions.get(access.sid)
                if session is None:
                    # Not cached: ask auth. An outage is an error answer (never 401), so nobody is signed out by it.
                    res = await deps.clients.auth.check_session(access.sid)
                    if not res.valid:
                        raise Errors.unauthorized()
                    # Setup can finish in this very session: recheck limited sessions so stale state never rejects the next request.
                    if not res.limited:
                        sessions.remember(access.sid)
                    limited = res.limited
                else:
                    limited = session.limited
                if limited and not (path.startswith('/auth/') or (path == '/me' and request.method == 'GET')):
                    raise AppError('forbidden', 'Finish securing your account first', {'setupRequired': True})
                request.state.ctx = Ctx(user_id=access.sub, tz=access.tz, request_id=request.state.request_id)

        # Double-submit CSRF: the header must repeat the JS-readable cookie. Sign-in paths and non-browser callers are exempt.
        csrf_checked = request.method in _MUTATING and not is_csrf_exempt(path)
        if csrf_checked and not safe_equal(request.headers.get(HEADERS.csrf), cookie(request, COOKIES.csrf)):
            raise Errors.forbidden('CSRF token missing or wrong')

    return guard

