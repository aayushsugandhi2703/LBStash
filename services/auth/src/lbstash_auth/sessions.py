"""Browser sessions: refresh-token rotation with reuse detection, revocation, the gateway check."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from fastapi import Request
from lbstash.common import COOKIES, Errors
from lbstash.contracts import SessionCheckRes, SessionDto
from lbstash.crypto import TokenError, new_hashed_token, sha256_hex, sign_access_token, verify_access_token
from lbstash.db import Tx

from .allowlist import allowed_ips, allows
from .client_info import ClientInfo
from .cookies import Tokens, new_csrf_token, parse_cookies
from .limits import SESSION_IDLE_HOURS, SESSION_MAX_DAYS
from .svc import Svc

ALIVE = (
    f's.revoked_at IS NULL AND s.expires_at > now() AND s.last_used_at > now() - make_interval(hours => {SESSION_IDLE_HOURS})'
)


@dataclass(frozen=True, slots=True)
class IssuedSession:
    sid: str
    tokens: Tokens


def _access_for(svc: Svc, sid: str, user_id: str, timezone: str) -> str:
    return sign_access_token(svc.deps.env.ACCESS_TOKEN_SECRET, sub=user_id, sid=sid, tz=timezone)


async def start_session(svc: Svc, tx: Tx, user_id: str, timezone: str, info: ClientInfo) -> IssuedSession:
    """New session family with its first refresh token. Refused from an address that is not on the user's list."""
    if not allows(await allowed_ips(tx, user_id), info.ip):
        svc.deps.log.warning('sign-in refused by address list', uid=user_id, ip=info.ip)
        raise Errors.forbidden('Sign-in is not allowed from this address')
    sid = str(uuid.uuid4())
    await tx.execute(
        'INSERT INTO sessions (id, user_id, family_id, device, ip, expires_at) '
        'VALUES ($1, $2, $1, $3, $4, now() + make_interval(days => $5))',
        [sid, user_id, info.device, info.ip, SESSION_MAX_DAYS],
    )
    refresh = await _insert_refresh_token(tx, sid, user_id)
    return IssuedSession(sid, Tokens(_access_for(svc, sid, user_id, timezone), refresh, new_csrf_token()))


async def _insert_refresh_token(tx: Tx, sid: str, user_id: str) -> str:
    t = new_hashed_token()
    await tx.execute(
        'INSERT INTO refresh_tokens (token_hash, session_id, user_id, expires_at) '
        'VALUES ($1, $2, $3, now() + make_interval(days => $4))',
        [t.hash, sid, user_id, SESSION_MAX_DAYS],
    )
    return t.token


@dataclass(frozen=True, slots=True)
class RotateResult:
    kind: Literal['ok', 'reuse', 'invalid']
    user_id: str | None = None
    tokens: IssuedSession | None = None


async def rotate_refresh(svc: Svc, tx: Tx, refresh_token: str, csrf: str | None, info: ClientInfo) -> RotateResult:
    """Swap a refresh token for a new pair. A token seen again after use was copied, so its whole family is revoked
    (the caller commits that and answers 401)."""
    digest = sha256_hex(refresh_token)
    row = await tx.maybe_one(
        f"""SELECT rt.session_id, rt.user_id, rt.used_at, rt.expires_at, ({ALIVE}) AS ok, u.timezone, u.allowed_ips
              FROM refresh_tokens rt JOIN sessions s ON s.id = rt.session_id JOIN users u ON u.id = rt.user_id
             WHERE rt.token_hash = $1 FOR UPDATE OF rt""",
        [digest],
    )
    if row is None:
        return RotateResult('invalid')
    if row['used_at'] is not None:
        await revoke_family(tx, row['session_id'], 'refresh_token_reuse')
        return RotateResult('reuse', user_id=row['user_id'])
    if not row['ok'] or row['expires_at'] <= datetime.now(UTC) or not allows(row['allowed_ips'], info.ip):
        return RotateResult('invalid')
    await tx.execute('UPDATE refresh_tokens SET used_at = now() WHERE token_hash = $1', [digest])
    await tx.execute('UPDATE sessions SET last_used_at = now(), ip = COALESCE($2, ip) WHERE id = $1', [row['session_id'], info.ip])
    refresh = await _insert_refresh_token(tx, row['session_id'], row['user_id'])
    access = _access_for(svc, row['session_id'], row['user_id'], row['timezone'])
    return RotateResult('ok', user_id=row['user_id'], tokens=IssuedSession(row['session_id'], Tokens(access, refresh, csrf or new_csrf_token())))


async def revoke_family(tx: Tx, sid: str, reason: str) -> int:
    """End a session and its whole family. Returns how many sessions ended."""
    return await tx.execute(
        'UPDATE sessions SET revoked_at = now(), revoked_reason = $2 '
        'WHERE family_id = (SELECT family_id FROM sessions WHERE id = $1) AND revoked_at IS NULL',
        [sid, reason],
    )


async def revoke_others(tx: Tx, user_id: str, except_sid: str | None, reason: str) -> int:
    """Revoke the user's live sessions except `except_sid` (None = all)."""
    return await tx.execute(
        'UPDATE sessions SET revoked_at = now(), revoked_reason = $3 '
        'WHERE user_id = $1 AND revoked_at IS NULL AND ($2::uuid IS NULL OR id <> $2::uuid)',
        [user_id, except_sid, reason],
    )


async def list_sessions(tx: Tx, user_id: str, current: str | None) -> list[SessionDto]:
    rows = await tx.many(
        f'SELECT s.id, s.device, s.ip, s.created_at, s.last_used_at FROM sessions s '
        f'WHERE s.user_id = $1 AND {ALIVE} ORDER BY s.last_used_at DESC',
        [user_id],
    )
    return [
        SessionDto(id=r['id'], device=r['device'], ip=r['ip'], created_at=r['created_at'], last_active_at=r['last_used_at'], current=r['id'] == current)
        for r in rows
    ]  # fmt: skip


async def check_session(tx: Tx, sid: str, ip: str | None = None) -> SessionCheckRes:
    """Gateway check: is the session alive, is it limited (setup unfinished or no passkey), is the caller's `ip` on the user's list."""
    row = await tx.maybe_one(
        f"""SELECT (u.setup_completed_at IS NULL OR NOT EXISTS (
                      SELECT 1 FROM auth_factors af WHERE af.user_id = u.id AND af.kind = 'passkey'
                    )) AS limited, u.allowed_ips
               FROM sessions s JOIN users u ON u.id = s.user_id
              WHERE s.id = $1 AND {ALIVE}
                AND NOT EXISTS (SELECT 1 FROM sessions f WHERE f.family_id = s.family_id AND f.revoked_at IS NOT NULL)""",
        [sid],
    )
    if row is None or not allows(row['allowed_ips'], ip):
        return SessionCheckRes(valid=False, limited=False)
    # touch at most once a minute: one write per minute for the idle limit, not per request
    await tx.execute("UPDATE sessions SET last_used_at = now() WHERE id = $1 AND last_used_at < now() - interval '1 minute'", [sid])
    return SessionCheckRes(valid=True, limited=row['limited'])


def current_sid(svc: Svc, request: Request, user_id: str) -> str | None:
    """The session id from the access cookie (None for non-browser callers)."""
    token = parse_cookies(request.headers.get('cookie')).get(COOKIES.access)
    if not token:
        return None
    try:
        claims = verify_access_token(svc.deps.env.ACCESS_TOKEN_SECRET, token)
    except TokenError:
        return None
    return claims.sid if claims.sub == user_id else None


async def session_from_refresh(tx: Tx, token: str | None) -> tuple[str, str] | None:
    """(session id, owner) for a refresh token."""
    if not token:
        return None
    r = await tx.maybe_one('SELECT session_id, user_id FROM refresh_tokens WHERE token_hash = $1', [sha256_hex(token)])
    return (r['session_id'], r['user_id']) if r else None


def require_sid(sid: str | None) -> str:
    if not sid:
        raise Errors.bad_request('This request must come from a signed-in browser')
    return sid
