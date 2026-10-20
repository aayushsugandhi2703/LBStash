"""FastAPI dependencies for routes: the request's identity, deps and common path parameters."""

from typing import Annotated

from fastapi import Depends, Path, Request
from pydantic import BaseModel

from lbstash.common import Ctx, Errors
from lbstash.contracts import MonthKey, Uuid
from lbstash.crypto import InternalClaims

from .app import Deps


def get_deps(request: Request) -> Deps:
    """The service's `Deps` (env, log, pool, bus, clients)."""
    return request.app.state.deps


def service_claims(request: Request) -> InternalClaims:
    """The verified internal-token claims; 401 when the request has none."""
    claims = getattr(request.state, 'internal', None)
    if claims is None:
        raise Errors.unauthorized('Missing service token')
    return claims


def optional_ctx(request: Request) -> Ctx | None:
    """The user context when the token names a user, else None (webhooks, ingest, system calls)."""
    return getattr(request.state, 'ctx', None)


def user_ctx(request: Request) -> Ctx:
    """The user context; 401 when the token names no user."""
    ctx = optional_ctx(request)
    if ctx is None:
        raise Errors.unauthorized()
    return ctx


def request_id(request: Request) -> str:
    """The id of this request (also sent back as `x-request-id`)."""
    return request.state.request_id


class IdParam(BaseModel):
    """`/things/{id}` with a UUID."""

    id: Uuid


class MonthParam(BaseModel):
    """`/plans/{month}` with 'YYYY-MM'."""

    month: MonthKey


def id_param(id: Annotated[Uuid, Path()]) -> IdParam:
    """Dependency: validated `{id}` path parameter. `p: IdParam = Depends(id_param)`."""
    return IdParam(id=id)


def month_param(month: Annotated[MonthKey, Path()]) -> MonthParam:
    """Dependency: validated `{month}` path parameter. `p: MonthParam = Depends(month_param)`."""
    return MonthParam(month=month)


UserCtx = Annotated[Ctx, Depends(user_ctx)]
OptionalCtx = Annotated[Ctx | None, Depends(optional_ctx)]
ServiceClaims = Annotated[InternalClaims, Depends(service_claims)]
DepsDep = Annotated[Deps, Depends(get_deps)]
RequestId = Annotated[str, Depends(request_id)]

__all__ = [
    'DepsDep', 'IdParam', 'MonthParam', 'OptionalCtx', 'RequestId', 'ServiceClaims', 'UserCtx', 'get_deps', 'id_param',
    'month_param', 'optional_ctx', 'request_id', 'service_claims', 'user_ctx',
]  # fmt: skip
