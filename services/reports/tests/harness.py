"""The ui-spec dataset (01 Now, 05 Repeats, 06 Trends) behind fake clients that record who every call was made for.

All money is the spec's rupees x 100 (paise).
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from bt.common import AppError, months_ending_at
from bt.contracts import (
    AlertsRes,
    BudgetsRes,
    CategoryMonthsRes,
    DailyRes,
    MonthsRes,
    MonthSummaryRes,
    PlanWithSpendDto,
    RecurringRes,
    SpendByCategoryRes,
    UnparsedCountRes,
)
from bt.kit.testing import AppHarness, build_test_app
from bt_reports.routes import make_register


def R(rupees: int) -> int:
    return rupees * 100


NOW = datetime.fromisoformat('2026-10-18T10:00:00+05:30')  # day 18 of 31


def clock() -> datetime:
    return NOW


def uid() -> str:
    return str(uuid.uuid4())


ID = {k: uid() for k in ('rent', 'sip', 'food', 'fun', 'travel', 'bills')}
NAME = {v: k for k, v in ID.items()}

# spec data
MONTHS = [
    {'month': '2026-05', 'income': 50000, 'spent': 41200, 'closing': 6400},
    {'month': '2026-06', 'income': 50000, 'spent': 44800, 'closing': 11600},
    {'month': '2026-07', 'income': 52000, 'spent': 47300, 'closing': 16300},
    {'month': '2026-08', 'income': 50000, 'spent': 43100, 'closing': 23200},
    {'month': '2026-09', 'income': 50000, 'spent': 45900, 'closing': 27300},
    {'month': '2026-10', 'income': 50000, 'spent': 39709, 'closing': 37591},
]
# flexible categories per month (May..Oct), chosen so each month sums to out - 30,000 and the "usual" figures are the spec's
FLEX = {
    ID['food']: [6000, 7800, 9200, 7400, 7550, 5420],  # usual 7,590
    ID['fun']: [1200, 1500, 1900, 1300, 1250, 1640],  # usual 1,430
    ID['bills']: [2400, 2500, 2600, 2500, 2500, 1299],  # usual 2,500
    ID['travel']: [1600, 3000, 3600, 1900, 4600, 1350],  # usual 2,940
}
CAT_MONTHS: list[dict[str, Any]] = []
for _i, _m in enumerate(MONTHS):
    CAT_MONTHS.append({'month': _m['month'], 'categoryId': ID['rent'], 'categoryName': 'rent', 'spentMinor': R(20000)})
    CAT_MONTHS.append({'month': _m['month'], 'categoryId': ID['sip'], 'categoryName': 'sip', 'spentMinor': R(10000)})
    for _cid, _v in FLEX.items():
        CAT_MONTHS.append({'month': _m['month'], 'categoryId': _cid, 'categoryName': NAME[_cid], 'spentMinor': R(_v[_i])})
DAILY = [240, 370, 340, 530, 420, 350, 850, 380, 910, 620, 970, 440, 730, 480, 570, 740, 380, 389]


def rule(n: str, cat: str, amount: int, day: int, due: str, **extra: Any) -> dict[str, Any]:
    return {
        'id': uid(), 'name': n, 'categoryId': cat, 'categoryName': NAME[cat], 'amountMinor': R(amount),
        'schedule': {'kind': 'monthly', 'day': day}, 'nextDue': due, 'paused': False, 'endsOn': None, 'note': None,
        'matchHint': None, 'active': True, **extra,
    }  # fmt: skip


def rules() -> list[dict[str, Any]]:
    return [
        rule('Rent', ID['rent'], 20000, 1, '2026-11-01'),
        rule('Nifty 50 index fund', ID['sip'], 10000, 5, '2026-11-05'),
        rule('Cloud storage', ID['bills'], 130, 12, '2026-11-12'),
        rule('Netflix', ID['fun'], 649, 17, '2026-11-17'),
    ]


def rent_paused() -> list[dict[str, Any]]:
    return [{**r, 'paused': True, 'active': False} if r['name'] == 'Rent' else r for r in rules()]


@dataclass
class Call:
    client: str
    method: str
    as_: Any
    args: tuple[Any, ...]


@dataclass
class Fakes:
    """Hand-written stand-ins for the four neighbours. `failing` names the clients (or `client.method`) that answer 502."""

    rules: Any = rules
    failing: tuple[str, ...] = ()
    empty: bool = False
    # Category x month rows the ledger answers with (the spec's by default).
    cat_months: list[dict[str, Any]] | None = None
    # Seconds every call takes: lets a test see how many are in flight at once (`peak`).
    delay: float = 0
    calls: list[Call] = field(default_factory=list)
    in_flight: int = 0
    peak: int = 0

    def clients(self) -> dict[str, Any]:
        return {n: _Fake(self, n) for n in ('ledger', 'planning', 'recurring', 'ingest')}


class _Fake:
    def __init__(self, fakes: Fakes, client: str) -> None:
        self._f = fakes
        self._client = client

    def __getattr__(self, method: str) -> Any:
        impl = getattr(_IMPL, f'{self._client}_{method}')

        async def call(as_: Any, *args: Any) -> Any:
            f = self._f
            f.calls.append(Call(self._client, method, as_, args))
            f.in_flight += 1
            f.peak = max(f.peak, f.in_flight)
            try:
                await asyncio.sleep(f.delay)
            finally:
                f.in_flight -= 1
            if self._client in self._f.failing or f'{self._client}.{method}' in self._f.failing:
                raise AppError('upstream_failed', f'{self._client} down')
            return impl(self._f, as_, *args)

        return call


class _IMPL:
    @staticmethod
    def ledger_month_summary(f: Fakes, _as: Any, month: str) -> MonthSummaryRes:
        if f.empty:
            return MonthSummaryRes.model_validate({
                'month': '2026-10', 'carriedOverMinor': 0, 'incomeMinor': 0, 'spentMinor': 0, 'availableMinor': 0,
                'untaggedCount': 0, 'unaccountedCount': 0, 'lastCapturedAt': None,
            })  # fmt: skip
        return MonthSummaryRes.model_validate({
            'month': '2026-10', 'carriedOverMinor': R(27300), 'incomeMinor': R(50000), 'spentMinor': R(39709),
            'availableMinor': R(37591), 'untaggedCount': 1, 'unaccountedCount': 0,
            'lastCapturedAt': '2026-10-18T07:12:00+05:30',
        })  # fmt: skip

    @staticmethod
    def ledger_spend_by_category(f: Fakes, _as: Any, _from: Any, _to: Any) -> SpendByCategoryRes:
        spend = [('bills', 1299), ('fun', 1640), ('rent', 20000), ('travel', 1350), ('food', 5420), ('sip', 10000)]
        return SpendByCategoryRes.model_validate({
            'items': [] if f.empty else [{'categoryId': ID[n], 'categoryName': n, 'spentMinor': R(v)} for n, v in spend]
        })  # fmt: skip

    @staticmethod
    def ledger_months(f: Fakes, _as: Any, end: str, count: int) -> MonthsRes:
        keys = months_ending_at(end, count)
        return MonthsRes.model_validate({
            'items': [] if f.empty else [
                {'month': m['month'], 'incomeMinor': R(m['income']), 'spentMinor': R(m['spent']), 'closingMinor': R(m['closing'])}
                for m in MONTHS if m['month'] in keys
            ]
        })  # fmt: skip

    @staticmethod
    def ledger_category_months(f: Fakes, _as: Any, end: str, count: int) -> CategoryMonthsRes:
        keys = months_ending_at(end, count)
        rows = CAT_MONTHS if f.cat_months is None else f.cat_months
        return CategoryMonthsRes.model_validate({'items': [] if f.empty else [c for c in rows if c['month'] in keys]})

    @staticmethod
    def ledger_daily(f: Fakes, _as: Any, _month: str, _exclude: Any = ()) -> DailyRes:
        return DailyRes.model_validate({
            'items': [] if f.empty else [{'day': f'2026-10-{i + 1:02d}', 'spentMinor': R(v)} for i, v in enumerate(DAILY)]
        })  # fmt: skip

    @staticmethod
    def planning_plan(f: Fakes, _as: Any, month: str) -> PlanWithSpendDto:
        lines = [
            ('rent', 20000, 20000), ('sip', 10000, 10000), ('food', 7000, 5420),
            ('fun', 2000, 1640), ('travel', 3500, 1350), ('bills', 3000, 1299),
        ]  # fmt: skip
        return PlanWithSpendDto.model_validate({
            'month': month, 'totalMinor': R(50000), 'assignedMinor': R(45500), 'unassignedMinor': R(4500),
            'lines': [] if f.empty else [
                {'categoryId': ID[n], 'categoryName': n, 'allocatedMinor': R(a), 'spentMinor': R(s)} for n, a, s in lines
            ],
        })  # fmt: skip

    @staticmethod
    def planning_budgets(f: Fakes, _as: Any, month: str) -> BudgetsRes:
        def b(cat: str, limit: int, active: bool, spent: int, pct: int, projected: int, status: str) -> dict[str, Any]:
            return {
                'id': uid(), 'categoryId': ID[cat], 'categoryName': cat, 'limitMinor': R(limit), 'period': 'monthly',
                'warnPct': None, 'active': active, 'spentMinor': R(spent), 'pct': pct, 'projectedMinor': R(projected),
                'status': status,
            }  # fmt: skip

        items = [
            b('food', 9000, True, 5420, 60, 9330, 'fast'),
            b('fun', 2000, True, 1640, 82, 2820, 'close'),
            b('bills', 1300, False, 1299, 99, 2240, 'close'),
        ]
        return BudgetsRes.model_validate({'month': month, 'alertLevel': 80, 'items': [] if f.empty else items})

    @staticmethod
    def planning_alerts(f: Fakes, _as: Any) -> AlertsRes:
        return AlertsRes.model_validate({'unreadCount': 0 if f.empty else 1, 'items': []})

    @staticmethod
    def recurring_list(f: Fakes, _as: Any) -> RecurringRes:
        items = [] if f.empty else f.rules()
        committed = sum(r['amountMinor'] for r in items if r['active'])
        return RecurringRes.model_validate({'items': items, 'committedMinor': committed})

    @staticmethod
    def ingest_unparsed_count(f: Fakes, _as: Any) -> UnparsedCountRes:
        return UnparsedCountRes.model_validate({'open': 0 if f.empty else 2})


async def setup(fakes: Fakes | None = None, *, clk: Any = clock) -> tuple[AppHarness, Fakes]:
    fakes = fakes or Fakes()
    app = await build_test_app(service='reports', register=make_register(clk), clients=fakes.clients())
    return app, fakes


def get(app: AppHarness, user_id: str | None, url: str, tz: str = 'Asia/Kolkata'):
    headers = AppHarness.headers_for(user_id, 'gateway', tz)
    return app.client.get(url, headers=headers)

