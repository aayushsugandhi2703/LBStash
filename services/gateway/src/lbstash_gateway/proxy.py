"""Forward one request to the service that owns its path."""

import asyncio
from typing import Final

import httpx
from fastapi import Request, Response
from lbstash.common import HEADERS, Errors
from lbstash.crypto import sign_internal_token
from lbstash.kit import Deps

from .env import Env
from .guard import GatewayInfo
from .paths import resolve_service

# Answer headers passed on; all else is ours. `set-cookie` is handled apart (there can be several).
PASS_BACK: Final = ('content-type', 'content-disposition', 'retry-after', 'etag', 'location')
_BODYLESS: Final = frozenset({101, 204, 205, 304})


class _Truncated(Exception):
    """The upstream answered but the body did not arrive."""


def service_url(env: Env, svc: str) -> str:
    return getattr(env, f'{svc.upper()}_URL')


async def forward(deps: Deps[Env], client: httpx.AsyncClient, request: Request, gw: GatewayInfo, body: bytes | None) -> Response:
    """Build the upstream headers from scratch so a client cannot smuggle `x-internal-token`, `x-forwarded-*` or `host`. The token names the user from the verified cookie and always has `proxied=True`."""
    method = request.method
    svc = resolve_service(gw.path, method)
    if svc is None or svc == 'gateway':
        raise Errors.not_found('Route')

    rid: str = request.state.request_id
    user = None if gw.public else request.state.ctx
    token = sign_internal_token(
        deps.env.INTERNAL_SECRET, svc='gateway', user_id=user.user_id if user else None, tz=user.tz if user else None,
        request_id=rid, proxied=True,
    )  # fmt: skip

    headers = {HEADERS.internal_token: token, HEADERS.request_id: rid, 'x-forwarded-for': gw.ip}

    def pass_(name: str) -> None:
        if (v := request.headers.get(name)) is not None:
            headers[name] = v

    pass_('accept')
    if body is not None:
        pass_('content-type')
    # only auth reads cookies (refresh cookie, and the access cookie's session id); no other service sees one
    if svc == 'auth':
        pass_('cookie')
    # The two callers that are not browsers authenticate themselves with these.
    if gw.public and svc == 'ingest':
        pass_('authorization')
    if gw.public and svc == 'telegram':
        pass_('x-telegram-bot-api-secret-token')

    url = service_url(deps.env, svc).rstrip('/') + gw.path + gw.query
    content = body if body and method not in ('GET', 'HEAD') else None
    try:
        async with asyncio.timeout(deps.env.UPSTREAM_TIMEOUT_MS / 1000):
            res = await client.send(client.build_request(method, url, headers=headers, content=content), stream=True)
            try:
                data = await res.aread()
            except httpx.HTTPError:
                raise _Truncated from None
            finally:
                await res.aclose()
    except _Truncated:
        raise Errors.upstream(svc, f'{svc} did not finish its answer') from None
    except (httpx.HTTPError, TimeoutError, OSError):
        deps.log.warning('upstream unreachable', svc=svc, rid=rid)
        raise Errors.upstream(svc, f'{svc} is not reachable') from None

    out = {name: v for name in PASS_BACK if (v := res.headers.get(name))}
    bodyless = res.status_code in _BODYLESS or method == 'HEAD'
    response = Response(content=b'' if bodyless else data, status_code=res.status_code, headers=out)
    for cookie in res.headers.get_list('set-cookie'):
        response.headers.append('set-cookie', cookie)
    return response
