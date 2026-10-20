"""The numbers a limit shows: pct, month-end projection, status."""

from dataclasses import dataclass
from datetime import datetime

from lbstash.common import (
    Clock,
    MonthKey,
    days_in_month,
    limit_status,
    month_key,
    month_progress,
    pace_projection,
    pct_of,
)
from lbstash.common.metrics import LimitStatus


def days_elapsed(month: MonthKey, tz: str, now: datetime) -> int:
    """Days elapsed in `month` as of `now` in the user's zone (past month: all, future month: 0)."""
    cur = month_key(now, tz)
    if month < cur:
        return days_in_month(month)
    if month > cur:
        return 0
    return month_progress(now, tz).day


def effective_alert_pct(warn_pct: int | None, alert_level: int) -> int:
    """A limit's own warn percentage wins over the user's alert level."""
    return warn_pct if warn_pct is not None else alert_level


@dataclass(frozen=True, slots=True)
class BudgetFigures:
    pct: int
    projected_minor: int
    status: LimitStatus


def budget_figures(
    *, spent: int, limit: int, alert_pct: int, month: MonthKey, tz: str, now: Clock, warn_on_pace: bool
) -> BudgetFigures:
    """pct, month-end projection and status for one limit (shared by the Limits page, Now and the alert job)."""
    projected = pace_projection(spent, days_elapsed(month, tz, now()), days_in_month(month))
    status = limit_status(spent=spent, limit=limit, alert_pct=alert_pct, projected=projected)
    # warn_on_pace off: keep the projection, never report 'fast'
    return BudgetFigures(pct_of(spent, limit), projected, 'ok' if status == 'fast' and not warn_on_pace else status)
