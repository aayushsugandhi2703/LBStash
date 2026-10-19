"""Bank SMS sender ids look like `AX-HDFCBK`, `VM-HDFCBK-S` or `HDFCBK`: an operator prefix and optional suffix around the bare id."""

import re
from collections.abc import Iterable, Sequence

_PREFIX = re.compile(r'^[A-Z]{2}-(?=.)', re.ASCII | re.DOTALL)
_SUFFIX = re.compile(r'-[A-Z]$', re.ASCII)
_JUNK = re.compile(r'[^A-Z0-9]', re.ASCII)


def normalize_sender(s: str) -> str:
    return _JUNK.sub('', _SUFFIX.sub('', _PREFIX.sub('', s.strip().upper())))


def sender_allowed(allowed: Sequence[str], sender: str | None) -> bool:
    """An empty allow-list accepts every sender; otherwise the request needs a matching `sender`."""
    if not allowed:
        return True
    if not sender:
        return False
    s = normalize_sender(sender)
    return any(normalize_sender(a) == s for a in allowed)


def normalize_sender_list(xs: Iterable[str]) -> list[str]:
    """Normalised and de-duplicated (first wins); empty ids dropped."""
    return list(dict.fromkeys(n for n in map(normalize_sender, xs) if n))
