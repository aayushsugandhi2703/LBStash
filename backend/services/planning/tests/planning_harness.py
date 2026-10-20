"""Planning test harness: the app over a real (RLS-enforced) database, workers on an in-memory bus, fake transactions and auth. Named `planning_harness` so several services' tests never import the wrong one."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import httpx
from lbstash.common import month_key
from lbstash.contracts import CategoriesRes, CategoryDto, ResolveCategoryRes, SpendByCategoryItem, SpendByCategoryRes
from lbstash.db.testing import TempDatabase
from lbstash.kit.testing import AppHarness, build_test_app, headers_for
from lbstash_planning.routes import routes_with
from lbstash_planning.workers import start_workers

TZ = 'Asia/Kolkata'


class FrozenClock:
    """A controllable "now": October 18th 2026, 12:00 in Kolkata = day 18 of 31, the Limits sample."""

    START = datetime(2026, 10, 18, 6, 30, tzinfo=UTC)

    def __init__(self) -> None:
        self.at = self.START

    def reset(self) -> None:
        self.at = self.START

    def __call__(self) -> datetime:
        return self.at


clock = FrozenClock()
now = clock


class FakeTransactions:
    """The slice of the transactions planning talks to: categories, spend per category per month, resolve-by-tag."""

    def __init__(self) -> None:
        self.cats: dict[str, str] = {}
        # month -> category id -> paise
        self.spend: dict[str, dict[str, int]] = {}
        self.calls = {'spend': 0, 'categories': 0, 'resolve': 0}
        self.last_range: dict[str, str] | None = None

    def cat(self, name: str) -> str:
        for id_, n in self.cats.items():
            if n == name:
                return id_
        id_ = str(uuid.uuid4())
        self.cats[id_] = name
        return id_

    def set_spend(self, month: str, name: str, paise: int) -> None:
        self.spend.setdefault(month, {})[self.cat(name)] = paise

    async def categories(self, as_: Any, **_: Any) -> CategoriesRes:
        self.calls['categories'] += 1
        return CategoriesRes(items=[CategoryDto(id=id_, name=name, archived=False) for id_, name in self.cats.items()])

    async def resolve_category(self, as_: Any, tag: str) -> ResolveCategoryRes:
        self.calls['resolve'] += 1
        existed = tag in self.cats.values()
        id_ = self.cat(tag)
        return ResolveCategoryRes(category=CategoryDto(id=id_, name=tag, archived=False), created=not existed)

    async def spend_by_category(self, as_: Any, from_: str, to: str) -> SpendByCategoryRes:
        self.calls['spend'] += 1
        self.last_range = {'from': from_, 'to': to}
        # an hour past the start of the range is inside the month the range names
        inside = datetime.fromisoformat(from_).timestamp() + 3600
        m = self.spend.get(month_key(datetime.fromtimestamp(inside, UTC), TZ), {})
        return SpendByCategoryRes(
            items=[
                SpendByCategoryItem(category_id=cid, category_name=self.cats.get(cid), spent_minor=spent)
                for cid, spent in m.items()
            ]
        )


class FakeAuth:
    def __init__(self) -> None:
        self.calls = 0

    async def me(self, as_: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(user=SimpleNamespace(id=as_.user_id, timezone=TZ))


class Harness:
    def __init__(self, db: TempDatabase, transactions: FakeTransactions, auth: FakeAuth, app: AppHarness) -> None:
        self.db = db
        self.transactions = transactions
        self.auth = auth
        self.app = app
        self.deps = app.deps
        self.bus = app.bus
        self.client: httpx.AsyncClient = app.client

    async def close(self) -> None:
        await self.app.close()

    @staticmethod
    def as_(user_id: str | None, svc: str = 'gateway', proxied: bool = False) -> dict[str, str]:
        return headers_for(user_id, svc, TZ, proxied)

    async def get(self, user_id: str | None, url: str) -> httpx.Response:
        return await self.client.get(url, headers=self.as_(user_id))

    async def send(self, user_id: str | None, method: str, url: str, payload: Any = None) -> httpx.Response:
        return await self.client.request(method, url, headers=self.as_(user_id), json=payload)

    async def internal(
        self,
        user_id: str | None,
        method: str,
        url: str,
        payload: Any = None,
        svc: str = 'gateway',
        proxied: bool = False,
    ) -> httpx.Response:
        return await self.client.request(method, url, headers=self.as_(user_id, svc, proxied), json=payload)

    async def deliver_events(self, name: str) -> None:
        """Hand recorded events called `name` to their handlers without running the jobs they queue, so a test sees exactly what the handler enqueued (`drain()` would run those jobs too)."""
        handlers = self.bus._event_handlers[name]
        events = [e for e in self.bus.events if e.event == name]
        self.bus.events[:] = [e for e in self.bus.events if e.event != name]
        for e in events:
            for fn in handlers:
                await fn(e.payload)


async def make_harness(db: TempDatabase) -> Harness:
    transactions, auth = FakeTransactions(), FakeAuth()
    app = await build_test_app(
        service='planning', register=routes_with(now), pool=db.pool, clients={'transactions': transactions, 'auth': auth}
    )
    await start_workers(app.deps, now)
    return Harness(db, transactions, auth, app)
