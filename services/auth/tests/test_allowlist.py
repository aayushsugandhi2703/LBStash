"""The optional list of addresses the web app accepts: set with a fresh code, never locks the caller out, applies to
sign-in, token refresh and the gateway's session check."""

import pytest_asyncio
from auth_harness import Account, Browser, Harness, make_harness
from bt_auth.allowlist import allows, normalize_entry

HOME = '203.0.113.7'
ELSEWHERE = '198.51.100.9'


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def h(db):
    harness = await make_harness(db)
    yield harness
    await harness.close()


async def account_at(h: Harness, email: str, ip: str = HOME) -> tuple[Browser, Account]:
    b = h.browser(ip=ip)
    return b, await b.create_account(h, email)


async def check(b: Browser, ip: str | None) -> dict:
    return (await b.internal('POST', '/internal/sessions/check', None, {'sid': b.sid(), 'ip': ip})).body


class TestTheMatching:
    def test_addresses_ranges_and_both_ip_versions_are_normalised_and_matched(self) -> None:
        assert normalize_entry(' 203.0.113.7 ') == '203.0.113.7'
        assert normalize_entry('203.0.113.0/24') == '203.0.113.0/24'
        assert normalize_entry('2001:DB8::1') == '2001:db8::1'
        for bad in ['', 'nope', '203.0.113.256', '203.0.113.0/33']:
            try:
                normalize_entry(bad)
            except ValueError:
                continue
            raise AssertionError(bad)
        assert allows([], None) and allows([], '1.2.3.4')  # no list: anywhere
        assert allows(['203.0.113.7'], '203.0.113.7')
        assert allows(['203.0.113.0/24'], '203.0.113.99')
        assert allows(['203.0.113.7'], '::ffff:203.0.113.7')  # IPv4 seen through an IPv6 socket
        assert not allows(['203.0.113.7'], '203.0.113.8')
        assert not allows(['203.0.113.7'], None)  # a list never lets an unknown address through
        assert not allows(['203.0.113.7'], 'garbage')
        assert not allows(['2001:db8::/32'], '203.0.113.7')


class TestSettingTheList:
    async def test_needs_a_fresh_code_and_refuses_a_list_without_the_callers_own_address_or_with_junk(self, h: Harness) -> None:
        b, who = await account_at(h, 'lock-set@example.com')
        assert (await b.call('GET', '/auth/allowed-ips')).body == {'ips': [], 'yourIp': HOME}

        no_code = await b.call('PUT', '/auth/allowed-ips', {'ips': [HOME]})
        assert no_code.status == 400  # the body must carry a 6-digit code

        locked_out = await b.call('PUT', '/auth/allowed-ips', {'ips': [ELSEWHERE], 'code': await h.code(who.user_id, who.secret)})
        assert locked_out.status == 400 and 'lock yourself out' in str(locked_out.body)
        junk = await b.call('PUT', '/auth/allowed-ips', {'ips': ['not-an-ip'], 'code': await h.code(who.user_id, who.secret)})
        assert junk.status == 400
        wrong = await b.call('PUT', '/auth/allowed-ips', {'ips': [HOME], 'code': '000000'})
        assert wrong.status == 401
        assert (await b.call('GET', '/auth/allowed-ips')).body['ips'] == []  # nothing was saved

        ok = await b.call('PUT', '/auth/allowed-ips', {'ips': [HOME, HOME, ' 198.51.100.0/24 '], 'code': await h.code(who.user_id, who.secret)})
        assert ok.status == 200 and ok.body['ips'] == [HOME, '198.51.100.0/24']
        assert 'allowlist.changed' in [r['action'] for r in await h.t.admin_pool.query('SELECT action FROM auth.audit_log WHERE user_id = $1', [who.user_id])]


class TestEnforcement:
    async def test_the_session_check_sign_in_and_refresh_all_refuse_other_addresses_and_an_empty_list_lifts_it(self, h: Harness) -> None:
        b, who = await account_at(h, 'lock-enforce@example.com')
        assert (await check(b, ELSEWHERE))['valid'] is True  # no list yet
        await b.call('PUT', '/auth/allowed-ips', {'ips': [HOME], 'code': await h.code(who.user_id, who.secret)})

        assert (await check(b, HOME))['valid'] is True
        assert (await check(b, ELSEWHERE))['valid'] is False
        assert (await check(b, None))['valid'] is False

        # a second browser on another address knows the password and the code and still gets no session
        other = h.browser(ip=ELSEWHERE)
        refused = await other.sign_in(h, who, 'lock-enforce@example.com')
        assert refused.status == 403 and 'not allowed from this address' in str(refused.body)
        assert other.access is None

        # a copied refresh cookie used from another address does not renew anything
        thief = h.browser(ip=ELSEWHERE)
        thief.jar.update({k: v for k, v in b.jar.items()})
        assert (await thief.call('POST', '/auth/refresh', None, no_cookies=False)).status == 401

        # the same sign-in from a listed address works
        home2 = h.browser(ip=HOME)
        assert (await home2.sign_in(h, who, 'lock-enforce@example.com')).status == 200

        # emptying the list lifts the limit
        assert (await b.call('PUT', '/auth/allowed-ips', {'ips': [], 'code': await h.code(who.user_id, who.secret)})).status == 200
        assert (await check(b, ELSEWHERE))['valid'] is True
        assert (await h.browser(ip=ELSEWHERE).sign_in(h, who, 'lock-enforce@example.com')).status == 200
