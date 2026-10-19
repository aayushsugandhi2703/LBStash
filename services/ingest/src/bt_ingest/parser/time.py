import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import NamedTuple

from bt.common import tz_parts, zoned_to_utc

from ._text import FLAGS, FLAGS_I

_MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
_FULL = [
    'january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december',
]  # fmt: skip


def _month_of(word: str) -> int | None:
    w = word.lower()
    if w[:3] not in _MONTHS:
        return None
    i = _MONTHS.index(w[:3])
    # "Oct", "Sept", "October": the word must be a prefix of the full name (so "Mar" matches, "Marked" does not)
    return i + 1 if _FULL[i].startswith(w) or w == 'sept' else None


@dataclass(frozen=True, slots=True)
class _DateHit:
    index: int
    length: int
    y: int | None
    m: int
    d: int


_ISO = re.compile(r'\b(\d{4})[-:](\d{2})[-:](\d{2})(?=[T :)]|\b)', FLAGS)
_NUMERIC = re.compile(r'\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4}|\d{2})\b', FLAGS)
_TEXTUAL = re.compile(r"\b(\d{1,2})[-/ .]?([A-Za-z]{3,9})(?:[-/ .,']*(\d{4}|\d{2})\b)?", FLAGS)


def _full_year(s: str) -> int:
    return 2000 + int(s) if len(s) == 2 else int(s)


def _valid_day(y: int, m: int, d: int) -> bool:
    # years below 100 are not trusted
    if y < 100:
        return False
    try:
        date(y, m, d)
    except ValueError:
        return False
    return True


def _find_date(text: str) -> _DateHit | None:
    hits: list[_DateHit] = []
    for m in _ISO.finditer(text):
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        if _valid_day(y, mo, d):
            hits.append(_DateHit(m.start(), len(m[0]), y, mo, d))
    for m in _NUMERIC.finditer(text):
        d, mo, y = int(m[1]), int(m[2]), _full_year(m[3])
        if 1 <= mo <= 12 and _valid_day(y, mo, d):
            hits.append(_DateHit(m.start(), len(m[0]), y, mo, d))
    for m in _TEXTUAL.finditer(text):
        mo = _month_of(m[2])
        if not mo:
            continue
        d = int(m[1])
        y = _full_year(m[3]) if m[3] else None
        if d < 1 or d > 31 or (y is not None and not _valid_day(y, mo, d)):
            continue
        hits.append(_DateHit(m.start(), len(m[0]), y, mo, d))
    hits.sort(key=lambda h: h.index)
    # drop a hit that overlaps an earlier one (a numeric date inside an ISO one)
    for h in hits:
        if not any(o is not h and o.index < h.index and o.index + o.length > h.index for o in hits):
            return h
    return None


_TIME = re.compile(r'\b(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*([ap])\.?m\.?)?(?!\d)', FLAGS_I)


class MessageTime(NamedTuple):
    at: datetime
    exact: bool


def find_message_time(text: str, tz: str, received_at: datetime) -> MessageTime | None:
    """The payment time written in the message as a real instant, or None. A date alone books noon of that day; a time in the future or over 45 days old is rejected as a misread."""
    hit = _find_date(text)
    if hit is None:
        return None
    now = tz_parts(received_at, tz)
    y = hit.y if hit.y is not None else now.y
    if hit.y is None and zoned_to_utc({'y': y, 'm': hit.m, 'd': hit.d, 'h': 12}, tz) > received_at + timedelta(hours=36):
        y -= 1  # "17-Dec" read in January
    if not _valid_day(y, hit.m, hit.d):
        return None

    rest = text[: hit.index] + ' ' + text[hit.index + hit.length :]
    t = _TIME.search(rest)
    exact = False
    if t:
        h = int(t[1])
        mi = int(t[2])
        s = int(t[3]) if t[3] else 0
        if t[4]:
            h = h % 12 + (12 if t[4].lower() == 'p' else 0)
        if h > 23 or mi > 59 or s > 59:
            return None
        out = zoned_to_utc({'y': y, 'm': hit.m, 'd': hit.d, 'h': h, 'mi': mi, 's': s}, tz)
        exact = True
    elif (y, hit.m, hit.d) == (now.y, now.m, now.d):
        out = received_at
    else:
        out = zoned_to_utc({'y': y, 'm': hit.m, 'd': hit.d, 'h': 12}, tz)
    out = out.astimezone(UTC)
    delta = out - received_at
    if delta > timedelta(minutes=30) or delta < -timedelta(days=45):
        return None
    return MessageTime(out, exact)
