"""Session cookies, all SameSite=Strict, `Secure` only on https:

- access: HttpOnly, Path=/, 15 minutes
- refresh: HttpOnly, Path=/api/auth
- csrf: readable by JS; sent back as x-csrf-token and compared by the gateway
"""

from dataclasses import dataclass

from bt.common import COOKIES
from bt.crypto import random_token

from .env import Env, is_secure_url
from .limits import ACCESS_TTL_SECONDS, SESSION_MAX_DAYS

REFRESH_COOKIE_PATH = '/api/auth'


@dataclass(frozen=True, slots=True)
class Tokens:
    access: str
    refresh: str
    csrf: str


def _serialize(name: str, value: str, *, max_age: int, path: str, http_only: bool, secure: bool) -> str:
    parts = [f'{name}={value}', f'Path={path}', f'Max-Age={max_age}', 'SameSite=Strict']
    if http_only:
        parts.append('HttpOnly')
    if secure:
        parts.append('Secure')
    return '; '.join(parts)


def parse_cookies(header: str | None) -> dict[str, str]:
    """Cookie header -> dict; the first occurrence of a name wins."""
    out: dict[str, str] = {}
    for part in (header or '').split(';'):
        i = part.find('=')
        if i < 0:
            continue
        k = part[:i].strip()
        if k and k not in out:
            out[k] = part[i + 1 :].strip()
    return out


def new_csrf_token() -> str:
    return random_token(24)


def session_cookies(env: Env, t: Tokens) -> list[str]:
    """Set-Cookie header values for a fresh or renewed session."""
    secure = is_secure_url(env)
    life = SESSION_MAX_DAYS * 86400
    return [
        _serialize(COOKIES.access, t.access, max_age=ACCESS_TTL_SECONDS, path='/', http_only=True, secure=secure),
        _serialize(COOKIES.refresh, t.refresh, max_age=life, path=REFRESH_COOKIE_PATH, http_only=True, secure=secure),
        _serialize(COOKIES.csrf, t.csrf, max_age=life, path='/', http_only=False, secure=secure),
    ]


def cleared_cookies(env: Env) -> list[str]:
    """Set-Cookie header values that remove all three cookies."""
    secure = is_secure_url(env)
    return [
        _serialize(COOKIES.access, '', max_age=0, path='/', http_only=True, secure=secure),
        _serialize(COOKIES.refresh, '', max_age=0, path=REFRESH_COOKIE_PATH, http_only=True, secure=secure),
        _serialize(COOKIES.csrf, '', max_age=0, path='/', http_only=False, secure=secure),
    ]
