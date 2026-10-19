"""`recurring.post` every 5 minutes, `account.deleted`, and the nightly retention sweep (nothing to expire here yet)."""

from collections.abc import Awaitable, Callable
from typing import Any

from bt.common import Clock, system_clock
from bt.contracts import sweep_queue
from bt.kit import Deps

from .posting import make_tz_resolver, post_due_rules
from .rules import delete_all_for


def make_workers(clock: Clock = system_clock) -> Callable[[Deps[Any]], Awaitable[None]]:
    """`start_workers(deps)` with an injectable clock for tests."""

    async def start_workers(deps: Deps[Any]) -> None:
        tz_of = make_tz_resolver(deps, clock)

        async def post(_payload: Any) -> None:
            res = await post_due_rules(deps, clock, tz_of)
            if res['handled'] or res['failed']:
                deps.log.info('recurring.post', handled=res['handled'], failed=res['failed'])

        await deps.bus.on_job('recurring.post', post, policy='short')
        await deps.bus.schedule('recurring.post', '*/5 * * * *')

        async def account_deleted(p: Any) -> None:
            await delete_all_for(deps, p.user_id)

        await deps.bus.on_event('account.deleted', account_deleted)

        async def sweep(_payload: Any) -> None:
            return None

        await deps.bus.on_job('retention.sweep', sweep, queue=sweep_queue('recurring'))
        await deps.bus.schedule(sweep_queue('recurring'), '30 3 * * *')

    return start_workers


start_workers = make_workers()
