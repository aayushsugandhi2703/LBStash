from bt.contracts import sweep_queue
from bt.kit import Deps

from .maintenance import purge_user, sweep


async def start_workers(deps: Deps) -> None:
    async def on_account_deleted(p) -> None:
        await purge_user(deps, p.user_id)

    await deps.bus.on_event('account.deleted', on_account_deleted)

    async def on_sweep(_p) -> None:
        deps.log.info('retention sweep', **await sweep(deps))

    await deps.bus.on_job('retention.sweep', on_sweep, queue=sweep_queue('ingest'))
    await deps.bus.schedule(sweep_queue('ingest'), '30 3 * * *', {}, 'Asia/Kolkata')
