"""Fixtures for the recurring service tests: its own throwaway database as the `recurring` role."""

from pathlib import Path

import pytest

pytest_plugins = ['lbstash.kit.pytest_plugin']


@pytest.fixture(scope='session')
def lbstash_service() -> str:
    return 'recurring'


@pytest.fixture(scope='session')
def lbstash_migrations() -> str:
    return str(Path(__file__).parents[1] / 'migrations')
