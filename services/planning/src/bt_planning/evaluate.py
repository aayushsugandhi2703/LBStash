"""`budget.evaluate`: recompute one limit for one period and fire its alerts once."""

import uuid
from typing import Literal

from bt.clients import CallAs
from bt.common import DEFAULT_TZ, AppError, Clock, Ctx, is_month_key, month_key, reaches_pct
from bt.contracts import BudgetEvaluateJob
from bt.kit import Deps

from .figures import effective_alert_pct
from .ledger import category_names, month_spend
from .settings import load_settings


async def _zone_of(deps: Deps, user_id: str, saved: str | None) -> str:
    """Zone for work no request started: saved from their last request, else auth, else the default."""
    if saved:
        return saved
    try:
        return (await deps.clients.auth.me(CallAs(user_id=user_id))).user.timezone
    except AppError:  # the clients map every failure (unreachable, timeout, bad answer) to an AppError
        return DEFAULT_TZ


async def evaluate_budget(deps: Deps, p: BudgetEvaluateJob, now: Clock) -> Literal['fired', 'skipped']:
    """Recompute one limit for one period; write the alert row once per (budget, period, level). Safe to rerun. Only the current period fires."""
    if not is_month_key(p.period_key):
        return 'skipped'
    async with deps.as_user(p.user_id) as tx:
        budget = await tx.maybe_one(
            'SELECT id, limit_minor, warn_pct FROM budgets WHERE category_id = $1 AND active', [p.category_id]
        )
        if budget is None:
            return 'skipped'
        settings = await load_settings(tx, p.user_id)
        have = {
            r['level']
            for r in await tx.many(
                'SELECT level FROM alerts WHERE budget_id = $1 AND period_key = $2', [budget['id'], p.period_key]
            )
        }
    tz = await _zone_of(deps, p.user_id, settings.tz)
    if month_key(now(), tz) != p.period_key:
        return 'skipped'
    ctx = Ctx(user_id=p.user_id, tz=tz, request_id=str(uuid.uuid4()))

    spent = (await month_spend(deps, ctx, p.period_key)).get(p.category_id, 0)
    limit = budget['limit_minor']
    alert_pct = effective_alert_pct(budget['warn_pct'], settings.alert_level)
    # one push per run: the highest level reached ('fast' never pushes)
    level = 'exceeded' if reaches_pct(spent, limit, 100) else 'alert' if reaches_pct(spent, limit, alert_pct) else None
    if level is None or level in have:
        return 'skipped'

    category_name = (await category_names(deps, ctx)).get(p.category_id, '')
    pct = (spent * 100) // limit
    async with deps.as_user(p.user_id) as tx:
        # edited since we read it: that edit queued its own evaluation, let it decide
        still = await tx.maybe_one(
            'SELECT limit_minor, warn_pct, active FROM budgets WHERE id = $1 FOR UPDATE', [budget['id']]
        )
        if not still or not still['active'] or still['limit_minor'] != limit or still['warn_pct'] != budget['warn_pct']:
            return 'skipped'
        ins = await tx.maybe_one(
            """INSERT INTO alerts (user_id, budget_id, period_key, level, pct, category_name) VALUES ($1, $2, $3, $4, $5, $6)
               ON CONFLICT (budget_id, period_key, level) DO NOTHING RETURNING id""",
            [p.user_id, budget['id'], p.period_key, level, pct, category_name],
        )
        if ins is None:
            return 'skipped'
        await deps.bus.emit(
            tx,
            'alert.created',
            {
                'userId': p.user_id, 'alertId': ins['id'], 'budgetId': budget['id'], 'categoryId': p.category_id,
                'categoryName': category_name, 'level': level, 'periodKey': p.period_key, 'pct': pct,
            },
        )  # fmt: skip
        return 'fired'
