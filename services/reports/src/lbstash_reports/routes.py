"""Public read models. The user comes from the token; nothing is stored or cached. `clock` is injectable so tests can freeze "today"."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, FastAPI, Query
from lbstash.common import Clock, system_clock
from lbstash.contracts import (
    DashboardQuery,
    DashboardRes,
    ReportDailyQuery,
    ReportDailyRes,
    ReportMatrixRes,
    ReportMonthsRes,
    ReportRangeQuery,
)
from lbstash.kit import Deps, DepsDep, UserCtx

from . import trends
from .dashboard import dashboard


def make_register(clock: Clock = system_clock) -> Callable[[FastAPI, Deps[Any]], None]:
    def register(app: FastAPI, deps: Deps[Any]) -> None:
        r = APIRouter()

        @r.get('/dashboard', response_model=DashboardRes)
        async def get_dashboard(ctx: UserCtx, d: DepsDep, q: Annotated[DashboardQuery, Query()]) -> DashboardRes:
            return await dashboard(d, ctx, clock, q)

        @r.get('/reports/daily', response_model=ReportDailyRes)
        async def get_daily(ctx: UserCtx, d: DepsDep, q: Annotated[ReportDailyQuery, Query()]) -> ReportDailyRes:
            return await trends.daily(d, ctx, clock, q)

        @r.get('/reports/months', response_model=ReportMonthsRes)
        async def get_months(ctx: UserCtx, d: DepsDep, q: Annotated[ReportRangeQuery, Query()]) -> ReportMonthsRes:
            return await trends.months(d, ctx, clock, q)

        @r.get('/reports/category-matrix', response_model=ReportMatrixRes)
        async def get_matrix(ctx: UserCtx, d: DepsDep, q: Annotated[ReportRangeQuery, Query()]) -> ReportMatrixRes:
            return await trends.category_matrix(d, ctx, clock, q)

        app.include_router(r)

    return register


register = make_register()
