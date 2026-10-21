import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import ClassVar
from zoneinfo import ZoneInfo

import pytest
from gateway_helpers import (
    ACCESS_SECRET,
    NAMES,
    USER,
    Fakes,
    Gateway,
    Login,
    Reply,
    Seen,
    auth_fake,
    login,
    raw_status,
)
from lbstash.common import DEMO_USER_ID
from lbstash.crypto import InternalClaims, sign_access_token

MakeGw = Callable[..., Awaitable[Gateway]]
JSON = {'content-type': 'application/json'}


@pytest.fixture(autouse=True)
def _auth(fakes: Fakes, alive: set[str], setup_limited: set[str]) -> None:
    auth_fake(fakes.auth, alive, limited=setup_limited)


@pytest.fixture
def signed_in(alive: set[str]) -> Callable[..., Login]:
    """A signed-in browser whose session auth says is alive."""

    def make(**opts: object) -> Login:
        lg = login(**opts)  # type: ignore[arg-type]
        alive.add(lg.sid)
        return lg

    return make


def session_checks(fakes: Fakes) -> int:
    return len([s for s in fakes.auth.seen if s.url == '/internal/sessions/check'])


class TestSessionCheck:
    async def test_no_cookie_401_in_the_standard_shape_nothing_forwarded(self, gw: Gateway, fakes: Fakes) -> None:
        res = await gw.get('/transactions')
        assert res.status_code == 401
        assert res.json()['error']['code'] == 'unauthorized'
        assert fakes.transactions.seen == []

    async def test_tampered_wrongly_signed_and_expired_tokens_401(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        jwt = lg.cookie.split('lbstash_access=')[1].split(';')[0]
        tampered = jwt[:-4] + ('BBBB' if jwt.endswith('AAAA') else 'AAAA')
        wrong_key = sign_access_token('another-secret-another-secret-another!!', sub=USER, sid=lg.sid, tz='UTC')
        expired = sign_access_token(ACCESS_SECRET, sub=USER, sid=lg.sid, tz='UTC', ttl_seconds=-30)
        for t in [tampered, wrong_key, expired, 'garbage']:
            res = await gw.get('/transactions', headers={'cookie': f'lbstash_access={t}'})
            assert res.status_code == 401, t[:12]
        assert fakes.transactions.seen == []
        assert session_checks(fakes) == 0

    async def test_a_revoked_session_401_and_no_is_never_cached(self, gw: Gateway, fakes: Fakes, alive: set[str]) -> None:
        lg = login()  # not in `alive`
        assert (await gw.get('/transactions', headers=lg.headers)).status_code == 401
        assert (await gw.get('/transactions', headers=lg.headers)).status_code == 401
        assert session_checks(fakes) == 2
        alive.add(lg.sid)
        assert (await gw.get('/transactions', headers=lg.headers)).status_code == 200

    async def test_a_live_session_is_asked_about_once_then_served_from_the_cache(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        for _ in range(3):
            assert (await gw.get('/transactions', headers=lg.headers)).status_code == 200
        assert session_checks(fakes) == 1

    async def test_keeps_setup_limited_sessions_out_of_app_data_routes_while_allowing_auth_setup_and_me(
        self, gw: Gateway, fakes: Fakes, alive: set[str], setup_limited: set[str], signed_in
    ) -> None:
        user = {'id': USER, 'email': 'test@example.com', 'name': None, 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None}
        auth_fake(fakes.auth, alive, lambda s: Reply(body={'user': user}) if s.url == '/internal/me' else None, setup_limited)
        lg = signed_in()
        setup_limited.add(lg.sid)

        denied = await gw.get('/transactions', headers=lg.headers)
        assert denied.status_code == 403
        assert denied.json()['error']['details'] == {'setupRequired': True}
        assert fakes.transactions.seen == []

        factors = await gw.get('/auth/factors', headers=lg.headers)
        assert factors.status_code == 200
        assert fakes.auth.last().url == '/auth/factors'

        assert (await gw.get('/me', headers=lg.headers)).status_code == 200

    async def test_a_limited_session_may_only_read_me(self, gw: Gateway, fakes: Fakes, setup_limited: set[str], signed_in) -> None:
        lg = signed_in()
        setup_limited.add(lg.sid)
        res = await gw.request('PATCH', '/me', headers={**lg.headers, **JSON}, content='{}')
        assert res.status_code == 403
        assert fakes.auth.non_check() == []

    async def test_rechecks_setup_limited_sessions_so_completed_setup_takes_effect_immediately(
        self, gw: Gateway, fakes: Fakes, setup_limited: set[str], signed_in
    ) -> None:
        lg = signed_in()
        setup_limited.add(lg.sid)
        assert (await gw.get('/transactions', headers=lg.headers)).status_code == 403
        setup_limited.discard(lg.sid)
        assert (await gw.get('/transactions', headers=lg.headers)).status_code == 200
        assert session_checks(fakes) == 2

    async def test_auth_being_down_is_an_error_answer_not_a_sign_out(self, gw: Gateway, fakes: Fakes) -> None:
        lg = login()
        fakes.auth.handler = lambda _s: Reply(500, {'error': {'code': 'internal', 'message': 'x'}})
        res = await gw.get('/transactions', headers=lg.headers)
        assert res.status_code == 500  # the client maps the upstream error through; never 401

    async def test_auth_unreachable_is_502_not_401(self, gw: Gateway, fakes: Fakes) -> None:
        gw.network.down.add('auth')
        res = await gw.get('/transactions', headers=login().headers)
        assert res.status_code == 502
        assert res.json()['error']['code'] == 'upstream_failed'


class TestForwarding:
    async def test_signs_the_request_as_the_gateway_for_the_cookie_user_proxied_with_the_request_id_the_browser_cookie_stays_behind(
        self, gw: Gateway, fakes: Fakes, signed_in
    ) -> None:
        lg = signed_in(tz='Asia/Tokyo')
        res = await gw.get(
            '/transactions?month=2026-10&x=1', headers={**lg.headers, 'accept': 'application/json', 'x-forwarded-for': '1.2.3.4'}
        )
        assert res.status_code == 200
        seen = fakes.transactions.last()
        assert seen.url == '/transactions?month=2026-10&x=1'
        assert fakes.transactions.claims() == InternalClaims(
            svc='gateway', user_id=USER, tz='Asia/Tokyo', request_id=res.headers['x-request-id'], proxied=True
        )
        assert 'cookie' not in seen.headers
        assert seen.headers['x-request-id'] == res.headers['x-request-id']
        assert seen.headers['x-forwarded-for'] == '1.2.3.4'
        assert seen.headers['accept'] == 'application/json'

    async def test_forwards_method_json_body_byte_for_byte_and_content_type(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        body = '{ "amountMinor":  4500,"note":"a b" }'
        res = await gw.request('POST', '/credits', headers={**lg.headers, **JSON}, content=body)
        assert res.status_code == 200
        assert fakes.transactions.last().method == 'POST'
        assert fakes.transactions.last().body == body
        assert 'application/json' in fakes.transactions.last().headers['content-type']

    async def test_forwards_a_delete_with_a_body(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        res = await gw.request('DELETE', '/devices/abc', headers={**lg.headers, **JSON}, content='{"code":"000000"}')
        assert res.status_code == 200
        assert (fakes.ingest.last().method, fakes.ingest.last().body) == ('DELETE', '{"code":"000000"}')

    async def test_drops_a_client_supplied_x_internal_token_and_signs_its_own(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        await gw.get('/transactions', headers={**lg.headers, 'x-internal-token': 'forged'})
        assert fakes.transactions.last().headers['x-internal-token'] != 'forged'
        assert fakes.transactions.claims().proxied is True
        # same on a public path
        await gw.request('POST', '/ingest/message', headers={'x-internal-token': 'forged', **JSON}, content='{}')
        assert fakes.ingest.last().headers['x-internal-token'] != 'forged'

    async def test_builds_upstream_headers_from_scratch(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        sent = {
            'host': 'evil.example', 'x-forwarded-host': 'evil.example', 'x-forwarded-proto': 'ftp', 'x-forwarded-for': '1.2.3.4',
            'forwarded': 'for=6.6.6.6', 'authorization': 'Bearer abc', 'x-telegram-bot-api-secret-token': 'tok', 'x-real-ip': '9.9.9.9',
        }  # fmt: skip
        await gw.get('/transactions', headers={**lg.headers, **sent})
        got = fakes.transactions.last().headers
        assert got['host'] == 'transactions.test'
        for h in ('x-forwarded-host', 'x-forwarded-proto', 'forwarded', 'authorization', 'x-telegram-bot-api-secret-token', 'x-real-ip'):
            assert h not in got, h
        assert got['x-forwarded-for'] == '1.2.3.4'

    async def test_passes_status_and_body_through_and_every_set_cookie(self, gw: Gateway, fakes: Fakes, alive: set[str]) -> None:
        cookies = [
            'lbstash_access=a; Path=/; HttpOnly; Secure; SameSite=Strict',
            'lbstash_refresh=r; Path=/api/auth; HttpOnly; Secure; SameSite=Strict',
            'lbstash_csrf=c; Path=/; Secure; SameSite=Strict',
        ]
        fakes.auth.handler = lambda s: (
            Reply(200, {'next': '2fa'}, cookies) if s.url == '/auth/login' else Reply(409, {'error': {'code': 'conflict', 'message': 'nope'}})
        )
        ok = await gw.request('POST', '/api/auth/login', headers=JSON, content='{"email":"a@b.c","password":"x"}')
        assert ok.json() == {'next': '2fa'}
        sc = ok.headers.get_list('set-cookie')
        assert len(sc) == 3
        assert [c.split('=')[0] for c in sc] == ['lbstash_access', 'lbstash_refresh', 'lbstash_csrf']
        bad = await gw.request('POST', '/auth/refresh', headers=JSON, content='{}')
        assert bad.status_code == 409
        assert bad.json()['error']['code'] == 'conflict'

    async def test_gives_auth_and_only_auth_the_cookies_so_the_refresh_cookie_reaches_auth(self, gw: Gateway, fakes: Fakes) -> None:
        res = await gw.request('POST', '/auth/refresh', headers={'cookie': 'lbstash_refresh=abc', **JSON}, content='{}')
        assert res.status_code == 200
        assert fakes.auth.last().headers['cookie'] == 'lbstash_refresh=abc'
        assert fakes.auth.claims().user_id is None  # public path: token without a user

    async def test_only_ingest_gets_authorization_and_only_telegram_the_secret_header(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        h = {'authorization': 'Bearer t', 'x-telegram-bot-api-secret-token': 'tok', **JSON}
        await gw.request('POST', '/telegram/webhook/s', headers=h, content='{}')
        assert 'authorization' not in fakes.telegram.last().headers
        assert fakes.telegram.last().headers['x-telegram-bot-api-secret-token'] == 'tok'
        await gw.request('POST', '/ingest/message', headers=h, content='{}')
        assert fakes.ingest.last().headers['authorization'] == 'Bearer t'
        assert 'x-telegram-bot-api-secret-token' not in fakes.ingest.last().headers

    async def test_upstream_down_502_upstream_failed(self, gw: Gateway, signed_in) -> None:
        lg = signed_in()
        gw.network.down.add('recurring')
        res = await gw.get('/recurring', headers=lg.headers)
        assert res.status_code == 502
        assert res.json()['error']['code'] == 'upstream_failed'
        assert res.json()['error']['details'] == {'service': 'recurring'}

    async def test_upstream_timeout_502_upstream_failed(self, make_gw: MakeGw, signed_in) -> None:
        gw = await make_gw(UPSTREAM_TIMEOUT_MS=50)
        lg = signed_in()
        gw.network.slow['transactions'] = 1.0
        res = await gw.get('/transactions', headers=lg.headers)
        assert res.status_code == 502
        assert res.json()['error']['code'] == 'upstream_failed'

    async def test_the_shared_proxy_client_is_closed_when_the_server_shuts_down(self, gw: Gateway) -> None:
        client = gw.app.state.proxy_client
        assert not client.is_closed
        messages = iter([{'type': 'lifespan.startup'}, {'type': 'lifespan.shutdown'}])
        sent: list[str] = []

        async def receive() -> dict[str, str]:
            return next(messages)

        async def send(message: dict[str, str]) -> None:
            sent.append(message['type'])

        await gw.app({'type': 'lifespan', 'asgi': {'version': '3.0'}}, receive, send)
        assert sent == ['lifespan.startup.complete', 'lifespan.shutdown.complete']
        assert client.is_closed


ROUTES = [
    ('GET', '/transactions', 'transactions'), ('GET', '/transactions/abc', 'transactions'), ('GET', '/categories', 'transactions'),
    ('GET', '/balance-checks', 'transactions'), ('POST', '/balance-check', 'transactions'),
    ('POST', '/me/email', 'auth'), ('PATCH', '/me', 'auth'), ('DELETE', '/auth/session', 'auth'), ('GET', '/sessions', 'auth'),
    ('POST', '/account/export', 'auth'),
    ('GET', '/devices', 'ingest'), ('GET', '/unparsed', 'ingest'), ('GET', '/plans/2026-10', 'planning'),
    ('GET', '/budgets', 'planning'), ('GET', '/alerts', 'planning'),
    ('GET', '/recurring', 'recurring'), ('GET', '/dashboard', 'reports'), ('GET', '/reports/months', 'reports'),
    ('POST', '/telegram/pairing', 'telegram'),
]  # fmt: skip


class TestRouting:
    @pytest.mark.parametrize(('method', 'url', 'svc'), ROUTES, ids=[f'{m} {u} -> {s}' for m, u, s in ROUTES])
    async def test_route_goes_to_its_service_only(self, gw: Gateway, fakes: Fakes, signed_in, method: str, url: str, svc: str) -> None:
        lg = signed_in()
        mutating = method != 'GET'
        res = await gw.request(method, url, headers={**lg.headers, **(JSON if mutating else {})}, content='{}' if mutating else None)
        assert res.status_code == 200
        for other in NAMES:
            hits = fakes[other].non_check()
            assert len(hits) == (1 if other == svc else 0), f'{other} for {url}'

    async def test_accepts_the_api_prefix_and_strips_it(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        assert (await gw.get('/api/budgets?month=2026-10', headers=lg.headers)).status_code == 200
        assert fakes.planning.last().url == '/budgets?month=2026-10'

    async def test_unknown_paths_are_404_for_a_signed_in_user_and_401_otherwise_internal_is_never_routed(
        self, gw: Gateway, fakes: Fakes, signed_in
    ) -> None:
        lg = signed_in()
        assert (await gw.get('/nothing-here', headers=lg.headers)).status_code == 404
        assert (await gw.get('/internal/me', headers=lg.headers)).status_code == 404
        assert (await gw.get('/internal/me')).status_code == 401
        for s in fakes.values():
            assert [x for x in s.seen if x.url.startswith('/internal/') and x.url != '/internal/sessions/check'] == []

    async def test_refuses_dot_segments_and_encoded_slashes_before_routing(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        # Raw request targets: an HTTP client would normalise them before they reached us.
        lg = signed_in()
        for url in [b'/transactions/../internal/me', b'/transactions/%2e%2e/auth', b'/transactions%2fx', b'/transactions//x', b'/transactions%01x', b'/api/transactions/%2E/x']:
            assert await raw_status(gw.app, url, lg.headers) == 400, url
        # A line break never matches the framework's catch-all route at all: refused (404) before it could be forwarded.
        assert await raw_status(gw.app, b'/transactions%0d%0ax', lg.headers) in (400, 404)
        assert await raw_status(gw.app, b'/transactions', lg.headers) == 200
        assert [s.url for s in fakes.transactions.seen] == ['/transactions']

    async def test_routes_the_path_the_guard_checked_not_a_second_decoding_of_it(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        # `%61pi` decodes to `api`, but the raw path has no prefix, so it is one unknown path (and never `/me`).
        assert await raw_status(gw.app, b'/%61pi/me', lg.headers) == 404
        assert fakes.transactions.seen == []

    async def test_a_trailing_slash_does_not_dodge_a_composed_route_or_the_guard(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        assert (await gw.get('/me/')).status_code == 401
        assert (await gw.get('/settings/')).status_code == 401


class TestCsrf:
    async def _post(self, gw: Gateway, headers: dict[str, str], url: str = '/credits'):
        return await gw.request('POST', url, headers={**headers, **JSON}, content='{}')

    async def test_a_mutation_needs_x_csrf_token_equal_to_the_bt_csrf_cookie(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        assert (await self._post(gw, {'cookie': lg.cookie})).status_code == 403
        assert (await self._post(gw, {'cookie': lg.cookie, 'x-csrf-token': 'other'})).status_code == 403
        bare = lg.cookie.split('; lbstash_csrf=')[0]
        assert (await self._post(gw, {'cookie': bare, 'x-csrf-token': lg.csrf})).status_code == 403
        assert (await self._post(gw, {'cookie': lg.cookie, 'x-csrf-token': ''})).status_code == 403
        assert (await self._post(gw, lg.headers)).status_code == 200
        assert (await self._post(gw, lg.headers, '/credits')).status_code == 200
        assert len(fakes.transactions.seen) == 2
        assert (await self._post(gw, {'cookie': lg.cookie})).json()['error']['code'] == 'forbidden'

    async def test_the_cookie_is_compared_percent_decoded_like_the_browser_sends_it(self, gw: Gateway, signed_in) -> None:
        lg = signed_in()
        base = lg.cookie.split('; lbstash_csrf=')[0]
        cookie = f'{base}; lbstash_csrf=ab%2Bc%3Dd%2Fe'
        assert (await self._post(gw, {'cookie': cookie, 'x-csrf-token': 'ab+c=d/e'})).status_code == 200
        assert (await self._post(gw, {'cookie': cookie, 'x-csrf-token': 'ab%2Bc%3Dd%2Fe'})).status_code == 403

    async def test_every_mutating_verb_is_checked_reads_are_not(self, gw: Gateway, signed_in) -> None:
        lg = signed_in()
        for method in ('PUT', 'PATCH', 'DELETE'):
            res = await gw.request(method, '/categories/x', headers={'cookie': lg.cookie})
            assert res.status_code == 403, method
        assert (await gw.get('/categories', headers={'cookie': lg.cookie})).status_code == 200

    async def test_exempt_paths_pass_without_a_token_others_need_a_session_first_401_before_403(self, gw: Gateway) -> None:
        assert (await self._post(gw, {}, '/auth/login')).status_code == 200
        assert (await self._post(gw, {}, '/auth/reset/confirm')).status_code == 200
        assert (await self._post(gw, {}, '/credits')).status_code == 401
        assert (await self._post(gw, {}, '/auth/session')).status_code == 401


class TestComposedRoutes:
    month = datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y-%m')
    user: ClassVar[dict[str, object]] = {'id': USER, 'email': 'a@b.c', 'name': 'Asha', 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None}

    @pytest.fixture(autouse=True)
    def _fakes(self, fakes: Fakes, alive: set[str]) -> None:
        summary = {
            'month': self.month, 'carriedOverMinor': 0, 'incomeMinor': 0, 'spentMinor': 0, 'availableMinor': 0,
            'untaggedCount': 4, 'unaccountedCount': 0, 'lastCapturedAt': None,
        }  # fmt: skip
        auth_fake(fakes.auth, alive, lambda s: Reply(body={'user': self.user}) if s.url == '/internal/me' else None)
        fakes.planning.handler = lambda _s: Reply(body={'unreadCount': 2, 'items': []})
        fakes.ingest.handler = lambda _s: Reply(body={'open': 3})
        fakes.transactions.handler = lambda _s: Reply(body=summary)

    async def test_get_me_composes_the_user_and_three_counts(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        res = await gw.get('/api/me', headers=lg.headers)
        assert res.status_code == 200
        assert res.json() == {**self.user, 'alertBadgeCount': 2, 'needsLookCount': 3, 'untaggedCount': 4, 'demo': False}
        assert fakes.transactions.last().url == f'/internal/aggregates/summary?month={self.month}'
        assert fakes.auth.claims().proxied is False  # the gateway's own calls are not "from outside"

    async def test_get_me_survives_a_failing_optional_dependency_count_0(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        fakes.planning.handler = lambda _s: Reply(500, {'error': {'code': 'internal', 'message': 'x'}})
        res = await gw.get('/me', headers=signed_in().headers)
        assert res.status_code == 200
        assert res.json() == {**self.user, 'alertBadgeCount': 0, 'needsLookCount': 3, 'untaggedCount': 4, 'demo': False}

    async def test_get_me_degrades_a_slow_optional_dependency_to_0_after_2_5_seconds(self, gw: Gateway, fakes: Fakes, signed_in, monkeypatch) -> None:
        from lbstash_gateway import compose

        monkeypatch.setattr(compose, 'OPTIONAL_TIMEOUT_S', 0.05)
        original = gw.app.state.deps.clients.ingest.unparsed_count

        async def slow(as_):
            await asyncio.sleep(1)
            return await original(as_)

        monkeypatch.setattr(gw.app.state.deps.clients.ingest, 'unparsed_count', slow)
        res = await gw.get('/me', headers=signed_in().headers)
        assert res.status_code == 200
        assert res.json()['needsLookCount'] == 0
        assert res.json()['alertBadgeCount'] == 2

    async def test_get_me_fails_when_auth_the_user_itself_fails(self, gw: Gateway, fakes: Fakes, alive: set[str], signed_in) -> None:
        auth_fake(fakes.auth, alive, lambda s: Reply(404, {'error': {'code': 'not_found', 'message': 'gone'}}) if s.url == '/internal/me' else None)
        assert (await gw.get('/me', headers=signed_in().headers)).status_code == 404

    class TestSettings:
        state: ClassVar[dict[str, dict[str, object]]] = {
            'transactions': {'openingBalanceMinor': 1000, 'reconcileGraceHours': 6},
            'planning': {'alertLevel': 80, 'warnOnPace': True},
            'telegram': {'allowReveal': False, 'sessionIdleDays': 30, 'digestMode': 'daily', 'digestHour': 8, 'afterTag': 'delete'},
        }  # fmt: skip

        @pytest.fixture(autouse=True)
        def _owners(self, fakes: Fakes) -> None:
            state = {k: dict(v) for k, v in self.state.items()}
            self.current = state
            for n in ('transactions', 'planning', 'telegram'):

                def handler(s: Seen, n: str = n) -> Reply:
                    if s.method == 'PATCH':
                        state[n].update(json.loads(s.body))
                    return Reply(body=state[n])

                fakes[n].handler = handler

        async def test_get_merges_the_three_owners_and_adds_the_currency(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
            res = await gw.get('/settings', headers=signed_in().headers)
            assert res.json() == {**self.current['transactions'], **self.current['planning'], **self.current['telegram'], 'currency': 'INR'}
            for n in ('transactions', 'planning', 'telegram'):
                assert fakes[n].last().url == '/internal/settings'
            assert fakes.transactions.claims().user_id == USER

        async def test_patch_sends_each_owner_only_its_own_fields_and_returns_the_merged_result(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
            lg = signed_in()
            res = await gw.request(
                'PATCH', '/api/settings', headers={**lg.headers, **JSON},
                json={'openingBalanceMinor': 5000, 'alertLevel': 90, 'afterTag': 'keep', 'digestHour': 21},
            )  # fmt: skip
            assert res.status_code == 200
            patches = lambda n: [json.loads(s.body) for s in fakes[n].seen if s.method == 'PATCH']
            assert patches('transactions') == [{'openingBalanceMinor': 5000}]
            assert patches('planning') == [{'alertLevel': 90}]
            assert patches('telegram') == [{'afterTag': 'keep', 'digestHour': 21}]
            got = res.json()
            assert {k: got[k] for k in ('openingBalanceMinor', 'alertLevel', 'afterTag', 'digestHour', 'warnOnPace', 'currency')} == {
                'openingBalanceMinor': 5000, 'alertLevel': 90, 'afterTag': 'keep', 'digestHour': 21, 'warnOnPace': True, 'currency': 'INR',
            }  # fmt: skip

        async def test_patch_calls_an_owner_only_if_the_patch_has_fields_for_it(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
            lg = signed_in()
            await gw.request('PATCH', '/settings', headers={**lg.headers, **JSON}, json={'warnOnPace': False})
            assert [s.method for s in fakes.transactions.seen] == ['GET']
            assert [s.method for s in fakes.telegram.seen] == ['GET']
            assert [s.method for s in fakes.planning.seen] == ['PATCH']

        async def test_patch_validates_before_calling_anyone_and_needs_csrf(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
            lg = signed_in()
            bad = await gw.request('PATCH', '/settings', headers={**lg.headers, **JSON}, json={'alertLevel': 55})
            assert bad.status_code == 400
            assert bad.json()['error']['code'] == 'validation_failed'
            assert 'alertLevel' in bad.json()['error']['details']
            no_csrf = await gw.request('PATCH', '/settings', headers={'cookie': lg.cookie, **JSON}, json={'warnOnPace': True})
            assert no_csrf.status_code == 403
            for n in ('transactions', 'planning', 'telegram'):
                assert fakes[n].seen == []

        async def test_patch_with_an_empty_body_just_reads(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
            lg = signed_in()
            res = await gw.request('PATCH', '/settings', headers=lg.headers)
            assert res.status_code == 200
            for n in ('transactions', 'planning', 'telegram'):
                assert [s.method for s in fakes[n].seen] == ['GET']


class TestPublicMachinePaths:
    async def test_ingest_message_needs_no_session_or_csrf_token_proxied_with_no_user_bearer_and_raw_body_pass_through(
        self, gw: Gateway, fakes: Fakes
    ) -> None:
        body = '{"text":"Rs.1 debited",  "nonce":"n-1"}'
        res = await gw.request(
            'POST', '/ingest/message', headers={'authorization': 'Bearer dev-token', **JSON, 'cookie': 'lbstash_refresh=zzz'}, content=body
        )
        assert res.status_code == 200
        seen = fakes.ingest.last()
        assert seen.body == body
        assert seen.headers['authorization'] == 'Bearer dev-token'
        assert 'cookie' not in seen.headers
        claims = fakes.ingest.claims()
        assert (claims.svc, claims.proxied, claims.user_id) == ('gateway', True, None)
        assert fakes.auth.seen == []  # no session lookup

    async def test_a_signed_in_cookie_does_not_turn_public_paths_into_user_calls(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        await gw.request('POST', '/api/ingest/message', headers={**lg.headers, **JSON}, content='{}')
        assert fakes.ingest.claims().user_id is None

    async def test_telegram_webhook_needs_no_session_secret_header_passes_token_has_no_user(self, gw: Gateway, fakes: Fakes) -> None:
        res = await gw.request(
            'POST', '/telegram/webhook/s3cret', headers={'x-telegram-bot-api-secret-token': 'tok', **JSON}, content='{"update_id":1}'
        )
        assert res.status_code == 200
        assert fakes.telegram.last().url == '/telegram/webhook/s3cret'
        assert fakes.telegram.last().headers['x-telegram-bot-api-secret-token'] == 'tok'
        claims = fakes.telegram.claims()
        assert (claims.proxied, claims.user_id) == (True, None)

    async def test_other_ingest_and_telegram_paths_still_need_a_session(self, gw: Gateway) -> None:
        assert (await gw.get('/ingest/other')).status_code == 401
        assert (await gw.request('POST', '/telegram/pairing')).status_code == 401


class TestLimitsAndHeaders:
    async def test_ingest_message_is_capped_at_8_kb_other_bodies_at_1_mb(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        small = await gw.request('POST', '/ingest/message', headers=JSON, content=json.dumps({'text': 'x' * 9000}))
        assert small.status_code == 413
        assert small.json()['error']['code'] == 'bad_request'
        lg = signed_in()
        big = await gw.request('POST', '/credits', headers={**lg.headers, **JSON}, content=json.dumps({'note': 'x' * 1_100_000}))
        assert big.status_code == 413
        assert fakes.ingest.seen == []
        assert fakes.transactions.seen == []

    async def test_a_body_just_under_the_cap_passes_and_the_webhook_cap_is_64_kb(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        ok = await gw.request('POST', '/ingest/message', headers=JSON, content=json.dumps({'text': 'x' * 8000}))
        assert ok.status_code == 200
        hook = lambda n: gw.request('POST', '/telegram/webhook/s', headers=JSON, content=json.dumps({'t': 'x' * n}))
        assert (await hook(60_000)).status_code == 200
        assert (await hook(70_000)).status_code == 413
        lg = signed_in()
        mid = await gw.request('POST', '/credits', headers={**lg.headers, **JSON}, content=json.dumps({'note': 'x' * 70_000}))
        assert mid.status_code == 200  # only the machine endpoints are small

    async def test_the_cap_holds_without_a_content_length_chunked_uploads(self, gw: Gateway, fakes: Fakes) -> None:
        async def chunks():
            yield b'{"text":"'
            for _ in range(4):
                yield b'x' * 3000
            yield b'"}'

        res = await gw.request('POST', '/ingest/message', headers=JSON, content=chunks())
        assert res.status_code == 413
        assert fakes.ingest.seen == []

    async def test_the_session_is_checked_before_a_private_body_is_read(self, gw: Gateway, fakes: Fakes) -> None:
        res = await gw.request('POST', '/credits', headers=JSON, content=json.dumps({'note': 'x' * 5000}))
        assert res.status_code == 401

    async def test_rejects_malformed_json_in_the_standard_shape(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        for body in ('{nope', '{"a": NaN}', '\xff'):
            res = await gw.request('POST', '/credits', headers={**lg.headers, **JSON}, content=body.encode('latin-1'))
            assert res.status_code == 400, body
            assert res.json()['error']['code'] == 'bad_request'
        assert fakes.transactions.seen == []

    async def test_other_content_types_are_forwarded_as_they_are(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        lg = signed_in()
        await gw.request('POST', '/credits', headers={**lg.headers, 'content-type': 'text/plain'}, content='{nope')
        assert fakes.transactions.last().body == '{nope'
        assert fakes.transactions.last().headers['content-type'] == 'text/plain'

    async def test_api_responses_are_never_cached_carry_security_headers_and_use_a_gateway_made_request_id(
        self, gw: Gateway, fakes: Fakes, signed_in
    ) -> None:
        lg = signed_in()
        res = await gw.get('/transactions', headers={**lg.headers, 'x-request-id': 'client-chosen'})
        assert res.headers['cache-control'] == 'no-store'
        assert "default-src 'none'" in res.headers['content-security-policy']
        assert res.headers['permissions-policy']
        assert res.headers['x-content-type-options'] == 'nosniff'
        assert res.headers['referrer-policy'] == 'no-referrer'
        assert 'access-control-allow-origin' not in res.headers
        assert res.headers['x-request-id'] != 'client-chosen'
        assert fakes.transactions.last().headers['x-request-id'] == res.headers['x-request-id']
        denied = await gw.get('/transactions')
        assert denied.headers['cache-control'] == 'no-store'
        assert "default-src 'none'" in denied.headers['content-security-policy']

    async def test_an_upstream_cannot_loosen_our_headers(self, gw: Gateway, fakes: Fakes, signed_in) -> None:
        fakes.transactions.handler = lambda _s: Reply(headers={'cache-control': 'public, max-age=999', 'content-security-policy': "default-src *", 'x-powered-by': 'x'})
        res = await gw.get('/transactions', headers=signed_in().headers)
        assert res.headers['cache-control'] == 'no-store'
        assert res.headers['content-security-policy'].startswith("default-src 'none'")
        assert 'x-powered-by' not in res.headers

    async def test_health_is_open_health_deps_needs_a_session_or_a_service_token_and_lists_ready_of_each_service(
        self, gw: Gateway, fakes: Fakes, signed_in
    ) -> None:
        health = (await gw.get('/health')).json()
        assert health['ok'] is True
        assert health['service'] == 'gateway'
        assert (await gw.get('/health/deps')).status_code == 401
        lg = signed_in()
        res = await gw.get('/health/deps', headers=lg.headers)
        assert res.status_code == 200
        assert res.json()['services'] == dict.fromkeys(NAMES, True)
        assert fakes.transactions.last().url == '/ready'
        fakes.reports.handler = lambda _s: Reply(503, {'ok': False})
        degraded = await gw.get('/health/deps', headers=lg.headers)
        assert degraded.status_code == 503
        assert degraded.json()['services']['reports'] is False

    async def test_health_deps_is_open_to_a_valid_internal_token(self, gw: Gateway) -> None:
        from lbstash.kit.testing import headers_for

        assert (await gw.get('/health/deps', headers=headers_for(None, svc='ops'))).status_code == 200
        assert (await gw.get('/api/health/deps', headers={'x-internal-token': 'forged'})).status_code == 401

    async def test_health_deps_reports_a_down_service(self, gw: Gateway, signed_in) -> None:
        gw.network.down.add('telegram')
        res = await gw.get('/health/deps', headers=signed_in().headers)
        assert res.status_code == 503
        assert res.json()['services']['telegram'] is False


class TestRateLimits:
    async def test_login_trips_after_the_strict_per_ip_limit_another_ip_is_unaffected(self, make_gw: MakeGw) -> None:
        gw = await make_gw()  # fresh counters; limit 5 / 15 min

        def sign_in(ip: str, url: str = '/auth/login'):
            return gw.request('POST', url, headers={**JSON, 'x-forwarded-for': ip}, content='{}')

        for _ in range(5):
            assert (await sign_in('7.7.7.7')).status_code == 200
        blocked = await sign_in('7.7.7.7')
        assert blocked.status_code == 429
        assert blocked.json()['error']['code'] == 'too_many_requests'
        assert 0 < int(blocked.headers['retry-after']) <= 15 * 60
        assert (await sign_in('8.8.8.8')).status_code == 200
        # 2FA and reset have their own buckets
        assert (await sign_in('7.7.7.7', '/auth/2fa/verify')).status_code == 200
        assert (await sign_in('7.7.7.7', '/auth/reset/request')).status_code == 200

    async def test_the_general_limit_is_per_user_when_signed_in_per_ip_otherwise(self, make_gw: MakeGw, alive: set[str]) -> None:
        gw = await make_gw(RATE_LIMIT_PER_MINUTE=3)
        a, b = login(sub=str(uuid.uuid4())), login(sub=str(uuid.uuid4()))
        alive.update({a.sid, b.sid})

        def get(h: dict[str, str], ip: str = '5.5.5.5'):
            return gw.get('/transactions', headers={**h, 'x-forwarded-for': ip})

        for _ in range(3):
            assert (await get(a.headers)).status_code == 200
        blocked = await get(a.headers)
        assert blocked.status_code == 429
        assert int(blocked.headers['retry-after']) > 0
        assert (await get(b.headers)).status_code == 200  # same IP, other user
        for _ in range(3):
            await get({}, '6.6.6.6')
        assert (await get({}, '6.6.6.6')).status_code == 429

    async def test_ingest_message_is_limited_per_ip(self, make_gw: MakeGw) -> None:
        gw = await make_gw(RATE_LIMIT_INGEST_PER_MINUTE=2)

        def send():
            return gw.request('POST', '/ingest/message', headers=JSON, content='{}')

        assert (await send()).status_code == 200
        assert (await send()).status_code == 200
        assert (await send()).status_code == 429

    async def test_the_telegram_webhook_is_limited_per_ip(self, make_gw: MakeGw) -> None:
        gw = await make_gw(RATE_LIMIT_WEBHOOK_PER_MINUTE=1)

        def send():
            return gw.request('POST', '/telegram/webhook/s', headers=JSON, content='{}')

        assert (await send()).status_code == 200
        assert (await send()).status_code == 429

    async def test_a_flood_of_bad_cookies_is_counted_before_the_session_check(self, make_gw: MakeGw, fakes: Fakes) -> None:
        gw = await make_gw(RATE_LIMIT_PER_MINUTE=2)
        for _ in range(2):
            assert (await gw.get('/transactions', headers={'cookie': 'lbstash_access=garbage'})).status_code == 401
        assert (await gw.get('/transactions', headers={'cookie': 'lbstash_access=garbage'})).status_code == 429
        assert session_checks(fakes) == 0


class TestDemoAccount:
    """DEMO_MODE: the demo user may read and sign out, nothing else; with it off, or for anyone else, nothing changes."""

    refused = 'This is a demo, so it is read-only. Create an account to make changes.'

    @pytest.fixture(autouse=True)
    def _me(self, fakes: Fakes, alive: set[str]) -> None:
        summary = {'month': '2026-10', 'untaggedCount': 0, 'unaccountedCount': 0, 'carriedOverMinor': 0, 'incomeMinor': 0, 'spentMinor': 0, 'availableMinor': 0, 'lastCapturedAt': None}
        user = {'id': DEMO_USER_ID, 'email': 'demo@example.com', 'name': 'Demo', 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None}
        auth_fake(fakes.auth, alive, lambda s: Reply(body={'user': user}) if s.url == '/internal/me' else None)
        fakes.planning.handler = lambda _s: Reply(body={'unreadCount': 0, 'items': []})
        fakes.ingest.handler = lambda _s: Reply(body={'open': 0})
        fakes.transactions.handler = lambda _s: Reply(body=summary)

    async def test_refuses_every_write_of_the_demo_user_before_anything_is_forwarded(self, make_gw: MakeGw, fakes: Fakes, signed_in) -> None:
        gw = await make_gw(DEMO_MODE=True)
        lg = signed_in(sub=DEMO_USER_ID)
        for method, url in [('POST', '/credits'), ('PUT', '/plans/2026-10'), ('PATCH', '/settings'), ('PATCH', '/me'), ('DELETE', '/recurring/x'), ('POST', '/account/delete')]:
            res = await gw.request(method, url, headers={**lg.headers, **JSON}, content='{}')
            assert res.status_code == 403, (method, url)
            assert res.json()['error']['message'] == self.refused
            assert res.json()['error']['details'] == {'demoReadOnly': True}
        assert fakes.non_check() == []

    async def test_still_lets_the_demo_user_read_and_sign_out_and_renew_or_restart_the_session(self, make_gw: MakeGw, fakes: Fakes, signed_in) -> None:
        gw = await make_gw(DEMO_MODE=True)
        lg = signed_in(sub=DEMO_USER_ID)
        assert (await gw.get('/transactions', headers=lg.headers)).status_code == 200
        assert (await gw.get('/settings', headers=lg.headers)).status_code == 200
        assert (await gw.request('POST', '/auth/logout', headers=lg.headers)).status_code == 200
        assert fakes.auth.last().url == '/auth/logout'
        # public paths are never stopped for the demo cookie
        assert (await gw.request('POST', '/auth/refresh', headers={'cookie': lg.cookie})).status_code == 200
        assert (await gw.request('POST', '/auth/demo', headers={'cookie': lg.cookie})).status_code == 200

    async def test_leaves_other_users_alone_and_does_nothing_when_demo_mode_is_off(self, make_gw: MakeGw, signed_in) -> None:
        on = await make_gw(DEMO_MODE=True)
        other = signed_in(sub=USER)
        assert (await on.request('POST', '/credits', headers={**other.headers, **JSON}, content='{}')).status_code == 200
        off = await make_gw()
        demo = signed_in(sub=DEMO_USER_ID)
        assert (await off.request('POST', '/credits', headers={**demo.headers, **JSON}, content='{}')).status_code == 200

    async def test_get_me_says_demo_only_for_the_demo_user_in_demo_mode(self, make_gw: MakeGw, fakes: Fakes, alive: set[str], signed_in) -> None:
        assert (await (await make_gw(DEMO_MODE=True)).get('/me', headers=signed_in(sub=DEMO_USER_ID).headers)).json()['demo'] is True
        assert (await (await make_gw()).get('/me', headers=signed_in(sub=DEMO_USER_ID).headers)).json()['demo'] is False
        not_demo = {'id': USER, 'email': 'a@b.c', 'name': None, 'timezone': 'Asia/Kolkata', 'pendingEmail': None, 'deleteAfter': None}
        auth_fake(fakes.auth, alive, lambda s: Reply(body={'user': not_demo}) if s.url == '/internal/me' else None)
        assert (await (await make_gw(DEMO_MODE=True)).get('/me', headers=signed_in(sub=USER).headers)).json()['demo'] is False

    async def test_the_demo_sign_in_has_its_own_per_ip_limit(self, make_gw: MakeGw) -> None:
        gw = await make_gw(RATE_LIMIT_DEMO_PER_15_MIN=2)

        def start(ip: str):
            return gw.request('POST', '/auth/demo', headers={**JSON, 'x-forwarded-for': ip}, content='{}')

        assert [(await start('7.7.7.7')).status_code for _ in range(2)] == [200, 200]
        assert (await start('7.7.7.7')).status_code == 429
        assert (await start('8.8.8.8')).status_code == 200
        # login keeps its own bucket
        assert (await gw.request('POST', '/auth/login', headers={**JSON, 'x-forwarded-for': '7.7.7.7'}, content='{}')).status_code == 200
