"""Ingest (README 10.1): save a parsed bank message (link, merge, replace or reverse), then the balance check; and recurring posts."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lbstash.common import Ctx, Errors, Parts, add_days, date_key, zoned_to_utc
from lbstash.contracts import (
    IngestOutcome,
    IngestTransactionReq,
    IngestTransactionRes,
    RecurringPostReq,
    RecurringPostRes,
)
from lbstash.db import Tx

from .balance import claim_newest, create_check, evaluate_open
from .categories import get_category
from .classify import classify
from .model import (
    TX_SELECT,
    D,
    TxRow,
    add_alias,
    emit_changed,
    find_by_key,
    get_tx,
    insert_tx,
    key_of,
    lock_user,
    to_dto,
)


async def _near(tx: Tx, ctx: Ctx, at: datetime, days: int, where: str, params: list[Any]) -> list[TxRow]:
    """Locked candidate rows within `days` calendar days of `at`, closest first (calendar days because a hand-added credit only has a date). `where` may use $6 and up."""
    return await tx.many(  # type: ignore[return-value]
        f"""{TX_SELECT} WHERE t.user_id = $1 AND t.status <> 'reversed' AND abs((t.occurred_at AT TIME ZONE $2)::date - $3::date) <= $4 AND {where}
      ORDER BY abs(extract(epoch FROM (t.occurred_at - $5::timestamptz))), t.id LIMIT 10 FOR UPDATE OF t""",
        [ctx.user_id, ctx.tz, date_key(at, ctx.tz), days, at, *params],
    )


def _hint_matches(hint: str | None, payee: str | None) -> bool:
    """The same payment if one payee contains the other (an empty hint matches anything). No payee, no match."""
    p = key_of(payee)
    h = key_of(hint)
    if not p:
        return False
    return not h or h in p or p in h


@dataclass(slots=True)
class _Placed:
    outcome: IngestOutcome
    row: TxRow


async def _merge(deps: D, tx: Tx, ctx: Ctx, row: TxRow, req: IngestTransactionReq) -> TxRow:
    """Fold the message into an existing row and register its dedupe key so a re-send is a `duplicate`."""
    await tx.query(
        """UPDATE transactions SET linked = true, captured_at = $2, device_id = $3, reference = COALESCE(reference, $4), account_last4 = COALESCE(account_last4, $5),
            payee = COALESCE(payee, $6), payee_key = COALESCE(payee_key, $7), updated_at = now() WHERE id = $1""",
        [row['id'], req.captured_at, req.device_id, req.reference, req.account_last4, req.payee, key_of(req.payee)],
    )
    await add_alias(tx, ctx.user_id, req.dedupe_key, row['id'])
    fresh = await get_tx(tx, row['id'])
    assert fresh is not None
    await emit_changed(deps, tx, ctx.tz, fresh, 'updated', before=row['category_id'])
    return fresh


async def _place(deps: D, tx: Tx, ctx: Ctx, req: IngestTransactionReq, at: datetime) -> _Placed:
    type_ = req.type

    if req.reversal:
        # the original is the debit with the same reference and amount; reversing it is not a second credit
        orig = None
        if req.reference:
            found = await tx.many(
                f"""{TX_SELECT} WHERE t.user_id = $1 AND t.reference = $2 AND t.amount_minor = $3 AND t.type = 'debit' AND t.status <> 'reversed'
            ORDER BY t.occurred_at DESC LIMIT 1 FOR UPDATE OF t""",
                [ctx.user_id, req.reference, req.amount_minor],
            )
            orig = found[0] if found else None
        if orig:
            await tx.query(
                "UPDATE transactions SET status = 'reversed', captured_at = GREATEST(COALESCE(captured_at, $2), $2), updated_at = now() WHERE id = $1",
                [orig['id'], req.captured_at],
            )
            await add_alias(tx, ctx.user_id, req.dedupe_key, orig['id'])
            fresh = await get_tx(tx, orig['id'])
            assert fresh is not None
            await emit_changed(deps, tx, ctx.tz, fresh, 'updated', before=orig['category_id'])
            return _Placed('reversed_original', fresh)
        type_ = 'credit'  # a refund with no original on file: money came back, tag it #refund
    elif type_ == 'credit':
        manual = await _near(
            tx, ctx, at, 1, "t.type = 'credit' AND t.source = 'manual' AND NOT t.linked AND t.amount_minor = $6", [req.amount_minor]
        )
        if manual:
            return _Placed('linked_manual', await _merge(deps, tx, ctx, manual[0], req))
    else:
        posts = await _near(
            tx, ctx, at, 2, "t.type = 'debit' AND t.source = 'recurring' AND NOT t.linked AND t.amount_minor = $6", [req.amount_minor]
        )
        post = next((p for p in posts if _hint_matches(p['match_hint'], req.payee)), None)
        if post:
            return _Placed('linked_recurring', await _merge(deps, tx, ctx, post, req))

    c = None if req.reversal else await classify(tx, ctx.user_id, req.payee)
    status = 'confirmed' if c else 'pending'

    if not req.reversal:
        # a late real message replaces the Unaccounted entry booked for it: same row and amount, balance unchanged
        unaccounted = await _near(
            tx, ctx, at, 3,
            "t.source = 'unaccounted' AND t.status = 'pending' AND t.category_id IS NULL AND t.type = $6 AND t.amount_minor = $7",
            [type_, req.amount_minor],
        )  # fmt: skip
        if unaccounted:
            un = unaccounted[0]
            await tx.query(
                """UPDATE transactions SET source = 'captured', occurred_at = $2, payee = $3, payee_key = $4, reference = $5, account_last4 = $6, device_id = $7, captured_at = $8,
                weak_parse = $9, category_id = $10, status = $11, classified_by = $12, rule_pattern = $13, updated_at = now() WHERE id = $1""",
                [un['id'], at, req.payee, key_of(req.payee), req.reference, req.account_last4, req.device_id, req.captured_at,
                 req.weak_parse, c.category_id if c else None, status, c.by if c else None,
                 c.pattern if c and c.by == 'rule' else None],
            )  # fmt: skip
            await add_alias(tx, ctx.user_id, req.dedupe_key, un['id'])
            fresh = await get_tx(tx, un['id'])
            assert fresh is not None
            await emit_changed(deps, tx, ctx.tz, fresh, 'updated', before=None, tagged_via='rule' if c else None)
            return _Placed('replaced_unaccounted', fresh)

    row = await insert_tx(
        tx, ctx.user_id, type=type_, amount_minor=req.amount_minor, occurred_at=at, source='captured', status=status,
        dedupe_key=req.dedupe_key, payee=req.payee, reference=req.reference, account_last4=req.account_last4,
        device_id=req.device_id, captured_at=req.captured_at, weak_parse=req.weak_parse,
        category_id=c.category_id if c else None, classified_by=c.by if c else None,
        rule_pattern=c.pattern if c and c.by == 'rule' else None,
    )  # fmt: skip
    if not row:  # lost a race with the same key
        existing = await find_by_key(tx, ctx.user_id, req.dedupe_key)
        assert existing is not None
        return _Placed('duplicate', existing)
    await emit_changed(deps, tx, ctx.tz, row, 'created', tagged_via='rule' if c else None)
    return _Placed('saved_as_credit' if req.reversal else 'created', row)


async def ingest(deps: D, ctx: Ctx, req: IngestTransactionReq, now: datetime) -> IngestTransactionRes:
    """In one transaction with the outbox rows: dedupe, reversal, link to a hand-added credit or recurring post, replace an Unaccounted entry, else create. Then re-check the balance: a balance in the message opens a check, otherwise an open check is re-measured."""
    async with deps.as_user(ctx) as tx:
        await lock_user(tx, ctx.user_id)
        dup = await find_by_key(tx, ctx.user_id, req.dedupe_key)
        if dup:
            return IngestTransactionRes(outcome='duplicate', transaction=to_dto(dup))

        at = req.occurred_at
        placed = await _place(deps, tx, ctx, req, at)
        if placed.outcome != 'duplicate':
            if req.balance_after_minor is not None and await claim_newest(tx, ctx.user_id, at):
                await create_check(deps, tx, ctx, bank_minor=req.balance_after_minor, as_of=at, source='message', now=now)
            else:
                await evaluate_open(deps, tx, ctx.user_id, now, None, ctx.tz)
        final = await get_tx(tx, placed.row['id'])
        assert final is not None
        return IngestTransactionRes(outcome=placed.outcome, transaction=to_dto(final))


async def post_recurring(deps: D, ctx: Ctx, req: RecurringPostReq) -> RecurringPostRes:
    """Post a due rule, or link the debit the phone already captured (+-2 days, same amount, matching payee)."""
    try:
        add_days(req.due_date, 0)
    except ValueError:
        raise Errors.validation({'dueDate': 'Not a calendar day'}) from None
    async with deps.as_user(ctx) as tx:
        await lock_user(tx, ctx.user_id)
        key = f'rec:{req.rule_id}:{req.due_date}'
        done = await find_by_key(tx, ctx.user_id, key)
        if done:
            return RecurringPostRes(outcome='already_posted', transaction=to_dto(done))

        cat = await get_category(tx, req.category_id)
        y, m, d = (int(x) for x in req.due_date.split('-'))
        due = zoned_to_utc(Parts(y, m, d), ctx.tz)  # start of the due day: never in the future when the cron posts it
        hint = req.match_hint or req.name

        captured = await _near(
            tx, ctx, due, 2,
            "t.type = 'debit' AND t.source = 'captured' AND t.recurring_id IS NULL AND t.amount_minor = $6", [req.amount_minor],
        )  # fmt: skip
        hit = next((c for c in captured if _hint_matches(hint, c['payee'])), None)
        if hit:
            await tx.query(
                """UPDATE transactions SET recurring_id = $2, category_id = COALESCE(category_id, $3), status = 'confirmed', linked = true,
                classified_by = CASE WHEN category_id IS NULL THEN 'recurring' ELSE classified_by END, updated_at = now() WHERE id = $1""",
                [hit['id'], req.rule_id, cat.id],
            )
            await add_alias(tx, ctx.user_id, key, hit['id'])
            fresh = await get_tx(tx, hit['id'])
            assert fresh is not None
            await emit_changed(deps, tx, ctx.tz, fresh, 'updated', before=hit['category_id'])
            return RecurringPostRes(outcome='linked', transaction=to_dto(fresh))

        row = await insert_tx(
            tx, ctx.user_id, type='debit', amount_minor=req.amount_minor, occurred_at=due, source='recurring',
            status='confirmed', dedupe_key=key, payee=req.name, category_id=cat.id, recurring_id=req.rule_id,
            match_hint=hint, classified_by='recurring',
        )  # fmt: skip
        if not row:
            existing = await find_by_key(tx, ctx.user_id, key)
            assert existing is not None
            return RecurringPostRes(outcome='already_posted', transaction=to_dto(existing))
        await emit_changed(deps, tx, ctx.tz, row, 'created')
        return RecurringPostRes(outcome='posted', transaction=to_dto(row))
