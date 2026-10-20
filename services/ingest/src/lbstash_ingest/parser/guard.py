"""OTP / promo guard (README 15.3). Runs on the raw text before anything is parsed, stored or logged; an OTP that mentions a payment is still an OTP."""

import re

from ._text import FLAGS_I, js_spaces

_OTP = [
    r'\botps?\b',
    r'one[\s-]?time[\s-]?(?:pass(?:word|code)?|pin|code)',
    r'\bdo\s*not\s*share\b',
    r"\bdon['’]?t\s*share\b",
    r'\bnever\s*share\b',
    r'verif(?:y|ication)\s*code',
    r'(?:login|log-in|security|authenticat\w*|confirmation|activation)\s*code',
    r'\bpass\s?code\b',
    r'\bvalid\s*(?:for|till|until|upto|up\s*to)\s*\d+\s*(?:min(?:ute)?s?|sec(?:ond)?s?|hours?|hrs?)\b',
    r'\bvalid\s+(?:till|until|upto|up\s+to)\s+\d{1,2}[:.]\d{2}',
    r'\b(?:code|pin|password)\s*(?:is|:)\s*\d{4,8}\b',
    r'\bcvv\b',
]
OTP = [re.compile(p, FLAGS_I) for p in _OTP]

_PROMO = [
    r'\boffers?\b',
    r'\bpromo(?:tion(?:al)?|code)?\b',
    r'\bexclusive\s+(?:deal|offer|reward)',
    r'\bpre[\s-]?(?:approved|qualified)\b',
    r'\bapply\s+now\b',
    r'\blimited[\s-]?period\b',
    r'\bt\s?&\s?cs?\s+apply\b',
    r'\bterms\s+and\s+conditions\s+apply\b',
    r'\blucky\s+draw\b',
    r'\b(?:avail|claim)\s+now\b',
    r'\bhurry\b',
    r'\bdownload\s+the\s+app\b',
    r'\bclick\s+(?:here|on|the\s+link)\b',
    r'\bbit\.ly\b',
    r'\bconvert\b.*\bemi\b',
    r'\bwin\s+(?:up\s+to|a|big)\b',
]
PROMO = [re.compile(p, FLAGS_I) for p in _PROMO]

# Real bank texts that are not a payment: future debits, due reminders, collect requests, "will be refunded".
_NOT_A_TRANSACTION = [
    r'\b(?:will|shall|would)\s+be\s+(?:auto[\s-]?)?(?:debited|credited|deducted|refunded|reversed)\b',
    r'\b(?:to\s+be|scheduled\s+to\s+be)\s+(?:debited|deducted)\b',
    r'\bif\s+(?:any|debited|deducted)\b',
    r'\bmin(?:imum)?\.?\s*(?:amount\s*)?due\b',
    r'\btotal\s*(?:amount\s*)?due\b',
    r'\bpayment\s+(?:is\s+)?due\b',
    r'\bdue\s*(?:date|on|by)\b',
    r'\bbill\s+(?:is\s+)?(?:generated|due)\b',
    r'\bstatement\s+(?:for|is|has|of)\b',
    r'\b(?:has\s+)?requested\s+(?:money|rs|inr|₹|payment)',
    r'\bcollect\s+request\b',
    r'\bmandate\b.*\b(?:created|registered|set\s*up|approved|pending)\b',
]
NOT_A_TRANSACTION = [re.compile(p, FLAGS_I) for p in _NOT_A_TRANSACTION]


def is_otp_like(text: str) -> bool:
    t = js_spaces(text)
    return any(r.search(t) for r in OTP)


def is_promo(text: str) -> bool:
    t = js_spaces(text)
    return any(r.search(t) for r in PROMO)


def is_otp_or_promo(text: str) -> bool:
    return is_otp_like(text) or is_promo(text)


def is_not_a_transaction(text: str) -> bool:
    t = js_spaces(text)
    return any(r.search(t) for r in NOT_A_TRANSACTION)
