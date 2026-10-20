"""Derived metrics (README 12), shared so budgets, dashboard, reports and Telegram agree."""

from typing import Literal

from .money import TEN_RUPEES, Paise

LimitStatus = Literal['over', 'close', 'fast', 'ok']


def available_balance(opening: Paise, credits: Paise, debits: Paise) -> Paise:
    """opening + credits - debits (balance is derived, never stored)."""
    return opening + credits - debits


def pace_projection(spent: Paise, days_elapsed: int, days_in_month: int) -> Paise:
    """spent / days elapsed x days in month, rounded to the nearest ₹10 (integer math, halves up)."""
    if days_elapsed <= 0:
        return 0
    step = TEN_RUPEES
    return ((2 * spent * days_in_month + days_elapsed * step) // (2 * days_elapsed * step)) * step


def reaches_pct(spent: Paise, limit: Paise, pct: float) -> bool:
    """True once spent reaches `pct` percent of the limit (no float drift)."""
    return limit > 0 and spent * 100 >= pct * limit


def pct_of(spent: Paise, limit: Paise) -> int:
    """Whole percent for display, floored so 99.9% never reads 100%."""
    return (spent * 100) // limit if limit > 0 else 0


def limit_status(*, spent: Paise, limit: Paise, alert_pct: float, projected: Paise) -> LimitStatus:
    """over >= 100%; close >= alert level; fast = projected past the limit while under the alert level; else ok."""
    if reaches_pct(spent, limit, 100):
        return 'over'
    if reaches_pct(spent, limit, alert_pct):
        return 'close'
    if projected > limit:
        return 'fast'
    return 'ok'


def plan_left(planned: Paise, spent_on_planned: Paise) -> Paise:
    return planned - spent_on_planned


def safe_per_day(left: Paise, days_left: int) -> Paise:
    """Plan left / days left (including today), floored, never negative."""
    return max(0, left // days_left) if days_left > 0 else 0


def kept_rate(income: Paise, spent: Paise) -> float:
    """Share of income not spent; 0 with no income."""
    return (income - spent) / income if income > 0 else 0.0

