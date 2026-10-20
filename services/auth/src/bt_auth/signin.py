"""Sign-up and sign-in: register, password step, second step, refresh, logout."""

from dataclasses import dataclass
from typing import Any, Literal
from zoneinfo import ZoneInfo

from bt.common import DEFAULT_TZ, AppError, Errors, check_password, password_acceptable
from bt.contracts import AuthMethod, AuthSessionRes, PasskeyLoginOptionsRes, SetupState
from bt.crypto import dummy_hash, hash_password, needs_rehash, new_hashed_token, sha256_hex, verify_password
from bt.db import Row, Tx

from .audit import record_audit
from .client_info import ClientInfo
from .cookies import Tokens
from .factors import consume_totp, note_second_step_failure, second_step_key, use_recovery_code
from .limits import LOGIN_CHALLENGE_MINUTES, MAX_CHALLENGE_ATTEMPTS
from .passkeys import login_options, passkey_count, verify_login
from .sessions import revoke_family, rotate_refresh, session_from_refresh, start_session
from .svc import Svc
from .throttle import (
    LOGIN_EMAIL_POLICY,
    LOGIN_POLICY,
    clear_failures,
    locked_error,
    locked_for,
    record_failure,
    throttle_key,
)
from .users import USER_COLS, UserRow, find_user_by_email, load_user, session_res, setup_state
from .welcome import send_welcome

GENERIC_LOGIN_ERROR = "That email and password don't match."


@dataclass(frozen=True, slots=True)
class Issued:
    """The JSON body and the tokens to put in cookies."""

    body: AuthSessionRes
    tokens: Tokens


def password_problems(password: str, email: str) -> dict[str, str] | None:
    """The field error for an unacceptable password, None when fine."""
    c = check_password(password, email)
    if password_acceptable(c):
        return None
    if not c.len:
        return {'password': 'Use at least 12 characters'}
    if not c.common:
        return {'password': 'That password is too common'}
    return {'password': 'Do not use your email name in the password'}


def _valid_zone(tz: str) -> bool:
    try:
        ZoneInfo(tz)
    except (ValueError, OSError, LookupError):
        return False
    return True


async def register(svc: Svc, email: str, password: str, name: str | None, timezone: str | None, info: ClientInfo) -> Issued:
    problems = password_problems(password, email)
    if problems:
        raise Errors.validation(problems)
    if timezone and not _valid_zone(timezone):
        raise Errors.validation({'timezone': 'Unknown time zone'})
    password_hash = await hash_password(password)
    async with svc.deps.as_system() as tx:
        # serialize sign-ups so "first-only" and the unique e-mail hold under concurrency
        await tx.execute("SELECT pg_advisory_xact_lock(hashtext('auth:register'))")
        if svc.deps.env.REGISTRATION == 'first-only' and await tx.maybe_one('SELECT 1 FROM users LIMIT 1'):
            raise Errors.forbidden('This app already has its account. Sign in instead.')
        if await find_user_by_email(tx, email):
            raise Errors.conflict('An account with this email already exists')
        row = await tx.one(
            f'INSERT INTO users (email, password_hash, name, timezone) VALUES ($1, $2, $3, $4) RETURNING {USER_COLS}',
            [email, password_hash, name, timezone or DEFAULT_TZ],
        )
        user = UserRow(**row)
        await record_audit(tx, user.id, 'register', ip=info.ip)
        started = await start_session(svc, tx, user.id, user.timezone, info)
        result = Issued(await session_res(tx, user), started.tokens)
    # after the commit: the account exists whatever happens to the mail
    await send_welcome(svc, user.email, user.name)
    return result


@dataclass(frozen=True, slots=True)
class LoginOutcome:
    kind: Literal['challenge', 'setup']
    two_factor_token: str | None = None
    methods: tuple[AuthMethod, ...] = ()
    issued: Issued | None = None
    setup: SetupState | None = None


async def login(svc: Svc, email: str, password: str, info: ClientInfo) -> LoginOutcome:
    """Step 1: e-mail + password. Unknown e-mail and wrong password look the same from outside."""
    key_ip = throttle_key('login', email, info.ip)
    key_email = throttle_key('login-email', email)
    async with svc.deps.as_system() as tx:
        wait = max(await locked_for(tx, key_ip), await locked_for(tx, key_email))
    if wait > 0:
        raise locked_error(wait)

    async with svc.deps.as_system() as tx:
        user = await find_user_by_email(tx, email)
    matches = await verify_password(password, user.password_hash if user else await dummy_hash())
    if user is None or not matches:
        async with svc.deps.as_system() as tx:
            a = await record_failure(tx, key_ip, LOGIN_POLICY)
            b = await record_failure(tx, key_email, LOGIN_EMAIL_POLICY)
            if user:
                await record_audit(tx, user.id, 'login.failed', ip=info.ip, meta={'step': 'password'})
                if a.locked_seconds > 0 or b.locked_seconds > 0:
                    await record_audit(tx, user.id, 'login.locked', ip=info.ip, meta={'step': 'password'})
        raise Errors.unauthorized(GENERIC_LOGIN_ERROR)
    rehash = await hash_password(password) if await needs_rehash(user.password_hash) else None

    async with svc.deps.as_system() as tx:
        await clear_failures(tx, key_ip, key_email)
        if rehash:
            await tx.execute('UPDATE users SET password_hash = $2 WHERE id = $1', [user.id, rehash])
        if not user.totp_enabled_at:
            # setup unfinished: only a setup-limited session
            await record_audit(tx, user.id, 'login.ok', ip=info.ip, meta={'step': 'password', 'setup': True})
            issued = await start_session(svc, tx, user.id, user.timezone, info)
            return LoginOutcome('setup', issued=Issued(await session_res(tx, user), issued.tokens), setup=await setup_state(tx, user))
        await record_audit(tx, user.id, 'login.ok', ip=info.ip, meta={'step': 'password'})
        t = new_hashed_token()
        await tx.execute(
            "INSERT INTO challenges (user_id, kind, token_hash, ip, expires_at) "
            "VALUES ($1, 'login', $2, $3, now() + make_interval(mins => $4))",
            [user.id, t.hash, info.ip, LOGIN_CHALLENGE_MINUTES],
        )
        methods: list[AuthMethod] = ['totp', 'recovery']
        if await passkey_count(tx, user.id) > 0:
            methods.insert(1, 'passkey')
        return LoginOutcome('challenge', two_factor_token=t.token, methods=tuple(methods))


async def _find_login_challenge(tx: Tx, token: str) -> Row | None:
    return await tx.maybe_one(
        "SELECT id, user_id, attempts, webauthn_challenge FROM challenges WHERE token_hash = $1 AND kind = 'login' "
        'AND used_at IS NULL AND expires_at > now() FOR UPDATE',
        [sha256_hex(token)],
    )


def _sign_in_again() -> AppError:
    return Errors.unauthorized('That sign-in expired. Enter your password again.')


async def passkey_login_options(svc: Svc, two_factor_token: str) -> PasskeyLoginOptionsRes:
    async with svc.deps.as_system() as tx:
        ch = await _find_login_challenge(tx, two_factor_token)
        if ch is None:
            raise _sign_in_again()
        return await login_options(svc, tx, ch['id'], ch['user_id'])


@dataclass(frozen=True, slots=True)
class SecondStep:
    """The single proof a second-step request carries."""

    kind: Literal['totp', 'recovery', 'passkey']
    value: Any


async def verify_second_step(svc: Svc, two_factor_token: str, proof: SecondStep, info: ClientInfo) -> Issued:
    """Step 2: prove the second factor and create the session. Misses are counted and locked out for every method."""
    method = proof.kind
    issued: Issued | None = None
    error: AppError | None = None
    # errors are values here: failure counters must commit before the 401/423 answer
    async with svc.deps.as_system() as tx:
        ch = await _find_login_challenge(tx, two_factor_token)
        if ch is None:
            error = _sign_in_again()
        elif (wait := await locked_for(tx, second_step_key(ch['user_id']))) > 0:
            error = locked_error(wait)
        else:
            user = await load_user(tx, ch['user_id'], lock=True)
            if method == 'totp':
                ok = await consume_totp(svc, tx, user, proof.value)
            elif method == 'recovery':
                ok = await use_recovery_code(tx, user.id, proof.value)
            else:
                ok = await verify_login(svc, tx, ch, user, proof.value)
            if not ok:
                await tx.execute(
                    'UPDATE challenges SET attempts = attempts + 1, '
                    'used_at = CASE WHEN attempts + 1 >= $2 THEN now() ELSE used_at END WHERE id = $1',
                    [ch['id'], MAX_CHALLENGE_ATTEMPTS],
                )
                error = await note_second_step_failure(tx, user.id, info.ip, method)
            else:
                await tx.execute('UPDATE challenges SET used_at = now() WHERE id = $1', [ch['id']])
                await clear_failures(tx, second_step_key(user.id))
                await record_audit(tx, user.id, '2fa.ok', ip=info.ip, meta={'method': method})
                if method == 'recovery':
                    await record_audit(tx, user.id, 'recovery_code.used', ip=info.ip)
                deletion_cancelled = False
                if user.delete_after:
                    await tx.execute('UPDATE users SET delete_after = NULL WHERE id = $1', [user.id])
                    await record_audit(tx, user.id, 'delete.restored', ip=info.ip, meta={'via': 'sign-in'})
                    deletion_cancelled = True
                started = await start_session(svc, tx, user.id, user.timezone, info)
                fresh = await load_user(tx, user.id)
                body = await session_res(tx, fresh, recovery_code_used=method == 'recovery', deletion_cancelled=deletion_cancelled)
                issued = Issued(body, started.tokens)
    if error is not None:
        raise error
    assert issued is not None
    return issued


async def refresh(svc: Svc, refresh_token: str, csrf: str | None, info: ClientInfo) -> Issued | None:
    """Exchange the refresh token. None = refused (unknown, expired, revoked, or reused)."""
    async with svc.deps.as_system() as tx:
        r = await rotate_refresh(svc, tx, refresh_token, csrf, info)
        if r.kind == 'invalid':
            return None
        assert r.user_id is not None
        if r.kind == 'reuse':
            await record_audit(tx, r.user_id, 'session.revoked', ip=info.ip, meta={'reason': 'refresh_token_reuse'})
            return None
        assert r.tokens is not None
        user = await load_user(tx, r.user_id)
        return Issued(await session_res(tx, user), r.tokens.tokens)


async def logout(svc: Svc, *, refresh_token: str | None, access_sid: str | None, user_id: str | None, ip: str | None) -> None:
    """End the session named by the refresh cookie and/or the verified access cookie."""
    async with svc.deps.as_system() as tx:
        found: dict[str, str] = {}  # sid -> user id
        from_refresh = await session_from_refresh(tx, refresh_token)
        if from_refresh:
            found[from_refresh[0]] = from_refresh[1]
        if access_sid and user_id:
            found[access_sid] = user_id
        for sid, owner in found.items():
            if await revoke_family(tx, sid, 'logout') > 0:
                await record_audit(tx, owner, 'logout', ip=ip)

