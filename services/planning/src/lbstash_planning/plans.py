"""Monthly plans: total, lines, spend per line, credits."""

import asyncio

from lbstash.common import Ctx, Errors, MonthKey
from lbstash.contracts import PlanLineWithSpend, PlanPutReq, PlanWithSpendDto
from lbstash.kit import Deps

from .transactions import category_names, month_spend, resolve_ref


async def get_plan(deps: Deps, ctx: Ctx, month: MonthKey) -> PlanWithSpendDto:
    """Plan for a month with spend per line. An unplanned month reads as empty, not 404."""
    async with deps.as_user(ctx) as tx:
        p = await tx.maybe_one('SELECT id, total_minor FROM plans WHERE month = $1', [month])
        if p is None:
            total, lines = 0, []
        else:
            total = p['total_minor']
            lines = await tx.many(
                'SELECT category_id, allocated_minor FROM plan_lines WHERE plan_id = $1 ORDER BY position, id',
                [p['id']],
            )
    if not lines:
        return PlanWithSpendDto(month=month, total_minor=total, lines=[], assigned_minor=0, unassigned_minor=total)
    names, spend = await asyncio.gather(category_names(deps, ctx), month_spend(deps, ctx, month))
    out = [
        PlanLineWithSpend(
            category_id=line['category_id'],
            category_name=names.get(line['category_id'], ''),
            allocated_minor=line['allocated_minor'],
            spent_minor=spend.get(line['category_id'], 0),
        )
        for line in lines
    ]
    assigned = sum(line.allocated_minor for line in out)
    return PlanWithSpendDto(
        month=month, total_minor=total, lines=out, assigned_minor=assigned, unassigned_minor=total - assigned
    )


async def put_plan(deps: Deps, ctx: Ctx, month: MonthKey, body: PlanPutReq) -> PlanWithSpendDto:
    """Replace the total and every line. Over-assigning is allowed; it shows as a negative `unassigned_minor`."""
    names = await category_names(deps, ctx)
    seen: set[str] = set()
    lines: list[tuple[str, int]] = []
    for i, line in enumerate(body.lines):
        category_id, _ = await resolve_ref(deps, ctx, line, names)
        if category_id in seen:
            raise Errors.validation({f'lines.{i}': 'This category is already on the plan'})
        seen.add(category_id)
        lines.append((category_id, line.allocated_minor))
    async with deps.as_user(ctx) as tx:
        # the upsert locks the plan row, so concurrent saves of one month serialize
        p = await tx.one(
            """INSERT INTO plans (user_id, month, total_minor) VALUES ($1, $2, $3)
               ON CONFLICT (user_id, month) DO UPDATE SET total_minor = EXCLUDED.total_minor, updated_at = now() RETURNING id""",
            [ctx.user_id, month, body.total_minor],
        )
        await tx.execute('DELETE FROM plan_lines WHERE plan_id = $1', [p['id']])
        for pos, (category_id, allocated) in enumerate(lines):
            await tx.execute(
                'INSERT INTO plan_lines (user_id, plan_id, category_id, allocated_minor, position) VALUES ($1, $2, $3, $4, $5)',
                [ctx.user_id, p['id'], category_id, allocated, pos],
            )
    return await get_plan(deps, ctx, month)


async def add_credit(deps: Deps, ctx: Ctx | str, month: MonthKey, transaction_id: str, amount_minor: int) -> int:
    """Add a credit to the month's total once per transaction id (the HTTP call and `credit.added` can both arrive)."""
    user_id = ctx if isinstance(ctx, str) else ctx.user_id
    async with deps.as_user(user_id) as tx:
        first = await tx.maybe_one(
            'INSERT INTO plan_credits (user_id, transaction_id, month, amount_minor) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING RETURNING transaction_id',
            [user_id, transaction_id, month, amount_minor],
        )
        if first:
            await tx.execute(
                """INSERT INTO plans (user_id, month, total_minor) VALUES ($1, $2, $3)
                   ON CONFLICT (user_id, month) DO UPDATE SET total_minor = plans.total_minor + EXCLUDED.total_minor, updated_at = now()""",
                [user_id, month, amount_minor],
            )
        p = await tx.maybe_one('SELECT total_minor FROM plans WHERE month = $1', [month])
        return p['total_minor'] if p else 0


async def allocation_for(deps: Deps, ctx: Ctx, month: MonthKey, category_id: str) -> int:
    """The month's allocation for a category (0 if the plan has no line for it)."""
    async with deps.as_user(ctx) as tx:
        r = await tx.maybe_one(
            'SELECT l.allocated_minor FROM plan_lines l JOIN plans p ON p.id = l.plan_id WHERE p.month = $1 AND l.category_id = $2',
            [month, category_id],
        )
        return r['allocated_minor'] if r else 0
