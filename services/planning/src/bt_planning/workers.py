"""Event/job consumers and cron for this service."""

from bt.common import DEFAULT_TZ, Clock, month_key, system_clock
from bt.contracts import (
    AccountDeletedEvent,
    BudgetEvaluateJob,
    CreditAddedEvent,
    RetentionSweepJob,
    TransactionChangedEvent,
    sweep_queue,
)
from bt.kit import Deps

from .evaluate import evaluate_budget
from .jobs import enqueue_evaluate
from .plans import add_credit
from .settings import read_settings

# Alerts older than this are history nobody reads.
ALERT_RETENTION = '12 months'


async def start_workers(deps: Deps, now: Clock = system_clock) -> None:
    """Register every consumer and the nightly sweep."""

    # transaction.changed -> one budget.evaluate per (user, category, period); the key collapses bursts
    async def on_transaction_changed(e: TransactionChangedEvent) -> None:
        cats = list(dict.fromkeys(c for c in e.category_ids if c is not None))  # None = Uncategorised: in no budget
        if not cats:
            return
        async with deps.as_user(e.user_id) as tx:
            tz = e.tz
            if tz is None:
                saved = await read_settings(tx, e.user_id)
                tz = saved.tz if saved and saved.tz else DEFAULT_TZ
            period = month_key(e.occurred_at, tz)
            for category_id in cats:
                has = await tx.maybe_one('SELECT 1 FROM budgets WHERE category_id = $1 AND active', [category_id])
                if has:
                    await enqueue_evaluate(deps, tx, e.user_id, category_id, period)

    await deps.bus.on_event('transaction.changed', on_transaction_changed)

    async def on_evaluate(p: BudgetEvaluateJob) -> None:
        await evaluate_budget(deps, p, now)

    # 'short' = at most one queued evaluation per key
    await deps.bus.on_job('budget.evaluate', on_evaluate, policy='short')

    # a hand-added credit with "add to plan": same once-per-transaction logic as the credit route
    async def on_credit_added(e: CreditAddedEvent) -> None:
        if e.add_to_plan and e.amount_minor > 0:
            await add_credit(deps, e.user_id, e.month, e.transaction_id, e.amount_minor)

    await deps.bus.on_event('credit.added', on_credit_added)

    async def on_account_deleted(e: AccountDeletedEvent) -> None:
        async with deps.as_user(e.user_id) as tx:
            # plan_lines and alerts go with their plan / budget
            for table in ('plans', 'budgets', 'plan_credits', 'planning_settings'):
                await tx.execute(f'DELETE FROM {table} WHERE user_id = $1', [e.user_id])

    await deps.bus.on_event('account.deleted', on_account_deleted)

    async def on_sweep(_: RetentionSweepJob) -> None:
        async with deps.as_system() as tx:
            await tx.execute(f"DELETE FROM alerts WHERE sent_at < now() - interval '{ALERT_RETENTION}'")

    sweep = sweep_queue('planning')
    await deps.bus.on_job('retention.sweep', on_sweep, queue=sweep)
    await deps.bus.schedule(sweep, '20 3 * * *')
