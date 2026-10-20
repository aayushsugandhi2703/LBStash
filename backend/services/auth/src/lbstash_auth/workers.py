"""Consumers and cron: audit.record events, the nightly sweep, the hourly deletion check."""

from lbstash.contracts import AuditRecordEvent, sweep_queue
from lbstash.kit import Deps

from .audit import record_audit_if_user
from .env import Env
from .lifecycle import delete_due_accounts, sweep_expired

# queue of the hourly account-deletion check
DELETION_QUEUE = 'auth.account-deletion'


async def start_workers(deps: Deps[Env]) -> None:
    # at-least-once; a late event for a deleted user is dropped
    async def on_audit(e: AuditRecordEvent) -> None:
        async with deps.as_system() as tx:
            await record_audit_if_user(tx, e.user_id, e.action, ip=e.ip, device_id=e.device_id, meta=e.meta)

    await deps.bus.on_event('audit.record', on_audit)

    async def sweep(_payload: object) -> None:
        out = await sweep_expired(deps)
        deps.log.info('retention sweep', **out)

    await deps.bus.on_job('retention.sweep', sweep, queue=sweep_queue('auth'))
    await deps.bus.schedule(sweep_queue('auth'), '30 2 * * *', {}, 'Asia/Kolkata')

    async def delete_due(_payload: object) -> None:
        await delete_due_accounts(deps)

    await deps.bus.on_job('retention.sweep', delete_due, queue=DELETION_QUEUE)
    await deps.bus.schedule(DELETION_QUEUE, '5 * * * *', {}, 'UTC')
