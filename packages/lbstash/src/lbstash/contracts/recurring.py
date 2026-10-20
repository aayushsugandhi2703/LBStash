"""Recurring service contracts: rules the cron posts through the transactions (or links to a captured debit within 2 days)."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, TypeAdapter, model_validator

from .base import (
    Bool,
    DateKey,
    Int,
    Model,
    Opt,
    OptNull,
    Paise,
    PositivePaise,
    Uuid,
    discriminated,
    refine_fail,
)


class MonthlySchedule(Model):
    kind: Literal['monthly']
    day: Annotated[Int, Field(ge=1, le=31)]


class WeeklySchedule(Model):
    kind: Literal['weekly']
    weekday: Annotated[Int, Field(ge=0, le=6)]


class YearlySchedule(Model):
    kind: Literal['yearly']
    month: Annotated[Int, Field(ge=1, le=12)]
    day: Annotated[Int, Field(ge=1, le=31)]


Schedule = discriminated('kind', MonthlySchedule, WeeklySchedule, YearlySchedule)
ScheduleAdapter: TypeAdapter[MonthlySchedule | WeeklySchedule | YearlySchedule] = TypeAdapter(Schedule)


class RecurringRuleDto(Model):
    id: Uuid
    name: str
    category_id: Uuid
    category_name: str
    amount_minor: PositivePaise
    schedule: Schedule
    next_due: DateKey
    paused: Bool
    ends_on: DateKey | None
    # Short line under the name on the Repeats page ("to landlord").
    note: str | None = None
    # Payee or keyword used to link an already-captured debit within +-2 days of the due date.
    match_hint: str | None = None
    # Counts toward `committed_minor`: not paused and not past its end date.
    active: Bool = True


class RecurringRes(Model):
    """`GET /recurring` (public and internal). `committed_minor` = sum over active rules, per month."""

    items: list[RecurringRuleDto]
    committed_minor: Paise


RuleName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
RuleNote = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
RuleHint = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
_Tag = Annotated[str, StringConstraints(min_length=1, max_length=64)]


class CreateRecurringReq(Model):
    """`POST /recurring`. Give `category_id` or a `tag` (a new tag becomes a category). `starts_on` defaults to today and may not be in the past."""

    name: RuleName
    category_id: Opt[Uuid] = None
    tag: Opt[_Tag] = None
    amount_minor: PositivePaise
    schedule: Schedule
    starts_on: Opt[DateKey] = None
    ends_on: OptNull[DateKey] = None
    match_hint: OptNull[RuleHint] = None
    note: OptNull[RuleNote] = None

    @model_validator(mode='after')
    def _either(self) -> 'CreateRecurringReq':
        if bool(self.category_id) == bool(self.tag):
            refine_fail('give either categoryId or tag')
        return self


class PatchRecurringReq(Model):
    """`PATCH /recurring/:id`. Edits apply from the next occurrence. `paused` pauses or resumes; `skip_next` skips one occurrence."""

    name: Opt[RuleName] = None
    category_id: Opt[Uuid] = None
    tag: Opt[_Tag] = None
    amount_minor: Opt[PositivePaise] = None
    schedule: Opt[Schedule] = None
    ends_on: OptNull[DateKey] = None
    match_hint: OptNull[RuleHint] = None
    note: OptNull[RuleNote] = None
    paused: Opt[Bool] = None
    skip_next: Opt[Literal[True]] = None

    @model_validator(mode='after')
    def _checks(self) -> 'PatchRecurringReq':
        issues: list[str] = []
        if not self.present_keys():
            issues.append('nothing to change')
        if self.category_id and self.tag:
            issues.append('give either categoryId or tag')
        if issues:
            refine_fail(*issues)
        return self


class RecurringMutationRes(Model):
    """Every mutation answers with the row and the figure the page shows beside it."""

    rule: RecurringRuleDto
    committed_minor: Paise


class RecurringDeleteRes(Model):
    ok: Literal[True]
    committed_minor: Paise
