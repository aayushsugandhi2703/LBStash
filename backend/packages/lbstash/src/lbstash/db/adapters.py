"""How Python values travel to and from Postgres.

Read: uuid -> str, date -> 'YYYY-MM-DD', numeric -> int if whole else Decimal, timestamptz -> aware UTC datetime, jsonb -> objects.
Write: int and list params are sent untyped (the server infers); dict -> jsonb; `jsonb(value)` forces jsonb.

SQL uses `$1, $2, ...`; `rewrite_placeholders` converts to psycopg's named form.
"""

import json
import re
from datetime import date, datetime
from decimal import Decimal
from functools import lru_cache
from typing import Any
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.adapt import Dumper, Loader
from psycopg.types.json import Jsonb, JsonbDumper

_DOLLAR_TAG = re.compile(r'\$(?:[^\W\d]\w*)?\$')
_PARAM = re.compile(r'\$([0-9]+)')


def _ident_char(c: str) -> bool:
    return c.isalnum() or c in '_$'


def _skip_quoted(sql: str, i: int, quote: str, backslash: bool) -> int:
    """Index just past the quoted run that starts at `i` (a doubled quote is an escaped quote)."""
    n, j = len(sql), i + 1
    while j < n:
        if backslash and sql[j] == '\\':
            j += 2
            continue
        if sql[j] == quote:
            if j + 1 < n and sql[j + 1] == quote:
                j += 2
                continue
            return j + 1
        j += 1
    return n


def _skip_block_comment(sql: str, i: int) -> int:
    depth, j, n = 0, i, len(sql)
    while j < n:
        if sql.startswith('/*', j):
            depth += 1
            j += 2
        elif sql.startswith('*/', j):
            depth -= 1
            j += 2
            if depth == 0:
                return j
        else:
            j += 1
    return n


@lru_cache(maxsize=4096)
def rewrite_placeholders(sql: str) -> tuple[str, tuple[int, ...]]:
    """`$n` -> `%(pn)s` and literal `%` -> `%%`; returns the SQL and the parameter numbers used. `$n` inside strings, identifiers, comments and dollar-quoted bodies is left alone."""
    out: list[str] = []
    used: set[int] = set()
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        prev = sql[i - 1] if i else ''
        if c == "'":
            # E'...' strings treat backslash as an escape
            escape = prev in ('e', 'E') and (i < 2 or not _ident_char(sql[i - 2]))
            j = _skip_quoted(sql, i, "'", escape)
        elif c == '"':
            j = _skip_quoted(sql, i, '"', False)
        elif c == '-' and sql.startswith('--', i):
            j = sql.find('\n', i)
            j = n if j < 0 else j
        elif c == '/' and sql.startswith('/*', i):
            j = _skip_block_comment(sql, i)
        elif c == '$' and not (prev and _ident_char(prev)):
            tag = _DOLLAR_TAG.match(sql, i)
            if tag:
                end = sql.find(tag[0], tag.end())
                j = n if end < 0 else end + len(tag[0])
            elif (m := _PARAM.match(sql, i)) is not None:
                used.add(int(m[1]))
                out.append(f'%(p{m[1]})s')
                i = m.end()
                continue
            else:
                j = i + 1
        else:
            out.append('%%' if c == '%' else c)
            i += 1
            continue
        out.append(sql[i:j].replace('%', '%%'))
        i = j
    return ''.join(out), tuple(sorted(used))


def bind(sql: str, params: Any) -> tuple[str, dict[str, Any] | None]:
    """The (sql, params) pair for psycopg, from `$n`-style SQL and a positional list."""
    if not params:
        # no parameters: psycopg uses the simple protocol, so several statements and a literal `%` pass through
        return sql, None
    text, used = rewrite_placeholders(sql)
    want = used[-1] if used else 0
    if want != len(params) or used != tuple(range(1, want + 1)):
        raise ValueError(f'SQL uses parameters {list(used)} but {len(params)} were given')
    return text, {f'p{i}': params[i - 1] for i in used}


def _json_default(o: Any) -> Any:
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, (UUID, Decimal)):
        return str(o)
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f'{type(o).__name__} is not JSON serialisable')


def json_dumps(value: Any) -> str:
    """JSON text for jsonb parameters; dates, UUIDs and Decimals become strings."""
    return json.dumps(value, default=_json_default, ensure_ascii=False, separators=(',', ':'))


def jsonb(value: Any) -> Jsonb:
    """Send `value` (list, scalar or dict) as jsonb."""
    return Jsonb(value, dumps=json_dumps)


class _IntDumper(Dumper):
    """int as untyped text: the server picks int2/int4/int8/numeric from context."""

    def dump(self, obj: int) -> bytes:
        return str(obj).encode()


class _DictDumper(JsonbDumper):
    _dumps = staticmethod(json_dumps)


def _array_element(v: Any) -> str:
    if v is None:
        return 'NULL'
    if isinstance(v, (list, tuple)):
        return '{' + ','.join(_array_element(x) for x in v) + '}'
    if isinstance(v, bool):
        text = 'true' if v else 'false'
    elif isinstance(v, (int, float, Decimal)):
        return str(v)
    elif isinstance(v, (bytes, bytearray, memoryview)):
        text = '\\x' + bytes(v).hex()
    elif isinstance(v, (dict, Jsonb)):
        text = json_dumps(v.obj if isinstance(v, Jsonb) else v)
    elif isinstance(v, (datetime, date)):
        text = v.isoformat()
    else:
        text = str(v)
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'


class _ArrayDumper(Dumper):
    """list/tuple as an untyped array literal (`{"a","b"}`), so `= ANY($1)` works against uuid, int or text."""

    def dump(self, obj: list[Any] | tuple[Any, ...]) -> bytes:
        return _array_element(obj).encode()


class _TextLoader(Loader):
    """Keep the text Postgres printed (dates, uuids)."""

    def load(self, data: Any) -> str:
        return bytes(data).decode()


class _NumericLoader(Loader):
    def load(self, data: Any) -> int | Decimal:
        d = Decimal(bytes(data).decode())
        return int(d) if d.is_finite() and d == d.to_integral_value() else d


def configure_connection(conn: AsyncConnection[Any]) -> None:
    a = conn.adapters
    a.register_dumper(int, _IntDumper)
    a.register_dumper(list, _ArrayDumper)
    a.register_dumper(tuple, _ArrayDumper)
    a.register_dumper(dict, _DictDumper)
    a.register_loader('date', _TextLoader)
    a.register_loader('uuid', _TextLoader)
    a.register_loader('numeric', _NumericLoader)
