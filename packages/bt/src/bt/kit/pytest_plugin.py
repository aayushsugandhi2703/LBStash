"""pytest fixtures for service tests. Enable with `pytest_plugins = ['bt.kit.pytest_plugin']` in `tests/conftest.py` and define `bt_service` and `bt_migrations`.

Tests then get `db` (one throwaway database per module), `app_factory` (builds `AppHarness` apps) and `test_db_factory`.
"""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
import pytest_asyncio

from bt.db.testing import TempDatabase, create_test_database

from .testing import AppHarness, build_test_app


@pytest.fixture(scope='session')
def bt_service() -> str:
    """Service under test; override in conftest."""
    raise RuntimeError('define a session-scoped `bt_service` fixture (the service name) in your conftest.py')


@pytest.fixture(scope='session')
def bt_migrations() -> str:
    """Migrations folder; override in conftest."""
    raise RuntimeError('define a session-scoped `bt_migrations` fixture (the migrations folder) in your conftest.py')


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def test_db_factory() -> AsyncIterator[Callable[[str, str], Awaitable[TempDatabase]]]:
    """`await test_db_factory(service, migrations_dir)` -> a throwaway database, dropped when the module ends."""
    made: list[TempDatabase] = []

    async def make(service: str, migrations_dir: str) -> TempDatabase:
        t = await create_test_database(service, migrations_dir)
        made.append(t)
        return t

    yield make
    for t in made:
        await t.drop()


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def db(test_db_factory: Callable[[str, str], Awaitable[TempDatabase]], bt_service: str, bt_migrations: str) -> TempDatabase:
    """This module's throwaway database (`db.pool` is the service role)."""
    return await test_db_factory(bt_service, bt_migrations)


@pytest_asyncio.fixture(loop_scope='session')
async def app_factory(bt_service: str) -> AsyncIterator[Callable[..., Awaitable[AppHarness]]]:
    """`await app_factory(register=..., pool=db.pool, clients={...})` -> `AppHarness`; `service` defaults to yours."""
    made: list[AppHarness] = []

    async def make(**kw: Any) -> AppHarness:
        h = await build_test_app(**({'service': bt_service} | kw))
        made.append(h)
        return h

    yield make
    for h in made:
        await h.close()
