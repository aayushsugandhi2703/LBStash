"""Idempotent database setup, run by `db-init` and tests:

 - schema `lbstash` with `lbstash.enable_rls(table)`, the one place RLS policies are defined
 - a login role and schema per data service (`svc_transactions` owns `transactions`)
 - role `lbstash_queue` owning schema `queue`
"""

import contextlib
from collections.abc import Mapping
from typing import Final

from psycopg import sql

from lbstash.common import SERVICES, Logger

from .pool import connect

DATA_SERVICES: Final[tuple[str, ...]] = tuple(s for s in SERVICES if s not in ('gateway', 'reports'))
QUEUE_ROLE: Final = 'lbstash_queue'
QUEUE_SCHEMA: Final = 'queue'


def role_of(service: str) -> str:
    """Login role of a data service."""
    return f'svc_{service}'


# The `%s` / `%I` below belong to Postgres' format(); this text is never passed through psycopg's parameter parser.
ENABLE_RLS: Final = """
CREATE OR REPLACE FUNCTION lbstash.enable_rls(tbl regclass, user_col text DEFAULT 'user_id') RETURNS void LANGUAGE plpgsql AS $f$
BEGIN
  EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', tbl);
  EXECUTE format('ALTER TABLE %s FORCE ROW LEVEL SECURITY', tbl);
  EXECUTE format('DROP POLICY IF EXISTS lbstash_user_isolation ON %s', tbl);
  EXECUTE format(
    $p$CREATE POLICY lbstash_user_isolation ON %s
       USING (%I = nullif(current_setting('app.user_id', true), '')::uuid OR current_setting('app.system', true) = 'on')
       WITH CHECK (%I = nullif(current_setting('app.user_id', true), '')::uuid OR current_setting('app.system', true) = 'on')$p$,
    tbl, user_col, user_col);
END $f$;
"""


async def bootstrap_database(
    *, admin_url: str, passwords: Mapping[str, str | None], log: Logger | None = None
) -> None:
    """Create the helper schema, roles and schemas. `passwords` maps each data service and `queue` to its role password."""
    targets = [('queue', QUEUE_ROLE, QUEUE_SCHEMA), *((s, role_of(s), s) for s in DATA_SERVICES)]
    for key, _, _ in targets:  # check everything before changing anything
        if not passwords.get(key):
            raise ValueError(f'no database password for {key}')
    conn = await connect(admin_url, name='db-init')
    try:
        await conn.execute("SELECT pg_advisory_lock(hashtext('lbstash:bootstrap'))")
        await conn.execute('CREATE SCHEMA IF NOT EXISTS lbstash')
        await conn.execute('GRANT USAGE ON SCHEMA lbstash TO PUBLIC')
        await conn.execute(ENABLE_RLS)
        db = sql.Identifier((await (await conn.execute('SELECT current_database() AS d')).fetchone())['d'])  # type: ignore[index]
        for key, role, schema in targets:
            r, s, pw = sql.Identifier(role), sql.Identifier(schema), sql.Literal(passwords[key])
            exists = await (await conn.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', [role])).fetchone()
            verb = 'ALTER ROLE {} WITH LOGIN PASSWORD {}' if exists else 'CREATE ROLE {} LOGIN PASSWORD {}'
            await conn.execute(sql.SQL(verb).format(r, pw))
            await conn.execute(sql.SQL('CREATE SCHEMA IF NOT EXISTS {} AUTHORIZATION {}').format(s, r))
            await conn.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(db, r))
            if role == QUEUE_ROLE:
                await conn.execute(sql.SQL('REVOKE CREATE ON DATABASE {} FROM {}').format(db, r))
            else:
                await conn.execute(sql.SQL('ALTER ROLE {} SET search_path = {}, lbstash, public').format(r, s))
        if log:
            log.info('database bootstrapped')
    finally:
        with contextlib.suppress(Exception):  # the connection may be unusable after an error; the lock dies with it
            await conn.execute("SELECT pg_advisory_unlock(hashtext('lbstash:bootstrap'))")
        await conn.close()
