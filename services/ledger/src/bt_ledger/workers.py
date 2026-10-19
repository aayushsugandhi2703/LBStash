"""Event/job consumers and cron. All handlers are idempotent (at-least-once delivery)."""

from collections.abc import Awaitable, Callable
from typing import Any

from bt.common import Clock, system_clock
from bt.contracts import sweep_queue
from bt.kit import Deps

from .balance import reconcile, reconcile_due
from .maintenance import purge_user, sweep

# Queue of the 30-minute scan for checks past their grace period. No payload, so it reuses the empty `retention.sweep` job shape.
RECONCILE_SCAN_QUEUE = 'balance.reconcile.scan'


def make_workers(clock: Clock = system_clock) -> Callable[[Deps[Any]], Awaitable[None]]:
    """`clock` is injectable so tests can freeze "now"."""

    async def start(deps: Deps[Any]) -> None:
        async def on_account_deleted(p: Any) -> None:
            await purge_user(deps, p.user_id)
            deps.log.info('ledger rows purged', uid=p.user_id)

        async def on_reconcile(p: Any) -> None:
            await reconcile(deps, p.user_id, p.check_id, clock())

        async def on_scan(_p: Any) -> None:
            await reconcile_due(deps, clock())

        async def on_sweep(_p: Any) -> None:
            r = await sweep(deps, clock())
            deps.log.info('retention sweep', **r)

        await deps.bus.on_event('account.deleted', on_account_deleted)

        await deps.bus.on_job('balance.reconcile', on_reconcile)
        await deps.bus.on_job('retention.sweep', on_scan, queue=RECONCILE_SCAN_QUEUE)
        await deps.bus.schedule(RECONCILE_SCAN_QUEUE, '*/30 * * * *')

        await deps.bus.on_job('retention.sweep', on_sweep, queue=sweep_queue('ledger'))
        await deps.bus.schedule(sweep_queue('ledger'), '30 3 * * *', {}, 'Asia/Kolkata')

    return start


start_workers = make_workers()
