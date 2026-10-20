"""Fixtures: fake services behind an in-process network, and a gateway wired to them the way `main.py` builds it (edge mode)."""

from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
import pytest_asyncio
from gateway_helpers import Fakes as FakeServices
from gateway_helpers import Gateway, make_gateway, start_fakes


@pytest.fixture
def fakes() -> FakeServices:
    return start_fakes()


@pytest.fixture
def alive() -> set[str]:
    """Session ids the auth fake says are alive."""
    return set()


@pytest.fixture
def setup_limited() -> set[str]:
    """Session ids the auth fake says have not finished the mandatory setup."""
    return set()


@pytest_asyncio.fixture(loop_scope='session')
async def make_gw(fakes: FakeServices) -> AsyncIterator[Callable[..., Awaitable[Gateway]]]:
    """`await make_gw(RATE_LIMIT_PER_MINUTE=3)` -> a fresh gateway (fresh limit counters, empty session cache)."""
    made: list[Gateway] = []

    async def make(**extra: object) -> Gateway:
        gw = make_gateway(fakes, **extra)
        made.append(gw)
        return gw

    yield make
    for gw in made:
        await gw.aclose()


@pytest_asyncio.fixture(loop_scope='session')
async def gw(make_gw: Callable[..., Awaitable[Gateway]]) -> Gateway:
    return await make_gw()
