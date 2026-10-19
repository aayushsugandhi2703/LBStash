import re
import uuid

from bt.contracts import BudgetEvaluateJob, RetentionSweepJob, sweep_queue
from bt.queue.memory import RecordedJob
from bt_planning.evaluate import evaluate_budget
from planning_harness import Harness, now


def rs(n: int) -> int:
    return n * 100


class TestInternalSettings:
    u = str(uuid.uuid4())

    async def test_defaults_to_80_with_the_pace_warning_on_patches_partially_validates(self, h: Harness) -> None:
        u = self.u

        async def call(method: str, payload: object = None, user: str | None = u):
            return await h.internal(user, method, '/internal/settings', payload)

        assert (await call('GET')).json() == {'alertLevel': 80, 'warnOnPace': True}
        assert (await call('PATCH', {'alertLevel': 90})).json() == {'alertLevel': 90, 'warnOnPace': True}
        assert (await call('PATCH', {'warnOnPace': False})).json() == {'alertLevel': 90, 'warnOnPace': False}
        assert (await call('PATCH', {})).json() == {'alertLevel': 90, 'warnOnPace': False}
        assert (await call('PATCH', {'alertLevel': 85})).status_code == 400
        assert (await call('PATCH', {'warnOnPace': 'yes'})).status_code == 400
        # another user is unaffected
        assert (await call('GET', user=str(uuid.uuid4()))).json() == {'alertLevel': 80, 'warnOnPace': True}

    async def test_needs_a_user_and_refuses_calls_forwarded_from_outside(self, h: Harness) -> None:
        assert (await h.internal(None, 'GET', '/internal/settings')).status_code == 401
        proxied = await h.internal(self.u, 'GET', '/internal/settings', proxied=True)
        assert proxied.status_code == 403


class TestExportAccountDeletionRetention:
    u, other = str(uuid.uuid4()), str(uuid.uuid4())
    budget_id = ''

    async def seed(self, h: Harness) -> None:
        for who in (self.u, self.other):
            h.ledger.set_spend('2026-10', 'food', rs(900))
            await h.send(
                who,
                'PUT',
                '/plans/2026-10',
                {'totalMinor': rs(100), 'lines': [{'tag': 'food', 'allocatedMinor': rs(40)}]},
            )
            b = (await h.send(who, 'POST', '/budgets', {'tag': 'food', 'limitMinor': rs(1000)})).json()
            if who == self.u:
                type(self).budget_id = b['id']
            await evaluate_budget(
                h.deps, BudgetEvaluateJob(user_id=who, category_id=b['categoryId'], period_key='2026-10'), now
            )
            await h.internal(
                who,
                'POST',
                '/internal/plans/2026-10/credit',
                {'transactionId': str(uuid.uuid4()), 'amountMinor': 5},
                svc='ledger',
            )

    async def test_export_carries_only_the_callers_rows_in_every_table(self, h: Harness) -> None:
        await self.seed(h)
        r = await h.internal(self.u, 'GET', '/internal/export')
        assert r.status_code == 200
        body = r.json()
        tables = body['tables']
        assert body['service'] == 'planning'
        assert sorted(tables) == ['alerts', 'budgets', 'plan_credits', 'plan_lines', 'plans', 'settings']
        for name in ('plans', 'plan_lines', 'budgets', 'alerts', 'plan_credits'):
            assert len(tables[name]) == 1, name
        assert tables['budgets'][0]['id'] == self.budget_id
        assert all(p['user_id'] == self.u for p in tables['plans'])

    async def test_export_timestamps_are_iso_with_milliseconds(self, h: Harness) -> None:
        tables = (await h.internal(self.u, 'GET', '/internal/export')).json()['tables']
        assert re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', tables['alerts'][0]['sent_at'])
        assert re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z', tables['plans'][0]['created_at'])

    async def test_account_deleted_purges_the_user_and_nobody_else(self, h: Harness) -> None:
        await h.bus.emit(h.db.pool, 'account.deleted', {'userId': self.u})
        await h.bus.drain()
        t = (await h.internal(self.u, 'GET', '/internal/export')).json()['tables']
        for k in ('alerts', 'budgets', 'plan_credits', 'plan_lines', 'plans', 'settings'):
            assert t[k] == [], k
        assert (await h.get(self.u, '/budgets')).json()['items'] == []
        o = (await h.internal(self.other, 'GET', '/internal/export')).json()['tables']
        assert len(o['budgets']) == 1
        assert len(o['alerts']) == 1
        assert len(o['plan_lines']) == 1

    async def test_the_nightly_sweep_is_scheduled_and_drops_alerts_older_than_12_months_keeping_recent_ones(
        self, h: Harness
    ) -> None:
        other = self.other
        assert any(s.queue == sweep_queue('planning') for s in h.bus.schedules)
        await h.db.admin_pool.execute(
            "UPDATE planning.alerts SET sent_at = now() - interval '13 months' WHERE user_id = $1", [other]
        )
        keep = (await h.send(other, 'POST', '/budgets', {'tag': 'fun', 'limitMinor': rs(10)})).json()
        h.ledger.set_spend('2026-10', 'fun', rs(10))
        await evaluate_budget(
            h.deps, BudgetEvaluateJob(user_id=other, category_id=keep['categoryId'], period_key='2026-10'), now
        )
        assert len((await h.get(other, '/alerts')).json()['items']) == 2
        h.bus.jobs.append(RecordedJob('retention.sweep', sweep_queue('planning'), RetentionSweepJob()))
        await h.bus.drain()
        left = (await h.get(other, '/alerts')).json()['items']
        assert len(left) == 1
        assert left[0]['categoryName'] == 'fun'
