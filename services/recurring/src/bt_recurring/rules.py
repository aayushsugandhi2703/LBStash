"""Recurring rules: list, create, edit, delete, export. No FastAPI types here."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from bt.common import Clock, Ctx, Errors, add_days, date_key, to_iso
from bt.contracts import (
    CreateRecurringReq,
    MonthlySchedule,
    PatchRecurringReq,
    RecurringDeleteRes,
    RecurringMutationRes,
    RecurringRes,
    RecurringRuleDto,
    WeeklySchedule,
    YearlySchedule,
)
from bt.db import Queryable, Row
from bt.kit import Deps

from .schedule import Schedule, first_occurrence, is_real_date, next_occurrence


@dataclass(frozen=True, slots=True)
class RuleRow:
    """One `recurring_rules` row."""

    id: str
    user_id: str
    name: str
    note: str | None
    category_id: str
    amount_minor: int
    kind: str
    day_of_month: int | None
    weekday: int | None
    month_of_year: int | None
    next_due: str
    last_handled_due: str | None
    paused: bool
    ends_on: str | None
    match_hint: str | None


def to_row(r: Row) -> RuleRow:
    """A database row as a `RuleRow` (other columns are ignored)."""
    return RuleRow(**{k: r[k] for k in RuleRow.__dataclass_fields__})


def schedule_of(r: RuleRow) -> Schedule:
    """The schedule a row stores."""
    if r.kind == 'monthly':
        return MonthlySchedule(kind='monthly', day=r.day_of_month)  # type: ignore[arg-type]
    if r.kind == 'weekly':
        return WeeklySchedule(kind='weekly', weekday=r.weekday)  # type: ignore[arg-type]
    return YearlySchedule(kind='yearly', month=r.month_of_year, day=r.day_of_month)  # type: ignore[arg-type]


def _schedule_cols(s: Schedule) -> dict[str, Any]:
    return {
        'kind': s.kind,
        'day': None if isinstance(s, WeeklySchedule) else s.day,
        'weekday': s.weekday if isinstance(s, WeeklySchedule) else None,
        'month': s.month if isinstance(s, YearlySchedule) else None,
    }


def _same_schedule(a: Schedule, b: Schedule) -> bool:
    return _schedule_cols(a) == _schedule_cols(b)


def is_active(r: RuleRow) -> bool:
    """Counts toward the committed total: not paused and not past its end date."""
    return not r.paused and (r.ends_on is None or r.next_due <= r.ends_on)


def _to_dto(r: RuleRow, names: dict[str, str]) -> RecurringRuleDto:
    return RecurringRuleDto(
        id=r.id, name=r.name, category_id=r.category_id, category_name=names.get(r.category_id, 'untagged'),
        amount_minor=r.amount_minor, schedule=schedule_of(r), next_due=r.next_due, paused=r.paused, ends_on=r.ends_on,
        note=r.note, match_hint=r.match_hint, active=is_active(r),
    )


async def _committed_of(tx: Queryable) -> int:
    rows = await tx.query(
        'SELECT COALESCE(SUM(amount_minor), 0)::bigint AS total FROM recurring_rules '
        'WHERE NOT paused AND (ends_on IS NULL OR next_due <= ends_on)'
    )
    return int(rows[0]['total'])


async def _category_names(deps: Deps[Any], ctx: Ctx) -> dict[str, str]:
    res = await deps.clients.ledger.categories(ctx, include_archived=True)
    return {c.id: c.name for c in res.items}


async def _resolve_category(deps: Deps[Any], ctx: Ctx, category_id: str | None, tag: str | None) -> str:
    """`category_id` must be one of the user's categories; a tag is resolved (created if new) by the ledger."""
    if tag:
        return (await deps.clients.ledger.resolve_category(ctx, tag)).category.id
    res = await deps.clients.ledger.categories(ctx)
    if not any(c.id == category_id for c in res.items):
        raise Errors.validation({'categoryId': 'Unknown category'})
    assert category_id is not None
    return category_id


def _check_date(field: str, d: str) -> None:
    if not is_real_date(d):
        raise Errors.validation({field: 'Not a real date'})


async def list_rules(deps: Deps[Any], ctx: Ctx) -> RecurringRes:
    """Every rule with its category name, and the monthly total the active ones commit."""
    async with deps.as_user(ctx) as tx:
        rows = await tx.query('SELECT * FROM recurring_rules ORDER BY next_due, name, id')
    names = await _category_names(deps, ctx)
    rules = [to_row(r) for r in rows]
    return RecurringRes(
        items=[_to_dto(r, names) for r in rules],
        committed_minor=sum(r.amount_minor for r in rules if is_active(r)),
    )


async def create(deps: Deps[Any], ctx: Ctx, clock: Clock, body: CreateRecurringReq) -> RecurringMutationRes:
    """Create a rule; its first payment is the first occurrence on or after `starts_on` (today by default)."""
    today = date_key(clock(), ctx.tz)
    starts_on = body.starts_on or today
    _check_date('startsOn', starts_on)
    if starts_on < today:
        raise Errors.validation({'startsOn': 'The first payment cannot be in the past'})
    if body.ends_on:
        _check_date('endsOn', body.ends_on)
    next_due = first_occurrence(body.schedule, starts_on)
    if body.ends_on and body.ends_on < next_due:
        raise Errors.validation({'endsOn': 'The end date is before the first payment'})

    category_id = await _resolve_category(deps, ctx, body.category_id, body.tag)
    c = _schedule_cols(body.schedule)
    async with deps.as_user(ctx) as tx:
        row = to_row(
            await tx.one(
                """INSERT INTO recurring_rules (user_id, name, note, category_id, amount_minor, kind, day_of_month, weekday, month_of_year, next_due, ends_on, match_hint)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING *""",
                [ctx.user_id, body.name, body.note, category_id, body.amount_minor, c['kind'], c['day'], c['weekday'], c['month'],
                 next_due, body.ends_on, body.match_hint],
            )
        )
        committed = await _committed_of(tx)
    return RecurringMutationRes(rule=_to_dto(row, await _category_names(deps, ctx)), committed_minor=committed)


async def patch(deps: Deps[Any], ctx: Ctx, clock: Clock, rule_id: str, body: PatchRecurringReq) -> RecurringMutationRes:
    """Edit under a row lock. Pause, resume and skip never post anything."""
    today = date_key(clock(), ctx.tz)
    sent = body.model_fields_set  # `note: null` clears it, a missing `note` leaves it
    if body.ends_on:
        _check_date('endsOn', body.ends_on)
    category_id = await _resolve_category(deps, ctx, body.category_id, body.tag) if body.category_id or body.tag else None

    async with deps.as_user(ctx) as tx:
        cur = await tx.maybe_one('SELECT * FROM recurring_rules WHERE id = $1 FOR UPDATE', [rule_id])
        if cur is None:
            raise Errors.not_found('Recurring payment')
        r = to_row(cur)
        schedule = schedule_of(r)
        next_due, paused, last_handled_due = r.next_due, r.paused, r.last_handled_due

        # a new schedule starts after anything already handled, and never before today
        if body.schedule is not None and not _same_schedule(body.schedule, schedule):
            schedule = body.schedule
            after_handled = add_days(last_handled_due, 1) if last_handled_due else None
            next_due = first_occurrence(schedule, after_handled if after_handled and after_handled > today else today)
        if body.paused is not None:
            was_paused, paused = paused, body.paused
            # resuming never back-posts what was missed while paused; a running rule that is merely behind keeps its backlog
            if was_paused and not paused and next_due < today:
                next_due = first_occurrence(schedule, today)
        ends_on = body.ends_on if 'ends_on' in sent else r.ends_on
        if body.skip_next:
            if ends_on is not None and next_due > ends_on:
                raise Errors.unprocessable('This payment has already ended')
            last_handled_due = next_due
            next_due = next_occurrence(schedule, next_due)
        c = _schedule_cols(schedule)
        nxt = to_row(
            await tx.one(
                """UPDATE recurring_rules SET name = $2, note = $3, category_id = $4, amount_minor = $5, kind = $6, day_of_month = $7, weekday = $8,
                     month_of_year = $9, next_due = $10, last_handled_due = $11, paused = $12, ends_on = $13, match_hint = $14, updated_at = now()
                   WHERE id = $1 RETURNING *""",
                [rule_id, body.name or r.name, body.note if 'note' in sent else r.note, category_id or r.category_id,
                 body.amount_minor or r.amount_minor, c['kind'], c['day'], c['weekday'], c['month'], next_due,
                 last_handled_due, paused, ends_on, body.match_hint if 'match_hint' in sent else r.match_hint],
            )
        )
        committed = await _committed_of(tx)
    return RecurringMutationRes(rule=_to_dto(nxt, await _category_names(deps, ctx)), committed_minor=committed)


async def remove(deps: Deps[Any], ctx: Ctx, rule_id: str) -> RecurringDeleteRes:
    """Delete a rule (what it already posted stays in the ledger)."""
    async with deps.as_user(ctx) as tx:
        if not await tx.execute('DELETE FROM recurring_rules WHERE id = $1', [rule_id]):
            raise Errors.not_found('Recurring payment')
        return RecurringDeleteRes(ok=True, committed_minor=await _committed_of(tx))


def _json_value(v: Any) -> Any:
    # ISO timestamps with milliseconds and a Z
    return to_iso(v) if isinstance(v, datetime) else v


async def export_rows(deps: Deps[Any], ctx: Ctx) -> dict[str, Any]:
    """This service's part of the user's data export."""
    async with deps.as_user(ctx) as tx:
        rows = await tx.query('SELECT * FROM recurring_rules ORDER BY created_at, id')
    return {'service': 'recurring', 'tables': {'recurring_rules': [{k: _json_value(v) for k, v in r.items()} for r in rows]}}


async def delete_all_for(deps: Deps[Any], user_id: str) -> None:
    """Purge the user's rules on `account.deleted`."""
    async with deps.as_user(user_id) as tx:
        await tx.execute('DELETE FROM recurring_rules')
