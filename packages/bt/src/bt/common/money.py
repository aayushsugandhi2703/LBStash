"""Money is an integer number of paise (1 rupee = 100), never a float."""

import math
import re
from typing import Final

Paise = int

PAISE_PER_RUPEE: Final = 100
# ₹10, the month-end pace rounding step.
TEN_RUPEES: Final[Paise] = 1000

_AMOUNT = re.compile(r'(-?)([0-9]+)(?:\.([0-9]{1,2}))?', re.ASCII)
_NOISE = re.compile(r'[₹\s,]')
_PREFIX_RS = re.compile(r'^rs\.?', re.IGNORECASE)
_PREFIX_INR = re.compile(r'^inr', re.IGNORECASE)
# comma before each pair of digits, counted from the right (the part left of the last three)
_PAIRS = re.compile(r'\B(?=([0-9]{2})+(?![0-9]))')


def assert_paise(n: object, what: str = 'amount') -> int:
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(f'{what} must be an integer number of paise')
    return n


def parse_rupees(value: str | float) -> Paise:
    """'450', '1,234.50', '₹ 450.00' -> paise. `ValueError` on junk or more than 2 decimals."""
    if isinstance(value, bool):
        raise TypeError('a bool is not an amount')
    if isinstance(value, int):
        return value * PAISE_PER_RUPEE
    if isinstance(value, float):
        paise = math.floor(value * PAISE_PER_RUPEE + 0.5) if math.isfinite(value) else 0
        if not math.isfinite(value) or abs(paise / PAISE_PER_RUPEE - value) > 1e-9:
            raise ValueError('amount has more than 2 decimals')
        return paise
    cleaned = _PREFIX_INR.sub('', _PREFIX_RS.sub('', _NOISE.sub('', value)))
    m = _AMOUNT.fullmatch(cleaned)
    if not m:
        raise ValueError(f'not an amount: {value}')
    sign, rupees, frac = m.groups()
    paise = int(rupees) * PAISE_PER_RUPEE + int((frac or '').ljust(2, '0') or '0')
    return -paise if sign else paise


def format_inr(paise: Paise, *, symbol: bool = False, force_decimals: bool = False) -> str:
    """Indian digit grouping: 3759100 -> '37,591'; 1234567890 -> '1,23,45,678.90'. Decimals only if non-zero."""
    assert_paise(paise)
    neg = paise < 0
    rupees, rem = divmod(abs(paise), PAISE_PER_RUPEE)
    s = str(rupees)
    last3, rest = s[-3:], s[:-3]
    grouped = _PAIRS.sub(',', rest) + ',' + last3 if rest else last3
    decimals = f'.{rem:02d}' if rem or force_decimals else ''
    return f'{"-" if neg else ""}{"₹" if symbol else ""}{grouped}{decimals}'


def round_to(paise: float, step: Paise = TEN_RUPEES) -> Paise:
    """Round to the nearest step (default ₹10), halves up (not banker's rounding)."""
    if isinstance(paise, int):
        return ((2 * paise + step) // (2 * step)) * step
    return math.floor(paise / step + 0.5) * step
