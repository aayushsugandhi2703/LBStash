"""Event and job consumers, and cron."""

from collections.abc import Awaitable, Callable
from typing import Any

from bt.contracts import sweep_queue
from bt.kit import Deps

from .link import purge_user
from .prompts import (
    digest_for,
    digest_tick,
    enqueue_sync,
    on_alert_created,
    on_transaction_changed,
    on_unparsed_created,
    send_prompt,
    sync_prompt,
)
from .runtime import Runtime, RuntimeOptions, shared_runtime


async def sweep(rt: Runtime) -> dict[str, int]:
    """Nightly: end idle sessions, drop expired pairings, re-hide stuck Reveals, delete old finished prompts."""
    now = rt.clock()
    async with rt.deps.as_system() as tx:
        sessions = await tx.execute(
            """UPDATE telegram_sessions s SET ended_at = $1, end_reason = 'idle'
                 FROM telegram_links l LEFT JOIN telegram_settings st ON st.user_id = l.user_id
                WHERE s.link_id = l.id AND s.ended_at IS NULL
                  AND s.last_seen_at <= $1::timestamptz - (COALESCE(st.session_idle_days, 30) * interval '1 day')""",
            [now],
        )
        pairings = await tx.execute("DELETE FROM telegram_pairings WHERE expires_at < $1::timestamptz - interval '1 hour'", [now])
        stuck = await tx.many(
            "SELECT id FROM telegram_prompts WHERE revealed_until IS NOT NULL AND revealed_until < $1::timestamptz - interval '1 minute'", [now]
        )
        for p in stuck:
            await enqueue_sync(rt, tx, p['id'])
        prompts = await tx.execute(
            """DELETE FROM telegram_prompts WHERE status IN ('tagged','auto_tagged','expired','failed')
                  AND created_at < $1::timestamptz - interval '90 days'""",
            [now],
        )
    # old published outbox rows (the in-memory test bus has none)
    purge = getattr(rt.deps.bus, 'purge_outbox', None)
    if callable(purge):
        await purge()
    return {'sessions': sessions, 'pairings': pairings, 'reveals': len(stuck), 'prompts': prompts}


def make_workers(opts: RuntimeOptions | None = None) -> Callable[[Deps[Any]], Awaitable[None]]:
    """`opts` lets tests inject a fake Bot API and clock."""

    async def start(deps: Deps[Any]) -> None:
        rt = shared_runtime(deps, opts)
        bus = deps.bus

        async def on_account_deleted(p: Any) -> None:
            await purge_user(rt, p.user_id)

        async def on_send(p: Any) -> None:
            await send_prompt(rt, p.prompt_id)

        async def on_sync(p: Any) -> None:
            await sync_prompt(rt, p.prompt_id)

        async def on_digest(p: Any) -> None:
            if p.user_id:
                await digest_for(rt, p.user_id)
            else:
                await digest_tick(rt)

        async def on_sweep(_p: Any) -> None:
            deps.log.info('retention sweep', **await sweep(rt))

        await bus.on_event('transaction.changed', lambda p: on_transaction_changed(rt, p))
        await bus.on_event('alert.created', lambda p: on_alert_created(rt, p))
        await bus.on_event('unparsed.created', lambda p: on_unparsed_created(rt, p))
        await bus.on_event('account.deleted', on_account_deleted)

        await bus.on_job('telegram.send', on_send)
        await bus.on_job('telegram.sync_prompt', on_sync)
        await bus.on_job('telegram.digest', on_digest)
        await bus.on_job('retention.sweep', on_sweep, queue=sweep_queue('telegram'))

        # hourly: each user's digest goes out in their chosen hour, in their zone
        await bus.schedule('telegram.digest', '0 * * * *', {})
        await bus.schedule(sweep_queue('telegram'), '30 3 * * *', {})

    return start


start_workers = make_workers()
