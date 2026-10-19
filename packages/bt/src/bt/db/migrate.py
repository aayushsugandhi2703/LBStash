"""Forward-only SQL migrations: one folder and one Postgres schema per service. Files run once, in name order, each in its own transaction."""

import contextlib
from pathlib import Path

from bt.common import Logger

from .pool import Pool


class MigrationError(RuntimeError):
    """A migration file failed; the message names it."""


async def migrate(pool: Pool, *, schema: str, dir: str | Path, log: Logger | None = None) -> list[str]:
    """Apply the folder's new `.sql` files under an advisory lock (safe with several replicas); returns their names."""
    files = sorted(p for p in Path(dir).iterdir() if p.suffix == '.sql')
    applied: list[str] = []
    lock = f'migrate:{schema}'
    async with pool.raw.connection() as conn:
        try:
            await conn.execute('SELECT pg_advisory_lock(hashtext(%s))', [lock])
            await conn.execute(
                f'CREATE TABLE IF NOT EXISTS {schema}._migrations '
                '(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())'
            )
            cur = await conn.execute(f'SELECT name FROM {schema}._migrations')
            done = {r['name'] for r in await cur.fetchall()}
            for f in files:
                if f.name in done:
                    continue
                try:
                    async with conn.transaction():
                        await conn.execute(f.read_text(encoding='utf-8'))  # no parameters: several statements are fine
                        await conn.execute(f'INSERT INTO {schema}._migrations (name) VALUES (%s)', [f.name])
                except Exception as e:
                    raise MigrationError(f'migration {f.name} failed: {e}') from e
                applied.append(f.name)
                if log:
                    log.info('migration applied', migration=f.name)
        finally:
            with contextlib.suppress(Exception):  # the connection may be unusable after an error; the lock dies with it
                await conn.execute('SELECT pg_advisory_unlock(hashtext(%s))', [lock])
    return applied
