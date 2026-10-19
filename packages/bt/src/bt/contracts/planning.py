"""Planning service contracts: plans, plan lines, budgets (limits), alerts, planning settings."""

from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .base import (
    Bool,
    Int,
    Model,
    MonthKey,
    NonNegativePaise,
    Opt,
    OptNull,
    Paise,
    PositivePaise,
    TimeStr,
    Uuid,
    partial,
    refine_fail,
)

_Tag = Annotated[str, StringConstraints(min_length=1, max_length=64)]
_WarnPct = Annotated[Int, Field(ge=50, le=99)]


class PlanLineDto(Model):
    category_id: Uuid
    category_name: str
    allocated_minor: Paise


class PlanDto(Model):
    month: MonthKey
    total_minor: Paise
    lines: list[PlanLineDto]


class PlanLineWithSpend(PlanLineDto):
    spent_minor: Paise


class PlanWithSpendDto(PlanDto):
    """`GET /plans/:month` (public and internal): plan with spend per line filled in from the ledger."""

    lines: list[PlanLineWithSpend]
    assigned_minor: Paise
    unassigned_minor: Paise


LimitStatus = Literal['ok', 'fast', 'close', 'over']


class BudgetDto(Model):
    id: Uuid
    category_id: Uuid
    category_name: str
    limit_minor: Paise
    period: Literal['monthly']
    warn_pct: _WarnPct | None
    active: Bool
    spent_minor: Paise
    pct: Int
    projected_minor: Paise
    status: LimitStatus


class BudgetsRes(Model):
    """`GET /budgets?month=`"""

    month: MonthKey
    alert_level: Int
    items: list[BudgetDto]


class AlertDto(Model):
    id: Uuid
    budget_id: Uuid
    category_name: str
    level: Literal['alert', 'exceeded']
    period_key: str
    sent_at: TimeStr
    read_at: TimeStr | None


class AlertsRes(Model):
    unread_count: Int
    items: list[AlertDto]


class PlanningSettings(Model):
    # 70, 80 or 90 (default 80).
    alert_level: Literal[70, 80, 90]
    warn_on_pace: Bool


PlanningSettingsPatch = partial(PlanningSettings, 'PlanningSettingsPatch')


class PlanCreditReq(Model):
    """Internal: ledger tells planning a hand-added credit should raise the month's plan total. Idempotent per transaction."""

    transaction_id: Uuid
    amount_minor: PositivePaise


class PlanCreditRes(Model):
    total_minor: Paise


# additive: request shapes for the public routes
class PlanLineInput(Model):
    """One plan line in `PUT /plans/:month`: the category by id, or by a (possibly new) tag. Exactly one of the two."""

    category_id: Opt[Uuid] = None
    tag: Opt[_Tag] = None
    allocated_minor: NonNegativePaise

    @model_validator(mode='after')
    def _either(self) -> 'PlanLineInput':
        if (self.category_id is None) == (self.tag is None):
            refine_fail(('Give either categoryId or tag', ('categoryId',)))
        return self


class PlanPutReq(Model):
    """`PUT /plans/:month`: replaces the total and every line (the response is the new PlanWithSpendDto)."""

    total_minor: NonNegativePaise
    lines: Annotated[list[PlanLineInput], Field(max_length=100)]


class BudgetsQuery(Model):
    month: Opt[MonthKey] = None


class BudgetCreateReq(Model):
    """`POST /budgets`: category by id or tag. Give the limit, or `use_month_allocation` to take it from `month`'s plan line (default: this month). `warn_pct` overrides the alert level for this limit."""

    category_id: Opt[Uuid] = None
    tag: Opt[_Tag] = None
    limit_minor: Opt[PositivePaise] = None
    period: Literal['monthly'] = 'monthly'
    warn_pct: OptNull[_WarnPct] = None
    use_month_allocation: Bool = False
    month: Opt[MonthKey] = None

    @model_validator(mode='after')
    def _checks(self) -> 'BudgetCreateReq':
        issues: list[tuple[str, tuple[str, ...]]] = []
        if (self.category_id is None) == (self.tag is None):
            issues.append(('Give either categoryId or tag', ('categoryId',)))
        if not (self.use_month_allocation or self.limit_minor is not None):
            issues.append(('Give a limit, or use the month allocation', ('limitMinor',)))
        if issues:
            refine_fail(*issues)
        return self


class BudgetPatchReq(Model):
    """`PATCH /budgets/:id`. Raising the limit (or the warn percentage) re-arms alerts for the current period."""

    limit_minor: Opt[PositivePaise] = None
    warn_pct: OptNull[_WarnPct] = None
    active: Opt[Bool] = None
    use_month_allocation: Opt[Bool] = None
    month: Opt[MonthKey] = None

    @model_validator(mode='after')
    def _something(self) -> 'BudgetPatchReq':
        if not self.present_keys():
            refine_fail('Nothing to change')
        return self


class AlertReadRes(Model):
    """`POST /alerts/:id/read`: the alert and the new badge count."""

    alert: AlertDto
    unread_count: Int
