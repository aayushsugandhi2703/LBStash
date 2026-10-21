"""The public demo sign-in: off unless DEMO_MODE, and only ever for the demo user. Own module, so its database starts with no users."""

import pytest_asyncio
from auth_harness import STRONG, Harness, make_harness
from lbstash.common import COOKIES, DEMO_USER_ID


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def h(db):
    harness = await make_harness(db)
    yield harness
    await harness.close()


async def add_demo_user(h: Harness) -> None:
    """What the demo seeder writes: a finished account (setup complete, one passkey) with the fixed id."""
    await h.t.admin_pool.execute(
        "INSERT INTO auth.users (id, email, password_hash, name, setup_completed_at) VALUES ($1, 'demo@example.com', 'x', 'Demo', now()) "
        'ON CONFLICT (id) DO NOTHING',
        [DEMO_USER_ID],
    )
    await h.t.admin_pool.execute(
        "INSERT INTO auth.auth_factors (user_id, kind, public_key, credential_id) SELECT $1, 'passkey', '\\x00', 'demo-passkey' "
        "WHERE NOT EXISTS (SELECT 1 FROM auth.auth_factors WHERE user_id = $1 AND kind = 'passkey')",
        [DEMO_USER_ID],
    )


async def remove_demo_user(h: Harness) -> None:
    await h.t.admin_pool.execute('DELETE FROM auth.users WHERE id = $1', [DEMO_USER_ID])


class TestDemoSignIn:
    async def test_is_a_missing_route_when_demo_mode_is_off_even_if_the_demo_user_exists(self, h: Harness):
        await add_demo_user(h)
        res = await h.browser().call('POST', '/auth/demo')
        assert res.status == 404
        assert res.body == {'error': {'code': 'not_found', 'message': 'No such route'}}
        assert res.set_cookie == []

    async def test_answers_404_when_the_demo_data_is_not_loaded_and_sets_no_cookies(self, h: Harness):
        await remove_demo_user(h)
        app = await h.app_with(DEMO_MODE=True)
        res = await h.browser(app=app).call('POST', '/auth/demo')
        assert res.status == 404
        assert res.body['error']['code'] == 'not_found'
        assert res.set_cookie == []

    async def test_starts_a_normal_full_session_for_the_demo_user_without_password_or_second_step(self, h: Harness):
        await add_demo_user(h)
        app = await h.app_with(DEMO_MODE=True)
        b = h.browser(app=app, ip='198.51.100.9')
        res = await b.call('POST', '/auth/demo')
        assert res.status == 200
        assert res.body['user']['id'] == DEMO_USER_ID and res.body['user']['email'] == 'demo@example.com'
        assert res.body['setup']['complete'] is True
        assert 'passwordHash' not in str(res.body) and 'password_hash' not in str(res.body)
        assert {c.split('=')[0] for c in res.set_cookie} == {COOKIES.access, COOKIES.refresh, COOKIES.csrf}
        # the session is real and not setup-limited, so the gateway lets it through
        chk = await b.internal('POST', '/internal/sessions/check', None, {'sid': b.sid()})
        assert chk.body == {'valid': True, 'limited': False}
        # refresh rotation works as for anyone
        assert (await b.call('POST', '/auth/refresh')).status == 200
        actions = [r['action'] for r in await h.t.admin_pool.query('SELECT action FROM auth.audit_log WHERE user_id = $1', [DEMO_USER_ID])]
        assert 'demo.login' in actions

    async def test_keeps_the_address_list_of_the_demo_user(self, h: Harness):
        await add_demo_user(h)
        await h.t.admin_pool.execute("UPDATE auth.users SET allowed_ips = ARRAY['203.0.113.7'] WHERE id = $1", [DEMO_USER_ID])
        try:
            app = await h.app_with(DEMO_MODE=True)
            assert (await h.browser(app=app, ip='198.51.100.9').call('POST', '/auth/demo')).status == 403
            assert (await h.browser(app=app, ip='203.0.113.7').call('POST', '/auth/demo')).status == 200
        finally:
            await h.t.admin_pool.execute("UPDATE auth.users SET allowed_ips = '{}' WHERE id = $1", [DEMO_USER_ID])

    async def test_never_signs_anyone_else_in(self, h: Harness):
        """Another account exists; the route takes no input and still only ever answers with the demo user."""
        await add_demo_user(h)
        other = await h.browser().call('POST', '/auth/register', {'email': 'owner@example.com', 'password': STRONG})
        assert other.status == 201
        app = await h.app_with(DEMO_MODE=True)
        b = h.browser(app=app)
        for body in (None, {'email': 'owner@example.com'}, {'userId': other.body['user']['id']}):
            res = await b.call('POST', '/auth/demo', body)
            assert res.status == 200 and res.body['user']['id'] == DEMO_USER_ID


class TestFirstOnlyRegistration:
    async def test_the_demo_user_does_not_close_registration_but_a_real_account_does(self, h: Harness):
        await h.t.admin_pool.execute("DELETE FROM auth.users WHERE id <> $1", [DEMO_USER_ID])
        await add_demo_user(h)
        app = await h.app_with(REGISTRATION='first-only')
        first = await h.browser(app=app).call('POST', '/auth/register', {'email': 'first-owner@example.com', 'password': STRONG})
        assert first.status == 201
        second = await h.browser(app=app).call('POST', '/auth/register', {'email': 'second-owner@example.com', 'password': STRONG})
        assert second.status == 403

    async def test_without_the_demo_user_the_first_account_is_still_accepted_and_the_second_refused(self, h: Harness):
        await h.t.admin_pool.execute('DELETE FROM auth.users')
        app = await h.app_with(REGISTRATION='first-only')
        assert (await h.browser(app=app).call('POST', '/auth/register', {'email': 'solo@example.com', 'password': STRONG})).status == 201
        assert (await h.browser(app=app).call('POST', '/auth/register', {'email': 'late@example.com', 'password': STRONG})).status == 403
