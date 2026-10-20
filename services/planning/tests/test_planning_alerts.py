import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from lbstash.contracts import BudgetEvaluateJob
from lbstash_planning.evaluate import evaluate_budget
from planning_harness import Harness, clock, now

OCT, NOV = '2026-10', '2026-11'


def rs(n: int) -> int:
    return n * 100


@pytest.fixture(autouse=True)
def _fresh_clock(h: Harness) -> None:
    clock.reset()
    h.bus.clear()


async def limit(h: Harness, u: str, tag: str, limit_rs: int) -> tuple[str, str]:
    """Create a limit; returns (budget id, category id)."""
    r = await h.send(u, 'POST', '/budgets', {'tag': tag, 'limitMinor': rs(limit_rs)})
    assert r.status_code == 201
    return r.json()['id'], r.json()['categoryId']


async def evaluate(h: Harness, u: str, category_id: str, period_key: str = OCT) -> str:
    return await evaluate_budget(
        h.deps, BudgetEvaluateJob(user_id=u, category_id=category_id, period_key=period_key), now
    )


async def alerts_of(h: Harness, u: str) -> dict:
    return (await h.get(u, '/alerts')).json()


def levels(h: Harness) -> list[str]:
    return [e.level for e in h.bus.events_of('alert.created')]


class TestBudgetEvaluate:
    async def test_fires_nothing_below_the_alert_level_alert_at_exactly_the_level_exceeded_at_exactly_100(
        self, h: Harness
    ) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 5000)  # the Phase 8 test: a 5,000 Food limit
        h.transactions.set_spend(OCT, 'food', rs(4000) - 1)
        assert await evaluate(h, u, cat) == 'skipped'
        assert (await alerts_of(h, u))['items'] == []

        h.transactions.set_spend(OCT, 'food', rs(4000))  # exactly 80%
        assert await evaluate(h, u, cat) == 'fired'
        assert [a['level'] for a in (await alerts_of(h, u))['items']] == ['alert']

        h.transactions.set_spend(OCT, 'food', rs(5000) - 1)  # 99.99%: still just the alert
        assert await evaluate(h, u, cat) == 'skipped'

        h.transactions.set_spend(OCT, 'food', rs(5000))  # exactly 100%
        assert await evaluate(h, u, cat) == 'fired'
        items = (await alerts_of(h, u))['items']
        assert sorted(a['level'] for a in items) == ['alert', 'exceeded']
        assert (items[0]['categoryName'], items[0]['periodKey'], items[0]['readAt']) == ('food', OCT, None)

        events = h.bus.events_of('alert.created')
        assert [(e.level, e.pct) for e in events] == [('alert', 80), ('exceeded', 100)]
        assert (events[0].user_id, events[0].category_id, events[0].category_name, events[0].period_key) == (
            u,
            cat,
            'food',
            OCT,
        )

    async def test_jumping_straight_past_100_sends_one_exceeded_not_two_messages(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'fun', 1000)
        h.transactions.set_spend(OCT, 'fun', rs(1500))
        await evaluate(h, u, cat)
        assert levels(h) == ['exceeded']

    async def test_re_evaluating_and_retrying_never_fires_a_level_twice_spend_going_back_down_does_not_re_fire_either(
        self, h: Harness
    ) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(900))
        assert await evaluate(h, u, cat) == 'fired'
        for _ in range(3):
            assert await evaluate(h, u, cat) == 'skipped'
        h.transactions.set_spend(OCT, 'food', rs(100))  # a debit was deleted
        await evaluate(h, u, cat)
        h.transactions.set_spend(OCT, 'food', rs(900))  # and it came back
        assert await evaluate(h, u, cat) == 'skipped'
        assert len(h.bus.events_of('alert.created')) == 1
        assert len((await alerts_of(h, u))['items']) == 1

    async def test_is_idempotent_when_the_same_job_runs_at_the_same_time_twice_a_crash_and_a_retry(
        self, h: Harness
    ) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'rent', 1000)
        h.transactions.set_spend(OCT, 'rent', rs(850))
        out = await asyncio.gather(*(evaluate(h, u, cat) for _ in range(3)))
        assert out.count('fired') == 1
        assert len(h.bus.events_of('alert.created')) == 1
        assert len((await alerts_of(h, u))['items']) == 1

    async def test_a_raised_limit_re_arms_the_alert_levels_still_reached_stay_fired(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        id_, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(850))
        await evaluate(h, u, cat)
        assert len((await alerts_of(h, u))['items']) == 1

        r = await h.send(u, 'PATCH', f'/budgets/{id_}', {'limitMinor': rs(2000)})  # 42%: the 80% alert is armed again
        assert r.status_code == 200
        assert (await alerts_of(h, u))['items'] == []
        assert await evaluate(h, u, cat) == 'skipped'  # nothing reached yet

        h.transactions.set_spend(OCT, 'food', rs(1700))  # 85% of the new limit
        assert await evaluate(h, u, cat) == 'fired'
        assert levels(h) == ['alert', 'alert']

        # raising it a little while still above the level keeps the alert fired (no repeat)
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'limitMinor': rs(2100)})  # 80.9%
        assert len((await alerts_of(h, u))['items']) == 1
        assert await evaluate(h, u, cat) == 'skipped'

        # exceeded then raised above the spend: exceeded re-arms, alert stays
        h.transactions.set_spend(OCT, 'food', rs(2100))
        await evaluate(h, u, cat)
        assert sorted(a['level'] for a in (await alerts_of(h, u))['items']) == ['alert', 'exceeded']
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'limitMinor': rs(2500)})  # 84%
        assert [a['level'] for a in (await alerts_of(h, u))['items']] == ['alert']
        h.transactions.set_spend(OCT, 'food', rs(2500))
        assert await evaluate(h, u, cat) == 'fired'
        assert levels(h)[-1] == 'exceeded'

    async def test_lowering_the_limit_does_not_delete_anything_editing_without_raising_does_not_re_arm(
        self, h: Harness
    ) -> None:
        u = str(uuid.uuid4())
        id_, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(900))
        await evaluate(h, u, cat)
        h.transactions.set_spend(OCT, 'food', rs(100))
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'limitMinor': rs(900)})
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'warnPct': None})
        assert len((await alerts_of(h, u))['items']) == 1

    async def test_a_limit_brought_back_by_post_after_being_switched_off_re_arms_like_a_raised_limit(
        self, h: Harness
    ) -> None:
        # re-arming must happen on POST too, not only on PATCH
        u = str(uuid.uuid4())
        id_, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(850))
        await evaluate(h, u, cat)
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'active': False})
        assert len((await alerts_of(h, u))['items']) == 1

        # same limit again: nothing to re-arm
        same = await h.send(u, 'POST', '/budgets', {'tag': 'food', 'limitMinor': rs(1000)})
        assert same.status_code == 201
        assert len((await alerts_of(h, u))['items']) == 1
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'active': False})

        # a raised limit the spend (85%) no longer reaches: the alert is armed again
        back = await h.send(u, 'POST', '/budgets', {'tag': 'food', 'limitMinor': rs(2000)})
        assert (back.status_code, back.json()['id']) == (201, id_)
        assert (await alerts_of(h, u))['items'] == []
        h.transactions.set_spend(OCT, 'food', rs(1700))
        assert await evaluate(h, u, cat) == 'fired'
        assert levels(h) == ['alert', 'alert']

    async def test_fires_again_in_the_next_period_and_only_the_current_period_fires(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(900))
        await evaluate(h, u, cat)
        h.transactions.set_spend(NOV, 'food', rs(900))
        assert await evaluate(h, u, cat, NOV) == 'skipped'  # it is still October
        assert await evaluate(h, u, cat, '2026-09') == 'skipped'
        clock.at = datetime(2026, 11, 5, 6, 30, tzinfo=UTC)
        assert await evaluate(h, u, cat, NOV) == 'fired'
        assert sorted(a['periodKey'] for a in (await alerts_of(h, u))['items']) == [OCT, NOV]
        assert await evaluate(h, u, cat, 'garbage') == 'skipped'

    async def test_the_month_turns_over_at_midnight_in_the_users_zone_not_utc(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(NOV, 'food', rs(900))
        clock.at = datetime(2026, 10, 31, 19, 0, tzinfo=UTC)  # 00:30 on Nov 1 in Kolkata
        assert await evaluate(h, u, cat, NOV) == 'fired'

    async def test_the_zone_comes_from_the_last_request_and_from_auth_when_none_was_saved(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 1000)  # the request saved its zone
        h.transactions.set_spend(NOV, 'food', rs(900))
        clock.at = datetime(2026, 10, 31, 19, 0, tzinfo=UTC)  # still October in UTC, November in Kolkata
        before = h.auth.calls
        assert await evaluate(h, u, cat, NOV) == 'fired'
        assert h.auth.calls == before
        # a user whose zone was never saved: asked of auth
        v = str(uuid.uuid4())
        _, v_cat = await limit(h, v, 'food', 1000)
        await h.db.admin_pool.execute('UPDATE planning.planning_settings SET tz = NULL WHERE user_id = $1', [v])
        assert await evaluate(h, v, v_cat, NOV) == 'fired'
        assert h.auth.calls == before + 1

    async def test_an_inactive_or_deleted_limit_is_not_evaluated(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        id_, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(900))
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'active': False})
        assert await evaluate(h, u, cat) == 'skipped'
        await h.send(u, 'DELETE', f'/budgets/{id_}')
        assert await evaluate(h, u, cat) == 'skipped'
        assert h.bus.events_of('alert.created') == []

    async def test_a_limit_changed_while_the_job_was_running_is_left_to_the_evaluation_that_edit_queued(
        self, h: Harness, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        u = str(uuid.uuid4())
        id_, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(900))
        spend_once = h.transactions.spend_by_category

        async def edited_mid_job(*a: str) -> object:
            r = await spend_once(*a)
            await h.db.admin_pool.execute(
                'UPDATE planning.budgets SET limit_minor = $2 WHERE id = $1', [id_, rs(5000)]
            )  # an edit lands mid-job
            return r

        monkeypatch.setattr(h.transactions, 'spend_by_category', edited_mid_job)
        assert await evaluate(h, u, cat) == 'skipped'
        assert h.bus.events_of('alert.created') == []

    async def test_a_per_limit_warn_percentage_and_the_user_alert_level_decide_the_level(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        id_, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(750))
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'warnPct': 90})
        assert await evaluate(h, u, cat) == 'skipped'
        await h.send(u, 'PATCH', f'/budgets/{id_}', {'warnPct': 75})
        assert await evaluate(h, u, cat) == 'fired'
        # user level 70 on another limit
        v = str(uuid.uuid4())
        _, other_cat = await limit(h, v, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(700))
        await h.internal(v, 'PATCH', '/internal/settings', {'alertLevel': 70}, svc='transactions')
        assert await evaluate(h, v, other_cat) == 'fired'

    async def test_lowering_the_alert_level_queues_an_evaluation_for_every_active_limit(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        _, a_cat = await limit(h, u, 'food', 1000)
        b_id, _ = await limit(h, u, 'fun', 1000)
        await h.send(u, 'PATCH', f'/budgets/{b_id}', {'active': False})
        h.bus.clear()
        await h.internal(u, 'PATCH', '/internal/settings', {'alertLevel': 70}, svc='transactions')
        assert [j.payload.category_id for j in h.bus.jobs] == [a_cat]
        h.bus.clear()
        await h.internal(
            u, 'PATCH', '/internal/settings', {'alertLevel': 70}, svc='transactions'
        )  # unchanged: nothing queued
        assert h.bus.jobs == []


def tx_changed(
    u: str, category_ids: list[str | None], occurred_at: str = '2026-10-17T08:00:00.000Z', **extra: object
) -> dict:
    return {
        'userId': u, 'transactionId': str(uuid.uuid4()), 'kind': 'created', 'type': 'debit', 'status': 'confirmed',
        'source': 'captured', 'occurredAt': occurred_at, 'categoryIds': category_ids, 'taggedVia': None, **extra,
    }  # fmt: skip


class TestTransactionChangedBudgetEvaluateAlertCreated:
    async def emit(self, h: Harness, payload: dict) -> None:
        await h.bus.emit(h.db.pool, 'transaction.changed', payload)

    async def test_queues_exactly_the_key_user_category_period_period_month_of_occurred_at_in_the_users_zone(
        self, h: Harness
    ) -> None:
        u = str(uuid.uuid4())
        _, food = await limit(h, u, 'food', 1000)
        _, fun = await limit(h, u, 'fun', 1000)
        h.bus.clear()
        # 2026-10-31T19:00Z is already November 1st in Kolkata; the old category was fun, the new food
        await self.emit(h, tx_changed(u, [fun, food], '2026-10-31T19:00:00.000Z'))
        await self.emit(h, tx_changed(u, [food]))
        # run only the event half: the handler's own output, without running the jobs
        await h.deliver_events('transaction.changed')
        assert [j.key for j in h.bus.jobs] == [f'{u}:{fun}:{NOV}', f'{u}:{food}:{NOV}', f'{u}:{food}:{OCT}']
        assert all(j.job == 'budget.evaluate' for j in h.bus.jobs)

    async def test_a_burst_every_enqueue_carries_the_same_key_which_is_what_the_queue_collapses_on(
        self, h: Harness
    ) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 1000)
        h.bus.clear()
        for _ in range(5):
            await self.emit(h, tx_changed(u, [cat]))
        await h.deliver_events('transaction.changed')
        assert len(h.bus.jobs) == 5
        assert {j.key for j in h.bus.jobs} == {f'{u}:{cat}:{OCT}'}

    async def test_uncategorised_changes_and_categories_without_a_limit_queue_nothing(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        await limit(h, u, 'food', 1000)
        h.bus.clear()
        await self.emit(h, tx_changed(u, [None]))
        await self.emit(h, tx_changed(u, []))
        await self.emit(h, tx_changed(u, [h.transactions.cat('no limit here')]))
        await h.bus.drain()
        assert h.bus.jobs == []

    async def test_end_to_end_the_debit_that_crosses_the_level_produces_one_alert_created_a_repeat_produces_none(
        self, h: Harness
    ) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 5000)
        sent: list[str] = []

        async def round_() -> None:
            # drain() clears what it delivered, so collect the alerts after each round
            await h.bus.drain()
            sent.extend(levels(h))
            h.bus.events.clear()

        h.transactions.set_spend(OCT, 'food', rs(4200))
        h.bus.clear()
        await self.emit(h, tx_changed(u, [cat]))
        await round_()
        assert sent == ['alert']
        await self.emit(h, tx_changed(u, [cat]))
        await round_()
        assert sent == ['alert']
        h.transactions.set_spend(OCT, 'food', rs(5100))
        await self.emit(h, tx_changed(u, [cat]))
        await round_()
        await self.emit(h, tx_changed(u, [cat]))
        await round_()
        assert sent == ['alert', 'exceeded']

    async def test_uses_the_zone_carried_by_the_event_when_there_is_one(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 1000)
        h.bus.clear()
        await self.emit(h, tx_changed(u, [cat], '2026-10-31T19:00:00.000Z', tz='UTC'))
        await h.deliver_events('transaction.changed')
        assert h.bus.jobs[-1].payload.period_key == OCT


class TestGetAlertsAndPostAlertsIdRead:
    async def test_newest_first_unread_count_mark_read_once(self, h: Harness) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'food', 1000)
        h.transactions.set_spend(OCT, 'food', rs(850))
        await evaluate(h, u, cat)
        h.transactions.set_spend(OCT, 'food', rs(1000))
        await evaluate(h, u, cat)
        a = await alerts_of(h, u)
        assert a['unreadCount'] == 2
        assert len(a['items']) == 2
        assert a['items'][0]['level'] == 'exceeded'  # newest first
        first = await h.send(u, 'POST', f'/alerts/{a["items"][0]["id"]}/read')
        assert first.status_code == 200
        assert first.json()['unreadCount'] == 1
        read_at = first.json()['alert']['readAt']
        assert read_at is not None
        again = await h.send(u, 'POST', f'/alerts/{a["items"][0]["id"]}/read')
        assert again.json()['alert']['readAt'] == read_at
        a = await alerts_of(h, u)
        assert a['unreadCount'] == 1
        assert (await h.send(u, 'POST', f'/alerts/{uuid.uuid4()}/read')).status_code == 404
        assert (await h.send(u, 'POST', '/alerts/nope/read')).status_code == 400

    async def test_keeps_the_category_name_it_had_when_it_fired_without_calling_the_transactions_on_read(
        self, h: Harness
    ) -> None:
        u = str(uuid.uuid4())
        _, cat = await limit(h, u, 'snap', 1000)
        h.transactions.set_spend(OCT, 'snap', rs(900))
        await evaluate(h, u, cat)
        before = h.transactions.calls['categories']
        assert (await alerts_of(h, u))['items'][0]['categoryName'] == 'snap'
        assert h.transactions.calls['categories'] == before
