"""The boot sequence every service uses: env, logger, pool, migrations, message bus, routes, workers, listen."""

import asyncio
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI

from lbstash.common import BaseEnv, Logger, create_logger, load_env, route_stdlib_logging
from lbstash.db import Pool, create_pool, migrate
from lbstash.queue import MessageBus, Messaging

from .app import DEFAULT_BODY_LIMIT, Deps, NoBus, create_app, make_deps

Register = Callable[[FastAPI, Deps[Any]], None]
Workers = Callable[[Deps[Any]], Awaitable[None]]


@dataclass
class RunningService:
    """A booted service that is not listening yet."""

    app: FastAPI
    deps: Deps[Any]
    close: Callable[[], Awaitable[None]]


async def boot_service(
    name: str,
    *,
    register: Register,
    env_model: type[BaseEnv] = BaseEnv,
    migrations_dir: str | Path | None = None,
    workers: Workers | None = None,
    body_limit: int = DEFAULT_BODY_LIMIT,
    edge: bool = False,
    environ: dict[str, str] | None = None,
) -> RunningService:
    """Everything `run_service` does except listen; `close()` shuts it all down."""
    env = load_env(env_model, {**(os.environ if environ is None else environ), 'SERVICE_NAME': name})
    log: Logger = create_logger(name, env.LOG_LEVEL)
    route_stdlib_logging(log)
    pool: Pool | None = None
    bus: MessageBus | None = None
    if migrations_dir is not None:
        if not env.DATABASE_URL:
            raise ValueError('DATABASE_URL is not set')
        pool = await create_pool(env.DATABASE_URL, name=name)
        await migrate(pool, schema=name, dir=migrations_dir, log=log)
        if not env.QUEUE_DATABASE_URL:
            raise ValueError('QUEUE_DATABASE_URL is not set')
        bus = await Messaging.start(service=name, pool=pool, queue_url=env.QUEUE_DATABASE_URL, log=log)
    deps = make_deps(env=env, log=log, pool=pool, bus=bus or NoBus())
    app = create_app(deps, register, edge=edge, body_limit=body_limit)
    closed = False

    async def close() -> None:
        nonlocal closed
        if closed:
            return
        closed = True
        log.info('shutting down')
        await deps.bus.stop()
        await deps.clients.close()
        if pool is not None:
            await pool.close()

    # uvicorn runs the lifespan shutdown after it stops accepting requests: the moment to finish in-flight work and close pools
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        await close()

    app.router.lifespan_context = lifespan
    if workers is not None:
        await workers(deps)
    return RunningService(app, deps, close)


async def serve_service(name: str, **kwargs: Any) -> None:
    """Boot the service and serve until SIGTERM/SIGINT (graceful shutdown)."""
    svc = await boot_service(name, **kwargs)
    env = svc.deps.env
    config = uvicorn.Config(
        svc.app, host=env.HOST, port=env.PORT, log_config=None, access_log=False, proxy_headers=True,
        forwarded_allow_ips='*', timeout_graceful_shutdown=15,
    )
    server = uvicorn.Server(config)
    svc.deps.log.info('listening', port=env.PORT)
    try:
        await server.serve()
    finally:
        await svc.close()


def run_service(
    name: str,
    *,
    register: Register,
    env_model: type[BaseEnv] = BaseEnv,
    migrations_dir: str | Path | None = None,
    workers: Workers | None = None,
    body_limit: int = DEFAULT_BODY_LIMIT,
    edge: bool = False,
) -> None:
    """A service's `main()`: boot, listen on `HOST:PORT`, exit cleanly on SIGTERM/SIGINT. Leave `migrations_dir` out for services without a database."""
    asyncio.run(
        serve_service(
            name, register=register, env_model=env_model, migrations_dir=migrations_dir, workers=workers,
            body_limit=body_limit, edge=edge,
        )
    )
