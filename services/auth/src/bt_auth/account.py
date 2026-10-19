"""Account: profile, password, reset, e-mail change, export, deletion, internal TOTP check."""

import asyncio
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import psycopg.errors
from bt.common import Ctx, Errors, to_iso
from bt.contracts import (
    ChangeEmailRes,
    ConfirmEmailReq,
    ConfirmEmailRes,
    DeleteAccountRes,
    ExportPart,
    ExportRes,
    MeInternalRes,
    PasswordChangeRes,
    ResetVerifyRes,
    RestoreAccountRes,
    UpdateMeRes,
)
from bt.crypto import hash_password, new_hashed_token, sha256_hex, verify_password
from bt.db import Row

from .audit import record_audit
from .client_info import ClientInfo
from .factors import consume_totp, find_recovery_code, require_fresh_code, second_step_key
from .limits import DELETE_GRACE_DAYS, EMAIL_LINK_HOURS, RESET_CHALLENGE_MINUTES
from .sessions import revoke_others
from .signin import password_problems
from .svc import Svc
from .throttle import (
    LOGIN_EMAIL_POLICY,
    LOGIN_POLICY,
    PASSWORD_CHECK_POLICY,
    clear_failures,
    locked_error,
    locked_for,
    record_failure,
    throttle_key,
)
from .users import assert_setup_complete, find_user_by_email, load_user, to_user_dto


async def update_name(svc: Svc, ctx: Ctx, name: str, ip: str | None) -> UpdateMeRes:
    async with svc.deps.as_user(ctx) as tx:
        u = await load_user(tx, ctx.user_id, lock=True)
        assert_setup_complete(u)
        nxt = None if name == '' else name
        if nxt != u.name:
            await tx.execute('UPDATE users SET name = $2 WHERE id = $1', [ctx.user_id, nxt])
            await record_audit(tx, ctx.user_id, 'profile.updated', ip=ip, meta={'field': 'name'})
        return UpdateMeRes(user=to_user_dto(await load_user(tx, ctx.user_id)))


async def me(svc: Svc, ctx: Ctx) -> MeInternalRes:
    async with svc.deps.as_user(ctx) as tx:
        return MeInternalRes(user=to_user_dto(await load_user(tx, ctx.user_id)))


async def change_password(
    svc: Svc, ctx: Ctx, current_sid: str | None, current_password: str, new_password: str, code: str, ip: str | None
) -> PasswordChangeRes:
    async with svc.deps.as_user(ctx) as tx:
        user = await load_user(tx, ctx.user_id)
    assert_setup_complete(user)
    pw_key = throttle_key('pw', ctx.user_id)
    async with svc.deps.as_system() as tx:
        wait = await locked_for(tx, pw_key)
    if wait > 0:
        raise locked_error(wait)
    if not await verify_password(current_password, user.password_hash):
        async with svc.deps.as_system() as tx:
            await record_failure(tx, pw_key, PASSWORD_CHECK_POLICY)
        raise Errors.validation({'currentPassword': 'That is not your current password'})
    problems = password_problems(new_password, user.email)
    if problems:
        raise Errors.validation({'newPassword': problems['password']})
    if new_password == current_password:
        raise Errors.validation({'newPassword': 'Choose a password you have not used just now'})
    digest = await hash_password(new_password)
    # code last: a good code is spent, so catch every other mistake first
    await require_fresh_code(svc, ctx.user_id, code, ip)
    async with svc.deps.as_user(ctx) as tx:
        await tx.execute('UPDATE users SET password_hash = $2, password_changed_at = now() WHERE id = $1', [ctx.user_id, digest])
        n = await revoke_others(tx, ctx.user_id, current_sid, 'password_changed')
        await record_audit(tx, ctx.user_id, 'password.changed', ip=ip, meta={'signedOutOthers': n})
        await clear_failures(tx, pw_key)
        return PasswordChangeRes(ok=True, signed_out_others=n)


async def reset_verify(svc: Svc, email: str, recovery_code: str, info: ClientInfo) -> ResetVerifyRes:
    """Reset step 1: check e-mail + recovery code (not used up yet) and hand out a short-lived token."""
    key_ip = throttle_key('reset', email, info.ip)
    key_email = throttle_key('reset-email', email)
    async with svc.deps.as_system() as tx:
        wait = max(await locked_for(tx, key_ip), await locked_for(tx, key_email))
        if wait > 0:
            error = locked_error(wait)
        else:
            user = await find_user_by_email(tx, email)
            factor_id = await find_recovery_code(tx, user.id, recovery_code) if user else None
            if user is None or factor_id is None:
                await record_failure(tx, key_ip, LOGIN_POLICY)
                await record_failure(tx, key_email, LOGIN_EMAIL_POLICY)
                if user:
                    await record_audit(tx, user.id, 'login.failed', ip=info.ip, meta={'step': 'reset'})
                error = Errors.unprocessable("That email or recovery code isn't valid.")
            else:
                t = new_hashed_token()
                await tx.execute("DELETE FROM challenges WHERE user_id = $1 AND kind = 'reset'", [user.id])
                await tx.execute(
                    "INSERT INTO challenges (user_id, kind, token_hash, factor_id, ip, expires_at) "
                    "VALUES ($1, 'reset', $2, $3, $4, now() + make_interval(mins => $5))",
                    [user.id, t.hash, factor_id, info.ip, RESET_CHALLENGE_MINUTES],
                )
                return ResetVerifyRes(reset_token=t.token)
    raise error  # raised after the transaction so the failure counters commit


async def reset_complete(svc: Svc, reset_token: str, new_password: str, info: ClientInfo) -> None:
    """Reset step 2: set the password, use the recovery code up, sign every session out (does not sign in)."""
    expired = Errors.unprocessable('That reset expired. Start again with your recovery code.')
    async with svc.deps.as_system() as tx:
        ch = await tx.maybe_one(
            "SELECT id, user_id, factor_id FROM challenges WHERE token_hash = $1 AND kind = 'reset' "
            'AND used_at IS NULL AND expires_at > now()',
            [sha256_hex(reset_token)],
        )
    if ch is None:
        raise expired
    async with svc.deps.as_system() as tx:
        user = await load_user(tx, ch['user_id'])
    problems = password_problems(new_password, user.email)
    if problems:
        raise Errors.validation({'newPassword': problems['password']})
    digest = await hash_password(new_password)
    async with svc.deps.as_system() as tx:
        if await tx.execute('UPDATE challenges SET used_at = now() WHERE id = $1 AND used_at IS NULL', [ch['id']]) != 1 or await tx.execute(
            'UPDATE auth_factors SET used_at = now() WHERE id = $1 AND used_at IS NULL AND revoked_at IS NULL', [ch['factor_id']]
        ) != 1:
            done = False
        else:
            await tx.execute('UPDATE users SET password_hash = $2, password_changed_at = now() WHERE id = $1', [user.id, digest])
            n = await revoke_others(tx, user.id, None, 'password_reset')
            await clear_failures(
                tx, throttle_key('pw', user.id), second_step_key(user.id), throttle_key('login-email', user.email),
                throttle_key('login', user.email, info.ip),
            )  # fmt: skip
            await record_audit(tx, user.id, 'recovery_code.used', ip=info.ip)
            await record_audit(tx, user.id, 'password.reset', ip=info.ip, meta={'signedOut': n})
            done = True
    if not done:
        raise expired


async def request_email_change(svc: Svc, ctx: Ctx, new_email: str, code: str, ip: str | None) -> ChangeEmailRes:
    async with svc.deps.as_user(ctx) as tx:
        user = await load_user(tx, ctx.user_id)
    assert_setup_complete(user)
    if new_email == user.email:
        raise Errors.validation({'newEmail': 'That is already your email'})
    await require_fresh_code(svc, ctx.user_id, code, ip)
    # an address owned by another account gets the same answer and no mail, so e-mails cannot be looked up
    async with svc.deps.as_system() as tx:
        taken = await find_user_by_email(tx, new_email)
    if taken:
        return ChangeEmailRes(pending_email=new_email)
    t = new_hashed_token()
    async with svc.deps.as_user(ctx) as tx:
        await tx.execute('UPDATE users SET pending_email = $2 WHERE id = $1', [ctx.user_id, new_email])
        await tx.execute('DELETE FROM email_changes WHERE user_id = $1 AND used_at IS NULL', [ctx.user_id])
        await tx.execute(
            'INSERT INTO email_changes (user_id, new_email, token_hash, expires_at) '
            'VALUES ($1, $2, $3, now() + make_interval(hours => $4))',
            [ctx.user_id, new_email, t.hash, EMAIL_LINK_HOURS],
        )
        await record_audit(tx, ctx.user_id, 'email.change_requested', ip=ip)
    link = f'{svc.deps.env.PUBLIC_URL.removesuffix("/")}/account/confirm-email?token={t.token}'
    await svc.mailer.send(
        new_email,
        'Confirm your new Ledger email',
        'Open this link while you are signed in to Ledger to confirm your new sign-in email. '
        f'It works once and expires in {EMAIL_LINK_HOURS} hours.\n\n{link}\n\n'
        'If you did not ask for this, ignore this message: nothing changes until the link is opened.',
    )
    return ChangeEmailRes(pending_email=new_email)


async def confirm_email_change(svc: Svc, ctx: Ctx, body: ConfirmEmailReq, ip: str | None) -> ConfirmEmailRes:
    try:
        async with svc.deps.as_user(ctx) as tx:
            row = await tx.maybe_one(
                'SELECT id, new_email FROM email_changes WHERE token_hash = $1 AND user_id = $2 AND used_at IS NULL '
                'AND expires_at > now() FOR UPDATE',
                [sha256_hex(body.token), ctx.user_id],
            )
            if row is None:
                raise Errors.unprocessable('That link is not valid or has expired')
            await tx.execute('UPDATE users SET email = $2, pending_email = NULL WHERE id = $1', [ctx.user_id, row['new_email']])
            await tx.execute('UPDATE email_changes SET used_at = now() WHERE id = $1', [row['id']])
            await record_audit(tx, ctx.user_id, 'email.changed', ip=ip)
            return ConfirmEmailRes(user=to_user_dto(await load_user(tx, ctx.user_id)))
    except psycopg.errors.UniqueViolation:
        raise Errors.conflict('That email is now used by another account') from None


def _iso(d: datetime | None) -> str | None:
    return to_iso(d) if d else None


async def _auth_part(svc: Svc, ctx: Ctx) -> ExportPart:
    """auth's rows without secrets (password hash, TOTP secret, public keys, code hashes)."""
    async with svc.deps.as_user(ctx) as tx:
        u = await load_user(tx, ctx.user_id)
        passkeys = await tx.many(
            "SELECT id, label, created_at, last_used_at FROM auth_factors WHERE user_id = $1 AND kind = 'passkey' ORDER BY created_at",
            [ctx.user_id],
        )
        codes = await tx.many(
            "SELECT id, created_at, used_at FROM auth_factors WHERE user_id = $1 AND kind = 'recovery_code' ORDER BY created_at",
            [ctx.user_id],
        )
        sessions = await tx.many(
            'SELECT id, device, ip, created_at, last_used_at, expires_at, revoked_at FROM sessions WHERE user_id = $1 ORDER BY created_at',
            [ctx.user_id],
        )
        audit = await tx.many('SELECT id, at, action, ip, meta FROM audit_log WHERE user_id = $1 ORDER BY id', [ctx.user_id])
    tables: dict[str, list[dict[str, Any]]] = {
        'users': [{
            'id': u.id, 'email': u.email, 'name': u.name, 'timezone': u.timezone, 'pending_email': u.pending_email,
            'created_at': _iso(u.created_at), 'password_changed_at': _iso(u.password_changed_at),
            'authenticator_enabled_at': _iso(u.totp_enabled_at), 'delete_after': _iso(u.delete_after),
        }],
        'passkeys': [
            {'id': p['id'], 'label': p['label'], 'created_at': _iso(p['created_at']), 'last_used_at': _iso(p['last_used_at'])}
            for p in passkeys
        ],
        'recovery_codes': [{'id': c['id'], 'created_at': _iso(c['created_at']), 'used_at': _iso(c['used_at'])} for c in codes],
        'sessions': [_session_row(s) for s in sessions],
        'audit_log': [{'id': a['id'], 'at': _iso(a['at']), 'action': a['action'], 'ip': a['ip'], 'meta': a['meta']} for a in audit],
    }  # fmt: skip
    return ExportPart(service='auth', tables=tables)


def _session_row(s: Row) -> dict[str, Any]:
    return {
        'id': s['id'], 'device': s['device'], 'ip': s['ip'], 'created_at': _iso(s['created_at']),
        'last_used_at': _iso(s['last_used_at']), 'expires_at': _iso(s['expires_at']), 'revoked_at': _iso(s['revoked_at']),
    }  # fmt: skip


async def export_account(svc: Svc, ctx: Ctx, code: str, ip: str | None) -> ExportRes:
    """Everything the user has, as one document: auth's rows plus every service's export part."""
    async with svc.deps.as_user(ctx) as tx:
        user = await load_user(tx, ctx.user_id)
    assert_setup_complete(user)
    await require_fresh_code(svc, ctx.user_id, code, ip)
    c = svc.deps.clients
    # all or nothing: never a silently incomplete export
    parts: list[ExportPart] = list(
        await asyncio.gather(
            _auth_part(svc, ctx), c.ledger.export(ctx), c.planning.export(ctx), c.recurring.export(ctx),
            c.ingest.export(ctx), c.telegram.export(ctx),
        )
    )
    entries = sum(len(rows) for p in parts for rows in p.tables.values())
    now = datetime.now(UTC)
    day = now.astimezone(ZoneInfo(user.timezone)).strftime('%Y-%m-%d')
    async with svc.deps.as_user(ctx) as tx:
        await record_audit(tx, ctx.user_id, 'export', ip=ip, meta={'entries': entries})
    return ExportRes(exported_at=now, filename=f'ledger-export-{day}.json', entries=entries, parts=parts)


async def schedule_deletion(svc: Svc, ctx: Ctx, code: str, ip: str | None) -> DeleteAccountRes:
    async with svc.deps.as_user(ctx) as tx:
        user = await load_user(tx, ctx.user_id)
    assert_setup_complete(user)
    await require_fresh_code(svc, ctx.user_id, code, ip)
    async with svc.deps.as_user(ctx) as tx:
        r = await tx.one(
            'UPDATE users SET delete_after = COALESCE(delete_after, now() + make_interval(days => $2)) WHERE id = $1 RETURNING delete_after',
            [ctx.user_id, DELETE_GRACE_DAYS],
        )
        await record_audit(tx, ctx.user_id, 'delete.scheduled', ip=ip)
        return DeleteAccountRes(delete_after=r['delete_after'])


async def restore_account(svc: Svc, ctx: Ctx, ip: str | None) -> RestoreAccountRes:
    async with svc.deps.as_user(ctx) as tx:
        u = await load_user(tx, ctx.user_id, lock=True)
        assert_setup_complete(u)
        if u.delete_after:
            await tx.execute('UPDATE users SET delete_after = NULL WHERE id = $1', [ctx.user_id])
            await record_audit(tx, ctx.user_id, 'delete.restored', ip=ip, meta={'via': 'restore'})
        return RestoreAccountRes(user=to_user_dto(await load_user(tx, ctx.user_id)))


async def verify_totp_for_service(svc: Svc, ctx: Ctx, code: str) -> None:
    """Verify a TOTP code for another service (e.g. Telegram /signin); the caller counts its own failures."""
    async with svc.deps.as_user(ctx) as tx:
        user = await load_user(tx, ctx.user_id, lock=True)
        ok = await consume_totp(svc, tx, user, code)
    if not ok:
        raise Errors.two_factor_invalid()

