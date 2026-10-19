"""Tag and payee normalisation (README 3.3)."""

import re
import unicodedata
from typing import Final

from ._text import utf16_len
from .errors import Errors

MAX_TAG_LENGTH: Final = 32

_SPACES = re.compile(r'\s+')
_PUNCT: Final = frozenset(" _&'./+-")


def _letter_or_digit(ch: str) -> bool:
    return unicodedata.category(ch)[0] in 'LN'


def normalize_tag(raw: str) -> str:
    """Stored tag name: lowercased, trimmed, spaces collapsed, leading '#' dropped. Raises a validation error if invalid."""
    t = unicodedata.normalize('NFKC', raw).strip().lstrip('#').strip().lower()
    t = _SPACES.sub(' ', t)
    if not t:
        raise Errors.validation({'tag': 'A tag cannot be empty'})
    if utf16_len(t) > MAX_TAG_LENGTH:
        raise Errors.validation({'tag': f'A tag can be at most {MAX_TAG_LENGTH} characters'})
    if not _letter_or_digit(t[0]) or not all(_letter_or_digit(c) or c in _PUNCT for c in t[1:]):
        raise Errors.validation({'tag': 'A tag can use letters, numbers and simple punctuation'})
    return t


def display_tag(name: str) -> str:
    """'bank charges' -> 'Bank charges'."""
    return name[:1].upper() + name[1:] if name else name


def payee_key(payee: str) -> str:
    """Key for payee memory and keyword rules."""
    return _SPACES.sub(' ', unicodedata.normalize('NFKC', payee).strip().lower())
