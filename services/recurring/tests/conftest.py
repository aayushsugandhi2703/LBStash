"""Fixtures for the recurring service tests: its own throwaway database as the `recurring` role."""

from pathlib import Path

import pytest

pytest_plugins = ['bt.kit.pytest_plugin']


@pytest.fixture(scope='session')
def bt_service() -> str:
    return 'recurring'


@pytest.fixture(scope='session')
def bt_migrations() -> str:
    return str(Path(__file__).parents[1] / 'migrations')
