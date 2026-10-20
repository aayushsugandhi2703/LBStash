"""Public routes (via the gateway) and `/internal/*` routes (other services only)."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Query
from lbstash.common import Clock, system_clock
from lbstash.contracts import (
    BalanceCheckReq,
    BalanceCheckRes,
    BalanceChecksQuery,
    BalanceChecksRes,
    CategoriesQuery,
    CategoriesUsageRes,
    CategoryMonthsRes,
    CategoryUsageDto,
    CoerceInt,
    CreateCategoryReq,
    CreditReq,
    CreditRes,
    CreditsQuery,
    CreditsRes,
    DailyQuery,
    DailyRes,
    DeleteCategoryQuery,
    DeleteCategoryRes,
    ExportPart,
    IngestTransactionReq,
    IngestTransactionRes,
    ManualTransactionReq,
    Model,
    MonthsQuery,
    MonthsRes,
    MonthSummaryRes,
    PatchCategoryReq,
    PatchTransactionReq,
    PatchTransactionRes,
    PendingRes,
    RecurringPostReq,
    RecurringPostRes,
    ResolveCategoryReq,
    ResolveCategoryRes,
    SpendByCategoryRes,
    SpendQuery,
    SplitReq,
    SplitRes,
    SummaryQuery,
    TagReq,
    TagRes,
    TransactionPageDto,
    TransactionRes,
    TransactionSettings,
    TransactionSettingsPatch,
    TransactionsQuery,
)
from lbstash.kit import Deps, IdParam, UserCtx, id_param
from pydantic import Field

from . import aggregates as agg
from . import balance, categories, credits, settings, transactions
from .ingest import ingest, post_recurring
from .maintenance import export_rows
from .model import to_dto

Id = Annotated[IdParam, Depends(id_param)]


class LimitQuery(Model):
    limit: CoerceInt = Field(default=50, ge=1, le=100)


def make_routes(clock: Clock = system_clock) -> Callable[[FastAPI, Deps[Any]], None]:
    """`clock` is injectable so tests can freeze "now"."""

    def register(app: FastAPI, deps: Deps[Any]) -> None:
        r = APIRouter()

        async def category_list(ctx: Any, q: CategoriesQuery) -> CategoriesUsageRes:
            async with deps.as_user(ctx) as tx:
                items = await categories.list_categories(
                    tx, ctx.user_id, sort=q.sort, limit=q.limit, include_archived=q.include_archived
                )
            return CategoriesUsageRes(items=items)

        async def resolve(ctx: Any, raw_tag: str) -> ResolveCategoryRes:
            async with deps.as_user(ctx) as tx:
                category, created = await categories.resolve_category(tx, ctx.user_id, raw_tag)
            return ResolveCategoryRes(category=category, created=created)

        # public
        @r.get('/transactions', response_model=TransactionPageDto)
        async def list_transactions(ctx: UserCtx, q: Annotated[TransactionsQuery, Query()]):
            return await transactions.transactions_page(deps, ctx, q)

        @r.patch('/transactions/{id}', response_model=PatchTransactionRes)
        async def patch_transaction(p: Id, body: PatchTransactionReq, ctx: UserCtx):
            return await transactions.patch(
                deps, ctx, p.id, tag=body.tag, category_id=body.category_id, recategorize=body.recategorize
            )

        @r.post('/transactions/{id}/split', response_model=SplitRes)
        async def split_transaction(p: Id, body: SplitReq, ctx: UserCtx):
            return await transactions.split(deps, ctx, p.id, body.parts)

        @r.get('/credits', response_model=CreditsRes)
        async def list_credits(ctx: UserCtx, q: Annotated[CreditsQuery, Query()]):
            return await credits.recent_credits(deps, ctx, q.limit)

        @r.post('/credits', response_model=CreditRes, status_code=201)
        async def add_credit(body: CreditReq, ctx: UserCtx):
            return await credits.add_credit(deps, ctx, body, clock())

        @r.get('/categories', response_model=CategoriesUsageRes)
        async def list_categories(ctx: UserCtx, q: Annotated[CategoriesQuery, Query()]):
            return await category_list(ctx, q)

        @r.post('/categories', response_model=ResolveCategoryRes)
        async def create_category(body: CreateCategoryReq, ctx: UserCtx):
            return await resolve(ctx, body.name)

        @r.patch('/categories/{id}', response_model=CategoryUsageDto)
        async def patch_category(p: Id, body: PatchCategoryReq, ctx: UserCtx):
            return await categories.patch_category(deps, ctx, p.id, body)

        @r.delete('/categories/{id}', response_model=DeleteCategoryRes)
        async def delete_category(p: Id, q: Annotated[DeleteCategoryQuery, Query()], ctx: UserCtx):
            return await categories.delete_category(deps, ctx, p.id, q.reassign_to)

        @r.post('/balance-check', response_model=BalanceCheckRes)
        async def balance_check(body: BalanceCheckReq, ctx: UserCtx):
            return await balance.manual_check(deps, ctx, body.bank_balance_minor, clock())

        @r.get('/balance-checks', response_model=BalanceChecksRes)
        async def balance_checks(ctx: UserCtx, q: Annotated[BalanceChecksQuery, Query()]):
            return await balance.list_checks(deps, ctx, q.limit)

        @r.post('/balance-checks/{id}/book', response_model=BalanceCheckRes)
        async def book_check(p: Id, ctx: UserCtx):
            return await balance.book_now(deps, ctx, p.id, clock())

        @r.post('/balance-checks/{id}/ignore', response_model=BalanceCheckRes)
        async def ignore_check(p: Id, ctx: UserCtx):
            return await balance.ignore(deps, ctx, p.id)

        # internal
        @r.post('/internal/transactions/ingest', response_model=IngestTransactionRes)
        async def ingest_transaction(body: IngestTransactionReq, ctx: UserCtx):
            return await ingest(deps, ctx, body, clock())

        @r.post('/internal/transactions/manual', response_model=TransactionRes, status_code=201)
        async def manual_transaction(body: ManualTransactionReq, ctx: UserCtx):
            return TransactionRes(transaction=to_dto(await transactions.create_manual(deps, ctx, body)))

        @r.post('/internal/transactions/recurring', response_model=RecurringPostRes)
        async def recurring_transaction(body: RecurringPostReq, ctx: UserCtx):
            return await post_recurring(deps, ctx, body)

        # registered before `/internal/transactions/{id}`: "pending" is not an id
        @r.get('/internal/transactions/pending', response_model=PendingRes)
        async def pending_transactions(ctx: UserCtx, q: Annotated[LimitQuery, Query()]):
            return await transactions.pending(deps, ctx, q.limit)

        @r.get('/internal/transactions/{id}', response_model=TransactionRes)
        async def get_transaction(p: Id, ctx: UserCtx):
            return TransactionRes(transaction=to_dto(await transactions.get_transaction(deps, ctx, p.id)))

        @r.post('/internal/transactions/{id}/tag', response_model=TagRes)
        async def tag_transaction(p: Id, body: TagReq, ctx: UserCtx):
            return await transactions.tag(deps, ctx, p.id, tag=body.tag, category_id=body.category_id, via=body.via)

        @r.get('/internal/categories', response_model=CategoriesUsageRes)
        async def internal_categories(ctx: UserCtx, q: Annotated[CategoriesQuery, Query()]):
            return await category_list(ctx, q)

        @r.post('/internal/categories/resolve', response_model=ResolveCategoryRes)
        async def resolve_category(body: ResolveCategoryReq, ctx: UserCtx):
            return await resolve(ctx, body.tag)

        @r.get('/internal/spend/by-category', response_model=SpendByCategoryRes)
        async def spend_by_category(ctx: UserCtx, q: Annotated[SpendQuery, Query()]):
            async with deps.as_user(ctx) as tx:
                return await agg.spend_by_category(tx, ctx.user_id, q.from_, q.to)

        @r.get('/internal/aggregates/summary', response_model=MonthSummaryRes)
        async def summary(ctx: UserCtx, q: Annotated[SummaryQuery, Query()]):
            async with deps.as_user(ctx) as tx:
                return await agg.month_summary(tx, ctx, q.month)

        @r.get('/internal/aggregates/months', response_model=MonthsRes)
        async def months(ctx: UserCtx, q: Annotated[MonthsQuery, Query()]):
            async with deps.as_user(ctx) as tx:
                return await agg.months(tx, ctx, q.end, q.count)

        @r.get('/internal/aggregates/category-months', response_model=CategoryMonthsRes)
        async def category_months(ctx: UserCtx, q: Annotated[MonthsQuery, Query()]):
            async with deps.as_user(ctx) as tx:
                return await agg.category_months(tx, ctx, q.end, q.count)

        @r.get('/internal/aggregates/daily', response_model=DailyRes)
        async def daily(ctx: UserCtx, q: Annotated[DailyQuery, Query()]):
            exclude = agg.parse_id_list(q.exclude_category_ids)
            async with deps.as_user(ctx) as tx:
                return await agg.daily(tx, ctx, q.month, exclude)

        @r.get('/internal/settings', response_model=TransactionSettings)
        async def get_settings(ctx: UserCtx):
            async with deps.as_user(ctx) as tx:
                s = await settings.get_settings(tx, ctx.user_id)
            return TransactionSettings(opening_balance_minor=s.opening_balance_minor, reconcile_grace_hours=s.reconcile_grace_hours)

        @r.patch('/internal/settings', response_model=TransactionSettings)
        async def patch_settings(ctx: UserCtx, body: TransactionSettingsPatch = TransactionSettingsPatch()):  # noqa: B008 - no body is an empty patch
            return await settings.patch_settings(
                deps, ctx, opening_balance_minor=body.opening_balance_minor, reconcile_grace_hours=body.reconcile_grace_hours
            )

        @r.get('/internal/export', response_model=ExportPart)
        async def export(ctx: UserCtx):
            return await export_rows(deps, ctx)

        app.include_router(r)

    return register


register = make_routes()
