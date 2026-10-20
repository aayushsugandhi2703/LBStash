"""Queueing `budget.evaluate`."""

from lbstash.contracts import BudgetEvaluateJob
from lbstash.db import Queryable
from lbstash.kit import Deps


def evaluate_key(user_id: str, category_id: str, period_key: str) -> str:
    """Same key for a burst of changes to one budget and period, so they collapse into one job."""
    return f'{user_id}:{category_id}:{period_key}'


async def enqueue_evaluate(deps: Deps, tx: Queryable, user_id: str, category_id: str, period_key: str) -> None:
    """Queue `budget.evaluate` in the caller's transaction, so it commits with the change."""
    await deps.bus.enqueue(
        tx,
        'budget.evaluate',
        BudgetEvaluateJob(user_id=user_id, category_id=category_id, period_key=period_key),
        key=evaluate_key(user_id, category_id, period_key),
    )
