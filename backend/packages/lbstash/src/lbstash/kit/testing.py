"""Test helpers: a real app with an injected pool, in-memory bus and fake clients, plus internal-token headers."""

import dataclasses
import secrets
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Self

import httpx
from fastapi import FastAPI
from pydantic import ConfigDict

from lbstash.common import BaseEnv, create_logger
from lbstash.crypto import sign_internal_token
from lbstash.db import Pool
from lbstash.queue import InMemoryBus

from .app import DEFAULT_BODY_LIMIT, Deps, create_app, make_deps

TEST_SECRET = secrets.token_hex(32)  # random per run


def test_env_values(service: str, **extra: Any) -> dict[str, Any]:
    """Environment for a test app (no real database or service URLs); `extra` adds or overrides variables."""
    return {
        'APP_ENV': 'test', 'SERVICE_NAME': service, 'HOST': '127.0.0.1', 'PORT': 3999, 'LOG_LEVEL': 'silent',
        'DATABASE_URL': 'unused', 'INTERNAL_SECRET': TEST_SECRET,
        'GATEWAY_URL': 'http://gateway.test', 'AUTH_URL': 'http://auth.test', 'TRANSACTIONS_URL': 'http://transactions.test',
        'INGEST_URL': 'http://ingest.test', 'PLANNING_URL': 'http://planning.test',
        'RECURRING_URL': 'http://recurring.test', 'REPORTS_URL': 'http://reports.test',
        'TELEGRAM_URL': 'http://telegram.test', **extra,
    }  # fmt: skip


test_env_values.__test__ = False  # type: ignore[attr-defined]  # not a pytest test


def headers_for(
    user_id: str | None, svc: str = 'transactions', tz: str = 'Asia/Kolkata', proxied: bool = False, request_id: str | None = None
) -> dict[str, str]:
    """Headers for a request from another service on behalf of a user. `proxied` = as the gateway forwards browser traffic."""
    return {'x-internal-token': sign_internal_token(TEST_SECRET, svc=svc, user_id=user_id, tz=tz, request_id=request_id, proxied=proxied)}


@dataclass
class AppHarness:
    """A built service app and what a test needs."""

    app: FastAPI
    deps: Deps[Any]
    bus: InMemoryBus
    client: httpx.AsyncClient

    @staticmethod
    def headers_for(
        user_id: str | None, svc: str = 'transactions', tz: str = 'Asia/Kolkata', proxied: bool = False, request_id: str | None = None
    ) -> dict[str, str]:
        """See `lbstash.kit.testing.headers_for`."""
        return headers_for(user_id, svc, tz, proxied, request_id)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()


def _env(model: type[BaseEnv], values: dict[str, Any]) -> BaseEnv:
    # accept variables the service model does not declare
    loose = type('TestEnv', (model,), {'model_config': ConfigDict(extra='allow')})
    return loose.model_validate(values)


async def build_test_app(
    *,
    service: str,
    register: Callable[[FastAPI, Deps[Any]], None],
    pool: Pool | None = None,
    clients: Any = None,
    env: Mapping[str, Any] | BaseEnv | None = None,
    env_model: type[BaseEnv] = BaseEnv,
    edge: bool = False,
    body_limit: int = DEFAULT_BODY_LIMIT,
) -> AppHarness:
    """Build a service app for tests: real routes, injected pool, in-memory bus. `clients` maps name -> fake (the rest stay real) or is a full clients object; `env` is a dict or env instance."""
    the_env = env if isinstance(env, BaseEnv) else _env(env_model, test_env_values(service, **(env or {})))
    bus = InMemoryBus()
    if clients is None or isinstance(clients, Mapping):
        from lbstash.clients import create_clients

        base = create_clients(service, the_env)
        clients = dataclasses.replace(base, **clients) if clients else base
    deps = make_deps(env=the_env, log=create_logger(service, 'silent'), pool=pool, bus=bus, clients=clients)
    app = create_app(deps, register, edge=edge, body_limit=body_limit)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test')
    return AppHarness(app, deps, bus, client)
