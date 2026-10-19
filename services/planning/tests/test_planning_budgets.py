import uuid

import pytest
import pytest_asyncio
from bt.contracts import BudgetEvaluateJob
from bt_planning.evaluate import evaluate_budget
from planning_harness import Harness, clock, now

OCT = '2026-10'


def rs(n: int) -> int:
    return n * 100


@pytest.fixture(autouse=True)
def _fresh_clock(h: Harness) -> None:
    clock.reset()
    h.bus.clear()


async def sample(h: Harness, u: str) -> dict[str, str]:
    """The docs/ui-spec/04-limits October sample, day 18 of 31."""
    ids: dict[str, str] = {}
    for name, spent, limit in [
        ('fun', 1640, 2000),
        ('food', 5420, 8000),
        ('bills', 1299, 2500),
        ('travel', 1350, 3000),
    ]:
        h.ledger.set_spend(OCT, name, rs(spent))
        r = await h.send(u, 'POST', '/budgets', {'tag': name, 'limitMinor': rs(limit)})
        assert r.status_code == 201
        ids[name] = r.json()['id']
    return ids


def by_name(items: list[dict], name: str) -> dict:
    return next(i for i in items if i['categoryName'] == name)


def subset(actual: dict, expected: dict) -> None:
    assert {k: actual[k] for k in expected} == expected


LIMITS_USER = str(uuid.uuid4())


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def ids(h: Harness) -> dict[str, str]:
    return await sample(h, LIMITS_USER)


class TestGetBudgetsTheLimitsPageFigures:
    u = LIMITS_USER

    async def test_october_sample_at_level_80_order_pct_projection_nearest_10_and_status(
        self, h: Harness, ids: dict
    ) -> None:
        r = await h.get(self.u, f'/budgets?month={OCT}')
        assert r.status_code == 200
        b = r.json()
        assert b['month'] == OCT
        assert b['alertLevel'] == 80
        assert [i['categoryName'] for i in b['items']] == ['fun', 'food', 'bills', 'travel']
        items = b['items']
        subset(by_name(items, 'fun'), {'id': ids['fun'], 'spentMinor': rs(1640), 'limitMinor': rs(2000), 'pct': 82, 'projectedMinor': rs(2820), 'status': 'close', 'period': 'monthly', 'active': True, 'warnPct': None})  # fmt: skip
        # spec shows 68 (rounded); pct_of floors 67.75
        subset(by_name(items, 'food'), {'pct': 67, 'projectedMinor': rs(9330), 'status': 'fast'})
        # spec rounds 51.96 to 52; pct_of floors so 99.9 never reads 100
        subset(by_name(items, 'bills'), {'pct': 51, 'projectedMinor': rs(2240), 'status': 'ok'})
        subset(by_name(items, 'travel'), {'pct': 45, 'projectedMinor': rs(2330), 'status': 'ok'})

    async def test_defaults_to_the_current_month_and_reads_the_month_in_the_users_zone(
        self, h: Harness, ids: dict
    ) -> None:
        r = await h.get(self.u, '/budgets')
        assert r.json()['month'] == OCT
        assert h.ledger.last_range == {'from': '2026-09-30T18:30:00.000Z', 'to': '2026-10-31T18:30:00.000Z'}

    async def test_a_past_month_is_projected_over_its_full_length_a_future_month_has_no_pace(
        self, h: Harness, ids: dict
    ) -> None:
        h.ledger.set_spend('2026-09', 'fun', rs(900))
        past = by_name((await h.get(self.u, '/budgets?month=2026-09')).json()['items'], 'fun')
        # 30 of 30 days: projection = spend
        subset(past, {'spentMinor': rs(900), 'projectedMinor': rs(900), 'status': 'ok'})
        future = by_name((await h.get(self.u, '/budgets?month=2026-12')).json()['items'], 'fun')
        subset(future, {'spentMinor': 0, 'projectedMinor': 0, 'status': 'ok'})

    async def test_level_90_turns_fun_into_spending_fast_level_70_leaves_food_67_75_fast_and_moves_the_level(
        self, h: Harness, ids: dict
    ) -> None:
        u = self.u

        async def set_level(level: int):
            return await h.internal(u, 'PATCH', '/internal/settings', {'alertLevel': level}, svc='ledger')

        assert (await set_level(90)).json() == {'alertLevel': 90, 'warnOnPace': True}
        items = (await h.get(u, '/budgets')).json()
        assert items['alertLevel'] == 90
        assert by_name(items['items'], 'fun')['status'] == 'fast'
        await set_level(70)
        items = (await h.get(u, '/budgets')).json()
        assert by_name(items['items'], 'food')['status'] == 'fast'
        assert by_name(items['items'], 'fun')['status'] == 'close'
        await set_level(80)

    async def test_warn_if_pace_runs_over_off_hides_spending_fast_but_keeps_the_projection(
        self, h: Harness, ids: dict
    ) -> None:
        u = self.u
        await h.internal(u, 'PATCH', '/internal/settings', {'warnOnPace': False}, svc='ledger')
        food = by_name((await h.get(u, '/budgets')).json()['items'], 'food')
        subset(food, {'status': 'ok', 'projectedMinor': rs(9330)})
        await h.internal(u, 'PATCH', '/internal/settings', {'warnOnPace': True}, svc='ledger')

    async def test_a_per_limit_warn_percentage_overrides_the_user_level(self, h: Harness, ids: dict) -> None:
        u = self.u
        r = await h.send(u, 'PATCH', f'/budgets/{ids["fun"]}', {'warnPct': 90})
        subset(r.json(), {'warnPct': 90, 'status': 'fast'})
        cleared = await h.send(u, 'PATCH', f'/budgets/{ids["fun"]}', {'warnPct': None})
        subset(cleared.json(), {'warnPct': None, 'status': 'close'})

    async def test_status_boundaries_exactly_at_the_alert_level_is_close_one_paisa_under_is_not_exactly_100_is_over(
        self, h: Harness, ids: dict
    ) -> None:
        u = self.u
        id_ = (await h.send(u, 'POST', '/budgets', {'tag': 'edge', 'limitMinor': rs(1000)})).json()['id']

        async def status() -> dict:
            return next(i for i in (await h.get(u, '/budgets')).json()['items'] if i['id'] == id_)

        for spent, pct, st in [
            (rs(800) - 1, 79, 'fast'), (rs(800), 80, 'close'), (rs(1000) - 1, 99, 'close'), (rs(1000), 100, 'over'), (rs(1200), 120, 'over'),
        ]:  # fmt: skip
            h.ledger.set_spend(OCT, 'edge', spent)
            subset(await status(), {'pct': pct, 'status': st})


class TestPostPatchDeleteBudgets:
    u = str(uuid.uuid4())

    async def test_creates_by_tag_new_category_by_id_rejects_a_second_limit_for_the_same_category(
        self, h: Harness
    ) -> None:
        u = self.u
        before = h.ledger.calls['resolve']
        r = await h.send(u, 'POST', '/budgets', {'tag': '#Gym', 'limitMinor': rs(1000)})
        assert r.status_code == 201
        subset(r.json(), {'categoryName': 'gym', 'limitMinor': rs(1000), 'spentMinor': 0, 'pct': 0, 'status': 'ok'})
        assert h.ledger.calls['resolve'] == before + 1
        by_id = await h.send(u, 'POST', '/budgets', {'categoryId': h.ledger.cat('pets'), 'limitMinor': rs(500)})
        assert by_id.status_code == 201
        dup = await h.send(u, 'POST', '/budgets', {'tag': 'gym', 'limitMinor': rs(2000)})
        assert dup.status_code == 409
        assert dup.json()['error']['code'] == 'conflict'

    async def test_creating_a_limit_queues_one_evaluation_for_the_current_period(self, h: Harness) -> None:
        u = self.u
        h.bus.clear()
        await h.send(u, 'POST', '/budgets', {'tag': 'books', 'limitMinor': rs(300)})
        cat = h.ledger.cat('books')
        assert len(h.bus.jobs) == 1
        job = h.bus.jobs[0]
        assert (job.job, job.queue, job.key) == ('budget.evaluate', 'budget.evaluate', f'{u}:{cat}:{OCT}')
        assert (job.payload.user_id, job.payload.category_id, job.payload.period_key) == (u, cat, OCT)

    async def test_use_this_months_allocation_as_the_limit_takes_the_plan_line_no_allocation_is_a_422(
        self, h: Harness
    ) -> None:
        u = self.u
        cat = h.ledger.cat('rent')
        await h.send(
            u,
            'PUT',
            f'/plans/{OCT}',
            {
                'totalMinor': rs(50000),
                'lines': [{'categoryId': cat, 'allocatedMinor': rs(20000)}, {'tag': 'zero', 'allocatedMinor': 0}],
            },
        )
        r = await h.send(u, 'POST', '/budgets', {'categoryId': cat, 'useMonthAllocation': True})
        assert r.status_code == 201
        assert r.json()['limitMinor'] == rs(20000)
        none = await h.send(u, 'POST', '/budgets', {'tag': 'nothing planned', 'useMonthAllocation': True})
        assert none.status_code == 422
        zero = await h.send(u, 'POST', '/budgets', {'tag': 'zero', 'useMonthAllocation': True})
        assert zero.status_code == 422
        # patch can re-point a limit at the allocation too
        bills = (await h.send(u, 'POST', '/budgets', {'tag': 'rent2', 'limitMinor': 100})).json()
        assert bills['limitMinor'] == 100
        rent_budget = r.json()['id']
        await h.send(
            u,
            'PUT',
            f'/plans/{OCT}',
            {'totalMinor': rs(50000), 'lines': [{'categoryId': cat, 'allocatedMinor': rs(22000)}]},
        )
        assert (await h.send(u, 'PATCH', f'/budgets/{rent_budget}', {'useMonthAllocation': True})).json()[
            'limitMinor'
        ] == rs(22000)

    async def test_patch_changes_the_limit_deactivates_and_reactivates_delete_removes_it(self, h: Harness) -> None:
        u = self.u
        b = (await h.send(u, 'POST', '/budgets', {'tag': 'toys', 'limitMinor': rs(100)})).json()
        assert (await h.send(u, 'PATCH', f'/budgets/{b["id"]}', {'limitMinor': rs(250)})).json()['limitMinor'] == rs(
            250
        )
        assert (await h.send(u, 'PATCH', f'/budgets/{b["id"]}', {'active': False})).json()['active'] is False
        # an inactive limit does not block creating the category's limit again: it comes back with the new numbers
        again = await h.send(u, 'POST', '/budgets', {'tag': 'toys', 'limitMinor': rs(400)})
        assert again.status_code == 201
        subset(again.json(), {'id': b['id'], 'limitMinor': rs(400), 'active': True})
        assert (await h.send(u, 'DELETE', f'/budgets/{b["id"]}')).json() == {'ok': True}
        assert (await h.send(u, 'DELETE', f'/budgets/{b["id"]}')).status_code == 404
        assert (await h.send(u, 'PATCH', f'/budgets/{b["id"]}', {'limitMinor': 5})).status_code == 404

    async def test_validation(self, h: Harness) -> None:
        u = self.u
        c = h.ledger.cat('food')

        async def bad(p: dict) -> int:
            return (await h.send(u, 'POST', '/budgets', p)).status_code

        assert await bad({'tag': 'x', 'limitMinor': 0}) == 400
        assert await bad({'tag': 'x', 'limitMinor': -5}) == 400
        assert await bad({'tag': 'x', 'limitMinor': 1.5}) == 400
        assert await bad({'tag': 'x'}) == 400  # no limit
        assert await bad({'limitMinor': 100}) == 400  # no category
        assert await bad({'tag': 'x', 'categoryId': c, 'limitMinor': 100}) == 400
        assert await bad({'tag': 'x', 'limitMinor': 100, 'period': 'weekly'}) == 400
        assert await bad({'tag': 'x', 'limitMinor': 100, 'warnPct': 49}) == 400
        assert await bad({'tag': 'x', 'limitMinor': 100, 'warnPct': 100}) == 400
        assert await bad({'categoryId': str(uuid.uuid4()), 'limitMinor': 100}) == 400  # unknown category
        assert await bad({'tag': '   ', 'limitMinor': 100}) == 400
        assert (await h.send(u, 'PATCH', f'/budgets/{uuid.uuid4()}', {})).status_code == 400
        assert (await h.send(u, 'PATCH', '/budgets/not-a-uuid', {'limitMinor': 5})).status_code == 400
        assert (await h.get(u, '/budgets?month=2026-1')).status_code == 400


class TestOwnership:
    a, b = str(uuid.uuid4()), str(uuid.uuid4())

    async def test_user_b_cannot_list_change_delete_or_see_alerts_of_user_a(self, h: Harness) -> None:
        a, b = self.a, self.b
        h.ledger.set_spend(OCT, 'secret', rs(900))
        made = (await h.send(a, 'POST', '/budgets', {'tag': 'secret', 'limitMinor': rs(1000)})).json()
        await evaluate_budget(h.deps, BudgetEvaluateJob(user_id=a, category_id=made['categoryId'], period_key=OCT), now)
        assert len((await h.get(a, '/alerts')).json()['items']) == 1
        alert_id = (await h.get(a, '/alerts')).json()['items'][0]['id']

        assert (await h.get(b, '/budgets')).json()['items'] == []
        assert (await h.send(b, 'PATCH', f'/budgets/{made["id"]}', {'limitMinor': 1})).status_code == 404
        assert (await h.send(b, 'DELETE', f'/budgets/{made["id"]}')).status_code == 404
        assert (await h.get(b, '/alerts')).json() == {'unreadCount': 0, 'items': []}
        assert (await h.send(b, 'POST', f'/alerts/{alert_id}/read')).status_code == 404
        # B has the same category id but no limit of their own: nothing to evaluate for them
        job = BudgetEvaluateJob(user_id=b, category_id=made['categoryId'], period_key=OCT)
        assert await evaluate_budget(h.deps, job, now) == 'skipped'
        # A is untouched
        assert len((await h.get(a, '/budgets')).json()['items']) == 1
        assert (await h.get(a, '/alerts')).json()['unreadCount'] == 1
