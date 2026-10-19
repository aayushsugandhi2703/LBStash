from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Direction = Literal['debit', 'credit']
IgnoredReason = Literal['otp_or_promo', 'not_a_transaction']
UnreadableReason = Literal['no_amount', 'direction_unclear', 'unreadable']


@dataclass(frozen=True, slots=True)
class ParseInput:
    # The SMS text exactly as the phone sent it.
    text: str
    # When the Shortcut ran (aware). Fallback payment time, and the reference for year-less dates.
    received_at: datetime
    # The device owner's IANA zone: times written in a bank message are local (IST).
    tz: str


@dataclass(frozen=True, slots=True)
class ParsedTx:
    type: Direction
    amount_minor: int
    payee: str | None
    reference: str | None
    account_last4: str | None
    # The time written in the message, else `received_at` (aware, UTC).
    occurred_at: datetime
    # True when `occurred_at` was read from the message text (a date at least).
    time_from_message: bool
    # True when a clock time was written, so `received_at - occurred_at` is a real delivery delay.
    time_is_exact: bool
    balance_after_minor: int | None
    # reversed / refund / failed notice (type is `credit`).
    reversal: bool
    # Only amount and direction were found (no template matched, no payee, no reference).
    weak_parse: bool
    # UPI ref if present, else a hash of amount, payee, time bucket and source.
    dedupe_key: str
    # Id of the template that matched, or None when only the generic fallback was used.
    template: str | None


@dataclass(frozen=True, slots=True)
class Hints:
    """What could still be guessed from an unreadable message; prefills the "Needs a look" form."""

    type: Direction | None
    amount_minor: int | None
    payee: str | None
    # Time written in the message, if any.
    occurred_at: datetime | None


@dataclass(frozen=True, slots=True)
class Parsed:
    tx: ParsedTx


@dataclass(frozen=True, slots=True)
class Ignored:
    reason: IgnoredReason


@dataclass(frozen=True, slots=True)
class Unreadable:
    reason: UnreadableReason
    hints: Hints


ParseResult = Parsed | Ignored | Unreadable
