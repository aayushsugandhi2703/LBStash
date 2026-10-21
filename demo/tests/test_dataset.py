"""The demo dataset follows the app's own rules. Pure: no database. Run: pytest demo/tests (from lbstash, inside the backend image)."""

import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import dataset as D  # noqa: E402

NOW = datetime(2026, 10, 21, 12, 30, tzinfo=D.TZ)


@pytest.fixture(scope='module')
def ds() -> D.Dataset:
    return D.build(NOW)


def test_same_moment_gives_the_same_rows(ds: D.Dataset) -> None:
    again = D.build(NOW)
    assert [t['id'] for t in again.transactions] == [t['id'] for t in ds.transactions]
    assert [t['amount_minor'] for t in again.transactions] == [t['amount_minor'] for t in ds.transactions]


def test_six_months_ending_this_month(ds: D.Dataset) -> None:
    assert ds.months == ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
    assert min(t['occurred_at'] for t in ds.transactions).date() >= D.date(2026, 5, 1)


def test_nothing_is_dated_after_now(ds: D.Dataset) -> None:
    assert all(t['occurred_at'] <= NOW for t in ds.transactions)


def test_rows_obey_the_schema_checks(ds: D.Dataset) -> None:
    keys = [t['dedupe_key'] for t in ds.transactions]
    assert len(keys) == len(set(keys))
    assert len({t['id'] for t in ds.transactions}) == len(ds.transactions)
    cats = {c['id'] for c in ds.categories}
    for t in ds.transactions:
        assert t['type'] in ('debit', 'credit') and t['amount_minor'] > 0
        assert t['source'] in ('captured', 'recurring', 'manual', 'unaccounted')
        assert t['status'] in ('pending', 'confirmed', 'reversed')
        assert t['category_id'] is None or t['category_id'] in cats
        assert t['classified_by'] in (None, 'memory', 'rule', 'user', 'recurring')
        if t['source'] == 'captured':
            assert t['reference'] and t['account_last4'] and t['device_id'] and t['captured_at']
        if t['payee']:
            assert t['payee_key'] == ' '.join(t['payee'].lower().split())
    for c in ds.categories:
        assert c['name'] == c['name'].lower() and 1 <= len(c['name']) <= 32


def test_a_tagged_row_is_confirmed_and_an_untagged_one_waits(ds: D.Dataset) -> None:
    for t in ds.transactions:
        if t['source'] in ('captured', 'manual', 'recurring') and t['category_id']:
            assert t['status'] == 'confirmed'
    waiting = [t for t in ds.transactions if t['source'] == 'captured' and t['category_id'] is None]
    assert len(waiting) == 3 and all(t['status'] == 'pending' for t in waiting)


def test_every_past_due_day_has_exactly_one_post(ds: D.Dataset) -> None:
    posts = defaultdict(list)
    for t in ds.transactions:
        if t['source'] == 'recurring':
            posts[t['recurring_id']].append(t['dedupe_key'])
    for r in ds.rules:
        got = posts.get(r['id'], [])
        assert len(got) == len(set(got))
        if r['paused']:
            assert r['next_due'] > ds.today
            continue
        assert len(got) == 5 + (1 if r['day_of_month'] <= ds.today.day else 0)  # May..Sep, and October once its day has passed
        assert r['last_handled_due'] is not None and r['last_handled_due'] <= ds.today < r['next_due']


def test_merged_bank_messages_point_at_their_post(ds: D.Dataset) -> None:
    ids = {t['id'] for t in ds.transactions}
    assert ds.tx_links and all(k['transaction_id'] in ids for k in ds.tx_links)


def test_the_balance_never_goes_below_zero_and_checks_agree_with_it(ds: D.Dataset) -> None:
    running = ds.settings['opening_balance_minor']
    for t in ds.transactions:
        running += t['amount_minor'] if t['type'] == 'credit' else -t['amount_minor']
        assert running > 0, t['occurred_at']
    booked = next(c for c in ds.balance_checks if c['status'] == 'booked')
    entry = next(t for t in ds.transactions if t['id'] == booked['transaction_id'])
    assert entry['source'] == 'unaccounted' and entry['status'] == 'pending' and entry['amount_minor'] == -booked['gap_minor']
    assert booked['bank_balance_minor'] == booked['transactions_balance_minor'] + booked['gap_minor']
    assert ds.balance_at(booked['as_of']) == booked['bank_balance_minor']
    assert sum(1 for c in ds.balance_checks if c['status'] == 'open') == 0


def test_finished_months_keep_something_and_this_month_runs_hot(ds: D.Dataset) -> None:
    income, spent = defaultdict(int), defaultdict(int)
    for t in ds.transactions:
        (income if t['type'] == 'credit' else spent)[D.month_key(t['occurred_at'].date())] += t['amount_minor']
    for m in ds.months[:-1]:
        assert 0 < spent[m] < income[m], m
        assert 60_000 * 100 < spent[m] < 100_000 * 100, m
    budget_cats = {b['category_id'] for b in ds.budgets}
    this = defaultdict(int)
    for t in ds.transactions:
        if t['type'] == 'debit' and t['category_id'] in budget_cats and D.month_key(t['occurred_at'].date()) == ds.months[-1]:
            this[t['category_id']] += t['amount_minor']
    assert any(this[b['category_id']] * 100 >= b['limit_minor'] * 70 for b in ds.budgets)


def test_plans_and_limits(ds: D.Dataset) -> None:
    assert [p['month'] for p in ds.plans] == ds.months[-3:]
    for p in ds.plans:
        lines = [ln for ln in ds.plan_lines if ln['plan_id'] == p['id']]
        assert lines and sum(ln['allocated_minor'] for ln in lines) <= p['total_minor']
        assert len({ln['category_id'] for ln in lines}) == len(lines)
    assert {b['category'] for b in ds.budgets} == set(D.LIMITED)
    assert all(b['limit_minor'] > 0 for b in ds.budgets)


def test_alerts_are_what_the_evaluator_would_raise(ds: D.Dataset) -> None:
    keys = [(a['budget_id'], a['period_key'], a['level']) for a in ds.alerts]
    assert len(keys) == len(set(keys))
    budgets = {b['id'] for b in ds.budgets}
    for a in ds.alerts:
        assert a['budget_id'] in budgets and a['level'] in ('alert', 'exceeded') and a['pct'] in (80, 100)
        assert (a['read_at'] is None) == (a['period_key'] == ds.months[-1])
        assert a['sent_at'] <= NOW


def test_other_days_work_too() -> None:
    for now in (datetime(2026, 1, 1, 7, 0, tzinfo=D.TZ), datetime(2026, 2, 28, 23, 59, tzinfo=D.TZ), datetime(2027, 3, 15, 15, 0, tzinfo=D.TZ)):
        d = D.build(now)
        assert d.transactions and all(t['occurred_at'] <= now for t in d.transactions)
        running = d.settings['opening_balance_minor']
        for t in d.transactions:
            running += t['amount_minor'] if t['type'] == 'credit' else -t['amount_minor']
        assert running > 0


def test_ids_match_the_backend_constant() -> None:
    try:
        from lbstash.common import DEMO_USER_ID
    except ImportError:  # the backend hook is not installed in this environment
        pytest.skip('lbstash.common.DEMO_USER_ID is not available here')
    assert DEMO_USER_ID == D.DEMO_USER_ID
