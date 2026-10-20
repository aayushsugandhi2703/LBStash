"""Public routes (via the gateway) and `/internal/*` (other services only)."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI
from lbstash.common import Clock, Errors, system_clock
from lbstash.contracts import (
    CreateRecurringReq,
    ExportPart,
    PatchRecurringReq,
    RecurringDeleteRes,
    RecurringMutationRes,
    RecurringRes,
)
from lbstash.kit import DepsDep, IdParam, OptionalCtx, ServiceClaims, UserCtx, id_param

from . import rules

Id = Annotated[IdParam, Depends(id_param)]


def make_routes(clock: Clock = system_clock):
    """`register(app, deps)` with an injectable clock for tests."""

    def register(app: FastAPI, _deps: Any) -> None:
        router = APIRouter()

        @router.get('/recurring', response_model=RecurringRes)
        async def list_rules(ctx: UserCtx, deps: DepsDep) -> RecurringRes:
            return await rules.list_rules(deps, ctx)

        @router.post('/recurring', response_model=RecurringMutationRes, status_code=201)
        async def create_rule(body: CreateRecurringReq, ctx: UserCtx, deps: DepsDep) -> RecurringMutationRes:
            return await rules.create(deps, ctx, clock, body)

        @router.patch('/recurring/{id}', response_model=RecurringMutationRes)
        async def patch_rule(p: Id, body: PatchRecurringReq, ctx: UserCtx, deps: DepsDep) -> RecurringMutationRes:
            return await rules.patch(deps, ctx, clock, p.id, body)

        @router.delete('/recurring/{id}', response_model=RecurringDeleteRes)
        async def delete_rule(p: Id, ctx: UserCtx, deps: DepsDep) -> RecurringDeleteRes:
            return await rules.remove(deps, ctx, p.id)

        # auth composes the data export from every service; the token names the user
        @router.get('/internal/export', response_model=ExportPart)
        async def export(_claims: ServiceClaims, ctx: OptionalCtx, deps: DepsDep) -> dict[str, Any]:
            if ctx is None:
                raise Errors.unauthorized()
            return await rules.export_rows(deps, ctx)

        app.include_router(router)

    return register


register = make_routes()
