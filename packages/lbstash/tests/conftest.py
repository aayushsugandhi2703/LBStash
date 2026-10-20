"""Fixtures for the shared-library tests: one throwaway database per module, connected as the `transactions` role."""

from pathlib import Path

import pytest_asyncio
from lbstash.db.testing import TempDatabase, create_test_database

MIGRATIONS = str(Path(__file__).parent / 'migrations')


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def db():
    t: TempDatabase = await create_test_database('transactions', MIGRATIONS)
    yield t
    await t.drop()
