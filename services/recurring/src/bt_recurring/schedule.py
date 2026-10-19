"""Schedule math on calendar days. Pure, no clock. A day the month lacks clamps to its last day and always counts from the wanted day (Jan 31 -> Feb 28 -> Mar 31)."""

import re
from datetime import date

from bt.common import DateKey, add_days, add_months_clamped, days_in_month
from bt.contracts import MonthlySchedule, WeeklySchedule, YearlySchedule

Schedule = MonthlySchedule | WeeklySchedule | YearlySchedule

_DATE = re.compile(r'(\d{4})-(\d{2})-(\d{2})', re.ASCII)


def is_real_date(d: str) -> bool:
    """True for an existing calendar day written exactly 'YYYY-MM-DD' (no 2026-02-31, no 2026-2-3)."""
    m = _DATE.fullmatch(d)
    if not m:
        return False
    y, mo, day = int(m[1]), int(m[2]), int(m[3])
    return 1 <= mo <= 12 and 1 <= day <= days_in_month(f'{y:04d}-{mo:02d}')


def first_occurrence(s: Schedule, from_: DateKey) -> DateKey:
    """The first occurrence on or after `from_`."""
    if isinstance(s, MonthlySchedule):
        first = f'{from_[:7]}-01'
        cand = add_months_clamped(first, 0, s.day)
        return cand if cand >= from_ else add_months_clamped(first, 1, s.day)
    if isinstance(s, WeeklySchedule):
        y, m, d = (int(x) for x in from_.split('-'))
        dow = (date(y, m, d).weekday() + 1) % 7  # Sunday is 0, as in the schedule
        return add_days(from_, (s.weekday - dow) % 7)

    y = int(from_[:4])

    def at(yy: int) -> DateKey:
        month = f'{yy:04d}-{s.month:02d}'
        return f'{month}-{min(s.day, days_in_month(month)):02d}'

    cand = at(y)
    return cand if cand >= from_ else at(y + 1)


def next_occurrence(s: Schedule, due: DateKey) -> DateKey:
    """The occurrence after `due`."""
    return first_occurrence(s, add_days(due, 1))
