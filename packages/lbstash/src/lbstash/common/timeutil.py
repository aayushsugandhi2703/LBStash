"""Time-zone aware month and day helpers (README 11). Pass a `Clock` so tests can freeze time. Naive datetimes are read as UTC."""

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import NamedTuple
from zoneinfo import ZoneInfo

Clock = Callable[[], datetime]
MonthKey = str  # 'YYYY-MM'
DateKey = str  # 'YYYY-MM-DD'


def system_clock() -> datetime:
    """Current instant (UTC)."""
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Parts:
    """Wall-clock fields in some zone."""

    y: int
    m: int
    d: int
    h: int = 0
    mi: int = 0
    s: int = 0


class MonthRange(NamedTuple):
    """[start, end) of a calendar month as instants."""

    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class MonthProgress:
    """'Today' within its month: day 18 of 31, 14 days left including today."""

    month: MonthKey
    day: int
    days: int
    days_left: int


@lru_cache(maxsize=64)
def _zone(tz: str) -> ZoneInfo:
    return ZoneInfo(tz)


def _aware(d: datetime) -> datetime:
    return d if d.tzinfo is not None else d.replace(tzinfo=UTC)


def tz_parts(date_: datetime, tz: str) -> Parts:
    """Wall-clock fields of an instant in `tz`."""
    local = _aware(date_).astimezone(_zone(tz))
    return Parts(local.year, local.month, local.day, local.hour, local.minute, local.second)


def _offset_seconds(instant: datetime, tz: str) -> int:
    off = instant.astimezone(_zone(tz)).utcoffset()
    assert off is not None
    return int(off.total_seconds())


def zoned_to_utc(p: Parts | Mapping[str, int], tz: str) -> datetime:
    """Local wall-clock time in `tz` -> UTC instant. Two-pass offset correction resolves DST gaps and folds."""
    parts = p if isinstance(p, Parts) else Parts(**p)
    guess = datetime(parts.y, parts.m, parts.d, parts.h, parts.mi, parts.s, tzinfo=UTC)
    t = guess - timedelta(seconds=_offset_seconds(guess, tz))
    return guess - timedelta(seconds=_offset_seconds(t, tz))


def month_key(date_: datetime, tz: str) -> MonthKey:
    """'YYYY-MM' of an instant in `tz`."""
    p = tz_parts(date_, tz)
    return f'{p.y:04d}-{p.m:02d}'


def date_key(date_: datetime, tz: str) -> DateKey:
    """'YYYY-MM-DD' of an instant in `tz`."""
    p = tz_parts(date_, tz)
    return f'{p.y:04d}-{p.m:02d}-{p.d:02d}'


_MONTH = re.compile(r'([0-9]{4})-(0[1-9]|1[0-2])')


def parse_month(key: MonthKey) -> tuple[int, int]:
    """'2026-10' -> (2026, 10). Raises `ValueError` for anything else."""
    m = _MONTH.fullmatch(key) if isinstance(key, str) else None
    if not m:
        raise ValueError(f'not a month: {key}')
    return int(m[1]), int(m[2])


def is_month_key(s: str) -> bool:
    """True if `s` is a valid 'YYYY-MM' key."""
    return isinstance(s, str) and _MONTH.fullmatch(s) is not None


def days_in_month(key: MonthKey) -> int:
    y, m = parse_month(key)
    nxt = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
    return (nxt - date(y, m, 1)).days


def month_range(key: MonthKey, tz: str) -> MonthRange:
    """[start, end) of a calendar month in `tz`."""
    y, m = parse_month(key)
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return MonthRange(zoned_to_utc(Parts(y, m, 1), tz), zoned_to_utc(Parts(ny, nm, 1), tz))


def add_months(key: MonthKey, n: int) -> MonthKey:
    """Shift a month key by `n` months (may be negative)."""
    y, m = parse_month(key)
    idx = y * 12 + (m - 1) + n
    yy, mm = divmod(idx, 12)
    return f'{yy:04d}-{mm + 1:02d}'


def months_ending_at(end: MonthKey, count: int) -> list[MonthKey]:
    """The `count` months ending at `end`, oldest first."""
    return [add_months(end, i - (count - 1)) for i in range(count)]


def month_progress(now: datetime, tz: str) -> MonthProgress:
    """Where 'today' sits in its month in `tz`."""
    month = month_key(now, tz)
    day = tz_parts(now, tz).d
    days = days_in_month(month)
    return MonthProgress(month, day, days, days - day + 1)


def _split_date(key: DateKey) -> tuple[int, int, int]:
    y, m, d = (int(x) for x in key.split('-'))
    return y, m, d


def add_months_clamped(date_: DateKey, n: int, wanted_day: int | None = None) -> DateKey:
    """Add months, keeping the wanted day but clamping short months (31st -> 30th/28th)."""
    y, m, d = _split_date(date_)
    target = add_months(f'{y:04d}-{m:02d}', n)
    day = min(wanted_day if wanted_day is not None else d, days_in_month(target))
    return f'{target}-{day:02d}'


def add_days(date_: DateKey, n: int) -> DateKey:
    """Add (or subtract) days."""
    y, m, d = _split_date(date_)
    return (date(y, m, d) + timedelta(days=n)).isoformat()


def to_iso(d: datetime) -> str:
    """UTC ISO-8601 with milliseconds and a Z: '2026-09-30T18:30:00.000Z'."""
    u = _aware(d).astimezone(UTC)
    return f'{u:%Y-%m-%dT%H:%M:%S}.{u.microsecond // 1000:03d}Z'
