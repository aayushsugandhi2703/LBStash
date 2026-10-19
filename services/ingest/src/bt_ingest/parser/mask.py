"""Hide account digits, long reference/phone numbers and the balance before an unreadable message is stored.
The amount and the words stay, so the user can still tell what it was.
"""

import re

from ._text import FLAGS_I, js_spaces

_DOTS = '••••'
_BALANCE = re.compile(
    r'\b((?:avl|avail(?:able)?|total|clear|closing|current)\.?\s*bal(?:ance)?\.?\s*(?:is\s*)?[:\-]?\s*)'
    r'((?:rs\.?|inr|₹)?\s*[\d,]+(?:\.\d+)?)',
    FLAGS_I,
)
_ACCOUNT = re.compile(
    r'\b((?:a/c|acct?\.?|account|card)(?:\s*(?:no\.?|number|ending(?:\s+(?:with|in))?))?\s*[:\-]?\s*)[Xx*•]*\s*\d{3,}',
    FLAGS_I,
)
_LONG_DIGITS = re.compile(r'\d{10,}', re.ASCII)


def mask_message(text: str) -> str:
    # balance, then account/card digits after a label, then long digit runs
    out = _BALANCE.sub(lambda m: f'{m[1]}INR ••••••', js_spaces(text))
    out = _ACCOUNT.sub(lambda m: f'{m[1]}{_DOTS}', out)
    return _LONG_DIGITS.sub(_DOTS, out)
