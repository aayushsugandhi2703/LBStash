"""The Trends read models: daily spend, months, and the category matrix."""

from typing import Any

from lbstash.common import Clock, Ctx, add_days, display_tag, kept_rate, pace_projection
from lbstash.contracts import (
    MonthPace,
    ReportDailyItem,
    ReportDailyQuery,
    ReportDailyRes,
    ReportMatrixItem,
    ReportMatrixMonth,
    ReportMatrixRes,
    ReportMonthAverages,
    ReportMonthItem,
    ReportMonthsRes,
    ReportRangeQuery,
)

from .common import avg, call_as, name_key, progress_of
from .fixed import load_window


async def daily(deps: Any, ctx: Ctx, clock: Clock, q: ReportDailyQuery) -> ReportDailyRes:
    """GET /reports/daily?month=: spend per day, leaving out fixed categories (see `fixed.py`)."""
    p = progress_of(clock, ctx.tz, q.month)
    w = await load_window(deps, ctx, p.month, 6, p.current)
    rows = await deps.clients.transactions.daily(call_as(ctx), p.month, sorted(w.fixed_ids))
    spent = {d.day: d.spent_minor for d in rows.items}
    first = f'{p.month}-01'
    items = []
    for i in range(p.days_in_month):
        day = add_days(first, i)
        items.append(ReportDailyItem(day=day, spent_minor=spent.get(day, 0)))
    total = sum(d.spent_minor for d in items)
    return ReportDailyRes(
        month=p.month, day_of_month=p.day_of_month, days_in_month=p.days_in_month, items=items,
        total_minor=total, average_minor=avg(total, p.day_of_month), fixed_categories=w.fixed_names,
    )


async def months(deps: Any, ctx: Ctx, clock: Clock, q: ReportRangeQuery) -> ReportMonthsRes:
    """GET /reports/months?range=6: income, spent, kept per month, the pace of the month in progress, and averages."""
    p = progress_of(clock, ctx.tz)
    w = await load_window(deps, ctx, p.month, q.range, p.current)
    have = {m.month: m for m in w.months}

    closing = 0
    items: list[ReportMonthItem] = []
    for month in w.keys:
        m = have.get(month)
        income = m.income_minor if m else 0
        spent = m.spent_minor if m else 0
        if m:
            closing = m.closing_minor  # a month the transactions has nothing for keeps the balance it started with
        in_progress = month == p.month
        pace: MonthPace | None = None
        if in_progress:
            flexible_so_far = sum(
                c.spent_minor for c in w.cat_months if c.month == month and not (c.category_id and c.category_id in w.fixed_ids)
            )
            flexible_pace = pace_projection(flexible_so_far, p.day_of_month, p.days_in_month)
            pace_spent = flexible_pace + w.fixed_committed_minor
            pace = MonthPace(
                day_of_month=p.day_of_month, days_in_month=p.days_in_month, spent_so_far_minor=spent,
                flexible_so_far_minor=flexible_so_far, fixed_minor=w.fixed_committed_minor,
                flexible_pace_minor=flexible_pace, pace_spent_minor=pace_spent, pace_kept_minor=income - pace_spent,
            )
        items.append(
            ReportMonthItem(
                month=month, income_minor=income, spent_minor=spent, kept_minor=income - spent,
                kept_rate=kept_rate(income, spent), closing_minor=closing, in_progress=in_progress, pace=pace,
            )
        )

    full = [i for i in items if i.month in w.full_months]
    income = sum(i.income_minor for i in full)
    spent = sum(i.spent_minor for i in full)
    first_active = next((i for i in items if i.income_minor > 0 or i.spent_minor > 0), None)
    last = items[-1] if items else None
    return ReportMonthsRes(
        end=p.month,
        items=items,
        averages=ReportMonthAverages(
            full_months=len(full),
            avg_monthly_spend_minor=avg(spent, len(full)),
            avg_kept_minor=avg(income - spent, len(full)),
            avg_kept_rate=kept_rate(income, spent),
            balance_since_minor=last.closing_minor - first_active.closing_minor if first_active and last else 0,
            balance_since_month=first_active.month if first_active else None,
        ),
    )


async def category_matrix(deps: Any, ctx: Ctx, clock: Clock, q: ReportRangeQuery) -> ReportMatrixRes:
    """GET /reports/category-matrix?range=6: flexible categories, usual (finished-month average) against this month's pace."""
    p = progress_of(clock, ctx.tz)
    w = await load_window(deps, ctx, p.month, q.range, p.current)

    by_cat: dict[str, tuple[str, dict[str, int]]] = {}
    for c in w.cat_months:
        if not c.category_id or c.category_id in w.fixed_ids:
            continue  # untagged spend has no row of its own; fixed categories never change
        _, spent = by_cat.setdefault(c.category_id, (c.category_name or 'untagged', {}))
        spent[c.month] = spent.get(c.month, 0) + c.spent_minor
    items: list[ReportMatrixItem] = []
    for category_id, (name, spent) in by_cat.items():
        usual = avg(sum(spent.get(m, 0) for m in w.full_months), len(w.full_months))
        so_far = spent.get(p.month, 0)
        pace = pace_projection(so_far, p.day_of_month, p.days_in_month)
        if usual > 0 or pace > 0:
            items.append(
                ReportMatrixItem(
                    category_id=category_id, name=name,
                    by_month=[ReportMatrixMonth(month=m, spent_minor=spent.get(m, 0)) for m in w.keys],
                    usual_minor=usual, spent_so_far_minor=so_far, pace_minor=pace, change_minor=pace - usual,
                )
            )
    items.sort(key=lambda i: (-i.change_minor, name_key(display_tag(i.name))))
    return ReportMatrixRes(
        end=p.month, months=w.keys, full_months=len(w.full_months), day_of_month=p.day_of_month,
        days_in_month=p.days_in_month, items=items,
    )
