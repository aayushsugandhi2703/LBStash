"""The gateway: guard (session, CSRF, rate limits), its own composed routes, then everything else proxied by ROUTE_TABLE. One catch-all route, so a request is routed by the same normalised path the guard checked."""

import asyncio
import json
from collections.abc import Callable
from typing import Any, Final

import httpx
from bt.common import HEADERS, AppError, Errors
from bt.contracts import SettingsPatch
from bt.contracts.base import validation_details
from bt.kit import Deps, user_ctx
from bt.kit.app import DEFAULT_BODY_LIMIT
from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import compose
from .env import Env
from .guard import GatewayInfo, RateLimited, build_guard, on_rate_limited
from .proxy import forward, service_url

INGEST_BODY_LIMIT: Final = 8 * 1024
WEBHOOK_BODY_LIMIT: Final = 64 * 1024
SERVICES_CHECKED: Final = ('auth', 'ledger', 'ingest', 'planning', 'recurring', 'reports', 'telegram')
_METHODS: Final = ['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE']
_WITH_BODY: Final = frozenset({'POST', 'PUT', 'PATCH', 'DELETE'})


def body_limit_for(method: str, path: str) -> int:
    """Small, fixed-size bodies get their own limits; everything else is under the kit's global 1 MB."""
    if method == 'POST' and path == '/ingest/message':
        return INGEST_BODY_LIMIT
    if method == 'POST' and path.startswith('/telegram/webhook/'):
        return WEBHOOK_BODY_LIMIT
    return DEFAULT_BODY_LIMIT


async def read_body(request: Request, limit: int) -> bytes:
    """The body as received, refused (413) as soon as it grows past `limit` instead of after buffering it all."""
    too_large = AppError('bad_request', 'Request body is too large', status=413)
    declared = request.headers.get('content-length')
    if declared and declared.isdigit() and int(declared) > limit:
        raise too_large
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise too_large
        chunks.append(chunk)
    return b''.join(chunks)


def _no_constant(name: str) -> Any:
    raise ValueError(name)


def parse_json_body(request: Request, raw: bytes) -> Any:
    """JSON bodies are kept as received (forwarded byte for byte) and also parsed, so composed routes validate them and a
    malformed body is refused here with the standard error shape. Other content types are forwarded as they are.
    """
    if not raw or request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'application/json':
        return None
    try:
        return json.loads(raw.decode('utf-8'), parse_constant=_no_constant)
    except (ValueError, RecursionError):
        raise Errors.bad_request('The body is not valid JSON') from None


class Hardening:
    """Outermost middleware (so it covers 413 and 500 too): locks the browser down, never allows caching, no CORS. Also closes the shared proxy client on shutdown."""

    def __init__(self, app: ASGIApp, *, on_shutdown: Callable[[], Any]) -> None:
        self.app = app
        self.on_shutdown = on_shutdown

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] == 'lifespan':

            async def lifespan_send(message: Message) -> None:
                if message['type'].startswith('lifespan.shutdown'):
                    await self.on_shutdown()
                await send(message)

            await self.app(scope, receive, lifespan_send)
            return
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        async def http_send(message: Message) -> None:
            if message['type'] == 'http.response.start':
                h = MutableHeaders(scope=message)
                h['cache-control'] = 'no-store'
                h['content-security-policy'] = "default-src 'none'; frame-ancestors 'none'"
                h['permissions-policy'] = 'camera=(), microphone=(), geolocation=()'
            await send(message)

        await self.app(scope, receive, http_send)


async def health_deps(deps: Deps[Env], client: httpx.AsyncClient, request_id: str) -> dict[str, Any]:
    """`GET /health/deps`: each service's `/ready`, for operators (200 only when all answer, else 503)."""

    async def ready(svc: str) -> tuple[str, bool]:
        try:
            async with asyncio.timeout(3):
                res = await client.get(service_url(deps.env, svc).rstrip('/') + '/ready', headers={HEADERS.request_id: request_id})
            return svc, res.is_success
        except (httpx.HTTPError, TimeoutError, OSError):
            return svc, False

    results = dict(await asyncio.gather(*(ready(s) for s in SERVICES_CHECKED)))
    return {'ok': all(results.values()), 'services': results}


def make_register(*, transport: httpx.AsyncBaseTransport | None = None) -> Callable[[FastAPI, Deps[Any]], None]:
    """`register(app, deps)` for the kit. `transport` lets tests put fake services behind the proxy client."""

    def register(app: FastAPI, deps: Deps[Any]) -> None:
        # One client for all proxying (connection reuse). Timeouts are enforced per call in `forward`, over the whole answer.
        client = httpx.AsyncClient(
            transport=transport, headers={'user-agent': 'bt-gateway', 'accept-encoding': 'identity'},
            limits=httpx.Limits(max_connections=200, max_keepalive_connections=50),
            timeout=httpx.Timeout(deps.env.UPSTREAM_TIMEOUT_MS / 1000), follow_redirects=False,
        )  # fmt: skip
        app.state.proxy_client = client

        async def close_client() -> None:
            if not client.is_closed:
                await client.aclose()

        app.add_middleware(Hardening, on_shutdown=close_client)
        app.add_exception_handler(RateLimited, on_rate_limited)
        router = APIRouter()

        @router.api_route('/{path:path}', methods=_METHODS, dependencies=[Depends(build_guard(deps))], include_in_schema=False)
        async def handle(request: Request) -> Response:
            gw: GatewayInfo = request.state.gw
            method, path = request.method, gw.path

            if method == 'GET' and path == '/me':
                return JSONResponse(await compose.me(deps, user_ctx(request)))
            if path == '/settings' and method in ('GET', 'PATCH'):
                ctx = user_ctx(request)
                if method == 'GET':
                    return JSONResponse(await compose.settings(deps, ctx))
                parsed = parse_json_body(request, await read_body(request, DEFAULT_BODY_LIMIT))
                try:
                    patch = SettingsPatch.model_validate({} if parsed is None else parsed)
                except ValidationError as e:
                    raise Errors.validation(validation_details(e)) from None
                return JSONResponse(await compose.settings(deps, ctx, patch))
            if method == 'GET' and path == '/health/deps':
                out = await health_deps(deps, client, request.state.request_id)
                return JSONResponse(out, status_code=200 if out['ok'] else 503)

            body: bytes | None = None
            if method in _WITH_BODY:
                body = await read_body(request, body_limit_for(method, path))
                parse_json_body(request, body)
            return await forward(deps, client, request, gw, body)

        app.include_router(router)

    return register


register = make_register()
