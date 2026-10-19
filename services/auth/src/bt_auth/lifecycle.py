"""Scheduled account deletion and the nightly clean-up of expired rows."""

from typing import Any

from bt.kit import Deps

from .env import Env
from .limits import SESSION_IDLE_HOURS


async def delete_due_accounts(deps: Deps[Env], limit: int = 100) -> int:
    """Hard-delete accounts past their grace period. `account.deleted` is emitted in the same transaction. One transaction per user, so one failure never blocks the rest."""
    async with deps.as_system() as tx:
        due = await tx.many(
            'SELECT id FROM users WHERE delete_after IS NOT NULL AND delete_after <= now() ORDER BY delete_after LIMIT $1', [limit]
        )
    deleted = 0
    for row in due:
        uid = row['id']
        try:
            async with deps.as_system() as tx:
                locked = await tx.query(
                    'SELECT 1 FROM users WHERE id = $1 AND delete_after IS NOT NULL AND delete_after <= now() FOR UPDATE SKIP LOCKED',
                    [uid],
                )
                if not locked:
                    continue  # restored meanwhile, or another replica has it
                await deps.bus.emit(tx, 'account.deleted', {'userId': uid})
                await tx.execute('DELETE FROM users WHERE id = $1', [uid])  # sessions, tokens, factors, challenges cascade
                await tx.query('SELECT purge_user_audit($1)', [uid])
            deleted += 1
        except Exception as e:  # noqa: BLE001 - retried next hour; must not block the others
            deps.log.error('account deletion failed, will retry', err=type(e).__name__, uid=uid)
    if deleted > 0:
        deps.log.info('accounts deleted', deleted=deleted)
    return deleted


async def sweep_expired(deps: Deps[Env]) -> dict[str, int]:
    """Delete expired sessions, tokens, challenges, e-mail links and throttle counters."""
    out: dict[str, int] = {}
    async with deps.as_system() as tx:
        out['sessions'] = await tx.execute(
            f"""DELETE FROM sessions WHERE expires_at < now() - interval '1 day'
                   OR revoked_at < now() - interval '30 days'
                   OR last_used_at < now() - make_interval(hours => {SESSION_IDLE_HOURS}) - interval '30 days'"""
        )
        out['refresh_tokens'] = await tx.execute("DELETE FROM refresh_tokens WHERE expires_at < now() - interval '1 day'")
        out['challenges'] = await tx.execute("DELETE FROM challenges WHERE expires_at < now() - interval '1 day'")
        out['email_changes'] = await tx.execute("DELETE FROM email_changes WHERE expires_at < now() - interval '7 days'")
        out['login_throttle'] = await tx.execute(
            "DELETE FROM login_throttle WHERE last_failure_at < now() - interval '1 day' "
            'AND (locked_until IS NULL OR locked_until < now())'
        )
    purge: Any = getattr(deps.bus, 'purge_outbox', None)
    if callable(purge):
        out['outbox'] = await purge()
    return out
