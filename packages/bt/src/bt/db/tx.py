"""`Tx`: one connection inside a transaction, with the row helpers the services use."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any, Protocol

from psycopg import AsyncConnection

from .adapters import bind

Row = dict[str, Any]


class NoRows(LookupError):
    """`Tx.one` found no row."""


class Queryable(Protocol):
    """Anything that can run SQL: a `Tx`, or a `Pool` (which runs each call in its own transaction)."""

    async def query(self, sql: str, params: Sequence[Any] | None = None) -> list[Row]: ...

    async def execute(self, sql: str, params: Sequence[Any] | None = None) -> int: ...


class Tx:
    """A connection inside an open transaction. SQL uses `$1, $2, ...` placeholders; rows are dicts."""

    def __init__(self, conn: AsyncConnection[Row]) -> None:
        self.conn = conn

    async def query(self, sql: str, params: Sequence[Any] | None = None) -> list[Row]:
        """Run SQL and return all rows (none for statements that return no rows)."""
        text, bound = bind(sql, params)
        async with self.conn.cursor() as cur:
            await cur.execute(text, bound)  # type: ignore[arg-type]
            return await cur.fetchall() if cur.description else []

    async def many(self, sql: str, params: Sequence[Any] | None = None) -> list[Row]:
        """Same as `query`."""
        return await self.query(sql, params)

    async def maybe_one(self, sql: str, params: Sequence[Any] | None = None) -> Row | None:
        """The first row, or None."""
        rows = await self.query(sql, params)
        return rows[0] if rows else None

    async def one(self, sql: str, params: Sequence[Any] | None = None) -> Row:
        """The first row; raises `NoRows` when there is none."""
        row = await self.maybe_one(sql, params)
        if row is None:
            raise NoRows('expected one row, got none')
        return row

    async def execute(self, sql: str, params: Sequence[Any] | None = None) -> int:
        """Run SQL and return the number of rows affected."""
        text, bound = bind(sql, params)
        async with self.conn.cursor() as cur:
            await cur.execute(text, bound)  # type: ignore[arg-type]
            return max(cur.rowcount, 0)

    @asynccontextmanager
    async def savepoint(self) -> AsyncIterator[None]:
        """A block that may fail (e.g. a unique violation) without aborting the surrounding transaction."""
        async with self.conn.transaction():
            yield
