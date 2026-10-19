from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from bt.db.testing import TempDatabase
from planning_harness import Harness, make_harness

pytest_plugins = ['bt.kit.pytest_plugin']


@pytest.fixture(scope='session')
def bt_service() -> str:
    return 'planning'


@pytest.fixture(scope='session')
def bt_migrations() -> str:
    return str(Path(__file__).resolve().parents[1] / 'migrations')


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def h(db: TempDatabase) -> AsyncIterator[Harness]:
    """The service app, workers and fakes over this module's throwaway database."""
    harness = await make_harness(db)
    yield harness
    await harness.close()
