"""Connection pool and its transaction scopes: plain, per user (row-level security) and system."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .adapters import configure_connection
from .tx import Row, Tx


async def connect(url: str, *, name: str = 'lbstash', autocommit: bool = True) -> psycopg.AsyncConnection[Row]:
    """One standalone connection with our adapters (bootstrap and tests)."""
    conn = await psycopg.AsyncConnection.connect(
        url, autocommit=autocommit, row_factory=dict_row, prepare_threshold=None,
        application_name=name, options='-c timezone=UTC',
    )  # fmt: skip
    configure_connection(conn)
    return conn


class Pool:
    """Pooled connections to one database role. Every use goes through a transaction scope."""

    def __init__(self, raw: AsyncConnectionPool[psycopg.AsyncConnection[Row]]) -> None:
        self.raw = raw

    @asynccontextmanager
    async def tx(self) -> AsyncIterator[Tx]:
        """A transaction: commits when the block ends, rolls back when it raises."""
        async with self.raw.connection() as conn, conn.transaction():
            yield Tx(conn)

    @asynccontextmanager
    async def user_tx(self, user_id: str) -> AsyncIterator[Tx]:
        """A transaction scoped to one user: sets `app.user_id` so row-level security applies."""
        async with self.tx() as tx:
            await tx.execute("SELECT set_config('app.user_id', $1, true)", [str(user_id)])
            yield tx

    @asynccontextmanager
    async def system_tx(self) -> AsyncIterator[Tx]:
        """Cross-user work (scheduler scans, retention sweeps); the RLS policy allows it only here."""
        async with self.tx() as tx:
            await tx.execute("SELECT set_config('app.system', 'on', true)")
            yield tx

    async def query(self, sql: str, params: Sequence[Any] | None = None) -> list[Row]:
        """Run one statement in its own transaction (no user scope) and return the rows."""
        async with self.tx() as tx:
            return await tx.query(sql, params)

    async def one(self, sql: str, params: Sequence[Any] | None = None) -> Row:
        """`Tx.one` in its own transaction."""
        async with self.tx() as tx:
            return await tx.one(sql, params)

    async def execute(self, sql: str, params: Sequence[Any] | None = None) -> int:
        """`Tx.execute` in its own transaction; returns the affected row count."""
        async with self.tx() as tx:
            return await tx.execute(sql, params)

    async def close(self) -> None:
        """Close every connection."""
        await self.raw.close()


async def create_pool(url: str, *, name: str = 'lbstash', max_size: int = 10) -> Pool:
    """Open a pool and check the database answers. Connections are autocommit; work happens in `Pool.tx()` scopes."""
    raw: AsyncConnectionPool[psycopg.AsyncConnection[Row]] = AsyncConnectionPool(
        url, min_size=1, max_size=max_size, open=False, name=name, max_idle=30,
        kwargs={'autocommit': True, 'row_factory': dict_row, 'prepare_threshold': None,
                'application_name': name, 'options': '-c timezone=UTC'},
        configure=_configure, check=AsyncConnectionPool.check_connection,
    )  # fmt: skip
    await raw.open(wait=True, timeout=15)
    return Pool(raw)


async def _configure(conn: psycopg.AsyncConnection[Row]) -> None:
    configure_connection(conn)
