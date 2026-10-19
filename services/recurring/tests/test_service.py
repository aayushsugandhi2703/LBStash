import dataclasses
import json
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import psycopg
import pytest
import pytest_asyncio
from bt.common import AppError, normalize_tag
from bt_recurring.posting import make_tz_resolver, post_due_rules
from bt_recurring.routes import make_routes
from bt_recurring.workers import make_workers

# a mutable clock and fake ledger / auth
STATE = SimpleNamespace(now=datetime.fromisoformat('2026-10-18T10:00:00+05:30'))


def clock() -> datetime:
    return STATE.now


def set_now(iso: str) -> None:
    STATE.now = datetime.fromisoformat(iso)


def uid_of(as_: Any) -> str:
    return as_['user_id'] if isinstance(as_, dict) else as_.user_id


class FakeLedger:
    """Stands in for the ledger client: records posts, dedupes on `rec:<ruleId>:<dueDate>`, can fail or link on demand."""

    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []
        self.seen: dict[str, str] = {}
        self.fail_next = 0
        self.link_keys: set[str] = set()
        self.cats: dict[str, list[SimpleNamespace]] = {}

    def reset(self) -> None:
        self.posts.clear()
        self.seen.clear()
        self.link_keys.clear()
        self.fail_next = 0

    def cats_of(self, user_id: str) -> list[SimpleNamespace]:
        return self.cats.setdefault(user_id, [])

    def add_cat(self, user_id: str, name: str) -> SimpleNamespace:
        c = SimpleNamespace(id=str(uuid.uuid4()), name=name, archived=False)
        self.cats_of(user_id).append(c)
        return c

    async def categories(self, as_: Any, include_archived: bool | None = None) -> SimpleNamespace:
        return SimpleNamespace(items=list(self.cats_of(uid_of(as_))))

    async def resolve_category(self, as_: Any, tag: str) -> SimpleNamespace:
        name = normalize_tag(tag)
        have = next((c for c in self.cats_of(uid_of(as_)) if c.name == name), None)
        return SimpleNamespace(category=have or self.add_cat(uid_of(as_), name), created=have is None)

    async def post_recurring(self, as_: Any, body: dict[str, Any]) -> SimpleNamespace:
        if self.fail_next > 0:
            self.fail_next -= 1
            raise AppError('upstream_failed', 'ledger down')
        self.posts.append({'as': as_, 'body': body})
        key = f'rec:{body["ruleId"]}:{body["dueDate"]}'
        prior = self.seen.get(key)
        outcome = 'already_posted' if prior else 'linked' if key in self.link_keys else 'posted'
        if not prior:
            self.seen[key] = 'linked' if outcome == 'linked' else 'posted'
        return SimpleNamespace(outcome=outcome, transaction=SimpleNamespace(id=str(uuid.uuid4())))


ZONES: dict[str, str] = {}


class FakeAuth:
    async def me(self, as_: Any) -> SimpleNamespace:
        return SimpleNamespace(user=SimpleNamespace(id=uid_of(as_), timezone=ZONES.get(uid_of(as_), 'Asia/Kolkata')))


ledger = FakeLedger()


class Env(SimpleNamespace):
    """What a test needs: the harness plus the database."""


@pytest_asyncio.fixture(loop_scope='session')
async def t(db, app_factory):
    """App + workers on a clean table, frozen clock and a fresh fake ledger."""
    h = await app_factory(register=make_routes(clock), pool=db.pool, clients={'ledger': ledger, 'auth': FakeAuth()})
    await make_workers(clock)(h.deps)
    ledger.reset()
    set_now('2026-10-18T10:00:00+05:30')
    async with db.pool.system_tx() as tx:
        await tx.execute('DELETE FROM recurring_rules')
    return Env(h=h, db=db, deps=h.deps, bus=h.bus)


async def call(t: Env, user: str, method: str, url: str, payload: Any = None, tz: str = 'Asia/Kolkata'):
    return await t.h.client.request(method, url, json=payload, headers=t.h.headers_for(user, 'gateway', tz))


def new_user() -> str:
    return str(uuid.uuid4())


def rent(cat: str, **extra: Any) -> dict[str, Any]:
    return {'name': 'Rent', 'categoryId': cat, 'amountMinor': 2000000, 'schedule': {'kind': 'monthly', 'day': 1}, **extra}


async def seed(t: Env, user_id: str, *, next_due: str, kind: str = 'monthly', day: Any = 'default', weekday: int | None = None,
               month: int | None = None, paused: bool = False, ends_on: str | None = None, amount: int = 100000,
               name: str = 'Rule', hint: str | None = None) -> SimpleNamespace:
    """Insert a rule directly (the API refuses start dates in the past; catch-up needs them)."""
    cat = str(uuid.uuid4())
    if day == 'default':
        day = None if kind == 'weekly' else 31
    async with t.db.pool.user_tx(user_id) as tx:
        row = await tx.one(
            """INSERT INTO recurring_rules (user_id, name, category_id, amount_minor, kind, day_of_month, weekday, month_of_year, next_due, paused, ends_on, match_hint)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) RETURNING id""",
            [user_id, name, cat, amount, kind, day, weekday, month, next_due, paused, ends_on, hint],
        )  # fmt: skip
    return SimpleNamespace(id=row['id'], category_id=cat)


async def next_due_of(t: Env, user_id: str, rule_id: str) -> str:
    async with t.db.pool.user_tx(user_id) as tx:
        rows = await tx.query('SELECT next_due FROM recurring_rules WHERE id = $1', [rule_id])
    return rows[0]['next_due']


async def tick(t: Env) -> dict[str, int]:
    return await post_due_rules(t.deps, clock, make_tz_resolver(t.deps, clock, 0))


def posted(rule_id: str | None = None) -> list[str]:
    return [p['body']['dueDate'] for p in ledger.posts if rule_id is None or p['body']['ruleId'] == rule_id]


class TestAPI:
    async def test_creates_lists_with_category_names_and_totals_the_committed_amount_the_repeats_page_numbers(self, t):
        u = new_user()
        cats = {n: ledger.add_cat(u, n).id for n in ['rent', 'sip', 'bills', 'fun']}
        rules = [
            {'name': 'Rent', 'categoryId': cats['rent'], 'amountMinor': 2000000, 'schedule': {'kind': 'monthly', 'day': 1}, 'note': 'to landlord'},
            {'name': 'Nifty 50 index fund', 'categoryId': cats['sip'], 'amountMinor': 1000000, 'schedule': {'kind': 'monthly', 'day': 5}, 'note': 'sip'},
            {'name': 'Cloud storage', 'categoryId': cats['bills'], 'amountMinor': 13000, 'schedule': {'kind': 'monthly', 'day': 12}, 'note': 'subscription'},
            {'name': 'Netflix', 'categoryId': cats['fun'], 'amountMinor': 64900, 'schedule': {'kind': 'monthly', 'day': 17}, 'note': 'subscription', 'matchHint': 'netflix'},
        ]  # fmt: skip
        for r in rules:
            res = await call(t, u, 'POST', '/recurring', r)
            assert res.status_code == 201
        res = await call(t, u, 'GET', '/recurring')
        assert res.status_code == 200
        body = res.json()
        assert body['committedMinor'] == 3077900  # 30,779
        assert [[i['name'], i['categoryName'], i['nextDue']] for i in body['items']] == [
            ['Rent', 'rent', '2026-11-01'],
            ['Nifty 50 index fund', 'sip', '2026-11-05'],
            ['Cloud storage', 'bills', '2026-11-12'],
            ['Netflix', 'fun', '2026-11-17'],
        ]
        netflix = next(i for i in body['items'] if i['name'] == 'Netflix')
        assert netflix['matchHint'] == 'netflix' and netflix['note'] == 'subscription' and netflix['active'] is True

        # pausing Rent drops it from the total (30,779 -> 10,779)
        rent_id = next(i['id'] for i in body['items'] if i['name'] == 'Rent')
        paused = await call(t, u, 'PATCH', f'/recurring/{rent_id}', {'paused': True})
        assert paused.json()['committedMinor'] == 1077900
        assert paused.json()['rule']['paused'] is True and paused.json()['rule']['active'] is False
        assert (await call(t, u, 'GET', '/recurring')).json()['committedMinor'] == 1077900

    async def test_a_new_tag_becomes_a_category_through_the_ledger(self, t):
        u = new_user()
        res = await call(t, u, 'POST', '/recurring', {'name': 'Gym', 'tag': '#Fitness', 'amountMinor': 150000, 'schedule': {'kind': 'weekly', 'weekday': 1}})
        assert res.status_code == 201
        assert res.json()['rule']['categoryName'] == 'fitness'
        assert res.json()['rule']['nextDue'] == '2026-10-19'  # Sunday the 18th -> Monday the 19th

    async def test_validates_input(self, t):
        u = new_user()
        cat = ledger.add_cat(u, 'rent').id

        async def bad(over: dict[str, Any], field: str | None = None) -> None:
            payload = {k: v for k, v in {**rent(cat), **over}.items() if v is not ...}
            res = await call(t, u, 'POST', '/recurring', payload)
            assert res.status_code == 400, json.dumps(over, default=str)
            if field:
                assert field in json.dumps(res.json()['error']['details'])

        await bad({'amountMinor': 0})
        await bad({'amountMinor': -5})
        await bad({'amountMinor': 10.5})
        await bad({'name': '   '})
        await bad({'schedule': {'kind': 'monthly', 'day': 32}})
        await bad({'schedule': {'kind': 'weekly', 'weekday': 7}})
        await bad({'schedule': {'kind': 'yearly', 'month': 13, 'day': 1}})
        await bad({'categoryId': ...})
        await bad({'tag': 'food'})  # both categoryId and tag
        await bad({'categoryId': 'nope'})
        await bad({'startsOn': '2026-02-31'}, 'startsOn')
        await bad({'startsOn': '2026-10-17'}, 'startsOn')  # yesterday
        await bad({'endsOn': '2026-10-31'}, 'endsOn')  # before the first payment (Nov 1)
        await bad({'endsOn': '2026-13-01'}, 'endsOn')
        await bad({'categoryId': str(uuid.uuid4())}, 'categoryId')  # not this user's category
        assert (await call(t, u, 'PATCH', f'/recurring/{uuid.uuid4()}', {})).status_code == 400  # nothing to change
        assert (await call(t, u, 'PATCH', f'/recurring/{uuid.uuid4()}', {'amountMinor': 0})).status_code == 400
        assert (await call(t, u, 'GET', '/recurring')).json()['items'] == []

    async def test_start_date_the_first_payment_can_be_today_or_later_ends_on_is_kept(self, t):
        u = new_user()
        cat = ledger.add_cat(u, 'rent').id
        a = await call(t, u, 'POST', '/recurring', rent(cat, schedule={'kind': 'monthly', 'day': 18}))
        assert a.json()['rule']['nextDue'] == '2026-10-18'  # due today
        b = await call(t, u, 'POST', '/recurring', rent(cat, startsOn='2026-12-01', endsOn='2027-03-01'))
        assert b.json()['rule']['nextDue'] == '2026-12-01' and b.json()['rule']['endsOn'] == '2027-03-01'

    async def test_edit_applies_from_the_next_occurrence_and_keeps_the_rows_already_posted_untouched(self, t):
        u = new_user()
        cat = ledger.add_cat(u, 'rent').id
        created = (await call(t, u, 'POST', '/recurring', rent(cat))).json()['rule']
        edited = await call(t, u, 'PATCH', f'/recurring/{created["id"]}', {'amountMinor': 2200000, 'name': 'Rent (new lease)', 'matchHint': 'landlord', 'note': None})
        assert edited.status_code == 200
        rule = edited.json()['rule']
        assert rule['amountMinor'] == 2200000 and rule['name'] == 'Rent (new lease)' and rule['matchHint'] == 'landlord'
        assert rule['note'] is None and rule['nextDue'] == '2026-11-01'
        assert edited.json()['committedMinor'] == 2200000
        # a new day moves the next due date (never before today)
        moved = await call(t, u, 'PATCH', f'/recurring/{created["id"]}', {'schedule': {'kind': 'monthly', 'day': 20}})
        assert moved.json()['rule']['nextDue'] == '2026-10-20'
        # the new amount is what the cron hands to the ledger
        set_now('2026-10-20T09:00:00+05:30')
        await tick(t)
        assert [[p['body']['amountMinor'], p['body']['dueDate'], p['body']['matchHint']] for p in ledger.posts] == [[2200000, '2026-10-20', 'landlord']]
        # schedule change after the occurrence was handled can't re-post it
        again = await call(t, u, 'PATCH', f'/recurring/{created["id"]}', {'schedule': {'kind': 'monthly', 'day': 19}})
        assert again.json()['rule']['nextDue'] == '2026-11-19'

    async def test_skip_one_occurrence_moves_on_without_posting_skip_on_an_ended_rule_is_refused(self, t):
        u = new_user()
        cat = ledger.add_cat(u, 'rent').id
        r = (await call(t, u, 'POST', '/recurring', rent(cat, endsOn='2026-12-01'))).json()['rule']
        s1 = await call(t, u, 'PATCH', f'/recurring/{r["id"]}', {'skipNext': True})
        assert s1.json()['rule']['nextDue'] == '2026-12-01'
        s2 = await call(t, u, 'PATCH', f'/recurring/{r["id"]}', {'skipNext': True})
        assert s2.json()['rule']['nextDue'] == '2027-01-01' and s2.json()['rule']['active'] is False
        assert s2.json()['committedMinor'] == 0
        assert (await call(t, u, 'PATCH', f'/recurring/{r["id"]}', {'skipNext': True})).status_code == 422
        assert ledger.posts == []

    async def test_resume_never_back_posts_what_was_missed_while_paused(self, t):
        u = new_user()
        seeded = await seed(t, u, next_due='2026-07-31', paused=True, day=31)
        await tick(t)
        assert ledger.posts == []
        res = await call(t, u, 'PATCH', f'/recurring/{seeded.id}', {'paused': False})
        assert res.json()['rule']['nextDue'] == '2026-10-31'
        await tick(t)
        assert ledger.posts == []

    async def test_a_patch_that_does_not_change_paused_keeps_a_running_rules_backlog(self, t):
        # a running rule that is behind is catching up; `paused: false` on it is not a resume and must not skip its backlog
        u = new_user()
        seeded = await seed(t, u, next_due='2026-08-31', day=31)
        res = await call(t, u, 'PATCH', f'/recurring/{seeded.id}', {'paused': False, 'note': 'still running'})
        assert res.json()['rule']['nextDue'] == '2026-08-31'
        await tick(t)
        assert posted() == ['2026-08-31', '2026-09-30']

    async def test_ends_on_and_note_can_be_cleared_with_null_and_are_kept_when_absent(self, t):
        u = new_user()
        cat = ledger.add_cat(u, 'rent').id
        r = (await call(t, u, 'POST', '/recurring', rent(cat, endsOn='2027-03-01', note='to landlord'))).json()['rule']
        kept = await call(t, u, 'PATCH', f'/recurring/{r["id"]}', {'amountMinor': 2100000})
        assert kept.json()['rule']['endsOn'] == '2027-03-01' and kept.json()['rule']['note'] == 'to landlord'
        cleared = await call(t, u, 'PATCH', f'/recurring/{r["id"]}', {'endsOn': None, 'note': None})
        assert cleared.json()['rule']['endsOn'] is None and cleared.json()['rule']['note'] is None

    async def test_delete_removes_the_rule_and_returns_the_new_total_unknown_id_is_404(self, t):
        u = new_user()
        cat = ledger.add_cat(u, 'rent').id
        a = (await call(t, u, 'POST', '/recurring', rent(cat))).json()['rule']
        await call(t, u, 'POST', '/recurring', rent(cat, name='SIP', amountMinor=1000000))
        d = await call(t, u, 'DELETE', f'/recurring/{a["id"]}')
        assert d.status_code == 200
        assert d.json() == {'ok': True, 'committedMinor': 1000000}
        assert (await call(t, u, 'DELETE', f'/recurring/{a["id"]}')).status_code == 404
        assert (await call(t, u, 'PATCH', f'/recurring/{a["id"]}', {'paused': True})).status_code == 404

    async def test_is_scoped_to_the_token_user_nobody_sees_edits_deletes_or_exports_another_users_rules(self, t):
        a, b = new_user(), new_user()
        cat_a = ledger.add_cat(a, 'rent').id
        mine = (await call(t, a, 'POST', '/recurring', rent(cat_a))).json()['rule']
        assert (await call(t, b, 'GET', '/recurring')).json() == {'items': [], 'committedMinor': 0}
        assert (await call(t, b, 'PATCH', f'/recurring/{mine["id"]}', {'amountMinor': 1})).status_code == 404
        assert (await call(t, b, 'DELETE', f'/recurring/{mine["id"]}')).status_code == 404
        # B cannot attach A's category
        assert (await call(t, b, 'POST', '/recurring', rent(cat_a))).status_code == 400
        assert len((await call(t, a, 'GET', '/recurring')).json()['items']) == 1

        c = t.h.client
        exp = await c.get('/internal/export', headers=t.h.headers_for(a, 'auth'))
        assert exp.status_code == 200
        assert exp.json()['service'] == 'recurring'
        assert len(exp.json()['tables']['recurring_rules']) == 1
        assert exp.json()['tables']['recurring_rules'][0]['id'] == mine['id']
        exp_b = await c.get('/internal/export', headers=t.h.headers_for(b, 'auth'))
        assert exp_b.json()['tables']['recurring_rules'] == []
        # internal routes refuse traffic forwarded from outside; public routes need a user
        assert (await c.get('/internal/export', headers=t.h.headers_for(a, 'gateway', 'UTC', True))).status_code == 403
        assert (await c.get('/internal/export', headers=t.h.headers_for(None, 'auth'))).status_code == 401
        assert (await c.get('/recurring', headers=t.h.headers_for(None, 'ingest'))).status_code == 401
        assert (await c.get('/recurring')).status_code == 401

    async def test_the_export_writes_timestamps_as_iso_strings(self, t):
        u = new_user()
        await seed(t, u, next_due='2026-11-01', day=1)
        part = (await t.h.client.get('/internal/export', headers=t.h.headers_for(u, 'auth'))).json()
        row = part['tables']['recurring_rules'][0]
        assert row['next_due'] == '2026-11-01'
        assert row['amount_minor'] == 100000
        assert row['created_at'].endswith('Z') and len(row['created_at']) == 24

    async def test_the_database_refuses_what_the_api_would_never_send(self, t):
        u = new_user()
        with pytest.raises(psycopg.errors.CheckViolation):
            await seed(t, u, next_due='2026-11-01', amount=0)
        with pytest.raises(psycopg.errors.CheckViolation):
            await seed(t, u, next_due='2026-11-01', kind='weekly', weekday=9, day=None)
        with pytest.raises(psycopg.errors.CheckViolation):
            await seed(t, u, next_due='2026-11-01', kind='monthly', day=None)


class TestPostingCron:
    async def test_posts_a_due_rule_once_with_the_right_payload_and_advances_next_due_a_second_tick_does_nothing(self, t):
        u = new_user()
        r = await seed(t, u, next_due='2026-10-18', day=18, amount=2000000, name='Rent', hint='landlord')
        assert await tick(t) == {'handled': 1, 'failed': 0}
        assert len(ledger.posts) == 1
        assert ledger.posts[0]['as'] == {'user_id': u, 'tz': 'Asia/Kolkata'}
        assert ledger.posts[0]['body'] == {
            'ruleId': r.id, 'name': 'Rent', 'categoryId': r.category_id, 'amountMinor': 2000000, 'dueDate': '2026-10-18', 'matchHint': 'landlord',
        }  # fmt: skip
        assert await next_due_of(t, u, r.id) == '2026-11-18'
        await tick(t)
        assert len(ledger.posts) == 1

    async def test_two_ticks_at_the_same_moment_post_once_row_lock(self, t):
        import asyncio

        u = new_user()
        r = await seed(t, u, next_due='2026-10-18', day=18)
        await asyncio.gather(tick(t), tick(t))
        assert len(ledger.posts) == 1
        assert await next_due_of(t, u, r.id) == '2026-11-18'

    async def test_nothing_is_posted_before_the_due_date_for_paused_rules_or_after_the_end_date(self, t):
        u = new_user()
        future = await seed(t, u, next_due='2026-10-19', day=19)
        paused = await seed(t, u, next_due='2026-10-01', day=1, paused=True)
        ended = await seed(t, u, next_due='2026-10-01', day=1, ends_on='2026-09-30')
        await tick(t)
        assert ledger.posts == []
        assert await next_due_of(t, u, future.id) == '2026-10-19'
        assert await next_due_of(t, u, paused.id) == '2026-10-01'
        assert await next_due_of(t, u, ended.id) == '2026-10-01'

    async def test_the_last_occurrence_posts_then_the_rule_is_over(self, t):
        u = new_user()
        r = await seed(t, u, next_due='2026-10-18', day=18, ends_on='2026-10-18')
        await tick(t)
        assert len(ledger.posts) == 1
        assert await next_due_of(t, u, r.id) == '2026-11-18'
        set_now('2026-12-01T10:00:00+05:30')
        await tick(t)
        assert len(ledger.posts) == 1

    async def test_catches_up_missed_occurrences_one_by_one_with_the_short_month_clamp_without_double_posting(self, t):
        u = new_user()
        r = await seed(t, u, next_due='2026-07-31', day=31)
        await tick(t)
        assert posted() == ['2026-07-31', '2026-08-31', '2026-09-30']
        assert await next_due_of(t, u, r.id) == '2026-10-31'
        await tick(t)
        assert len(ledger.posts) == 3
        assert len(set(posted())) == 3

    async def test_weekly_and_yearly_rules_advance_correctly(self, t):
        u = new_user()
        w = await seed(t, u, next_due='2026-10-12', kind='weekly', weekday=1, day=None)  # Mondays
        y = await seed(t, u, next_due='2026-02-28', kind='yearly', month=2, day=29)
        await tick(t)
        assert posted(w.id) == ['2026-10-12']
        assert await next_due_of(t, u, w.id) == '2026-10-19'
        assert posted(y.id) == ['2026-02-28']
        assert await next_due_of(t, u, y.id) == '2027-02-28'

    async def test_a_linked_capture_still_advances_the_rule(self, t):
        u = new_user()
        r = await seed(t, u, next_due='2026-10-18', day=18)
        ledger.link_keys.add(f'rec:{r.id}:2026-10-18')
        await tick(t)
        assert await next_due_of(t, u, r.id) == '2026-11-18'

    async def test_a_failed_ledger_call_leaves_next_due_unchanged_the_next_tick_retries_and_succeeds(self, t):
        u = new_user()
        r = await seed(t, u, next_due='2026-10-18', day=18)
        ledger.fail_next = 1
        assert await tick(t) == {'handled': 0, 'failed': 1}
        assert await next_due_of(t, u, r.id) == '2026-10-18'
        assert await tick(t) == {'handled': 1, 'failed': 0}
        assert await next_due_of(t, u, r.id) == '2026-11-18'
        assert len(ledger.posts) == 1

    async def test_one_failing_rule_does_not_block_the_others(self, t):
        u = new_user()
        a = await seed(t, u, next_due='2026-10-10', day=10, name='A')
        b = await seed(t, u, next_due='2026-10-11', day=11, name='B')
        ledger.fail_next = 1  # A is tried first
        assert await tick(t) == {'handled': 1, 'failed': 1}
        assert await next_due_of(t, u, a.id) == '2026-10-10'
        assert await next_due_of(t, u, b.id) == '2026-11-11'

    async def test_a_crash_after_the_ledger_call_but_before_the_commit_is_safe_the_retry_gets_already_posted_and_advances(self, t):
        u = new_user()
        r = await seed(t, u, next_due='2026-10-18', day=18)
        ledger.seen[f'rec:{r.id}:2026-10-18'] = 'posted'  # the ledger already has it
        await tick(t)
        assert posted() == ['2026-10-18']  # one call, outcome already_posted
        assert await next_due_of(t, u, r.id) == '2026-11-18'

    async def test_uses_each_users_own_time_zone_for_today(self, t):
        set_now('2026-10-17T20:00:00+00:00')  # Oct 18 in Auckland, still Oct 17 in Los Angeles
        nz, la = new_user(), new_user()
        ZONES[nz] = 'Pacific/Auckland'
        ZONES[la] = 'America/Los_Angeles'
        a = await seed(t, nz, next_due='2026-10-18', day=18)
        b = await seed(t, la, next_due='2026-10-18', day=18)
        await tick(t)
        assert [p['body']['ruleId'] for p in ledger.posts] == [a.id]
        assert ledger.posts[0]['as']['tz'] == 'Pacific/Auckland'
        assert await next_due_of(t, la, b.id) == '2026-10-18'
        set_now('2026-10-18T08:00:00+00:00')  # now Oct 18 in LA too
        await tick(t)
        assert [p['body']['ruleId'] for p in ledger.posts] == [a.id, b.id]

    async def test_falls_back_to_the_default_zone_when_auth_cannot_be_reached(self, t):
        u = new_user()
        r = await seed(t, u, next_due='2026-10-18', day=18)

        class Broken:
            async def me(self, as_: Any) -> None:
                raise RuntimeError('down')

        broken = dataclasses.replace(t.deps, clients=SimpleNamespace(ledger=ledger, auth=Broken()))
        await post_due_rules(broken, clock, make_tz_resolver(broken, clock, 0))
        assert ledger.posts[0]['as']['tz'] == 'Asia/Kolkata'
        assert await next_due_of(t, u, r.id) == '2026-11-18'

    async def test_an_unknown_zone_from_auth_falls_back_to_the_default_zone(self, t):
        u = new_user()
        ZONES[u] = 'Mars/Olympus_Mons'
        assert await make_tz_resolver(t.deps, clock, 0)(u) == 'Asia/Kolkata'

    async def test_the_cron_job_account_deleted_and_the_nightly_sweep_are_wired(self, t):
        assert {s.queue for s in t.bus.schedules} >= {'recurring.post', 'retention.sweep.recurring'}
        u = new_user()
        r = await seed(t, u, next_due='2026-10-18', day=18)
        await t.bus.enqueue(t.db.pool, 'recurring.post', {})
        await t.bus.drain()
        assert await next_due_of(t, u, r.id) == '2026-11-18'

        other = new_user()
        await seed(t, other, next_due='2027-01-01', day=1)
        await t.bus.emit(t.db.pool, 'account.deleted', {'userId': u})
        await t.bus.drain()
        async with t.db.pool.system_tx() as tx:
            left = await tx.query('SELECT user_id FROM recurring_rules WHERE user_id = ANY($1)', [[u, other]])
        assert [x['user_id'] for x in left] == [other]
        await t.bus.enqueue(t.db.pool, 'retention.sweep', {}, queue='retention.sweep.recurring')
        assert await t.bus.drain() is None
