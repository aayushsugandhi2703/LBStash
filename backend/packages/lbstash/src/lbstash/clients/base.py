"""HTTP client for service-to-service calls: signs a short-lived token, times out, retries GETs, maps error bodies back to `AppError` and validates the answer against the contract."""

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, TypeVar
from urllib.parse import urlencode, urljoin

import httpx
from pydantic import BaseModel, ValidationError

from lbstash.common import HEADERS, AppError, Errors
from lbstash.contracts.base import dump, iso_ms
from lbstash.crypto import sign_internal_token

M = TypeVar('M', bound=BaseModel)

Method = Literal['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
QueryValue = str | int | float | bool | datetime | None


@dataclass(frozen=True, slots=True)
class CallAs:
    """Who a call is for. Omit `user_id` for system calls. A `lbstash.common.Ctx` or a dict with the same keys works too."""

    user_id: str | None = None
    tz: str | None = None
    request_id: str | None = None


def _who(as_: Any) -> CallAs | None:
    if as_ is None or isinstance(as_, CallAs):
        return as_
    if isinstance(as_, Mapping):
        return CallAs(as_.get('user_id'), as_.get('tz'), as_.get('request_id'))
    return CallAs(getattr(as_, 'user_id', None), getattr(as_, 'tz', None), getattr(as_, 'request_id', None))


@dataclass(slots=True)
class ClientOptions:
    # Calling service; goes into the token.
    from_service: str
    base_url: str
    secret: str
    # Seconds per attempt, connect to last byte.
    timeout: float = 8.0
    # GET retries on network errors and 5xx. Writes are never retried here; make them idempotent and retry in the job.
    retries: int = 2
    # For tests: an httpx transport (e.g. `httpx.MockTransport`) or a ready `httpx.AsyncClient`.
    transport: httpx.AsyncBaseTransport | None = None
    client: httpx.AsyncClient | None = None
    # Back-off sleeper; tests replace it.
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


def _query_string(query: Mapping[str, QueryValue] | None) -> str:
    pairs: list[tuple[str, str]] = []
    for k, v in (query or {}).items():
        if v is None:
            continue
        if isinstance(v, bool):
            pairs.append((k, 'true' if v else 'false'))
        elif isinstance(v, datetime):
            pairs.append((k, iso_ms(v)))
        else:
            pairs.append((k, str(v)))
    return urlencode(pairs)


def _safe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except ValueError:
        return None


class ServiceClient:
    def __init__(self, o: ClientOptions, target: str) -> None:
        self.o = o
        self.target = target
        self._http: httpx.AsyncClient | None = o.client
        self._owns_http = o.client is None

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(transport=self.o.transport)
        return self._http

    async def aclose(self) -> None:
        """Release the connection pool (a client passed via `ClientOptions.client` stays open)."""
        if self._http is not None and self._owns_http:
            await self._http.aclose()
            self._http = None

    async def request(
        self,
        as_: Any,
        method: Method,
        path: str,
        *,
        query: Mapping[str, QueryValue] | None = None,
        body: Any = None,
        model: type[M] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Call `path`; return the validated `model` (or the parsed JSON if none)."""
        url = urljoin(self.o.base_url, path)
        qs = _query_string(query)
        if qs:
            url = f'{url}?{qs}'
        attempts = self.o.retries + 1 if method == 'GET' else 1
        last: BaseException | None = None
        for i in range(attempts):
            try:
                return await self._once(_who(as_), method, url, body, model, headers)
            except Exception as e:  # noqa: BLE001  (network errors, timeouts and AppError handled below)
                last = e
                retryable = not isinstance(e, AppError) or e.status >= 500
                if not retryable or i == attempts - 1:
                    break
                await self.o.sleep(0.1 * 2**i)
        if isinstance(last, AppError):
            raise last
        raise Errors.upstream(self.target, f'{self.target} is not reachable')

    async def _once(
        self, who: CallAs | None, method: str, url: str, body: Any, model: type[M] | None, extra: Mapping[str, str] | None
    ) -> Any:
        token = sign_internal_token(
            self.o.secret,
            svc=self.o.from_service,
            user_id=who.user_id if who else None,
            tz=who.tz if who else None,
            request_id=who.request_id if who else None,
        )
        headers: dict[str, str] = {HEADERS.internal_token: token}
        if who and who.request_id:
            headers[HEADERS.request_id] = who.request_id
        content: bytes | None = None
        if body is not None:
            payload = dump(body) if isinstance(body, BaseModel) else body
            content = json.dumps(payload, separators=(',', ':'), ensure_ascii=False).encode()
            headers['content-type'] = 'application/json'
        headers.update(extra or {})

        async with asyncio.timeout(self.o.timeout):
            res = await self._client().request(method, url, headers=headers, content=content)
        text = res.text
        data = _safe_json(text) if text else None
        if not res.is_success:
            err = data.get('error') if isinstance(data, dict) else None
            err = err if isinstance(err, dict) else {}
            code = err.get('code') if isinstance(err.get('code'), str) else None
            raise AppError(
                code or ('upstream_failed' if res.status_code >= 500 else 'bad_request'),  # type: ignore[arg-type]
                err.get('message') if isinstance(err.get('message'), str) else f'{self.target} answered {res.status_code}',
                err.get('details'),
                res.status_code,
            )
        if model is None:
            return data
        try:
            return model.model_validate(data)
        except ValidationError:
            raise Errors.upstream(self.target, f'{self.target} answered with an unexpected shape') from None
