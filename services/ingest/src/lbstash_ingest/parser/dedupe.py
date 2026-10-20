from datetime import UTC, datetime

from lbstash.crypto import sha256_hex

from .types import Direction

_MIN_MS = 60_000
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _epoch_ms(d: datetime) -> int:
    """Whole milliseconds since the epoch, exact for any microsecond value."""
    delta = d - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1000 + delta.microseconds // 1000


def dedupe_key(
    *,
    reference: str | None,
    reversal: bool,
    type: Direction,
    amount_minor: int,
    payee: str | None,
    occurred_at: datetime,
    time_from_message: bool,
    source: str | None = None,
) -> str:
    """UPI ref if present, else a hash of amount, payee, time bucket and source, so a re-sent message never counts twice. A reversal gets its own key. Do not change the hash input: stored keys must keep matching."""
    if reference:
        return f'ref:{reference.lower()}{":rev" if reversal else ""}'
    bucket = _epoch_ms(occurred_at) // ((5 if time_from_message else 30) * _MIN_MS)
    raw = '|'.join(
        [type, str(amount_minor), (payee or '').strip().lower(), str(bucket), source or 'captured', 'rev' if reversal else '']
    )
    return f'h:{sha256_hex(raw)[:40]}'
