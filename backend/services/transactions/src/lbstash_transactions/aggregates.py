"""Spend aggregates and the figures the Transactions shows next to a row. Month boundaries use the user's zone."""

import re
from datetime import datetime

from lbstash.common import (
    Ctx,
    Errors,
    MonthKey,
    available_balance,
    month_key,
    month_range,
    months_ending_at,
    to_iso,
)
from lbstash.contracts import (
    CategoryMonthItem,
    CategoryMonthsRes,
    CategoryStatDto,
    DailyItem,
    DailyRes,
    MonthItem,
    MonthsRes,
    MonthSummaryRes,
    SpendByCategoryItem,
    SpendByCategoryRes,
    TransactionFigures,
)
from lbstash.db import Tx

from .model import NOT_TRANSFER, TRANSFER
from .settings import balance_at, get_settings


async def category_stats(
    tx: Tx, user_id: str, from_: datetime | None = None, to: datetime | None = None
) -> list[CategoryStatDto]:
    """Money out / in per category among rows in scope; #transfer and reversed rows never count as spend or income."""
    rows = await tx.many(
        f"""SELECT c.id, c.name, c.archived,
            COUNT(t.id)::int AS count,
            COALESCE(SUM(t.amount_minor) FILTER (WHERE t.type = 'debit' AND t.status <> 'reversed' AND c.name <> '{TRANSFER}'), 0)::bigint AS spent,
            COALESCE(SUM(t.amount_minor) FILTER (WHERE t.type = 'credit' AND t.status <> 'reversed' AND c.name <> '{TRANSFER}'), 0)::bigint AS received
       FROM categories c
       LEFT JOIN transactions t ON t.category_id = c.id AND t.user_id = c.user_id
            AND ($2::timestamptz IS NULL OR t.occurred_at >= $2) AND ($3::timestamptz IS NULL OR t.occurred_at < $3)
      WHERE c.user_id = $1
      GROUP BY c.id
     HAVING NOT c.archived OR COUNT(t.id) > 0
      ORDER BY spent DESC, c.name""",
        [user_id, from_, to],
    )
    return [
        CategoryStatDto(
            category_id=r['id'], category_name=r['name'], archived=r['archived'], count=r['count'],
            spent_minor=r['spent'], received_minor=r['received'],
        )
        for r in rows
    ]  # fmt: skip


async def pending_counts(tx: Tx, user_id: str) -> tuple[int, int]:
    """(needs a tag, unaccounted) among pending rows."""
    r = await tx.one(
        """SELECT COUNT(*) FILTER (WHERE status = 'pending')::int AS needs,
            COUNT(*) FILTER (WHERE status = 'pending' AND source = 'unaccounted')::int AS unacc
       FROM transactions WHERE user_id = $1""",
        [user_id],
    )
    return r['needs'], r['unacc']


async def figures(tx: Tx, ctx: Ctx, occurred_at: datetime, category_ids: list[str | None]) -> TransactionFigures:
    """What the Transactions shows next to a row after a write: balance, both counters, and stats of the touched categories in the row's month."""
    start, end = month_range(month_key(occurred_at, ctx.tz), ctx.tz)
    wanted = {c for c in category_ids if c}
    bal = await balance_at(tx, ctx.user_id)
    needs, unacc = await pending_counts(tx, ctx.user_id)
    cats = await category_stats(tx, ctx.user_id, start, end)
    return TransactionFigures(
        balance_minor=bal, needs_tag_count=needs, unaccounted_count=unacc,
        categories=[c for c in cats if c.category_id in wanted],
    )  # fmt: skip


# aggregates for reports and planning
async def spend_by_category(tx: Tx, user_id: str, from_: datetime, to: datetime) -> SpendByCategoryRes:
    rows = await tx.many(
        f"""SELECT t.category_id, c.name, SUM(t.amount_minor)::bigint AS spent
       FROM transactions t LEFT JOIN categories c ON c.id = t.category_id AND c.user_id = t.user_id
      WHERE t.user_id = $1 AND t.type = 'debit' AND t.status <> 'reversed' AND t.occurred_at >= $2 AND t.occurred_at < $3 AND {NOT_TRANSFER}
      GROUP BY t.category_id, c.name ORDER BY spent DESC""",
        [user_id, from_, to],
    )
    return SpendByCategoryRes(
        items=[SpendByCategoryItem(category_id=r['category_id'], category_name=r['name'], spent_minor=r['spent']) for r in rows]
    )


async def month_summary(tx: Tx, ctx: Ctx, month: MonthKey) -> MonthSummaryRes:
    start, end = month_range(month, ctx.tz)
    s = await get_settings(tx, ctx.user_id)
    r = await tx.one(
        f"""SELECT COALESCE(SUM(t.amount_minor) FILTER (WHERE t.type = 'credit' AND t.occurred_at < $2), 0)::bigint AS cr_before,
            COALESCE(SUM(t.amount_minor) FILTER (WHERE t.type = 'debit' AND t.occurred_at < $2), 0)::bigint AS dr_before,
            COALESCE(SUM(t.amount_minor) FILTER (WHERE t.type = 'credit' AND t.occurred_at >= $2 AND t.occurred_at < $3 AND {NOT_TRANSFER}), 0)::bigint AS income,
            COALESCE(SUM(t.amount_minor) FILTER (WHERE t.type = 'debit' AND t.occurred_at >= $2 AND t.occurred_at < $3 AND {NOT_TRANSFER}), 0)::bigint AS spent
       FROM transactions t LEFT JOIN categories c ON c.id = t.category_id AND c.user_id = t.user_id
      WHERE t.user_id = $1 AND t.status <> 'reversed'""",
        [ctx.user_id, start, end],
    )
    needs, unacc = await pending_counts(tx, ctx.user_id)
    # when the phone last delivered a message, whatever became of the row (merged, even reversed)
    last = await tx.one('SELECT MAX(captured_at) AS at FROM transactions WHERE user_id = $1', [ctx.user_id])
    return MonthSummaryRes(
        month=month,
        carried_over_minor=available_balance(s.opening_balance_minor, r['cr_before'], r['dr_before']),
        income_minor=r['income'],
        spent_minor=r['spent'],
        available_minor=await balance_at(tx, ctx.user_id),
        untagged_count=needs,
        unaccounted_count=unacc,
        last_captured_at=last['at'],
    )


def _buckets(end: MonthKey, count: int, tz: str) -> tuple[list[str], list[str], list[str]]:
    months = months_ending_at(end, count)
    ranges = [month_range(m, tz) for m in months]
    return months, [to_iso(x.start) for x in ranges], [to_iso(x.end) for x in ranges]


async def months(tx: Tx, ctx: Ctx, end: MonthKey, count: int) -> MonthsRes:
    keys, starts, ends = _buckets(end, count, ctx.tz)
    s = await get_settings(tx, ctx.user_id)
    before = await tx.one(
        """SELECT COALESCE(SUM(CASE type WHEN 'credit' THEN amount_minor ELSE -amount_minor END), 0)::bigint AS net
       FROM transactions WHERE user_id = $1 AND status <> 'reversed' AND occurred_at < $2""",
        [ctx.user_id, starts[0]],
    )
    rows = await tx.many(
        f"""WITH b AS (SELECT * FROM unnest($2::text[], $3::timestamptz[], $4::timestamptz[]) AS x(month, s, e))
     SELECT b.month,
            COALESCE(SUM(t.amount_minor) FILTER (WHERE t.type = 'credit' AND {NOT_TRANSFER}), 0)::bigint AS income,
            COALESCE(SUM(t.amount_minor) FILTER (WHERE t.type = 'debit' AND {NOT_TRANSFER}), 0)::bigint AS spent,
            COALESCE(SUM(CASE t.type WHEN 'credit' THEN t.amount_minor ELSE -t.amount_minor END), 0)::bigint AS net
       FROM b LEFT JOIN (transactions t LEFT JOIN categories c ON c.id = t.category_id AND c.user_id = t.user_id)
         ON t.user_id = $1 AND t.status <> 'reversed' AND t.occurred_at >= b.s AND t.occurred_at < b.e
      GROUP BY b.month""",
        [ctx.user_id, keys, starts, ends],
    )
    by_month = {r['month']: r for r in rows}
    running = s.opening_balance_minor + before['net']
    items: list[MonthItem] = []
    for m in keys:
        r = by_month.get(m)
        running += r['net'] if r else 0
        items.append(
            MonthItem(month=m, income_minor=r['income'] if r else 0, spent_minor=r['spent'] if r else 0, closing_minor=running)
        )
    return MonthsRes(items=items)


async def category_months(tx: Tx, ctx: Ctx, end: MonthKey, count: int) -> CategoryMonthsRes:
    keys, starts, ends = _buckets(end, count, ctx.tz)
    rows = await tx.many(
        f"""WITH b AS (SELECT * FROM unnest($2::text[], $3::timestamptz[], $4::timestamptz[]) AS x(month, s, e))
     SELECT b.month, t.category_id, c.name, SUM(t.amount_minor)::bigint AS spent
       FROM b JOIN transactions t ON t.user_id = $1 AND t.type = 'debit' AND t.status <> 'reversed' AND t.occurred_at >= b.s AND t.occurred_at < b.e
       LEFT JOIN categories c ON c.id = t.category_id AND c.user_id = t.user_id
      WHERE {NOT_TRANSFER}
      GROUP BY b.month, t.category_id, c.name ORDER BY b.month, spent DESC""",
        [ctx.user_id, keys, starts, ends],
    )
    return CategoryMonthsRes(
        items=[
            CategoryMonthItem(month=r['month'], category_id=r['category_id'], category_name=r['name'], spent_minor=r['spent'])
            for r in rows
        ]
    )


async def daily(tx: Tx, ctx: Ctx, month: MonthKey, exclude: list[str]) -> DailyRes:
    """Debits per local day (days without spend are left out). `exclude` removes categories, e.g. rent."""
    start, end = month_range(month, ctx.tz)
    rows = await tx.many(
        f"""SELECT to_char(t.occurred_at AT TIME ZONE $2, 'YYYY-MM-DD') AS day, SUM(t.amount_minor)::bigint AS spent
       FROM transactions t LEFT JOIN categories c ON c.id = t.category_id AND c.user_id = t.user_id
      WHERE t.user_id = $1 AND t.type = 'debit' AND t.status <> 'reversed' AND t.occurred_at >= $3 AND t.occurred_at < $4 AND {NOT_TRANSFER}
        AND (t.category_id IS NULL OR t.category_id <> ALL($5::uuid[]))
      GROUP BY 1 ORDER BY 1""",
        [ctx.user_id, ctx.tz, start, end, exclude],
    )
    return DailyRes(items=[DailyItem(day=r['day'], spent_minor=r['spent']) for r in rows])


UUID_RE = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)


def parse_id_list(csv: str | None) -> list[str]:
    """`a,b,c` -> ids; anything that is not a UUID is a 400."""
    ids = [s.strip() for s in (csv or '').split(',') if s.strip()]
    if any(not UUID_RE.fullmatch(i) for i in ids):
        raise Errors.validation({'excludeCategoryIds': 'Comma separated category ids'})
    return ids
