"""Balance check (README 3.6, 10.9): gap = bank - ledger; wait the grace period; book one Unaccounted entry."""

from datetime import datetime, timedelta

from bt.common import DEFAULT_TZ, Ctx, Errors
from bt.contracts import BalanceCheckDto, BalanceCheckRes, BalanceChecksRes
from bt.db import Row, Tx

from .model import MIN_GAP, D, emit_changed, find_by_key, get_tx, insert_tx, lock_user, to_dto
from .settings import balance_at, get_settings


def _grace_end(c: Row, grace_hours: int) -> datetime:
    return c['checked_at'] + timedelta(hours=grace_hours)


def to_check_dto(c: Row, grace_hours: int) -> BalanceCheckDto:
    return BalanceCheckDto.model_validate(
        {**c, 'grace_ends_at': _grace_end(c, grace_hours) if c['status'] == 'open' else None}
    )


async def _get_check(tx: Tx, id: str) -> Row | None:
    return await tx.maybe_one('SELECT * FROM balance_checks WHERE id = $1 FOR UPDATE', [id])


async def _book(deps: D, tx: Tx, c: Row, gap: int, ledger: int, tz: str | None = None) -> Row:
    key = f'unaccounted:{c["id"]}'
    inserted = await insert_tx(
        tx, c['user_id'], type='debit' if gap < 0 else 'credit', amount_minor=abs(gap), occurred_at=c['as_of'],
        source='unaccounted', status='pending', dedupe_key=key,
    )  # fmt: skip
    if inserted:
        await emit_changed(deps, tx, tz, inserted, 'created')
    entry = inserted or await find_by_key(tx, c['user_id'], key)
    assert entry is not None
    booked = await tx.maybe_one(
        "UPDATE balance_checks SET status = 'booked', transaction_id = $2, ledger_balance_minor = $3, gap_minor = $4 WHERE id = $1 RETURNING *",
        [c['id'], entry['id'], ledger, gap],
    )
    assert booked is not None
    return booked


async def _evaluate(deps: D, tx: Tx, c: Row, now: datetime, *, force: bool = False, tz: str | None = None) -> Row:
    """Re-measure an open check at the bank balance's time. A late message that closes the gap resolves it; after the grace period (or when forced) the gap is booked."""
    if c['status'] != 'open':
        return c
    s = await get_settings(tx, c['user_id'])
    ledger = await balance_at(tx, c['user_id'], c['as_of'])
    gap = c['bank_balance_minor'] - ledger
    if abs(gap) < MIN_GAP:
        r = await tx.maybe_one(
            "UPDATE balance_checks SET status = 'resolved', ledger_balance_minor = $2, gap_minor = $3 WHERE id = $1 RETURNING *",
            [c['id'], ledger, gap],
        )
        assert r is not None
        return r
    if force or now >= _grace_end(c, s.reconcile_grace_hours):
        return await _book(deps, tx, c, gap, ledger, tz)
    r = await tx.maybe_one(
        'UPDATE balance_checks SET ledger_balance_minor = $2, gap_minor = $3 WHERE id = $1 RETURNING *', [c['id'], ledger, gap]
    )
    assert r is not None
    return r


async def evaluate_open(
    deps: D, tx: Tx, user_id: str, now: datetime, only: str | None = None, tz: str | None = None
) -> None:
    """Re-evaluate the user's open check after the ledger changed."""
    open_checks = await tx.many(
        f"SELECT * FROM balance_checks WHERE user_id = $1 AND status = 'open' {'AND id = $2' if only else ''} FOR UPDATE",
        [user_id, only] if only else [user_id],
    )
    for c in open_checks:
        await _evaluate(deps, tx, c, now, tz=tz)


async def claim_newest(tx: Tx, user_id: str, as_of: datetime) -> bool:
    """True (and records it) when `as_of` is newer than every balance used so far: out-of-order messages may not supply one."""
    await get_settings(tx, user_id)
    n = await tx.execute(
        'UPDATE ledger_settings SET last_balance_at = $2 WHERE user_id = $1 AND (last_balance_at IS NULL OR last_balance_at < $2)',
        [user_id, as_of],
    )
    return n > 0


async def create_check(
    deps: D, tx: Tx, ctx: Ctx, *, bank_minor: int, as_of: datetime, source: str, now: datetime
) -> tuple[Row | None, bool]:
    """Compare a bank balance with the ledger. Under Rs 1: nothing. Otherwise a new open check replaces any older one, waits the grace period, then books one Unaccounted entry."""
    s = await get_settings(tx, ctx.user_id)
    ledger = await balance_at(tx, ctx.user_id, as_of)
    gap = bank_minor - ledger
    small = abs(gap) < MIN_GAP
    # a newer measurement replaces the older open one: "resolved" if the books match, else "ignored" (superseded)
    await tx.query(
        "UPDATE balance_checks SET status = $2 WHERE user_id = $1 AND status = 'open'",
        [ctx.user_id, 'resolved' if small else 'ignored'],
    )
    if source == 'manual':
        await tx.query(
            'UPDATE ledger_settings SET last_balance_at = GREATEST(COALESCE(last_balance_at, $2), $2) WHERE user_id = $1',
            [ctx.user_id, as_of],
        )
    if small and source == 'message':
        return None, True

    check = await tx.maybe_one(
        """INSERT INTO balance_checks (user_id, bank_balance_minor, ledger_balance_minor, gap_minor, source, status, checked_at, as_of)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING *""",
        [ctx.user_id, bank_minor, ledger, gap, source, 'ignored' if small else 'open', now, as_of],
    )
    assert check is not None
    if not small:
        check = await _evaluate(deps, tx, check, now, tz=ctx.tz)
        await deps.bus.enqueue(
            tx, 'balance.reconcile', {'user_id': ctx.user_id, 'check_id': check['id']},
            key=f'reconcile:{check["id"]}',
            start_after_seconds=s.reconcile_grace_hours * 3600 if s.reconcile_grace_hours > 0 else None,
        )  # fmt: skip
    return check, small


async def _result(tx: Tx, ctx: Ctx, c: Row, matches: bool) -> BalanceCheckRes:
    s = await get_settings(tx, ctx.user_id)
    entry = await get_tx(tx, c['transaction_id']) if c['transaction_id'] else None
    return BalanceCheckRes(
        check=to_check_dto(c, s.reconcile_grace_hours),
        matches=matches,
        ledger_balance_minor=await balance_at(tx, ctx.user_id),
        transaction=to_dto(entry) if entry else None,
    )


async def manual_check(deps: D, ctx: Ctx, bank_minor: int, now: datetime) -> BalanceCheckRes:
    """The bank balance typed on the Now / Ledger page."""
    async with deps.as_user(ctx) as tx:
        await lock_user(tx, ctx.user_id)
        check, matches = await create_check(deps, tx, ctx, bank_minor=bank_minor, as_of=now, source='manual', now=now)
        assert check is not None  # only a matching *message* leaves no row
        return await _result(tx, ctx, check, matches)


async def book_now(deps: D, ctx: Ctx, id: str, now: datetime) -> BalanceCheckRes:
    """"Book it now" instead of waiting out the grace period."""
    async with deps.as_user(ctx) as tx:
        await lock_user(tx, ctx.user_id)
        c = await _get_check(tx, id)
        if not c:
            raise Errors.not_found('Balance check')
        if c['status'] not in ('open', 'booked'):
            raise Errors.conflict('This check is already closed')
        done = await _evaluate(deps, tx, c, now, force=True, tz=ctx.tz)
        return await _result(tx, ctx, done, abs(done['gap_minor']) < MIN_GAP)


async def ignore(deps: D, ctx: Ctx, id: str) -> BalanceCheckRes:
    """"This gap is a bank hold, not missing money" (README 17): an open check becomes `ignored` and nothing is booked."""
    async with deps.as_user(ctx) as tx:
        await lock_user(tx, ctx.user_id)
        c = await _get_check(tx, id)
        if not c:
            raise Errors.not_found('Balance check')
        if c['status'] != 'open':
            raise Errors.conflict('This check is already closed')
        done = await tx.one("UPDATE balance_checks SET status = 'ignored' WHERE id = $1 RETURNING *", [id])
        return await _result(tx, ctx, done, abs(done['gap_minor']) < MIN_GAP)


async def list_checks(deps: D, ctx: Ctx, limit: int) -> BalanceChecksRes:
    async with deps.as_user(ctx) as tx:
        s = await get_settings(tx, ctx.user_id)
        rows = await tx.many(
            'SELECT * FROM balance_checks WHERE user_id = $1 ORDER BY checked_at DESC, id LIMIT $2', [ctx.user_id, limit]
        )
        return BalanceChecksRes(items=[to_check_dto(r, s.reconcile_grace_hours) for r in rows])


# balance.reconcile job (consumer and cron)
def _job_ctx(user_id: str) -> Ctx:
    return Ctx(user_id=user_id, tz=DEFAULT_TZ, request_id='job:balance.reconcile')


async def reconcile(deps: D, user_id: str, check_id: str | None, now: datetime) -> None:
    """Evaluate one check (or the user's open check). Idempotent: closed checks are skipped."""
    async with deps.as_user(_job_ctx(user_id)) as tx:
        await lock_user(tx, user_id)
        await evaluate_open(deps, tx, user_id, now, check_id)


async def reconcile_due(deps: D, now: datetime) -> int:
    """Cron: every open check whose grace period has ended."""
    async with deps.as_system() as tx:
        due = await tx.many(
            """SELECT c.user_id, c.id FROM balance_checks c LEFT JOIN ledger_settings s ON s.user_id = c.user_id
      WHERE c.status = 'open' AND c.checked_at + make_interval(hours => COALESCE(s.reconcile_grace_hours, 6)) <= $1
      ORDER BY c.checked_at LIMIT 500""",
            [now],
        )
    for d in due:
        await reconcile(deps, d['user_id'], d['id'], now)
    return len(due)
