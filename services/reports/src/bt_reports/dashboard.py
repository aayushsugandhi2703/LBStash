"""GET /dashboard: the Now page."""

import asyncio
from collections.abc import Awaitable
from typing import Any

from bt.common import Clock, Ctx, display_tag, month_range, plan_left, safe_per_day
from bt.contracts import (
    AlertsRes,
    AttentionItem,
    DashboardBalance,
    DashboardQuery,
    DashboardRes,
    FlowItem,
    LimitAttention,
    NeedsLookAttention,
    RecurringAttention,
    RecurringRes,
    SafeToSpend,
    UnaccountedAttention,
    UnparsedCountRes,
    UntaggedAttention,
)

from .common import call_as, name_key, progress_of


async def dashboard(deps: Any, ctx: Ctx, clock: Clock, q: DashboardQuery) -> DashboardRes:
    """The Now page in one call. Ledger and plan are required; limits, alerts, recurring and the unparsed count are optional and listed in `degraded` when missing, so a slow neighbour never blanks the page."""
    as_ = call_as(ctx)
    p = progress_of(clock, ctx.tz, q.month)
    start, end = month_range(p.month, ctx.tz)
    degraded: list[str] = []

    async def optional[T](part: str, run: Awaitable[T], fallback: T) -> T:
        try:
            return await run
        except Exception as e:  # noqa: BLE001  (any failure of an optional part only degrades the page)
            degraded.append(part)
            deps.log.warning('dashboard part unavailable', part=part, code=getattr(e, 'code', 'error'))
            return fallback

    c = deps.clients
    summary, spend, plan, budgets, alerts, recurring, unparsed = await asyncio.gather(
        c.ledger.month_summary(as_, p.month),
        c.ledger.spend_by_category(as_, start, end),
        c.planning.plan(as_, p.month),
        optional('budgets', c.planning.budgets(as_, p.month), None),
        optional('alerts', c.planning.alerts(as_), AlertsRes(unread_count=0, items=[])),
        optional('recurring', c.recurring.list(as_), RecurringRes(items=[], committed_minor=0)),
        optional('ingest', c.ingest.unparsed_count(as_), UnparsedCountRes(open=0)),
    )

    available = summary.carried_over_minor + summary.income_minor - summary.spent_minor
    planned = sum(line.allocated_minor for line in plan.lines)
    spent_on_planned = sum(line.spent_minor for line in plan.lines)
    left = plan_left(planned, spent_on_planned)
    # whole rupees, rounded down: 445.46 must never show as 446
    per_day = safe_per_day(left, p.days_left) // 100 * 100

    flow = sorted(
        (
            FlowItem(name=display_tag(s.category_name) if s.category_name else 'Untagged', amount=s.spent_minor)
            for s in spend.items
            if s.spent_minor > 0
        ),
        key=lambda f: (-f.amount, name_key(f.name)),
    )
    flow.append(FlowItem(name='Still available', amount=max(0, available)))

    attention: list[AttentionItem] = []
    if budgets is not None:
        watching = [b for b in budgets.items if b.active and b.pct >= (budgets.alert_level if b.warn_pct is None else b.warn_pct)]
        for b in sorted(watching, key=lambda b: (-b.pct, name_key(b.category_name))):
            attention.append(
                LimitAttention(kind='limit', category=display_tag(b.category_name), pct=b.pct, status='over' if b.pct >= 100 else 'close')
            )
    if summary.untagged_count > 0:
        attention.append(UntaggedAttention(kind='untagged', count=summary.untagged_count))
    if unparsed.open > 0:
        attention.append(NeedsLookAttention(kind='needs_look', count=unparsed.open))
    if summary.unaccounted_count > 0:
        attention.append(UnaccountedAttention(kind='unaccounted', count=summary.unaccounted_count))
    upcoming = sorted((r for r in recurring.items if r.active), key=lambda r: (r.next_due, name_key(r.name)))
    if upcoming:
        nxt = upcoming[0]
        attention.append(RecurringAttention(kind='recurring', name=nxt.name, amount=nxt.amount_minor, due=nxt.next_due))

    return DashboardRes(
        month=p.month, day_of_month=p.day_of_month, days_in_month=p.days_in_month,
        balance=DashboardBalance(
            carried_over=summary.carried_over_minor, income=summary.income_minor, spent=summary.spent_minor, available=available
        ),
        safe_to_spend=SafeToSpend(plan_left=left, days_left=p.days_left, per_day=per_day),
        flow=flow, attention=attention,
        last_captured_at=summary.last_captured_at,
        untagged_count=summary.untagged_count, unaccounted_count=summary.unaccounted_count,
        needs_look_count=unparsed.open, alert_badge_count=alerts.unread_count,
        degraded=sorted(degraded),
    )
