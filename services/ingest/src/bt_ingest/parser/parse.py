"""The bank-message parser. Pure: text in, fields out.

  1. OTP / promo guard -> `Ignored`
  2. generic fallback (README 4.7): amount, direction, reference, payee, account, time, balance
  3. a matching template refines payee / reference / account / balance
  4. amount and direction are required, else `Unreadable`
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from bt.common import parse_rupees

from ._text import FLAGS, js_spaces, rx
from .dedupe import dedupe_key
from .guard import is_not_a_transaction, is_otp_or_promo
from .templates import TEMPLATES, Template
from .time import find_message_time
from .types import Direction, Hints, Ignored, Parsed, ParsedTx, ParseInput, ParseResult, Unreadable

# generic fallback patterns
_NUM = r'(\d[\d,]*(?:\.\d{1,2})?)'
AMOUNT_SYMBOL = rx(r'(?<![A-Za-z])(?:rs\.?|inr|₹|rupees)\s*' + _NUM + r'(?!\d)')
AMOUNT_BARE = rx(r'\b(?:debited|credited|spent|paid|received|sent|withdrawn|deposited)\s+(?:by|for|with|of)\s+' + _NUM + r'(?!\d)')
BALANCE_CONTEXT = rx(r'\b(bal(?:ance)?|limit|outstanding|due)\b[\s:.\-]*(?:is|of|=)?[\s:.\-]*$')

BALANCE = rx(r'\b(?:avl|avail(?:able)?|total|clear|closing|current)\.?\s*bal(?:ance)?\.?[\s:\-]*(?:is\s*)?(?:rs\.?|inr|₹)?\s*' + _NUM)
REFERENCE = rx(
    r'(?:UPI(?:\s*(?:Ref(?:erence)?\.?(?:\s*(?:No|Number)\.?)?|Txn(?:\s*Id)?|Id))?|Ref(?:erence)?\.?(?:\s*(?:No|Number)\.?)?'
    r'|Refno|UTR|RRN|IMPS(?:\s*Ref(?:\s*No)?)?)[\s:.#-]*(\d{9,12})(?!\d)'
)
ACCOUNT = rx(r'(?:a/c|acct?\.?|account|card)(?:\s*(?:no\.?|number|ending(?:\s+(?:with|in))?))?\s*[:\-]?\s*[Xx*•]*\s*\d*?(\d{3,4})(?!\d)')
REVERSAL = rx(r'\b(?:revers(?:ed|al)|refund(?:ed)?|failed|failure|declined|unsuccessful|chargeback)\b')

DEBIT_WORDS = rx(r'\b(?:debited|debit|sent|paid|spent|withdrawn|withdrawal|purchase|purchased|deducted)\b')
CREDIT_WORDS = rx(r'\b(?:credited|credit|received|deposited|deposit)\b')

_END = r"(?=\s+(?:on|ref|refno|upi|avl|not|if|call|dt|dated|via|using|utr|imps|neft|with|txn)\b|\s*[.;,(]|\s+-\s|$)"
PAYEE_VPA = rx(r'\b(?:to|from|by)\s+(?:a/c\s+linked\s+to\s+)?(?:VPA|UPI\s*ID)\s*[:\-]?\s*([\w.\-+]+@[\w.\-]+)')
PAYEE_VPA_BARE = rx(r'\bVPA\s*[:\-]?\s*([\w.\-+]+@[\w.\-]+)')
PAYEE_VPA_ANY = rx(r'\b([\w.\-+]{2,}@[a-z][\w.\-]{1,})')
PAYEE_TRF = rx(r'\b(?:trf|transfer(?:red)?)\s+(?:to|from)\s+(?!VPA\b)(.+?)' + _END)
# case-sensitive on purpose: a payee written in capitals
PAYEE_TO_CAPS = rx(r"\bto\s+([A-Z][A-Z0-9 .&'-]+?)(?=\s+(?:On|Ref|UPI|Avl|Not|Call|Dt|via|on)\b|\s*[.;(]|$)", FLAGS)
PAYEE_FROM = rx(r'\bfrom\s+(?!your\b|a/c\b|acct\b|account\b|VPA\b|HDFC\b|SBI\b|ICICI\b|Axis\b)([A-Za-z][^()]*?)' + _END)
PAYEE_AT = rx(r"\b(?:at|@)\s+([A-Za-z][A-Za-z0-9 .&'*\-]*?)" + _END)

BAD_PAYEE = rx(r'^(?:a/c|acct|account|your|bank|the|you|me|self|card|vpa|upi)\b')

_SPACES = re.compile(r'\s+', FLAGS)
_PAYEE_TAIL = re.compile(r'[\s.,;:)\]-]+$', FLAGS)
_PAYEE_HEAD = re.compile(r'^[\s(\[-]+', FLAGS)
_ALL_DIGITS = re.compile(r'\d+', FLAGS)
_CARDISH = rx(r'\b(?:card|spent|purchase|pos|txn)\b')
_HINT_DEBIT = rx(r'\b(?:card|txn|transaction|purchase|pos)\b')
_DEBIT_CARD = rx(r'\b(?:credit|debit)\s*cards?\b')
_CREDIT_LIMIT = rx(r'\bcredit\s+limit\b')
_BAL_WORD = rx(r'^bal')

_MAX_SAFE = 2**53 - 1


def clean_payee(raw: str | None) -> str | None:
    if not raw:
        return None
    p = _SPACES.sub(' ', raw)
    p = _PAYEE_TAIL.sub('', p)
    p = _PAYEE_HEAD.sub('', p).strip()[:200]
    if len(p) < 2 or BAD_PAYEE.search(p) or _ALL_DIGITS.fullmatch(p):
        return None
    return p


@lru_cache(maxsize=256)
def _compiled(src: str) -> re.Pattern[str]:
    return rx(src)


def _first(pattern: re.Pattern[str] | str, text: str) -> str | None:
    """Capture group 1 of the first match, or None. String patterns are compiled case-insensitively."""
    m = (_compiled(pattern) if isinstance(pattern, str) else pattern).search(text)
    return m[1] if m else None


def _coalesce[T](*values: T | None) -> T | None:
    """The first value that is not None (an empty string counts)."""
    return next((v for v in values if v is not None), None)


@dataclass(frozen=True, slots=True)
class _Amount:
    minor: int
    index: int
    kind: Literal['txn', 'balance', 'limit']


def _to_minor(s: str) -> int | None:
    try:
        n = parse_rupees(s.rstrip(','))
    except ValueError:
        return None
    return n if 0 < n <= _MAX_SAFE else None


def _find_amounts(text: str) -> list[_Amount]:
    out: list[_Amount] = []
    for pattern in (AMOUNT_SYMBOL, AMOUNT_BARE):
        for m in pattern.finditer(text):
            minor = _to_minor(m[1])
            if minor is None:
                continue
            index = m.start()
            ctx = BALANCE_CONTEXT.search(text[max(0, index - 30) : index])
            kind = 'txn' if not ctx else 'balance' if _BAL_WORD.search(ctx[1]) else 'limit'
            out.append(_Amount(minor, index, kind))
    return sorted(out, key=lambda a: a.index)


def _find_direction(text: str) -> Direction | None:
    t = _CREDIT_LIMIT.sub(' ', _DEBIT_CARD.sub(' ', text))
    d = DEBIT_WORDS.search(t)
    c = CREDIT_WORDS.search(t)
    if d is None and c is None:
        return None
    if d is None:
        return 'credit'
    if c is None:
        return 'debit'
    return 'debit' if d.start() < c.start() else 'credit'


def _generic_payee(text: str, type: Direction) -> str | None:
    cardish = _CARDISH.search(text) is not None
    chain = (
        [PAYEE_VPA, PAYEE_VPA_BARE, PAYEE_TRF, PAYEE_TO_CAPS, PAYEE_AT if cardish else None, PAYEE_VPA_ANY]
        if type == 'debit'
        else [PAYEE_VPA, PAYEE_VPA_BARE, PAYEE_FROM, PAYEE_TRF, PAYEE_VPA_ANY]
    )
    for pattern in chain:
        p = clean_payee(_first(pattern, text)) if pattern else None
        if p:
            return p
    return None


def _select_template(text: str) -> Template | None:
    for t in TEMPLATES:
        if _compiled(t.match).search(text):
            return t
    return None


def _normalise(s: str) -> str:
    return _SPACES.sub(' ', js_spaces(s)).strip(' ')


def _hints_for(text: str, amounts: list[_Amount], inp: ParseInput) -> Hints:
    amount = next((a for a in amounts if a.kind == 'txn'), None)
    direction = _find_direction(text)
    if direction is None and _HINT_DEBIT.search(text) and not CREDIT_WORDS.search(text):
        direction = 'debit'
    written = find_message_time(text, inp.tz, inp.received_at)
    at_payee = clean_payee(_first(PAYEE_AT, text))
    payee = _coalesce(_generic_payee(text, direction), at_payee) if direction else at_payee
    return Hints(type=direction, amount_minor=amount.minor if amount else None, payee=payee, occurred_at=written.at if written else None)


def parse_message(inp: ParseInput) -> ParseResult:
    text = _normalise(inp.text)
    if is_otp_or_promo(text):
        return Ignored('otp_or_promo')
    if is_not_a_transaction(text):
        return Ignored('not_a_transaction')

    amounts = _find_amounts(text)
    amount = next((a for a in amounts if a.kind == 'txn'), None)
    if amount is None:
        # only a balance figure ("Your a/c balance is Rs 1,000") is not a payment
        if amounts and not DEBIT_WORDS.search(text) and not CREDIT_WORDS.search(text):
            return Ignored('not_a_transaction')
        return Unreadable('no_amount', _hints_for(text, amounts, inp))

    reversal = REVERSAL.search(text) is not None
    direction: Direction | None = 'credit' if reversal else _find_direction(text)
    if direction is None:
        return Unreadable('direction_unclear', _hints_for(text, amounts, inp))

    template = _select_template(text)
    f = template.fields if template else {}
    payee = _coalesce(clean_payee(_first(f['payee'], text) if f.get('payee') else None), _generic_payee(text, direction))
    reference = _coalesce(_first(f['reference'], text) if f.get('reference') else None, _first(REFERENCE, text))
    account_last4 = _coalesce(_first(f['account'], text) if f.get('account') else None, _first(ACCOUNT, text))
    balance_raw = _coalesce(_first(f['balance'], text) if f.get('balance') else None, _first(BALANCE, text))
    balance_after_minor = _to_minor(balance_raw) if balance_raw else None

    written = find_message_time(text, inp.tz, inp.received_at)
    occurred_at = written.at if written else inp.received_at
    ref = reference[:64] if reference else None

    tx = ParsedTx(
        type=direction,
        amount_minor=amount.minor,
        payee=payee,
        reference=ref,
        account_last4=account_last4[-4:] if account_last4 else None,
        occurred_at=occurred_at,
        time_from_message=written is not None,
        time_is_exact=written.exact if written else False,
        balance_after_minor=balance_after_minor,
        reversal=reversal,
        weak_parse=template is None and not payee and not ref,
        dedupe_key=dedupe_key(
            reference=ref, reversal=reversal, type=direction, amount_minor=amount.minor, payee=payee,
            occurred_at=occurred_at, time_from_message=written is not None,
        ),
        template=template.id if template else None,
    )  # fmt: skip
    return Parsed(tx)
