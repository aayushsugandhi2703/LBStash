"""Opaque cursors for keyset pagination."""

import base64
import binascii
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import NoReturn

from .errors import Errors


@dataclass(frozen=True, slots=True)
class Cursor:
    """(occurred_at, id) of the last row of the previous page."""

    t: str
    id: str


@dataclass(frozen=True, slots=True)
class Page[T]:
    """Rows plus the next cursor (None on the last page)."""

    items: list[T]
    next_cursor: str | None


def encode_cursor(c: Cursor) -> str:
    """Cursor -> base64url JSON, no padding."""
    raw = json.dumps({'t': c.t, 'id': c.id}, separators=(',', ':'), ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def _bad_cursor() -> NoReturn:
    raise Errors.bad_request('Bad cursor') from None


def decode_cursor(s: str | None) -> Cursor | None:
    """Text -> Cursor; None if empty, `bad_request` if not a cursor we made."""
    if not s:
        return None
    try:
        obj = json.loads(base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)))
        t, id_ = obj['t'], obj['id']
        datetime.fromisoformat(t)  # TypeError unless a string
        if not isinstance(id_, str):
            return _bad_cursor()
        return Cursor(t, id_)
    except (ValueError, KeyError, TypeError, binascii.Error):
        return _bad_cursor()


def to_page[T](rows: list[T], limit: int, cursor_of: Callable[[T], Cursor]) -> Page[T]:
    """Trim `limit + 1` fetched rows to a page and compute the next cursor."""
    more = len(rows) > limit
    items = rows[:limit] if more else rows
    return Page(items, encode_cursor(cursor_of(items[-1])) if more and items else None)
