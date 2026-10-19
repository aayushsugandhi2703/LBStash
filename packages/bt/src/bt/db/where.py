"""SQL helpers: the `Where` collector and snake_case -> camelCase rows."""

import re
from collections.abc import Iterable, Mapping
from typing import Any

_CAMEL = re.compile(r'_([a-z0-9])')


class Where:
    """Parameter collector for dynamic WHERE clauses: `w = Where(); w.add('category_id = $?', cid)`. `$?` becomes the next `$n`; pass `initial` when the query already uses `$1..$k`."""

    def __init__(self, initial: Iterable[Any] = ()) -> None:
        self.params: list[Any] = list(initial)
        self._parts: list[str] = []

    def add(self, clause: str, *values: Any) -> 'Where':
        """Append a condition; each `$?` is replaced by the placeholder of the next value."""
        for v in values:
            self.params.append(v)
            clause = clause.replace('$?', f'${len(self.params)}', 1)
        self._parts.append(clause)
        return self

    @property
    def sql(self) -> str:
        """`WHERE a AND b`, or '' when nothing was added."""
        return f'WHERE {" AND ".join(self._parts)}' if self._parts else ''


def camel_key(k: str) -> str:
    """'amount_minor' -> 'amountMinor'."""
    return _CAMEL.sub(lambda m: m.group(1).upper(), k)


def camel(row: Mapping[str, Any]) -> dict[str, Any]:
    """snake_case row -> camelCase dict (values pass through)."""
    return {camel_key(k): v for k, v in row.items()}
