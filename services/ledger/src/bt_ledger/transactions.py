"""Transactions: read, tag (first write wins), split an Unaccounted entry, manual rows and the Ledger page."""

from datetime import datetime
from typing import Literal

from bt.common import Ctx, Cursor, Errors, decode_cursor, month_range, to_page
from bt.contracts import (
    CategoryStatDto,
    LedgerCountsDto,
    LedgerPageDto,
    LedgerQuery,
    ManualTransactionReq,
    PatchTransactionRes,
    PendingRes,
    SplitPart,
    SplitRes,
    TagRes,
)
from bt.db import Tx, Where

from .aggregates import UUID_RE, category_stats, figures
from .categories import get_category, resolve_category
from .classify import classify, remember_payee
from .model import (
    TX_SELECT,
    D,
    TxRow,
    emit_changed,
    get_tx,
    get_txs,
    insert_tx,
    key_of,
    lock_user,
    new_key,
    to_dto,
    to_row_dto,
)
from .settings import balance_at


async def get_transaction(deps: D, ctx: Ctx, id: str) -> TxRow:
    async with deps.as_user(ctx) as tx:
        r = await get_tx(tx, id)
        if not r:
            raise Errors.not_found('Transaction')
        return r


async def pending(deps: D, ctx: Ctx, limit: int) -> PendingRes:
    """Oldest first, like the Telegram queue. `count` is the total, `items` at most `limit`."""
    async with deps.as_user(ctx) as tx:
        count = (await tx.one("SELECT COUNT(*)::int AS n FROM transactions WHERE user_id = $1 AND status = 'pending'", [ctx.user_id]))['n']
        rows = await tx.many(
            f"{TX_SELECT} WHERE t.user_id = $1 AND t.status = 'pending' ORDER BY t.occurred_at, t.id LIMIT $2", [ctx.user_id, limit]
        )
        return PendingRes(count=count, items=[to_dto(r) for r in rows])


# tagging (README 3.3, 10.2)
async def tag_in(
    deps: D,
    tx: Tx,
    ctx: Ctx,
    row: TxRow,
    *,
    tag: str | None = None,
    category_id: str | None = None,
    via: Literal['telegram', 'web'],
    recategorize: bool = False,
) -> TagRes:
    """Give a row its category. First write wins unless `recategorize`. Remembers the payee and tags that payee's other pending items."""
    if row['status'] == 'reversed':
        raise Errors.unprocessable('A reversed transaction cannot be tagged')

    def unchanged(created: bool = False) -> TagRes:
        return TagRes(
            transaction=to_dto(row), changed=False, previous_category_id=row['category_id'], also_tagged_ids=[],
            category_created=created,
        )  # fmt: skip

    if row['category_id'] and not recategorize:
        return unchanged()

    created = False
    if category_id:
        c = await get_category(tx, category_id)
        if c.archived:
            raise Errors.unprocessable('That category is archived')
        target = c.id
    else:
        cat, created = await resolve_category(tx, ctx.user_id, tag or '')
        target = cat.id
    if row['category_id'] == target:
        return unchanged(created)

    before = row['category_id']
    await tx.query(
        "UPDATE transactions SET category_id = $2, status = 'confirmed', classified_by = 'user', rule_pattern = NULL, updated_at = now() WHERE id = $1",
        [row['id'], target],
    )
    await remember_payee(tx, ctx.user_id, row['payee'], target)

    key = key_of(row['payee'])
    also = (
        await tx.many(
            """UPDATE transactions SET category_id = $2, status = 'confirmed', classified_by = 'memory', rule_pattern = NULL, updated_at = now()
          WHERE user_id = $1 AND payee_key = $3 AND status = 'pending' AND category_id IS NULL AND source <> 'unaccounted' AND id <> $4 RETURNING id""",
            [ctx.user_id, target, key, row['id']],
        )
        if key
        else []
    )

    fresh = await get_tx(tx, row['id'])
    assert fresh is not None
    await emit_changed(deps, tx, ctx.tz, fresh, 'updated', before=before, tagged_via=via)
    for o in await get_txs(tx, [a['id'] for a in also]):
        await emit_changed(deps, tx, ctx.tz, o, 'updated', before=None, tagged_via='rule')
    return TagRes(
        transaction=to_dto(fresh), changed=True, previous_category_id=before, also_tagged_ids=[a['id'] for a in also],
        category_created=created,
    )  # fmt: skip


async def tag(
    deps: D, ctx: Ctx, id: str, *, tag: str | None, category_id: str | None, via: Literal['telegram', 'web']
) -> TagRes:
    async with deps.as_user(ctx) as tx:
        row = await get_tx(tx, id, lock=True)
        if not row:
            raise Errors.not_found('Transaction')
        return await tag_in(deps, tx, ctx, row, tag=tag, category_id=category_id, via=via)


async def patch(
    deps: D, ctx: Ctx, id: str, *, tag: str | None, category_id: str | None, recategorize: bool
) -> PatchTransactionRes:
    """Same as the internal tag, plus the figures the Ledger shows next to the row."""
    async with deps.as_user(ctx) as tx:
        row = await get_tx(tx, id, lock=True)
        if not row:
            raise Errors.not_found('Transaction')
        res = await tag_in(deps, tx, ctx, row, tag=tag, category_id=category_id, via='web', recategorize=recategorize)
        touched = [row['category_id'], res.transaction.category_id]
        return PatchTransactionRes(**dict(res), figures=await figures(tx, ctx, row['occurred_at'], touched))


# split an Unaccounted entry (README 3.6)
async def split(deps: D, ctx: Ctx, id: str, parts: list[SplitPart]) -> SplitRes:
    """Split an entry; parts add up exactly, so the balance never changes. An untagged part stays Unaccounted (at most one); tagged parts become manual rows."""
    async with deps.as_user(ctx) as tx:
        await lock_user(tx, ctx.user_id)
        row = await get_tx(tx, id, lock=True)
        if not row:
            raise Errors.not_found('Transaction')
        if row['source'] != 'unaccounted' or row['status'] != 'pending':
            raise Errors.unprocessable('Only an Unaccounted entry that is still waiting for a tag can be split')
        total = sum(p.amount_minor for p in parts)
        if total != row['amount_minor']:
            raise Errors.unprocessable('The parts must add up to the entry', {'entryMinor': row['amount_minor'], 'partsMinor': total})
        untagged = [p for p in parts if not p.tag and not p.category_id]
        if len(untagged) > 1:
            raise Errors.unprocessable('Only one part can stay Unaccounted')

        cats: list[str | None] = []
        for p in parts:
            if p.category_id:
                c = await get_category(tx, p.category_id)
                if c.archived:
                    raise Errors.unprocessable('That category is archived')
                cats.append(c.id)
            else:
                cats.append((await resolve_category(tx, ctx.user_id, p.tag))[0].id if p.tag else None)
        keep = next((i for i, p in enumerate(parts) if not p.tag and not p.category_id), 0)
        out: list[TxRow] = []
        for i, p in enumerate(parts):
            category_id = cats[i]
            if i == keep:
                await tx.query(
                    "UPDATE transactions SET amount_minor = $2, category_id = $3, status = $4, source = $5, description = $6, classified_by = $7, updated_at = now() WHERE id = $1",
                    [row['id'], p.amount_minor, category_id, 'confirmed' if category_id else 'pending',
                     'manual' if category_id else 'unaccounted',
                     'Split from Unaccounted' if category_id else row['description'], 'user' if category_id else None],
                )  # fmt: skip
                u = await get_tx(tx, row['id'])
                assert u is not None
                await emit_changed(deps, tx, ctx.tz, u, 'updated', before=None, tagged_via='web' if category_id else None)
                out.append(u)
            else:
                n = await insert_tx(
                    tx, ctx.user_id, type=row['type'], amount_minor=p.amount_minor, occurred_at=row['occurred_at'],
                    source='manual' if category_id else 'unaccounted', status='confirmed' if category_id else 'pending',
                    dedupe_key=new_key('split', row['id'], i), category_id=category_id,
                    description='Split from Unaccounted' if category_id else None, classified_by='user' if category_id else None,
                )  # fmt: skip
                assert n is not None
                await emit_changed(deps, tx, ctx.tz, n, 'created', tagged_via='web' if category_id else None)
                out.append(n)
        return SplitRes(items=[to_dto(r) for r in out], figures=await figures(tx, ctx, row['occurred_at'], cats))


# manual row (ingest resolving "Needs a look")
async def create_manual(deps: D, ctx: Ctx, b: ManualTransactionReq) -> TxRow:
    async with deps.as_user(ctx) as tx:
        await lock_user(tx, ctx.user_id)
        c = await classify(tx, ctx.user_id, b.payee)
        row = await insert_tx(
            tx, ctx.user_id, type=b.type, amount_minor=b.amount_minor, occurred_at=b.occurred_at, source='manual',
            status='confirmed' if c else 'pending', dedupe_key=new_key('manual'), payee=b.payee, description=b.description,
            category_id=c.category_id if c else None, classified_by=c.by if c else None,
            rule_pattern=c.pattern if c and c.by == 'rule' else None,
        )  # fmt: skip
        assert row is not None
        await emit_changed(deps, tx, ctx.tz, row, 'created', tagged_via='rule' if c else None)
        return row


# GET /ledger
def _filters(ctx: Ctx, q: LedgerQuery) -> Where:
    w = Where().add('t.user_id = $?', ctx.user_id)
    cat = (q.cat or '').strip().lower()
    if cat and cat != 'all':
        if cat in ('needs-tag', 'needs tag', 'needs_tag'):
            w.add("t.status = 'pending'")
        elif cat in ('uncategorised', 'uncategorized'):
            w.add('t.category_id IS NULL')
        elif UUID_RE.fullmatch(cat):
            w.add('t.category_id = $?', cat)
        else:
            w.add('lower(c.name) = $?', cat)
    if q.src == 'pending':
        w.add("t.status = 'pending'")
    elif q.src == 'unaccounted':
        w.add("t.source = 'unaccounted' AND t.status = 'pending'")
    elif q.src != 'all':
        w.add('t.source = $?', q.src)
    if q.month:
        start, end = month_range(q.month, ctx.tz)
        w.add('t.occurred_at >= $? AND t.occurred_at < $?', start, end)
    return w


def _cursor_of(r: TxRow) -> Cursor:
    # full microseconds: the millisecond wire format would repeat or skip rows that share a millisecond
    return Cursor(t=r['occurred_at'].isoformat(), id=r['id'])


async def ledger_page(deps: D, ctx: Ctx, q: LedgerQuery) -> LedgerPageDto:
    cursor = decode_cursor(q.cursor)
    async with deps.as_user(ctx) as tx:
        match_w = _filters(ctx, q)
        matching = (
            await tx.one(
                f"SELECT COUNT(*)::int AS n FROM transactions t LEFT JOIN categories c ON c.id = t.category_id AND c.user_id = t.user_id {match_w.sql}",
                match_w.params,
            )
        )['n']

        w = _filters(ctx, q)
        if cursor:
            w.add('(t.occurred_at, t.id) < ($?::timestamptz, $?::uuid)', cursor.t, cursor.id)
        w.params.append(q.limit + 1)
        rows: list[TxRow] = await tx.many(  # type: ignore[assignment]
            f'{TX_SELECT} {w.sql} ORDER BY t.occurred_at DESC, t.id DESC LIMIT ${len(w.params)}', w.params
        )
        page = to_page(rows, q.limit, _cursor_of)

        scope: tuple[datetime, datetime] | tuple[None, None] = month_range(q.month, ctx.tz) if q.month else (None, None)
        totals = await tx.one(
            """SELECT COUNT(*)::int AS n, COUNT(*) FILTER (WHERE status = 'pending')::int AS needs,
              COUNT(*) FILTER (WHERE status = 'pending' AND source = 'unaccounted')::int AS unacc
         FROM transactions WHERE user_id = $1 AND ($2::timestamptz IS NULL OR occurred_at >= $2) AND ($3::timestamptz IS NULL OR occurred_at < $3)""",
            [ctx.user_id, scope[0], scope[1]],
        )
        by_category: list[CategoryStatDto] = await category_stats(tx, ctx.user_id, scope[0], scope[1])
        return LedgerPageDto(
            month=q.month,
            items=[to_row_dto(r) for r in page.items],
            next_cursor=page.next_cursor,
            matching=matching,
            counts=LedgerCountsDto(all=totals['n'], needs_tag=totals['needs'], unaccounted=totals['unacc'], by_category=by_category),
            balance_minor=await balance_at(tx, ctx.user_id),
        )
