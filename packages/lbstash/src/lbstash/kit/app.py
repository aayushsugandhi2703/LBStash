"""Build the FastAPI app every service shares: request ids, internal-token auth, error shapes, health, security headers."""

import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import psycopg
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from lbstash.common import DEFAULT_TZ, HEADERS, AppError, BaseEnv, Ctx, Errors, Logger
from lbstash.crypto import InternalClaims, TokenError, verify_internal_token
from lbstash.db import Pool, Tx
from lbstash.queue import MessageBus

DEFAULT_BODY_LIMIT = 1_048_576
_UNPROTECTED = frozenset({'/health', '/ready'})
# Standard hardening headers (no Content-Security-Policy); a route's own header of the same name wins.
SECURITY_HEADERS = {
    'cross-origin-opener-policy': 'same-origin',
    'cross-origin-resource-policy': 'same-origin',
    'origin-agent-cluster': '?1',
    'referrer-policy': 'no-referrer',
    'strict-transport-security': 'max-age=15552000; includeSubDomains',
    'x-content-type-options': 'nosniff',
    'x-dns-prefetch-control': 'off',
    'x-download-options': 'noopen',
    'x-frame-options': 'SAMEORIGIN',
    'x-permitted-cross-domain-policies': 'none',
    'x-xss-protection': '0',
}


@dataclass
class Deps[E: BaseEnv]:
    """What a route or worker needs, passed in so tests can swap any of it."""

    env: E
    log: Logger
    # None for services without a database (gateway, reports)
    pool: Pool | None
    bus: MessageBus
    # `lbstash.clients.Clients`: typed clients for the other services, signed as this service
    clients: Any

    def _need_pool(self) -> Pool:
        if self.pool is None:
            raise RuntimeError(f'{self.env.SERVICE_NAME} has no database')
        return self.pool

    @asynccontextmanager
    async def as_user(self, ctx: Ctx | str) -> AsyncIterator[Tx]:
        """A transaction scoped to the user (row-level security applies)."""
        async with self._need_pool().user_tx(ctx if isinstance(ctx, str) else ctx.user_id) as tx:
            yield tx

    @asynccontextmanager
    async def as_system(self) -> AsyncIterator[Tx]:
        """A transaction that sees every user (scheduler scans, retention)."""
        async with self._need_pool().system_tx() as tx:
            yield tx


class NoBus:
    """Bus of a service without a database; any call except `stop` raises."""

    def __getattr__(self, name: str) -> Callable[..., Any]:
        async def refuse(*_a: Any, **_k: Any) -> None:
            if name != 'stop':
                raise RuntimeError('this service has no message bus')

        return refuse


def make_deps[E: BaseEnv](
    *, env: E, log: Logger, pool: Pool | None = None, bus: MessageBus | None = None, clients: Any = None
) -> Deps[E]:
    """Assemble `Deps`; `clients` defaults to `lbstash.clients.create_clients(env.SERVICE_NAME, env)`."""
    if clients is None:
        from lbstash.clients import create_clients

        clients = create_clients(env.SERVICE_NAME, env)
    return Deps(env=env, log=log, pool=pool, bus=bus or NoBus(), clients=clients)  # type: ignore[arg-type]


def _json(status: int, body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(body, status_code=status)


class _BodyTooLarge(Exception):
    pass


class RequestMiddleware:
    """Pure ASGI middleware: request id, internal-token check, body limit, security headers, request log."""

    def __init__(self, app: ASGIApp, *, deps: Deps[Any], edge: bool, body_limit: int) -> None:
        self.app = app
        self.deps = deps
        self.edge = edge
        self.body_limit = body_limit

    def _request_id(self, headers: Headers) -> str:
        # a client-chosen id is trusted only behind the gateway, and only if it is safe in logs and headers
        given = None if self.edge else headers.get(HEADERS.request_id)
        if given and 0 < len(given) <= 128 and all(c.isalnum() or c in '-_.:' for c in given):
            return given
        return str(uuid.uuid4())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return
        t0 = time.perf_counter()
        headers = Headers(scope=scope)
        rid = self._request_id(headers)
        state: dict[str, Any] = scope.setdefault('state', {})
        state.update(request_id=rid, internal=None, ctx=None)
        path: str = scope['path']
        status = 0
        started = False
        too_large = False

        rewriting = False  # the app answered an oversized body with its own error: replace it with the 413
        replaced = False

        async def send_wrapper(message: Message) -> None:
            nonlocal status, started, rewriting, replaced
            if too_large and message['type'] == 'http.response.start' and message['status'] != 413:
                rewriting = True
                message = {
                    'type': 'http.response.start', 'status': 413,
                    'headers': [(b'content-type', b'application/json'), (b'content-length', str(len(_TOO_LARGE_BODY)).encode())],
                }  # fmt: skip
            elif rewriting and message['type'] == 'http.response.body':
                if replaced:
                    return
                replaced = True
                message = {'type': 'http.response.body', 'body': _TOO_LARGE_BODY}
            if message['type'] == 'http.response.start':
                started = True
                status = message['status']
                h = MutableHeaders(scope=message)
                for k, v in SECURITY_HEADERS.items():
                    if k not in h:
                        h[k] = v
                h[HEADERS.request_id] = rid
            await send(message)

        async def reply(err: AppError) -> None:
            await _json(err.status, err.to_json())(scope, receive, send_wrapper)

        received = 0

        async def receive_wrapper() -> Message:
            nonlocal received, too_large
            msg = await receive()
            if msg['type'] == 'http.request':
                received += len(msg.get('body', b''))
                if received > self.body_limit:
                    too_large = True
                    raise _BodyTooLarge
            return msg

        try:
            if not self.edge and path not in _UNPROTECTED:
                token = headers.get(HEADERS.internal_token)
                if token is None:
                    return await reply(AppError('unauthorized', 'Missing service token'))
                try:
                    claims = verify_internal_token(self.deps.env.INTERNAL_SECRET, token)
                except TokenError:
                    return await reply(AppError('unauthorized', 'Bad service token'))
                # internal routes are for other services only: refuse anything the gateway forwarded from outside
                if path.startswith('/internal/') and claims.proxied:
                    return await reply(AppError('forbidden', 'Internal route'))
                self._attach(state, claims, rid)
            declared = headers.get('content-length')
            if declared and declared.isdigit() and int(declared) > self.body_limit:
                return await reply(AppError('bad_request', 'Request body is too large', status=413))
            try:
                await self.app(scope, receive_wrapper, send_wrapper)
            except _BodyTooLarge:
                if not started:
                    await reply(AppError('bad_request', 'Request body is too large', status=413))
            except Exception as e:
                self.deps.log.error('unhandled error', err=e, rid=rid)
                if started:
                    raise
                await reply(AppError('internal', 'Something went wrong', {'requestId': rid}))
        finally:
            if path not in _UNPROTECTED:
                ctx = state.get('ctx')
                route = scope.get('route')
                self.deps.log.info(
                    'req', method=scope['method'], path=getattr(route, 'path', None) or '(no route)', status=status,
                    ms=round((time.perf_counter() - t0) * 1000), rid=rid, uid=ctx.user_id if ctx else None,
                )  # fmt: skip

    @staticmethod
    def _attach(state: dict[str, Any], claims: InternalClaims, rid: str) -> None:
        state['internal'] = claims
        if claims.user_id:
            state['ctx'] = Ctx(user_id=claims.user_id, tz=claims.tz or DEFAULT_TZ, request_id=claims.request_id or rid)


_TOO_LARGE_BODY = b'{"error":{"code":"bad_request","message":"Request body is too large"}}'


def _details(exc: RequestValidationError) -> dict[str, str]:
    details: dict[str, str] = {}
    for err in exc.errors():
        loc = [str(p) for p in err['loc'][1:]]  # drop "body" / "query" / "path"
        msg = str(err['msg']).removeprefix('Value error, ')
        details.setdefault('.'.join(loc) or '_', msg)
    return details


def create_app(
    deps: Deps[Any],
    register: Callable[[FastAPI, Deps[Any]], None],
    *,
    edge: bool = False,
    body_limit: int = DEFAULT_BODY_LIMIT,
) -> FastAPI:
    """Build the app: middleware, error handlers, `/health`, `/ready`, then the service's `register(app, deps)`. `edge=True` (gateway) skips the internal-token check, so `register` must authenticate every route."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.deps = deps
    app.add_middleware(RequestMiddleware, deps=deps, edge=edge, body_limit=body_limit)

    @app.exception_handler(AppError)
    async def on_app_error(request: Request, exc: AppError) -> JSONResponse:
        if exc.status >= 500:
            deps.log.error('app error', code=exc.code, rid=request.state.request_id)
        return _json(exc.status, exc.to_json())

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        if any(e['type'] == 'json_invalid' for e in exc.errors()):
            deps.log.info('bad request', why='body is not valid JSON', rid=request.state.request_id)
            return _json(400, Errors.bad_request('Body is not valid JSON').to_json())
        details = _details(exc)
        # field names and rule messages only, never the values sent
        deps.log.info('validation failed', fields=details, rid=request.state.request_id)
        return _json(400, Errors.validation(details).to_json())

    @app.exception_handler(StarletteHTTPException)
    async def on_http(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code in (404, 405):
            return _json(404, {'error': {'code': 'not_found', 'message': 'No such route'}})
        if exc.status_code < 500:
            return _json(exc.status_code, {'error': {'code': 'bad_request', 'message': str(exc.detail)}})
        return _json(500, Errors.internal().to_json())

    @app.get('/health', include_in_schema=False)
    async def health() -> dict[str, Any]:
        return {'ok': True, 'service': deps.env.SERVICE_NAME}

    @app.get('/ready', include_in_schema=False)
    async def ready() -> Any:
        try:
            if deps.pool is not None:
                await deps.pool.execute('SELECT 1')
            return {'ok': True, 'service': deps.env.SERVICE_NAME}
        except (psycopg.Error, OSError):
            return _json(503, {'ok': False})

    register(app, deps)
    return app
