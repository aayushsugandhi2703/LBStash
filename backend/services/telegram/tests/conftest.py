from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from lbstash.db.testing import TempDatabase
from telegram_harness import World, make_world

pytest_plugins = ['lbstash.kit.pytest_plugin']


@pytest.fixture(scope='session')
def lbstash_service() -> str:
    return 'telegram'


@pytest.fixture(scope='session')
def lbstash_migrations() -> str:
    return str(Path(__file__).resolve().parents[1] / 'migrations')


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def _world(db: TempDatabase) -> AsyncIterator[World]:
    """The service app, workers and fakes over this module's throwaway database."""
    world = await make_world(db)
    yield world
    await world.close()


@pytest.fixture
def w(_world: World) -> World:
    """The module's world with the clock and bus reset."""
    _world.reset()
    return _world
