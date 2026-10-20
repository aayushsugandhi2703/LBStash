"""Fixtures for the ingest tests: a throwaway database per module, connected as the `ingest` role (so RLS is real)."""

from pathlib import Path

import pytest

pytest_plugins = ['lbstash.kit.pytest_plugin']


@pytest.fixture(scope='session')
def lbstash_service() -> str:
    return 'ingest'


@pytest.fixture(scope='session')
def lbstash_migrations() -> str:
    return str(Path(__file__).resolve().parents[1] / 'migrations')
