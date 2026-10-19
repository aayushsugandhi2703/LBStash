"""Public routes (via the gateway) and `/internal/*` routes (other services only)."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any

from bt.common import Clock, system_clock
from bt.contracts import (
    AlertReadRes,
    AlertsRes,
    BudgetCreateReq,
    BudgetDto,
    BudgetPatchReq,
    BudgetsQuery,
    BudgetsRes,
    ExportPart,
    Ok,
    PlanCreditReq,
    PlanCreditRes,
    PlanningSettings,
    PlanningSettingsPatch,
    PlanPutReq,
    PlanWithSpendDto,
)
from bt.contracts.base import iso_ms
from bt.kit import Deps, IdParam, MonthParam, UserCtx
from bt.kit.http import id_param, month_param
from fastapi import APIRouter, Depends, FastAPI, Query

from . import alerts, budgets, plans, settings

_EXPORT_TABLES = {
    'plans': 'SELECT * FROM plans ORDER BY month',
    'plan_lines': 'SELECT * FROM plan_lines ORDER BY plan_id, position',
    'plan_credits': 'SELECT * FROM plan_credits ORDER BY created_at',
    'budgets': 'SELECT * FROM budgets ORDER BY created_at',
    'alerts': 'SELECT * FROM alerts ORDER BY sent_at',
    'settings': 'SELECT * FROM planning_settings',
}


def _json_row(row: dict[str, Any]) -> dict[str, Any]:
    """Export timestamps as ISO with milliseconds and `Z` (`...00.000Z`)."""
    return {k: iso_ms(v) if isinstance(v, datetime) else v for k, v in row.items()}


def routes_with(now: Clock) -> Callable[[FastAPI, Deps], None]:
    """Route registrar with an injectable clock for tests."""

    def register(app: FastAPI, deps: Deps) -> None:
        r = APIRouter()
        month_p = Annotated[MonthParam, Depends(month_param)]
        id_p = Annotated[IdParam, Depends(id_param)]

        @r.get('/plans/{month}', response_model=PlanWithSpendDto)
        async def get_plan(p: month_p, ctx: UserCtx) -> PlanWithSpendDto:
            return await plans.get_plan(deps, ctx, p.month)

        @r.put('/plans/{month}', response_model=PlanWithSpendDto)
        async def put_plan(p: month_p, body: PlanPutReq, ctx: UserCtx) -> PlanWithSpendDto:
            return await plans.put_plan(deps, ctx, p.month, body)

        @r.get('/budgets', response_model=BudgetsRes)
        async def list_budgets(query: Annotated[BudgetsQuery, Query()], ctx: UserCtx) -> BudgetsRes:
            return await budgets.list_budgets(deps, ctx, query.month, now)

        @r.post('/budgets', response_model=BudgetDto, status_code=201)
        async def create_budget(body: BudgetCreateReq, ctx: UserCtx) -> BudgetDto:
            return await budgets.create_budget(deps, ctx, body, now)

        @r.patch('/budgets/{id}', response_model=BudgetDto)
        async def patch_budget(p: id_p, body: BudgetPatchReq, ctx: UserCtx) -> BudgetDto:
            return await budgets.patch_budget(deps, ctx, p.id, body, now)

        @r.delete('/budgets/{id}', response_model=Ok)
        async def delete_budget(p: id_p, ctx: UserCtx) -> Ok:
            await budgets.delete_budget(deps, ctx, p.id)
            return Ok(ok=True)

        @r.get('/alerts', response_model=AlertsRes)
        async def list_alerts(ctx: UserCtx) -> AlertsRes:
            return await alerts.list_alerts(deps, ctx)

        @r.post('/alerts/{id}/read', response_model=AlertReadRes)
        async def mark_read(p: id_p, ctx: UserCtx) -> AlertReadRes:
            return await alerts.mark_read(deps, ctx, p.id)

        # internal: all need a user (`UserCtx` answers 401 without one)
        @r.post('/internal/plans/{month}/credit', response_model=PlanCreditRes)
        async def add_credit(p: month_p, body: PlanCreditReq, ctx: UserCtx) -> PlanCreditRes:
            return PlanCreditRes(
                total_minor=await plans.add_credit(deps, ctx, p.month, body.transaction_id, body.amount_minor)
            )

        @r.get('/internal/settings', response_model=PlanningSettings)
        async def get_settings(ctx: UserCtx) -> PlanningSettings:
            return await settings.get_settings(deps, ctx)

        @r.patch('/internal/settings', response_model=PlanningSettings)
        async def patch_settings(body: PlanningSettingsPatch, ctx: UserCtx) -> PlanningSettings:
            return await settings.patch_settings(deps, ctx, body, now)

        @r.get('/internal/export', response_model=ExportPart)
        async def export(ctx: UserCtx) -> dict[str, Any]:
            async with deps.as_user(ctx) as tx:
                tables = {name: [_json_row(row) for row in await tx.many(sql)] for name, sql in _EXPORT_TABLES.items()}
            return {'service': 'planning', 'tables': tables}

        app.include_router(r)

    return register


register = routes_with(system_clock)
