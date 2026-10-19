"""Golden tests: the ui-spec dataset (01 Now, 05 Repeats, 06 Trends) goes in through fake clients and the page's exact
numbers must come out. All money below is the spec's rupees x 100 (paise)."""

import math
from datetime import datetime

import pytest
from bt.kit.testing import AppHarness, build_test_app
from bt_reports.common import avg
from bt_reports.routes import make_register
from harness import CAT_MONTHS, DAILY, ID, Fakes, R, get, rent_paused, rules, setup, uid

ME = uid()


class TestDashboardNow:
    async def test_reproduces_the_ui_spec_numbers_exactly(self):
        app, _ = await setup()
        res = await get(app, ME, '/dashboard?month=2026-10')
        assert res.status_code == 200
        assert res.json() == {
            'month': '2026-10', 'dayOfMonth': 18, 'daysInMonth': 31,
            'balance': {'carriedOver': 2730000, 'income': 5000000, 'spent': 3970900, 'available': 3759100},
            # days left after today (31 - 18 = 13), as in the design: Rs 445 a day
            'safeToSpend': {'planLeft': 579100, 'daysLeft': 13, 'perDay': 44500},
            # category names are stored lowercase, so "SIP" in the mock-up reads "Sip" (display_tag) unless the web special-cases it
            'flow': [
                {'name': 'Rent', 'amount': 2000000}, {'name': 'Sip', 'amount': 1000000}, {'name': 'Food', 'amount': 542000},
                {'name': 'Fun', 'amount': 164000}, {'name': 'Travel', 'amount': 135000}, {'name': 'Bills', 'amount': 129900},
                {'name': 'Still available', 'amount': 3759100},
            ],
            'attention': [
                {'kind': 'limit', 'category': 'Fun', 'pct': 82, 'status': 'close'},
                {'kind': 'untagged', 'count': 1},
                {'kind': 'needs_look', 'count': 2},
                {'kind': 'recurring', 'name': 'Rent', 'amount': 2000000, 'due': '2026-11-01'},
            ],
            # the ledger answers in UTC milliseconds (07:12 +05:30 is 01:42Z)
            'lastCapturedAt': '2026-10-18T01:42:00.000Z',
            'untaggedCount': 1, 'unaccountedCount': 0, 'needsLookCount': 2, 'alertBadgeCount': 1, 'degraded': [],
        }  # fmt: skip


class TestDashboardVariations:
    async def test_safe_to_spend_is_plan_left_over_days_left_rounded_down_to_whole_rupees_never_negative(self):
        app, _ = await setup()
        res = (await get(app, ME, '/dashboard?month=2026-10')).json()
        assert res['safeToSpend']['planLeft'] == R(45500) - R(39709)  # 5,791
        assert math.floor(res['safeToSpend']['planLeft'] / res['safeToSpend']['daysLeft']) == 44546
        assert res['safeToSpend']['perDay'] == 44500

    async def test_defaults_to_the_month_in_progress_a_finished_month_has_no_days_left_a_future_month_has_them_all(self):
        app, _ = await setup()
        cur = (await get(app, ME, '/dashboard')).json()
        assert cur['month'] == '2026-10' and cur['dayOfMonth'] == 18 and cur['safeToSpend']['daysLeft'] == 13
        past = (await get(app, ME, '/dashboard?month=2026-09')).json()
        assert (past['month'], past['dayOfMonth'], past['daysInMonth']) == ('2026-09', 30, 30)
        assert past['safeToSpend']['daysLeft'] == 0 and past['safeToSpend']['perDay'] == 0
        future = (await get(app, ME, '/dashboard?month=2026-11')).json()
        assert (future['month'], future['dayOfMonth']) == ('2026-11', 0) and future['safeToSpend']['daysLeft'] == 30

    async def test_uses_the_users_time_zone_for_today_oct_17_in_los_angeles_at_0200_utc_on_the_18th(self):
        app, _ = await setup(clk=lambda: datetime.fromisoformat('2026-10-18T02:00:00+00:00'))
        la = (await get(app, ME, '/dashboard', 'America/Los_Angeles')).json()
        assert (la['month'], la['dayOfMonth'], la['safeToSpend']['daysLeft']) == ('2026-10', 17, 14)
        assert (await get(app, ME, '/dashboard', 'Asia/Kolkata')).json()['dayOfMonth'] == 18

    async def test_attention_a_limit_appears_at_the_alert_level_a_paused_or_ended_rule_is_not_next(self):
        app, _ = await setup(Fakes(rules=rent_paused))
        att = (await get(app, ME, '/dashboard?month=2026-10')).json()['attention']
        limits = [a for a in att if a['kind'] == 'limit']
        # Food at 60% and an inactive limit are left out
        assert limits == [{'kind': 'limit', 'category': 'Fun', 'pct': 82, 'status': 'close'}]
        nxt = next(a for a in att if a['kind'] == 'recurring')
        assert nxt['name'] == 'Nifty 50 index fund' and nxt['due'] == '2026-11-05'

    async def test_a_user_with_nothing_yet_gets_a_valid_empty_dashboard(self):
        app, _ = await setup(Fakes(empty=True))
        res = (await get(app, ME, '/dashboard')).json()
        assert res['balance'] == {'carriedOver': 0, 'income': 0, 'spent': 0, 'available': 0}
        assert res['safeToSpend'] == {'planLeft': 0, 'daysLeft': 13, 'perDay': 0}
        assert res['flow'] == [{'name': 'Still available', 'amount': 0}]
        assert res['attention'] == []

    async def test_optional_neighbours_failing_degrade_the_page_the_ledger_failing_fails_it(self):
        app, _ = await setup(Fakes(failing=('ingest',)))
        res = await get(app, ME, '/dashboard')
        assert res.status_code == 200
        assert res.json()['needsLookCount'] == 0 and res.json()['degraded'] == ['ingest']
        down, _ = await setup(Fakes(failing=('ledger',)))
        assert (await get(down, ME, '/dashboard')).status_code == 502

    async def test_every_optional_part_failing_is_listed_sorted_and_zeroed(self):
        app, _ = await setup(Fakes(failing=('planning.budgets', 'planning.alerts', 'recurring', 'ingest')))
        res = (await get(app, ME, '/dashboard')).json()
        assert res['degraded'] == ['alerts', 'budgets', 'ingest', 'recurring']
        assert res['alertBadgeCount'] == 0 and res['needsLookCount'] == 0
        assert [a['kind'] for a in res['attention']] == ['untagged']

    async def test_validates_the_query_and_needs_a_signed_in_user(self):
        app, _ = await setup()
        assert (await get(app, ME, '/dashboard?month=2026-13')).status_code == 400
        assert (await get(app, ME, '/dashboard?month=october')).status_code == 400
        assert (await app.client.get('/dashboard')).status_code == 401
        assert (await get(app, None, '/dashboard')).status_code == 401


class TestReportsDaily:
    async def test_leaves_rent_and_sip_out_and_gives_the_page_its_bars_and_average(self):
        app, fakes = await setup()
        res = (await get(app, ME, '/reports/daily?month=2026-10')).json()
        assert len(res['items']) == 31
        assert [d['spentMinor'] // 100 for d in res['items'][:18]] == DAILY
        assert all(d['spentMinor'] == 0 for d in res['items'][18:])
        assert res['items'][0] == {'day': '2026-10-01', 'spentMinor': 24000}
        assert res['items'][30]['day'] == '2026-10-31'
        assert res['totalMinor'] == R(9709)  # 39,709 - 30,000
        assert res['averageMinor'] // 100 == 539  # "average Rs 539 a day, rent and SIP left out"
        assert res['fixedCategories'] == ['Rent', 'Sip']
        ask = next(c for c in fakes.calls if c.method == 'daily')
        assert sorted(ask.args[1]) == sorted([ID['rent'], ID['sip']])

    async def test_a_future_month_does_not_count_the_month_in_progress_as_finished(self):
        # A Rs 1 rule in a category whose only spend is this month's (the month in progress): with no finished history
        # it is fixed ("no history yet"), not judged against October's half-finished spend, which made it flexible.
        tiny_cloud = [{**r, 'amountMinor': 100} if r['name'] == 'Cloud storage' else r for r in rules()]
        cat_months = [c for c in CAT_MONTHS if not (c['categoryId'] == ID['bills'] and c['month'] != '2026-10')]
        app, _ = await setup(Fakes(rules=lambda: tiny_cloud, cat_months=cat_months))
        res = (await get(app, ME, '/reports/daily?month=2026-11')).json()
        assert 'Bills' in res['fixedCategories']
        assert res['dayOfMonth'] == 0 and res['averageMinor'] == 0 and len(res['items']) == 30
        # the same rule on this month's own report keeps October out of "usual" too (it is not finished yet)
        res = (await get(app, ME, '/reports/daily?month=2026-10')).json()
        assert 'Bills' in res['fixedCategories']


class TestReportsMonths:
    async def test_reproduces_the_trends_data_table_the_pace_and_the_aside(self):
        app, _ = await setup()
        res = (await get(app, ME, '/reports/months?range=6')).json()
        assert res['end'] == '2026-10'
        table = [
            [m['month'], m['incomeMinor'] // 100, m['spentMinor'] // 100, m['keptMinor'] // 100, m['closingMinor'] // 100, m['inProgress']]
            for m in res['items']
        ]  # fmt: skip
        assert table == [
            ['2026-05', 50000, 41200, 8800, 6400, False],
            ['2026-06', 50000, 44800, 5200, 11600, False],
            ['2026-07', 52000, 47300, 4700, 16300, False],
            ['2026-08', 50000, 43100, 6900, 23200, False],
            ['2026-09', 50000, 45900, 4100, 27300, False],
            ['2026-10', 50000, 39709, 10291, 37591, True],
        ]
        assert res['items'][0]['keptRate'] == pytest.approx(0.176, abs=5e-4)  # 17.6%
        assert all(m['pace'] is None for m in res['items'][:5])
        # October: flexible 9,709 / 18 x 31 = 16,720.9 -> Rs 16,720, plus Rent and SIP 30,000 = 46,720; kept 3,280
        assert res['items'][5]['pace'] == {
            'dayOfMonth': 18, 'daysInMonth': 31, 'spentSoFarMinor': R(39709), 'flexibleSoFarMinor': R(9709),
            'fixedMinor': R(30000), 'flexiblePaceMinor': R(16720), 'paceSpentMinor': R(46720), 'paceKeptMinor': R(3280),
        }  # fmt: skip
        avgs = res['averages']
        assert avgs['fullMonths'] == 5 and avgs['avgMonthlySpendMinor'] == R(44460) and avgs['avgKeptMinor'] == R(5940)
        assert avgs['balanceSinceMinor'] == R(31191) and avgs['balanceSinceMonth'] == '2026-05'
        assert avgs['avgKeptRate'] * 100 == pytest.approx(11.8, abs=0.05)

    async def test_range_3_narrows_the_window_and_its_averages_bad_ranges_are_refused(self):
        app, _ = await setup()
        res = (await get(app, ME, '/reports/months?range=3')).json()
        assert [m['month'] for m in res['items']] == ['2026-08', '2026-09', '2026-10']
        a = res['averages']
        assert a['fullMonths'] == 2 and a['avgMonthlySpendMinor'] == R(44500)
        assert a['balanceSinceMinor'] == R(37591 - 23200) and a['balanceSinceMonth'] == '2026-08'
        assert len((await get(app, ME, '/reports/months')).json()['items']) == 6  # default 6
        assert (await get(app, ME, '/reports/months?range=0')).status_code == 400
        assert (await get(app, ME, '/reports/months?range=25')).status_code == 400

    async def test_a_user_with_no_history_gets_zeros_not_errors(self):
        app, _ = await setup(Fakes(empty=True))
        res = (await get(app, ME, '/reports/months')).json()
        assert len(res['items']) == 6
        assert res['items'][5]['pace']['paceSpentMinor'] == 0 and res['items'][5]['pace']['paceKeptMinor'] == 0
        assert res['averages'] == {
            'fullMonths': 0, 'avgMonthlySpendMinor': 0, 'avgKeptMinor': 0, 'avgKeptRate': 0,
            'balanceSinceMinor': 0, 'balanceSinceMonth': None,
        }  # fmt: skip

    async def test_pausing_rent_makes_it_a_flexible_category_fixed_what_your_active_rules_cover(self):
        app, _ = await setup(Fakes(rules=rent_paused))
        pace = (await get(app, ME, '/reports/months')).json()['items'][5]['pace']
        assert pace['fixedMinor'] == R(10000)  # only SIP
        assert pace['flexibleSoFarMinor'] == R(29709)  # Rent's 20,000 now counts as flexible

    async def test_averages_round_half_up_not_to_even(self):
        # Python's round(2.5) is 2; half up gives 3, and -2.5 gives -2
        assert avg(5, 2) == 3 and avg(7, 2) == 4 and avg(-5, 2) == -2 and avg(0, 0) == 0 and avg(10, 4) == 3


class TestCategoryMatrix:
    async def test_reproduces_the_list_food_fun_bills_travel_most_above_usual_first_rent_and_sip_left_out(self):
        app, _ = await setup()
        res = (await get(app, ME, '/reports/category-matrix?range=6')).json()
        assert res['months'] == ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
        assert res['fullMonths'] == 5
        rows = [[i['name'], i['usualMinor'] // 100, i['paceMinor'] // 100, i['changeMinor'] // 100] for i in res['items']]
        assert rows == [
            ['food', 7590, 9330, 1740],  # up Rs 1,740 more
            ['fun', 1430, 2820, 1390],  # up Rs 1,390 more
            ['bills', 2500, 2240, -260],  # down Rs 260 less
            ['travel', 2940, 2330, -610],  # down Rs 610 less
        ]
        assert res['items'][0]['spentSoFarMinor'] == R(5420)
        assert [m['spentMinor'] // 100 for m in res['items'][0]['byMonth']] == [6000, 7800, 9200, 7400, 7550, 5420]


class TestOwnershipAndPlumbing:
    async def test_every_client_call_is_made_for_the_tokens_user_and_zone_whoever_asks(self):
        app, fakes = await setup()
        a, b = uid(), uid()
        urls = ['/dashboard?month=2026-10', '/reports/daily?month=2026-10', '/reports/months?range=6', '/reports/category-matrix?range=6']
        for user, tz in ((a, 'Asia/Kolkata'), (b, 'Europe/Berlin')):
            fakes.calls.clear()
            for u in urls:
                assert (await get(app, user, u, tz)).status_code == 200
            assert len(fakes.calls) > 10
            for c in fakes.calls:
                assert c.as_.user_id == user, f'{c.client}.{c.method}'
                assert c.as_.tz == tz, f'{c.client}.{c.method}'
            touched = {f'{c.client}.{c.method}' for c in fakes.calls}
            for m in (
                'ledger.month_summary', 'ledger.spend_by_category', 'planning.plan', 'planning.budgets', 'planning.alerts',
                'recurring.list', 'ingest.unparsed_count', 'ledger.daily', 'ledger.months', 'ledger.category_months',
            ):  # fmt: skip
                assert m in touched, m

    async def test_ignores_any_user_id_smuggled_in_the_query_string(self):
        app, fakes = await setup()
        a = uid()
        await get(app, a, f'/dashboard?month=2026-10&userId={uid()}')
        assert fakes.calls and all(c.as_.user_id == a for c in fakes.calls)

    async def test_has_no_database_and_stores_nothing_no_pool_no_internal_routes(self):
        fakes = Fakes()
        app = await build_test_app(service='reports', register=make_register(), clients=fakes.clients())
        assert app.deps.pool is None
        res = await app.client.get('/internal/export', headers=AppHarness.headers_for(ME, 'auth'))
        assert res.status_code == 404

    async def test_neighbour_calls_run_concurrently(self):
        # Every neighbour call starts before any answer is awaited, so one slow service does not add up with the others.
        app, fakes = await setup(Fakes(delay=0.01))
        assert (await get(app, ME, '/dashboard')).status_code == 200
        assert len(fakes.calls) == 7 and fakes.peak == 7
        fakes.calls.clear()
        fakes.peak = 0
        assert (await get(app, ME, '/reports/months')).status_code == 200
        assert len(fakes.calls) == 3 and fakes.peak == 3
