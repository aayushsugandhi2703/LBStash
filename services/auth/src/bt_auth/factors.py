"""Second factors: authenticator (TOTP), recovery codes, and the fresh-code check."""

from dataclasses import dataclass
from typing import Literal

from bt.common import AppError, Errors
from bt.contracts import (
    RECOVERY_CODE_COUNT,
    FactorsRes,
    PasskeyDto,
    RecoveryCodesFactor,
    RecoveryCodesRes,
    SetupState,
    TotpFactor,
    TwoFactorEnableConfirmRes,
    TwoFactorEnableStartRes,
)
from bt.crypto import (
    generate_recovery_codes,
    generate_totp_secret,
    normalize_recovery_code,
    otpauth_uri,
    sha256_hex,
    verify_totp,
)
from bt.db import Tx

from .audit import record_audit
from .svc import Svc
from .throttle import SECOND_STEP_POLICY, clear_failures, locked_error, locked_for, record_failure, throttle_key
from .users import UserRow, load_user, recovery_codes_left, setup_state


def second_step_key(user_id: str) -> str:
    return throttle_key('2fa', user_id)


async def consume_totp(svc: Svc, tx: Tx, user: UserRow, code: str) -> bool:
    """Check a TOTP code and burn its time step in the same statement, so it (or any older one) cannot be reused."""
    if not user.totp_secret_enc:
        return False
    secret = svc.cipher.decrypt_string(user.totp_secret_enc, user.id)
    step = verify_totp(secret, code, after_step=user.last_totp_step)
    if step is None:
        return False
    n = await tx.execute(
        'UPDATE users SET last_totp_step = $2 WHERE id = $1 AND (last_totp_step IS NULL OR last_totp_step < $2)', [user.id, step]
    )
    return n == 1


async def note_second_step_failure(tx: Tx, user_id: str, ip: str | None, method: str) -> AppError:
    """Count a wrong answer inside `tx` (which must commit) and build the error to raise afterwards."""
    r = await record_failure(tx, second_step_key(user_id), SECOND_STEP_POLICY)
    await record_audit(tx, user_id, '2fa.failed', ip=ip, meta={'method': method})
    if r.locked_seconds > 0:
        await record_audit(tx, user_id, 'login.locked', ip=ip, meta={'step': 'second'})
        return locked_error(r.locked_seconds)
    return AppError('two_factor_invalid', 'That code did not work', {'attemptsLeft': r.attempts_left})


async def fail_second_step(svc: Svc, user_id: str, ip: str | None, method: str) -> AppError:
    """Same, in its own transaction so the failure sticks even though the request fails."""
    async with svc.deps.as_system() as tx:
        return await note_second_step_failure(tx, user_id, ip, method)


@dataclass(frozen=True, slots=True)
class _Checked:
    kind: Literal['wait', 'no-authenticator', 'checked']
    wait: int = 0
    ok: bool = False


async def require_fresh_code(svc: Svc, user_id: str, code: str | None, ip: str | None = None) -> None:
    """The fresh-code check for sensitive actions. Missing code: two_factor_required; wrong, replayed or throttled:
    two_factor_invalid / locked. Do the request's other validations first: a good code is spent even if the action fails."""
    if not code:
        raise Errors.two_factor_required()
    async with svc.deps.as_user(user_id) as tx:
        wait = await locked_for(tx, second_step_key(user_id))
        if wait > 0:
            outcome = _Checked('wait', wait=wait)
        else:
            user = await load_user(tx, user_id, lock=True)
            if not user.totp_secret_enc:
                outcome = _Checked('no-authenticator')
            else:
                outcome = _Checked('checked', ok=await consume_totp(svc, tx, user, code))
    if outcome.kind == 'wait':
        raise locked_error(outcome.wait)
    if outcome.kind == 'no-authenticator':
        raise Errors.forbidden('Set up your authenticator first')
    if not outcome.ok:
        raise await fail_second_step(svc, user_id, ip, 'totp')
    async with svc.deps.as_system() as tx:
        await clear_failures(tx, second_step_key(user_id))


async def use_recovery_code(tx: Tx, user_id: str, text: str) -> bool:
    """Use up a recovery code. True when it existed and was unused."""
    n = await tx.execute(
        "UPDATE auth_factors SET used_at = now() WHERE user_id = $1 AND kind = 'recovery_code' AND code_hash = $2 "
        'AND used_at IS NULL AND revoked_at IS NULL',
        [user_id, sha256_hex(normalize_recovery_code(text))],
    )
    return n == 1


async def find_recovery_code(tx: Tx, user_id: str, text: str) -> str | None:
    r = await tx.maybe_one(
        "SELECT id FROM auth_factors WHERE user_id = $1 AND kind = 'recovery_code' AND code_hash = $2 "
        'AND used_at IS NULL AND revoked_at IS NULL',
        [user_id, sha256_hex(normalize_recovery_code(text))],
    )
    return r['id'] if r else None


async def make_recovery_codes(tx: Tx, user: UserRow, ip: str | None) -> tuple[list[str], SetupState]:
    """Replace all recovery codes. Returns the plain codes, shown to the user once."""
    codes = generate_recovery_codes(RECOVERY_CODE_COUNT)
    await tx.execute("DELETE FROM auth_factors WHERE user_id = $1 AND kind = 'recovery_code'", [user.id])
    for c in codes:
        await tx.execute(
            "INSERT INTO auth_factors (user_id, kind, code_hash) VALUES ($1, 'recovery_code', $2)",
            [user.id, sha256_hex(normalize_recovery_code(c))],
        )
    # setup is done once the authenticator is on and a recovery set exists
    if user.totp_enabled_at and not user.setup_completed_at:
        await tx.execute('UPDATE users SET setup_completed_at = now() WHERE id = $1', [user.id])
    await record_audit(tx, user.id, 'recovery_codes.regenerated', ip=ip)
    return codes, await setup_state(tx, await load_user(tx, user.id))


async def regenerate_recovery_codes(svc: Svc, user_id: str, code: str | None, ip: str | None) -> RecoveryCodesRes:
    """First-time setup needs no code (the authenticator was just proven); afterwards a fresh one."""
    async with svc.deps.as_user(user_id) as tx:
        u = await load_user(tx, user_id)
        if not u.totp_enabled_at:
            raise Errors.forbidden('Set up your authenticator first')
        first = u.setup_completed_at is None
    if not first:
        await require_fresh_code(svc, user_id, code, ip)
    async with svc.deps.as_user(user_id) as tx:
        user = await load_user(tx, user_id, lock=True)
        codes, setup = await make_recovery_codes(tx, user, ip)
        return RecoveryCodesRes(codes=codes, remaining=RECOVERY_CODE_COUNT, setup=setup)


async def start_totp_enable(svc: Svc, user_id: str, current_code: str | None, ip: str | None) -> TwoFactorEnableStartRes:
    """Begin (or replace) the authenticator. Replacing needs a fresh code from the old one."""
    async with svc.deps.as_user(user_id) as tx:
        user0 = await load_user(tx, user_id)
    if user0.totp_enabled_at:
        await require_fresh_code(svc, user_id, current_code, ip)
    secret = generate_totp_secret()
    async with svc.deps.as_user(user_id) as tx:
        await tx.execute('UPDATE users SET totp_pending_enc = $2 WHERE id = $1', [user_id, svc.cipher.encrypt_string(secret, user_id)])
    return TwoFactorEnableStartRes(secret=secret, otpauth_uri=otpauth_uri('Ledger', user0.email, secret))


async def confirm_totp_enable(svc: Svc, user_id: str, code: str, ip: str | None) -> TwoFactorEnableConfirmRes:
    """Confirm the new authenticator with a code from its secret."""
    async with svc.deps.as_user(user_id) as tx:
        wait = await locked_for(tx, second_step_key(user_id))
        if wait > 0:
            raise locked_error(wait)
        user = await load_user(tx, user_id, lock=True)
        if not user.totp_pending_enc:
            raise Errors.bad_request('Start the authenticator setup first')
        secret = svc.cipher.decrypt_string(user.totp_pending_enc, user_id)
        step = verify_totp(secret, code, after_step=user.last_totp_step)
        done: SetupState | None = None
        if step is not None:
            replaced = user.totp_enabled_at is not None
            await tx.execute(
                'UPDATE users SET totp_secret_enc = totp_pending_enc, totp_pending_enc = NULL, totp_enabled_at = now(), '
                'last_totp_step = $2 WHERE id = $1',
                [user_id, step],
            )
            if await recovery_codes_left(tx, user_id) > 0 and not user.setup_completed_at:
                await tx.execute('UPDATE users SET setup_completed_at = now() WHERE id = $1', [user_id])
            await record_audit(tx, user_id, '2fa.replaced' if replaced else '2fa.enabled', ip=ip)
            done = await setup_state(tx, await load_user(tx, user_id))
    if done is None:
        raise await fail_second_step(svc, user_id, ip, 'totp')
    async with svc.deps.as_system() as tx:
        await clear_failures(tx, second_step_key(user_id))
    return TwoFactorEnableConfirmRes(setup=done)


async def factors_of(svc: Svc, user_id: str) -> FactorsRes:
    async with svc.deps.as_user(user_id) as tx:
        u = await load_user(tx, user_id)
        keys = await tx.many(
            "SELECT id, label, created_at, last_used_at FROM auth_factors WHERE user_id = $1 AND kind = 'passkey' ORDER BY created_at",
            [user_id],
        )
        return FactorsRes(
            totp=TotpFactor(enabled=u.totp_enabled_at is not None, since=u.totp_enabled_at),
            passkeys=[
                PasskeyDto(id=p['id'], label=p['label'] or 'Passkey', created_at=p['created_at'], last_used_at=p['last_used_at'])
                for p in keys
            ],
            recovery_codes=RecoveryCodesFactor(remaining=await recovery_codes_left(tx, user_id), total=RECOVERY_CODE_COUNT),
            password_changed_at=u.password_changed_at,
            setup=await setup_state(tx, u),
        )  # fmt: skip
