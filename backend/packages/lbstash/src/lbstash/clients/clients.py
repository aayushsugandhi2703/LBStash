"""One typed client per service, one method per internal endpoint. Paths must match the routes. Methods take `as_` first and return the contract model."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Protocol, Self

from lbstash.contracts import (
    AlertsRes,
    BalanceCheckRes,
    BalanceChecksRes,
    BudgetsRes,
    CategoriesRes,
    CategoryMonthsRes,
    DailyRes,
    ExportPart,
    IngestTransactionRes,
    MeInternalRes,
    MonthsRes,
    MonthSummaryRes,
    PendingRes,
    PlanCreditRes,
    PlanningSettings,
    PlanWithSpendDto,
    RecurringPostRes,
    RecurringRes,
    ResolveCategoryRes,
    SessionCheckRes,
    SpendByCategoryRes,
    TagRes,
    TelegramSettings,
    TransactionRes,
    TransactionSettings,
    UnparsedCountRes,
    VerifyTotpRes,
)

from .base import CallAs, ClientOptions, ServiceClient

Body = Any


class TransactionsClient(ServiceClient):
    def __init__(self, o: ClientOptions) -> None:
        super().__init__(o, 'transactions')

    async def ingest(self, as_: Any, body: Body) -> IngestTransactionRes:
        return await self.request(as_, 'POST', '/internal/transactions/ingest', body=body, model=IngestTransactionRes)

    async def create_manual(self, as_: Any, body: Body) -> TransactionRes:
        return await self.request(as_, 'POST', '/internal/transactions/manual', body=body, model=TransactionRes)

    async def post_recurring(self, as_: Any, body: Body) -> RecurringPostRes:
        return await self.request(as_, 'POST', '/internal/transactions/recurring', body=body, model=RecurringPostRes)

    async def get_transaction(self, as_: Any, id: str) -> TransactionRes:
        return await self.request(as_, 'GET', f'/internal/transactions/{id}', model=TransactionRes)

    async def tag(self, as_: Any, id: str, body: Body) -> TagRes:
        return await self.request(as_, 'POST', f'/internal/transactions/{id}/tag', body=body, model=TagRes)

    async def pending(self, as_: Any, limit: int = 50) -> PendingRes:
        return await self.request(as_, 'GET', '/internal/transactions/pending', query={'limit': limit}, model=PendingRes)

    async def categories(
        self,
        as_: Any,
        *,
        sort: Literal['usage', 'name'] | None = None,
        limit: int | None = None,
        include_archived: bool | None = None,
    ) -> CategoriesRes:
        query = {'sort': sort, 'limit': limit, 'includeArchived': include_archived}
        return await self.request(as_, 'GET', '/internal/categories', query=query, model=CategoriesRes)

    async def resolve_category(self, as_: Any, tag: str) -> ResolveCategoryRes:
        return await self.request(
            as_, 'POST', '/internal/categories/resolve', body={'tag': tag}, model=ResolveCategoryRes
        )

    async def spend_by_category(self, as_: Any, from_: str | datetime, to: str | datetime) -> SpendByCategoryRes:
        """Debits per category in [from, to), excluding #transfer and reversed."""
        return await self.request(
            as_, 'GET', '/internal/spend/by-category', query={'from': from_, 'to': to}, model=SpendByCategoryRes
        )

    async def month_summary(self, as_: Any, month: str) -> MonthSummaryRes:
        return await self.request(
            as_, 'GET', '/internal/aggregates/summary', query={'month': month}, model=MonthSummaryRes
        )

    async def months(self, as_: Any, end: str, count: int = 6) -> MonthsRes:
        return await self.request(
            as_, 'GET', '/internal/aggregates/months', query={'end': end, 'count': count}, model=MonthsRes
        )

    async def category_months(self, as_: Any, end: str, count: int = 6) -> CategoryMonthsRes:
        return await self.request(
            as_,
            'GET',
            '/internal/aggregates/category-months',
            query={'end': end, 'count': count},
            model=CategoryMonthsRes,
        )

    async def daily(self, as_: Any, month: str, exclude_category_ids: Sequence[str] = ()) -> DailyRes:
        query = {'month': month, 'excludeCategoryIds': ','.join(exclude_category_ids) or None}
        return await self.request(as_, 'GET', '/internal/aggregates/daily', query=query, model=DailyRes)

    async def balance_checks(self, as_: Any, limit: int = 1) -> BalanceChecksRes:
        """Newest first (public route, composed by other services)."""
        return await self.request(as_, 'GET', '/balance-checks', query={'limit': limit}, model=BalanceChecksRes)

    async def balance_check(self, as_: Any, bank_balance_minor: int) -> BalanceCheckRes:
        """Compare a bank balance with the tracked one (public route, composed by other services)."""
        return await self.request(
            as_, 'POST', '/balance-check', body={'bankBalanceMinor': bank_balance_minor}, model=BalanceCheckRes
        )

    async def settings(self, as_: Any) -> TransactionSettings:
        return await self.request(as_, 'GET', '/internal/settings', model=TransactionSettings)

    async def export(self, as_: Any) -> ExportPart:
        return await self.request(as_, 'GET', '/internal/export', model=ExportPart)

    async def patch_settings(self, as_: Any, body: Body) -> TransactionSettings:
        return await self.request(as_, 'PATCH', '/internal/settings', body=body, model=TransactionSettings)


class AuthClient(ServiceClient):
    def __init__(self, o: ClientOptions) -> None:
        super().__init__(o, 'auth')

    async def verify_totp(self, as_: Any, code: str) -> VerifyTotpRes:
        """Check an authenticator code (accepted once per time step); raises two_factor_invalid."""
        return await self.request(as_, 'POST', '/internal/totp/verify', body={'code': code}, model=VerifyTotpRes)

    async def me(self, as_: Any) -> MeInternalRes:
        return await self.request(as_, 'GET', '/internal/me', model=MeInternalRes)

    async def check_session(self, sid: str, ip: str | None = None) -> SessionCheckRes:
        """Is this browser session still alive, and allowed from `ip`? Carries no user."""
        return await self.request(
            None, 'POST', '/internal/sessions/check', body={'sid': sid, 'ip': ip}, model=SessionCheckRes
        )


class PlanningClient(ServiceClient):
    def __init__(self, o: ClientOptions) -> None:
        super().__init__(o, 'planning')

    async def plan(self, as_: Any, month: str) -> PlanWithSpendDto:
        return await self.request(as_, 'GET', f'/plans/{month}', model=PlanWithSpendDto)

    async def budgets(self, as_: Any, month: str) -> BudgetsRes:
        return await self.request(as_, 'GET', '/budgets', query={'month': month}, model=BudgetsRes)

    async def alerts(self, as_: Any) -> AlertsRes:
        return await self.request(as_, 'GET', '/alerts', model=AlertsRes)

    async def add_credit_to_plan(self, as_: Any, month: str, body: Body) -> PlanCreditRes:
        return await self.request(as_, 'POST', f'/internal/plans/{month}/credit', body=body, model=PlanCreditRes)

    async def settings(self, as_: Any) -> PlanningSettings:
        return await self.request(as_, 'GET', '/internal/settings', model=PlanningSettings)

    async def export(self, as_: Any) -> ExportPart:
        return await self.request(as_, 'GET', '/internal/export', model=ExportPart)

    async def patch_settings(self, as_: Any, body: Body) -> PlanningSettings:
        return await self.request(as_, 'PATCH', '/internal/settings', body=body, model=PlanningSettings)


class RecurringClient(ServiceClient):
    def __init__(self, o: ClientOptions) -> None:
        super().__init__(o, 'recurring')

    async def list(self, as_: Any) -> RecurringRes:
        return await self.request(as_, 'GET', '/recurring', model=RecurringRes)

    async def export(self, as_: Any) -> ExportPart:
        return await self.request(as_, 'GET', '/internal/export', model=ExportPart)


class IngestClient(ServiceClient):
    def __init__(self, o: ClientOptions) -> None:
        super().__init__(o, 'ingest')

    async def unparsed_count(self, as_: Any) -> UnparsedCountRes:
        return await self.request(as_, 'GET', '/internal/unparsed/count', model=UnparsedCountRes)

    async def export(self, as_: Any) -> ExportPart:
        return await self.request(as_, 'GET', '/internal/export', model=ExportPart)


class TelegramClient(ServiceClient):
    def __init__(self, o: ClientOptions) -> None:
        super().__init__(o, 'telegram')

    async def settings(self, as_: Any) -> TelegramSettings:
        return await self.request(as_, 'GET', '/internal/settings', model=TelegramSettings)

    async def export(self, as_: Any) -> ExportPart:
        return await self.request(as_, 'GET', '/internal/export', model=ExportPart)

    async def patch_settings(self, as_: Any, body: Body) -> TelegramSettings:
        return await self.request(as_, 'PATCH', '/internal/settings', body=body, model=TelegramSettings)


class ClientEnv(Protocol):
    """The part of `lbstash.common.BaseEnv` the clients read."""

    INTERNAL_SECRET: str
    AUTH_URL: str
    TRANSACTIONS_URL: str
    INGEST_URL: str
    PLANNING_URL: str
    RECURRING_URL: str
    TELEGRAM_URL: str


@dataclass(slots=True)
class Clients:
    transactions: TransactionsClient
    auth: AuthClient
    planning: PlanningClient
    recurring: RecurringClient
    ingest: IngestClient
    telegram: TelegramClient

    def _all(self) -> list[ServiceClient]:
        return [self.transactions, self.auth, self.planning, self.recurring, self.ingest, self.telegram]

    async def close(self) -> None:
        """Release every connection pool."""
        for c in self._all():
            await c.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()


def create_clients(from_service: str, env: ClientEnv, **extra: Any) -> Clients:
    """All clients for one calling service (`deps.clients`). `extra` are `ClientOptions` fields."""

    def o(base_url: str) -> ClientOptions:
        return ClientOptions(from_service=from_service, base_url=base_url, secret=env.INTERNAL_SECRET, **extra)

    return Clients(
        transactions=TransactionsClient(o(env.TRANSACTIONS_URL)),
        auth=AuthClient(o(env.AUTH_URL)),
        planning=PlanningClient(o(env.PLANNING_URL)),
        recurring=RecurringClient(o(env.RECURRING_URL)),
        ingest=IngestClient(o(env.INGEST_URL)),
        telegram=TelegramClient(o(env.TELEGRAM_URL)),
    )


__all__ = [
    'AuthClient',
    'CallAs',
    'ClientEnv',
    'Clients',
    'IngestClient',
    'PlanningClient',
    'RecurringClient',
    'TelegramClient',
    'TransactionsClient',
    'create_clients',
]
