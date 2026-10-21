"""Path rules: what the guard and the proxy agree a request is for (no query, no `/api`, no trailing slash)."""

import re
from typing import Final, Literal

from lbstash.contracts import API_PREFIX, CSRF_EXEMPT_PATHS, PUBLIC_PATHS, ROUTE_TABLE

# Dot segments, doubled or encoded slashes, backslashes and control characters (raw or encoded) are refused: the
# service behind us would normalise them into another path.
_UNSAFE: Final = re.compile(
    r'(^|/)(\.|%2e){1,2}(/|$)|//|\\|%5c|%2f|%[01][0-9a-f]|%7f|[\x00-\x1f\x7f]', re.IGNORECASE
)


def normalize_path(raw_url: str) -> str | None:
    """The path the gateway uses: no query, no `/api` prefix, no trailing slash. None if it could escape the route table."""
    path = raw_url.split('?', 1)[0]
    if path == API_PREFIX or path.startswith(f'{API_PREFIX}/'):
        path = path[len(API_PREFIX):] or '/'
    if not path.startswith('/') or _UNSAFE.search(path):
        return None
    if len(path) > 1 and path.endswith('/'):
        path = path[:-1]
    return path


def query_of(raw_url: str) -> str:
    """The query string with its `?` (empty when there is none)."""
    i = raw_url.find('?')
    return '' if i < 0 else raw_url[i:]


def _matches(patterns: tuple[str, ...], path: str) -> bool:
    """Entries ending in `/*` match anything below that prefix; the others match exactly."""
    for p in patterns:
        if p.endswith('/*'):
            if path.startswith(p[:-1]) and len(path) > len(p) - 1:
                return True
        elif path == p:
            return True
    return False


def is_public_path(path: str) -> bool:
    """Reachable without a session (`PUBLIC_PATHS`)."""
    return _matches(PUBLIC_PATHS, path)


def is_csrf_exempt(path: str) -> bool:
    """Mutations here skip the CSRF check (`CSRF_EXEMPT_PATHS`)."""
    return _matches(CSRF_EXEMPT_PATHS, path)


_BY_LENGTH: Final = sorted(ROUTE_TABLE, key=lambda r: len(r[0]), reverse=True)


def resolve_service(path: str, method: str) -> str | None:
    """Longest-prefix match on `ROUTE_TABLE`. `PATCH /me` (name) is auth's too; `GET /me` is composed by the gateway first."""
    for prefix, service in _BY_LENGTH:
        if path.startswith(prefix):
            return service
    if path == '/me' and method != 'GET':
        return 'auth'
    return None


Bucket = Literal['login', '2fa', 'reset', 'ingest', 'webhook', 'demo']
STRICT_BUCKETS: Final[tuple[Bucket, ...]] = ('login', '2fa', 'reset', 'ingest', 'webhook', 'demo')


def bucket_of(path: str) -> Bucket | None:
    """Which extra per-IP limit (if any) a path falls under."""
    if path == '/auth/login':
        return 'login'
    if path == '/auth/2fa/verify':
        return '2fa'
    if path == '/auth/demo':
        return 'demo'
    if path.startswith('/auth/reset/'):
        return 'reset'
    if path == '/ingest/message':
        return 'ingest'
    if path.startswith('/telegram/webhook/'):
        return 'webhook'
    return None
