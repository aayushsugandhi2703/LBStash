"""Helpers shared by the read models."""

from dataclasses import dataclass

from bt.clients import CallAs
from bt.common import Clock, Ctx, MonthKey, days_in_month, month_progress


def call_as(ctx: Ctx) -> CallAs:
    """Who a client call is made for: always the token's user and zone, never anything from the request."""
    return CallAs(user_id=ctx.user_id, tz=ctx.tz, request_id=ctx.request_id)


@dataclass(frozen=True, slots=True)
class Progress:
    month: MonthKey
    day_of_month: int
    days_in_month: int
    days_left: int
    current: MonthKey


def progress_of(clock: Clock, tz: str, month: MonthKey | None = None) -> Progress:
    """Where "today" sits in `month`, in the user's zone. In progress: the real day, `days_left` at least 1. Finished: its last day. Future: day 0."""
    now = month_progress(clock(), tz)
    m = month or now.month
    days = days_in_month(m)
    if m == now.month:
        return Progress(m, now.day, days, max(1, days - now.day), now.month)
    if m < now.month:
        return Progress(m, days, days, 0, now.month)
    return Progress(m, 0, days, days, now.month)


def avg(total: int, n: int) -> int:
    """`total / n` rounded half up in integers (Python's `round` goes to even); 0 when n <= 0."""
    return (2 * total + n) // (2 * n) if n > 0 else 0


def name_key(name: str) -> tuple[str, str]:
    """Sort key for display names: case-insensitive, then exact for a stable order."""
    return (name.casefold(), name)
