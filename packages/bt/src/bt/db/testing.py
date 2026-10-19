"""A throwaway database bootstrapped like production. The pool connects as the service's own role, so tests exercise real row-level security."""

import os
import secrets
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

from .bootstrap import DATA_SERVICES, QUEUE_ROLE, bootstrap_database, role_of
from .migrate import migrate
from .pool import Pool, connect, create_pool

# Random per run: no credential is written into the source.
TEST_PASSWORD = secrets.token_hex(16)


def admin_url() -> str:
    """Admin connection string of the test Postgres, from `TEST_DATABASE_URL` (see docker-compose `test` profile)."""
    url = os.environ.get('TEST_DATABASE_URL')
    if not url:
        raise RuntimeError('TEST_DATABASE_URL is not set: point it at a throwaway Postgres (superuser) for the tests')
    return url


def url_for(base: str, *, database: str | None = None, user: str | None = None, password: str | None = None) -> str:
    """`base` with another database and/or credentials."""
    u = urlsplit(base)
    host = u.netloc.rsplit('@', 1)[-1]
    netloc = host
    if user is not None:
        netloc = f'{quote(user, safe="")}:{quote(password or "", safe="")}@{host}'
    elif '@' in u.netloc:
        netloc = u.netloc
    return urlunsplit((u.scheme, netloc, f'/{database}' if database else u.path, u.query, ''))


@dataclass
class TempDatabase:
    """`pool` is the service role; `admin_pool` is the owner (sees behind RLS)."""

    pool: Pool
    admin_pool: Pool
    url: str
    queue_url: str
    name: str
    admin_db_url: str
    _root_url: str

    async def drop(self) -> None:
        """Close the pools and delete the database."""
        await self.pool.close()
        await self.admin_pool.close()
        root = await connect(self._root_url, name='test-drop')
        try:
            await root.execute(f'DROP DATABASE IF EXISTS {self.name} WITH (FORCE)')
        finally:
            await root.close()


async def create_test_database(service: str, migrations_dir: str) -> TempDatabase:
    """Create, bootstrap and migrate a database for `service`, connected as its role."""
    root_url = admin_url()
    name = f'bt_t_{secrets.token_hex(5)}'
    root = await connect(root_url, name='test-create')
    try:
        await root.execute(f'CREATE DATABASE {name}')
        db_admin = url_for(root_url, database=name)
        passwords = {s: TEST_PASSWORD for s in DATA_SERVICES} | {'queue': TEST_PASSWORD}
        # roles are cluster-wide but advisory locks are per database: serialise role creation across test processes
        await root.execute("SELECT pg_advisory_lock(hashtext('bt:test-bootstrap'))")
        try:
            await bootstrap_database(admin_url=db_admin, passwords=passwords)
        finally:
            await root.execute("SELECT pg_advisory_unlock(hashtext('bt:test-bootstrap'))")
    finally:
        await root.close()

    svc_url = url_for(db_admin, user=role_of(service), password=TEST_PASSWORD)
    pool = await create_pool(svc_url, name=f'test-{service}', max_size=5)
    await migrate(pool, schema=service, dir=migrations_dir)
    admin_pool = await create_pool(db_admin, name='test-admin', max_size=2)
    return TempDatabase(
        pool=pool, admin_pool=admin_pool, url=svc_url, queue_url=url_for(db_admin, user=QUEUE_ROLE, password=TEST_PASSWORD),
        name=name, admin_db_url=db_admin, _root_url=root_url,
    )  # fmt: skip
