"""Reports contracts. No database: every figure is composed on read. Money is integer paise, rates are fractions (0.118 = 11.8%), months 'YYYY-MM', days 'YYYY-MM-DD'."""

from typing import Literal

from pydantic import Field, TypeAdapter

from .base import (
    Bool,
    CoerceInt,
    DateKey,
    Int,
    IsoDateTime,
    Model,
    MonthKey,
    Number,
    Opt,
    Paise,
    Uuid,
    discriminated,
)


# GET /dashboard?month= (the Now page)
class DashboardQuery(Model):
    month: Opt[MonthKey] = None


class LimitAttention(Model):
    """A limit at or above its alert level (WATCH). `category` is display-cased ("Fun")."""

    kind: Literal['limit']
    category: str
    pct: Int
    status: Literal['close', 'over']


class UntaggedAttention(Model):
    """Debits waiting for a tag (TAG)."""

    kind: Literal['untagged']
    count: Int


class NeedsLookAttention(Model):
    """Messages that could not be read (LOOK)."""

    kind: Literal['needs_look']
    count: Int


class UnaccountedAttention(Model):
    """Balance-check gaps booked as Unaccounted and not yet split or tagged."""

    kind: Literal['unaccounted']
    count: Int


class RecurringAttention(Model):
    """The next recurring payment that will leave (NEXT)."""

    kind: Literal['recurring']
    name: str
    amount: Paise
    due: DateKey


AttentionItem = discriminated(
    'kind', LimitAttention, UntaggedAttention, NeedsLookAttention, UnaccountedAttention, RecurringAttention
)
AttentionItemAdapter: TypeAdapter[
    LimitAttention | UntaggedAttention | NeedsLookAttention | UnaccountedAttention | RecurringAttention
] = TypeAdapter(AttentionItem)


class DashboardBalance(Model):
    carried_over: Paise
    income: Paise
    spent: Paise
    available: Paise


class SafeToSpend(Model):
    """`per_day` is plan left / days left (today included), rounded down to whole rupees."""

    plan_left: Paise
    days_left: Int
    per_day: Paise


class FlowItem(Model):
    name: str
    amount: Paise


class DashboardRes(Model):
    month: MonthKey
    # Day of the month "today" is on (the month's last day for past months, 0 for future months).
    day_of_month: Int
    days_in_month: Int
    balance: DashboardBalance
    safe_to_spend: SafeToSpend
    # Spent per category, biggest first, then "Still available" last. Sums to carried over + income.
    flow: list[FlowItem]
    attention: list[AttentionItem]
    last_captured_at: IsoDateTime | None
    untagged_count: Int
    unaccounted_count: Int
    needs_look_count: Int
    # Unread limit alerts (nav badge).
    alert_badge_count: Int
    # Optional parts that could not be read this time (e.g. 'ingest'); the figures that depend on them are zero/empty.
    degraded: list[str]


# GET /reports/daily?month=
class ReportDailyQuery(Model):
    month: Opt[MonthKey] = None


class ReportDailyItem(Model):
    day: DateKey
    spent_minor: Paise


class ReportDailyRes(Model):
    month: MonthKey
    day_of_month: Int
    days_in_month: Int
    # One entry per calendar day (future days are 0). Fixed payments (categories of your recurring rules) are left out.
    items: list[ReportDailyItem]
    total_minor: Paise
    # total / days elapsed (today included), rounded to a paisa.
    average_minor: Paise
    # Display names of the categories that were left out.
    fixed_categories: list[str]


# GET /reports/months?range=6 and /reports/category-matrix?range=6 (Trends)
class ReportRangeQuery(Model):
    range: CoerceInt = Field(default=6, ge=1, le=24)


class MonthPace(Model):
    """Month-end pace: flexible spend so far / days elapsed x days in month (Rs 10), plus the fixed payments."""

    day_of_month: Int
    days_in_month: Int
    spent_so_far_minor: Paise
    flexible_so_far_minor: Paise
    # Sum committed per month over the fixed categories (Rent, SIP).
    fixed_minor: Paise
    flexible_pace_minor: Paise
    # flexible_pace + fixed: where the month ends at this pace.
    pace_spent_minor: Paise
    # income so far - pace_spent.
    pace_kept_minor: Paise


class ReportMonthItem(Model):
    month: MonthKey
    income_minor: Paise
    spent_minor: Paise
    kept_minor: Paise
    # kept / income as a fraction (0 when there is no income).
    kept_rate: Number
    # Balance at the month's end (today's balance for the month in progress).
    closing_minor: Paise
    in_progress: Bool
    pace: MonthPace | None


class ReportMonthAverages(Model):
    # Finished months with any activity: what the averages are over.
    full_months: Int
    avg_monthly_spend_minor: Paise
    avg_kept_minor: Paise
    # Sum kept / sum income over the same months.
    avg_kept_rate: Number
    # Balance today - balance at the end of the first month with activity.
    balance_since_minor: Paise
    balance_since_month: MonthKey | None


class ReportMonthsRes(Model):
    # Last month of the range = the month in progress.
    end: MonthKey
    items: list[ReportMonthItem]
    averages: ReportMonthAverages


class ReportMatrixMonth(Model):
    month: MonthKey
    spent_minor: Paise


class ReportMatrixItem(Model):
    category_id: Uuid
    # Stored lowercase; show with display_tag.
    name: str
    by_month: list[ReportMatrixMonth]
    # Average of the finished months.
    usual_minor: Paise
    spent_so_far_minor: Paise
    # This month's pace for the category (Rs 10).
    pace_minor: Paise
    # pace - usual; positive = above a usual month.
    change_minor: Paise


class ReportMatrixRes(Model):
    end: MonthKey
    months: list[MonthKey]
    full_months: Int
    day_of_month: Int
    days_in_month: Int
    # Flexible categories only (categories of your recurring rules that stay the same are left out), most above usual first.
    items: list[ReportMatrixItem]
