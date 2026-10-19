"""Limits: list with figures, create, patch, delete."""

import asyncio
from typing import Any

import psycopg.errors
from bt.common import Clock, Ctx, Errors, MonthKey, month_key, reaches_pct
from bt.contracts import BudgetCreateReq, BudgetDto, BudgetPatchReq, BudgetsRes
from bt.db import Tx
from bt.kit import Deps

from .figures import budget_figures, effective_alert_pct
from .jobs import enqueue_evaluate
from .ledger import category_names, month_spend, resolve_ref
from .plans import allocation_for
from .settings import SettingsRow, load_settings

COLS = 'id, category_id, limit_minor, warn_pct, active'

Row = dict[str, Any]


def _to_dto(r: Row, name: str, spent: int, s: SettingsRow, month: MonthKey, tz: str, now: Clock) -> BudgetDto:
    f = budget_figures(
        spent=spent, limit=r['limit_minor'], alert_pct=effective_alert_pct(r['warn_pct'], s.alert_level),
        month=month, tz=tz, now=now, warn_on_pace=s.warn_on_pace,
    )  # fmt: skip
    return BudgetDto(
        id=r['id'], category_id=r['category_id'], category_name=name, limit_minor=r['limit_minor'], period='monthly',
        warn_pct=r['warn_pct'], active=r['active'], spent_minor=spent, pct=f.pct, projected_minor=f.projected_minor, status=f.status,
    )  # fmt: skip


async def list_budgets(deps: Deps, ctx: Ctx, month: MonthKey | None, now: Clock) -> BudgetsRes:
    """Every limit with spend, pct, projection and status for `month` (default: current), fullest first."""
    m = month or month_key(now(), ctx.tz)
    async with deps.as_user(ctx) as tx:
        settings = await load_settings(tx, ctx.user_id, ctx.tz)
        rows = await tx.many(f'SELECT {COLS} FROM budgets ORDER BY created_at, id')
    if not rows:
        return BudgetsRes(month=m, alert_level=settings.alert_level, items=[])
    names, spend = await asyncio.gather(category_names(deps, ctx), month_spend(deps, ctx, m))
    items = [
        _to_dto(r, names.get(r['category_id'], ''), spend.get(r['category_id'], 0), settings, m, ctx.tz, now)
        for r in rows
    ]
    items.sort(key=lambda i: (-i.pct, i.category_name))
    return BudgetsRes(month=m, alert_level=settings.alert_level, items=items)


async def _user_settings(deps: Deps, ctx: Ctx) -> SettingsRow:
    async with deps.as_user(ctx) as tx:
        return await load_settings(tx, ctx.user_id, ctx.tz)


async def _view_one(deps: Deps, ctx: Ctx, r: Row, now: Clock) -> BudgetDto:
    m = month_key(now(), ctx.tz)
    names, spend, settings = await asyncio.gather(
        category_names(deps, ctx), month_spend(deps, ctx, m), _user_settings(deps, ctx)
    )
    return _to_dto(r, names.get(r['category_id'], ''), spend.get(r['category_id'], 0), settings, m, ctx.tz, now)


async def _rearm(tx: Tx, before: Row, after: Row, alert_level: int, period: MonthKey, spent: int) -> None:
    """A higher limit or warn pct puts levels the spend no longer reaches back in play: they can fire again this period."""
    old_alert = effective_alert_pct(before['warn_pct'], alert_level)
    new_alert = effective_alert_pct(after['warn_pct'], alert_level)
    if after['limit_minor'] > before['limit_minor'] or new_alert > old_alert:
        gone = [
            level
            for level, pct in (('exceeded', 100), ('alert', new_alert))
            if not reaches_pct(spent, after['limit_minor'], pct)
        ]
        if gone:
            await tx.execute(
                'DELETE FROM alerts WHERE budget_id = $1 AND period_key = $2 AND level = ANY($3)',
                [after['id'], period, gone],
            )


async def create_budget(deps: Deps, ctx: Ctx, body: BudgetCreateReq, now: Clock) -> BudgetDto:
    names = await category_names(deps, ctx)
    category_id, _ = await resolve_ref(deps, ctx, body, names)
    limit = body.limit_minor
    if body.use_month_allocation:
        limit = await allocation_for(deps, ctx, body.month or month_key(now(), ctx.tz), category_id)
        if limit <= 0:
            raise Errors.unprocessable(
                'There is no allocation for this category in that month', {'categoryId': category_id}
            )
    assert limit is not None  # the request model guarantees a limit or the allocation
    period = month_key(now(), ctx.tz)
    # Reviving a deactivated limit re-arms its alerts like a PATCH. That needs the spend (a service call), so read it first.
    async with deps.as_user(ctx) as tx:
        prior = await tx.maybe_one('SELECT active FROM budgets WHERE category_id = $1', [category_id])
    spent = (await month_spend(deps, ctx, period)).get(category_id, 0) if prior and not prior['active'] else None
    try:
        async with deps.as_user(ctx) as tx:
            existing = await tx.maybe_one(
                f'SELECT {COLS} FROM budgets WHERE category_id = $1 FOR UPDATE', [category_id]
            )
            if existing and existing['active']:
                raise Errors.conflict('This category already has a limit', {'budgetId': existing['id']})
            if existing:
                row = await tx.one(
                    f'UPDATE budgets SET limit_minor = $2, warn_pct = $3, active = true, updated_at = now() WHERE id = $1 RETURNING {COLS}',
                    [existing['id'], limit, body.warn_pct],
                )
                if spent is not None:
                    level = (await load_settings(tx, ctx.user_id, ctx.tz)).alert_level
                    await _rearm(tx, existing, row, level, period, spent)
            else:
                row = await tx.one(
                    f'INSERT INTO budgets (user_id, category_id, limit_minor, warn_pct) VALUES ($1, $2, $3, $4) RETURNING {COLS}',
                    [ctx.user_id, category_id, limit, body.warn_pct],
                )
            await enqueue_evaluate(deps, tx, ctx.user_id, category_id, period)
    except psycopg.errors.UniqueViolation:
        raise Errors.conflict('This category already has a limit') from None
    return await _view_one(deps, ctx, row, now)


async def patch_budget(deps: Deps, ctx: Ctx, id: str, body: BudgetPatchReq, now: Clock) -> BudgetDto:
    period = month_key(now(), ctx.tz)
    async with deps.as_user(ctx) as tx:
        current = await tx.maybe_one(f'SELECT {COLS} FROM budgets WHERE id = $1', [id])
    if current is None:
        raise Errors.not_found('Limit')
    limit = body.limit_minor
    if body.use_month_allocation:
        limit = await allocation_for(deps, ctx, body.month or period, current['category_id'])
        if limit <= 0:
            raise Errors.unprocessable(
                'There is no allocation for this category in that month', {'categoryId': current['category_id']}
            )
    warn_given = 'warn_pct' in body.present_keys()  # an explicit null clears the limit's own percentage
    # the spend decides which alert levels get re-armed; read outside the transaction (service call)
    touches_level = limit is not None or warn_given
    spent = (await month_spend(deps, ctx, period)).get(current['category_id'], 0) if touches_level else 0

    async with deps.as_user(ctx) as tx:
        before = await tx.maybe_one(f'SELECT {COLS} FROM budgets WHERE id = $1 FOR UPDATE', [id])
        if before is None:
            raise Errors.not_found('Limit')
        nxt = await tx.one(
            f'UPDATE budgets SET limit_minor = $2, warn_pct = $3, active = $4, updated_at = now() WHERE id = $1 RETURNING {COLS}',
            [
                id,
                before['limit_minor'] if limit is None else limit,
                body.warn_pct if warn_given else before['warn_pct'],
                before['active'] if body.active is None else body.active,
            ],
        )
        level = (await load_settings(tx, ctx.user_id, ctx.tz)).alert_level
        await _rearm(tx, before, nxt, level, period, spent)
        if nxt['active']:
            await enqueue_evaluate(deps, tx, ctx.user_id, nxt['category_id'], period)
    return await _view_one(deps, ctx, nxt, now)


async def delete_budget(deps: Deps, ctx: Ctx, id: str) -> None:
    async with deps.as_user(ctx) as tx:
        r = await tx.maybe_one('DELETE FROM budgets WHERE id = $1 RETURNING id', [id])
    if r is None:
        raise Errors.not_found('Limit')
