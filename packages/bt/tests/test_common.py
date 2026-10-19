import json
from datetime import datetime
from typing import ClassVar

import pytest
from bt.common import (
    HEADERS,
    BaseEnv,
    Ctx,
    Cursor,
    EnvError,
    Errors,
    Parts,
    add_days,
    add_months,
    add_months_clamped,
    check_password,
    create_logger,
    date_key,
    days_in_month,
    decode_cursor,
    encode_cursor,
    format_inr,
    limit_status,
    load_env,
    month_key,
    month_progress,
    month_range,
    months_ending_at,
    normalize_tag,
    pace_projection,
    parse_rupees,
    password_label,
    password_score,
    reaches_pct,
    round_to,
    safe_per_day,
    to_iso,
    to_page,
    zoned_to_utc,
)


def at(s: str) -> datetime:
    return datetime.fromisoformat(s)


class TestMoney:
    def test_formats_with_indian_grouping(self):
        assert format_inr(3759100) == '37,591'
        assert format_inr(123456789000) == '1,23,45,67,890'
        assert format_inr(45050) == '450.50'
        assert format_inr(-120000, symbol=True) == '-₹1,200'
        assert format_inr(0) == '0'
        assert format_inr(1234567890) == '1,23,45,678.90'
        assert format_inr(100, force_decimals=True) == '1.00'

    def test_rejects_non_integers(self):
        with pytest.raises(TypeError):
            format_inr(1.5)  # type: ignore[arg-type]

    def test_parses_rupees_to_paise(self):
        assert parse_rupees('450') == 45000
        assert parse_rupees('₹1,234.5') == 123450
        assert parse_rupees('Rs. 99.05') == 9905
        assert parse_rupees('-12') == -1200
        assert parse_rupees(450) == 45000
        assert parse_rupees(450.5) == 45050
        with pytest.raises(ValueError):
            parse_rupees('12.345')
        with pytest.raises(ValueError):
            parse_rupees('abc')
        with pytest.raises(ValueError):
            parse_rupees(1.234)

    def test_rounds_to_ten_rupees_halves_up(self):
        assert round_to(46724) == 47000
        assert round_to(500) == 1000  # halves up, not banker's rounding
        assert round_to(499) == 0
        assert round_to(1500) == 2000
        assert round_to(46724.0) == 47000


class TestTime:
    tz = 'Asia/Kolkata'

    def test_month_key_uses_the_user_zone_not_utc(self):
        assert month_key(at('2026-09-30T20:00:00+00:00'), self.tz) == '2026-10'  # 01:30 IST on 1 Oct
        assert month_key(at('2026-09-30T20:00:00+00:00'), 'UTC') == '2026-09'
        assert date_key(at('2026-09-30T20:00:00+00:00'), self.tz) == '2026-10-01'

    def test_month_range_is_local_midnight_to_next_local_midnight(self):
        r = month_range('2026-10', self.tz)
        assert to_iso(r.start) == '2026-09-30T18:30:00.000Z'
        assert to_iso(r.end) == '2026-10-31T18:30:00.000Z'

    def test_handles_dst_zones(self):
        assert to_iso(zoned_to_utc(Parts(2026, 3, 29, 12), 'Europe/London')) == '2026-03-29T11:00:00.000Z'
        assert to_iso(month_range('2026-03', 'Europe/London').end) == '2026-03-31T23:00:00.000Z'
        assert to_iso(zoned_to_utc({'y': 2026, 'm': 7, 'd': 1}, 'America/New_York')) == '2026-07-01T04:00:00.000Z'

    def test_progress_days_and_month_math(self):
        p = month_progress(at('2026-10-18T10:00:00+05:30'), self.tz)
        assert (p.month, p.day, p.days, p.days_left) == ('2026-10', 18, 31, 14)
        assert days_in_month('2028-02') == 29
        assert days_in_month('2026-12') == 31
        assert add_months('2026-11', 3) == '2027-02'
        assert add_months('2026-01', -1) == '2025-12'
        assert months_ending_at('2026-10', 6) == ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10']
        assert add_months_clamped('2026-01-31', 1, 31) == '2026-02-28'
        assert add_months_clamped('2026-02-28', 1, 31) == '2026-03-31'
        assert add_months_clamped('2026-01-31', 1) == '2026-02-28'
        assert add_days('2026-12-31', 1) == '2027-01-01'
        assert add_days('2028-03-01', -1) == '2028-02-29'

    def test_rejects_bad_month_keys(self):
        with pytest.raises(ValueError):
            days_in_month('2026-13')
        with pytest.raises(ValueError):
            add_months('2026-1', 1)


class TestMetricsMatchTheDesignDataset:
    def test_pace_for_october(self):
        # Food spent 5,420 by day 18 of 31 -> 9,334.4 -> ₹9,330
        assert pace_projection(542000, 18, 31) == 933000
        assert pace_projection(164000, 18, 31) == 282000
        assert pace_projection(100, 0, 31) == 0

    def test_status_and_exact_percentages(self):
        assert reaches_pct(8000, 10000, 80)
        assert not reaches_pct(7999, 10000, 80)
        assert limit_status(spent=8200, limit=10000, alert_pct=80, projected=15000) == 'close'
        assert limit_status(spent=5000, limit=10000, alert_pct=80, projected=12000) == 'fast'
        assert limit_status(spent=10000, limit=10000, alert_pct=80, projected=12000) == 'over'
        assert limit_status(spent=1000, limit=10000, alert_pct=80, projected=9000) == 'ok'

    def test_safe_to_spend_per_day(self):
        assert safe_per_day(579100, 14) == 41364
        assert safe_per_day(-5, 14) == 0
        assert safe_per_day(100, 0) == 0


class TestTagsCursorPasswordPolicy:
    def test_normalises_tags(self):
        assert normalize_tag('  #Bank   Charges ') == 'bank charges'
        assert normalize_tag("Ｆｏｏｄ & drink") == 'food & drink'
        for bad in ('#', 'a' * 33, '-dash', 'x<y'):
            with pytest.raises(Exception) as e:
                normalize_tag(bad)
            assert e.value.code == 'validation_failed'  # type: ignore[attr-defined]
        assert normalize_tag('a' * 32) == 'a' * 32

    def test_round_trips_cursors(self):
        c = Cursor('2026-10-18T10:00:00.000Z', 'abc')
        assert decode_cursor(encode_cursor(c)) == c
        assert decode_cursor(None) is None
        assert '=' not in encode_cursor(c)
        for bad in ('###', 'e30', encode_cursor(Cursor('not a date', 'x'))):
            with pytest.raises(Exception) as e:
                decode_cursor(bad)
            assert e.value.code == 'bad_request'  # type: ignore[attr-defined]

    def test_to_page_trims_and_points_at_the_last_row(self):
        rows = [{'t': f'2026-10-0{i}T00:00:00.000Z', 'id': str(i)} for i in range(1, 5)]
        page = to_page(rows, 3, lambda r: Cursor(r['t'], r['id']))
        assert len(page.items) == 3
        assert decode_cursor(page.next_cursor) == Cursor('2026-10-03T00:00:00.000Z', '3')
        assert to_page(rows[:2], 3, lambda r: Cursor(r['t'], r['id'])).next_cursor is None

    def test_password_score_follows_the_design(self):
        c = check_password('abc', 'a@b.co')
        assert password_label(password_score('abc', c)) == 'weak'
        ok = check_password('correct-horse-battery', 'sam@example.com')
        assert password_label(password_score('correct-horse-battery', ok)) == 'strong'
        assert check_password('mysamword12345', 'sam@example.com').email is False
        assert check_password('password1234').common is False
        assert check_password('', '').len is False


class TestErrorsAndContext:
    def test_error_shapes(self):
        assert Errors.not_found('Thing').to_json() == {'error': {'code': 'not_found', 'message': 'Thing not found'}}
        e = Errors.conflict('dup', {'id': 1})
        assert (e.status, e.to_json()['error']['details']) == (409, {'id': 1})
        assert Errors.upstream('ledger').details == {'service': 'ledger'}
        assert Errors.two_factor_required().status == 401
        assert Errors.locked().status == 423
        assert Errors.too_many().status == 429

    def test_ctx_is_immutable_and_headers_are_namespaced(self):
        c = Ctx(user_id='u', tz='UTC', request_id='r')
        with pytest.raises(AttributeError):
            c.tz = 'x'  # type: ignore[misc]
        assert HEADERS.internal_token == 'x-internal-token'


class TestConfig:
    base: ClassVar[dict[str, str]] = {'SERVICE_NAME': 'ledger', 'PORT': '3002', 'DATABASE_URL': 'postgres://x', 'INTERNAL_SECRET': 'x' * 32}

    def test_loads_defaults_and_coerces(self):
        env = load_env(BaseEnv, self.base)
        assert (env.PORT, env.APP_ENV, env.LOG_LEVEL, env.LEDGER_URL) == (3002, 'development', 'info', 'http://ledger:3002')

    def test_node_env_is_a_fallback(self):
        assert load_env(BaseEnv, {**self.base, 'NODE_ENV': 'production'}).APP_ENV == 'production'
        assert load_env(BaseEnv, {**self.base, 'NODE_ENV': 'production', 'APP_ENV': 'test'}).APP_ENV == 'test'

    def test_reports_every_problem_at_once(self):
        with pytest.raises(EnvError) as e:
            load_env(BaseEnv, {'INTERNAL_SECRET': 'short', 'LOG_LEVEL': 'loud'})
        msg = str(e.value)
        for name in ('SERVICE_NAME', 'PORT', 'DATABASE_URL', 'INTERNAL_SECRET', 'LOG_LEVEL'):
            assert name in msg

    def test_log_level_aliases(self):
        assert load_env(BaseEnv, {**self.base, 'LOG_LEVEL': 'WARN'}).LOG_LEVEL == 'warning'
        assert load_env(BaseEnv, {**self.base, 'LOG_LEVEL': 'silent'}).LOG_LEVEL == 'silent'

    def test_secrets_stay_out_of_repr(self):
        assert 'xxxxxxxx' not in repr(load_env(BaseEnv, self.base))


class TestLogger:
    def test_writes_json_lines_and_redacts(self):
        import io

        buf = io.StringIO()
        log = create_logger('ledger', 'info', stream=buf)
        log.debug('hidden')
        log.info('req', status=200, email='a@b.co', nested={'amountMinor': 5, 'ok': 1}, err=ValueError('x'))
        log.bind(rid='r1').warning('w')
        first, second = (json.loads(x) for x in buf.getvalue().splitlines())
        assert first['msg'] == 'req' and first['service'] == 'ledger' and first['status'] == 200
        assert first['email'] == '[redacted]' and first['nested'] == {'amountMinor': '[redacted]', 'ok': 1}
        assert first['err'] == 'ValueError: x'
        assert second['rid'] == 'r1' and second['level'] == 'warning'

    def test_silent_writes_nothing(self):
        import io

        buf = io.StringIO()
        create_logger('x', 'silent', stream=buf).critical('boom')
        assert buf.getvalue() == ''
