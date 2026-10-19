"""Auth tests run on real Postgres as the `auth` service role, so row-level security is real."""

from pathlib import Path

import pytest

pytest_plugins = ['bt.kit.pytest_plugin']


@pytest.fixture(scope='session')
def bt_service() -> str:
    return 'auth'


@pytest.fixture(scope='session')
def bt_migrations() -> str:
    return str(Path(__file__).resolve().parents[1] / 'migrations')
