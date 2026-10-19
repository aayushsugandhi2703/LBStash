"""Credits added by hand (README 10.3) and the recent-credits list for the Add credit page."""

from datetime import datetime

from bt.common import Ctx, Errors, Parts, add_days, date_key, month_key, zoned_to_utc
from bt.contracts import CreditReq, CreditRes, CreditsRes

from .categories import resolve_category
from .model import TX_SELECT, D, emit_changed, insert_tx, lock_user, new_key, to_dto
from .settings import balance_at


async def add_credit(deps: D, ctx: Ctx, b: CreditReq, now: datetime) -> CreditRes:
    """Add a credit that counts in the balance at once (README 10.3); not dated in the future. With "add to plan", `credit.added` is emitted in the same transaction and planning is called after commit."""
    today = date_key(now, ctx.tz)
    try:
        add_days(b.date, 0)
    except ValueError:
        raise Errors.validation({'date': 'Not a calendar day'}) from None
    if b.date > today:
        raise Errors.unprocessable('The date cannot be in the future', {'date': 'In the future'})
    # today gets the current time, other days midday, so ordering and month boundaries stay sensible
    y, m, d = (int(x) for x in b.date.split('-'))
    occurred_at = now if b.date == today else zoned_to_utc(Parts(y, m, d, 12), ctx.tz)
    month = month_key(occurred_at, ctx.tz)

    async with deps.as_user(ctx) as tx:
        await lock_user(tx, ctx.user_id)
        cat, category_created = await resolve_category(tx, ctx.user_id, b.tag)
        row = await insert_tx(
            tx, ctx.user_id, type='credit', amount_minor=b.amount_minor, occurred_at=occurred_at, source='manual',
            status='confirmed', dedupe_key=new_key('manual'), description=b.note, category_id=cat.id, classified_by='user',
        )  # fmt: skip
        assert row is not None
        await emit_changed(deps, tx, ctx.tz, row, 'created', tagged_via='web')
        if b.add_to_plan:
            await deps.bus.emit(
                tx, 'credit.added',
                {'user_id': ctx.user_id, 'transaction_id': row['id'], 'month': month, 'amount_minor': b.amount_minor, 'add_to_plan': True},
            )  # fmt: skip
        balance = await balance_at(tx, ctx.user_id)

    plan_total: int | None = None
    if b.add_to_plan:
        try:
            res = await deps.clients.planning.add_credit_to_plan(
                ctx, month, {'transactionId': row['id'], 'amountMinor': b.amount_minor}
            )
            plan_total = res.total_minor
        except Exception as e:  # noqa: BLE001 - best effort: the credit.added event catches the plan up
            deps.log.warning('plan total not updated now, the credit.added event will do it', rid=ctx.request_id, tx=row['id'], err=e)
    return CreditRes(transaction=to_dto(row), category_created=category_created, balance_minor=balance, plan_total_minor=plan_total)


async def recent_credits(deps: D, ctx: Ctx, limit: int) -> CreditsRes:
    """Recent credits: bank and hand-added. Unaccounted gaps and reversed rows are not income."""
    async with deps.as_user(ctx) as tx:
        rows = await tx.many(
            f"{TX_SELECT} WHERE t.user_id = $1 AND t.type = 'credit' AND t.status <> 'reversed' AND t.source <> 'unaccounted' ORDER BY t.occurred_at DESC, t.id DESC LIMIT $2",
            [ctx.user_id, limit],
        )
        return CreditsRes(items=[to_dto(r) for r in rows], balance_minor=await balance_at(tx, ctx.user_id))
