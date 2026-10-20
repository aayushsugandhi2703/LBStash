"""HS256 tokens: the browser access token (issuer `lbstash-auth`) and the service-to-service token (issuer `lbstash-internal`)."""

import time
from dataclasses import dataclass
from typing import Any

import jwt as pyjwt


class TokenError(pyjwt.InvalidTokenError):
    """Malformed, forged, expired, wrong issuer, or missing claims."""


def _decode(secret: str, token: str, issuer: str) -> dict[str, Any]:
    try:
        return pyjwt.decode(
            token, secret.encode(), algorithms=['HS256'], issuer=issuer, options={'require': ['exp', 'iss']}
        )
    except pyjwt.PyJWTError as e:
        raise TokenError(str(e)) from e


def _encode(secret: str, claims: dict[str, Any], issuer: str, ttl_seconds: int) -> str:
    now = int(time.time())
    return pyjwt.encode({**claims, 'iss': issuer, 'iat': now, 'exp': now + ttl_seconds}, secret.encode(), algorithm='HS256')


@dataclass(frozen=True, slots=True)
class AccessClaims:
    """Browser access token: signed by auth, verified by the gateway."""

    sub: str
    sid: str
    tz: str


def sign_access_token(secret: str, *, sub: str, sid: str, tz: str, ttl_seconds: int = 15 * 60) -> str:
    return _encode(secret, {'sub': sub, 'sid': sid, 'tz': tz}, 'lbstash-auth', ttl_seconds)


def verify_access_token(secret: str, token: str) -> AccessClaims:
    """Raises `TokenError` unless signature, issuer, expiry and claims are valid."""
    p = _decode(secret, token, 'lbstash-auth')
    if not p.get('sub') or not isinstance(p.get('sid'), str) or not isinstance(p.get('tz'), str):
        raise TokenError('bad claims')
    return AccessClaims(p['sub'], p['sid'], p['tz'])


@dataclass(frozen=True, slots=True)
class InternalClaims:
    """Carried by every internal call. `user_id`/`tz` are absent for system work. `proxied` is set only by the gateway, so such calls can never reach `/internal/*`."""

    svc: str
    user_id: str | None = None
    tz: str | None = None
    request_id: str | None = None
    proxied: bool = False


def sign_internal_token(
    secret: str,
    *,
    svc: str,
    user_id: str | None = None,
    tz: str | None = None,
    request_id: str | None = None,
    proxied: bool = False,
    ttl_seconds: int = 60,
) -> str:
    claims: dict[str, Any] = {'svc': svc}
    if user_id:
        claims['sub'] = user_id
    if tz:
        claims['tz'] = tz
    if request_id:
        claims['rid'] = request_id
    if proxied:
        claims['px'] = 1
    return _encode(secret, claims, 'lbstash-internal', ttl_seconds)


def verify_internal_token(secret: str, token: str) -> InternalClaims:
    """Raises `TokenError` unless signature, issuer, expiry and claims are valid."""
    p = _decode(secret, token, 'lbstash-internal')
    if not isinstance(p.get('svc'), str):
        raise TokenError('bad claims')
    return InternalClaims(
        svc=p['svc'],
        user_id=p.get('sub'),
        tz=p['tz'] if isinstance(p.get('tz'), str) else None,
        request_id=p['rid'] if isinstance(p.get('rid'), str) else None,
        proxied=p.get('px') == 1,
    )
