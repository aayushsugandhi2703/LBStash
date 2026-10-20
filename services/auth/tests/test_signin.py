import base64
import json
import re
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from auth_harness import ACCESS_SECRET, STRONG, Account, Harness, make_harness
from bt.common import COOKIES
from bt.crypto import totp_code, totp_step, verify_access_token
from bt_auth.throttle import LOGIN_POLICY, locked_for, record_failure


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def h(db):
    harness = await make_harness(db)
    yield harness
    await harness.close()


def cookie_named(cookies: list[str], name: str) -> str:
    return next(c for c in cookies if c.startswith(f'{name}='))


async def audit_actions(h: Harness, user_id: str) -> list[str]:
    return [r['action'] for r in await h.t.admin_pool.query('SELECT action FROM auth.audit_log WHERE user_id = $1', [user_id])]


class TestRegistrationAndMandatorySetup:
    async def test_registers_sets_the_three_cookies_with_the_right_flags_and_a_setup_limited_session(self, h: Harness):
        b = h.browser()
        res = await b.call('POST', '/auth/register', {'email': 'Ann@Example.com', 'password': STRONG, 'name': 'Ann'})
        assert res.status == 201
        assert res.body['user']['email'] == 'ann@example.com'
        assert res.body['setup'] == {'totpEnabled': False, 'recoveryCodes': False, 'complete': False}
        assert 'argon2' not in json.dumps(res.body)

        access = cookie_named(res.set_cookie, COOKIES.access)
        refresh = cookie_named(res.set_cookie, COOKIES.refresh)
        csrf = cookie_named(res.set_cookie, COOKIES.csrf)
        assert 'HttpOnly' in access and 'SameSite=Strict' in access and 'Path=/' in access and 'Max-Age=900' in access
        assert 'HttpOnly' in refresh and 'SameSite=Strict' in refresh and 'Path=/api/auth' in refresh
        assert 'HttpOnly' not in csrf and 'SameSite=Strict' in csrf and 'Path=/;' in csrf
        for c in (access, refresh, csrf):
            assert 'Secure' not in c  # http PUBLIC_URL: local dev must work

        # limited: the gateway is told, and everything beyond setup is closed
        chk = await b.internal('POST', '/internal/sessions/check', None, {'sid': b.sid()})
        assert chk.body == {'valid': True, 'limited': True}
        for m, u in (('GET', '/sessions'), ('GET', '/audit'), ('PATCH', '/me')):
            r = await b.call(m, u, {'name': 'x'} if m == 'PATCH' else None)
            assert r.status == 403, u
            assert r.body['error']['details'] == {'setupRequired': True}
        assert (await b.call('POST', '/account/export', {'code': '123456'})).status == 403
        assert (await b.call('GET', '/auth/factors')).status == 200

    async def test_sends_one_welcome_mail_to_the_address_used_and_none_when_sign_up_fails(self, h: Harness):
        before = len(h.mails)
        b = h.browser()
        assert (await b.call('POST', '/auth/register', {'email': 'Welcome@Example.com', 'password': STRONG, 'name': 'Wen'})).status == 201
        sent = h.mails[before:]
        assert [(m.to, m.subject) for m in sent] == [('welcome@example.com', 'Welcome to Ledger')]
        assert sent[0].text.startswith('Hi Wen,') and 'Thank you for choosing Ledger' in sent[0].text

        # duplicate and weak-password attempts send nothing
        assert (await b.call('POST', '/auth/register', {'email': 'welcome@example.com', 'password': STRONG})).status == 409
        assert (await b.call('POST', '/auth/register', {'email': 'weak@example.com', 'password': 'short'})).status == 400
        assert len(h.mails) == before + 1

    async def test_a_failing_mailer_does_not_fail_the_sign_up(self, h: Harness):
        async def boom(to: str, subject: str, text: str) -> None:
            raise RuntimeError('smtp down')

        original = h.mailer.send
        h.mailer.send = boom  # type: ignore[method-assign]
        try:
            res = await h.browser().call('POST', '/auth/register', {'email': 'nomail@example.com', 'password': STRONG})
        finally:
            h.mailer.send = original  # type: ignore[method-assign]
        assert res.status == 201

    async def test_rejects_weak_common_and_email_containing_passwords_bad_zones_and_duplicate_emails(self, h: Harness):
        b = h.browser()

        async def register(**body):
            return await b.call('POST', '/auth/register', body)

        assert re.search('12', (await register(email='w1@example.com', password='short')).body['error']['details']['password'])
        assert re.search('common', (await register(email='w2@example.com', password='password1234')).body['error']['details']['password'])
        assert re.search('email', (await register(email='sandhya@example.com', password='my-sandhya-secret-1')).body['error']['details']['password'])
        assert (await register(email='w3@example.com', password=STRONG, timezone='Mars/Base')).status == 400
        assert (await register(email='not-an-email', password=STRONG)).status == 400
        assert (await register(email='ann@example.com', password=STRONG)).status == 409

    async def test_sets_secure_cookies_only_when_public_url_is_https(self, h: Harness):
        app = await h.app_with(PUBLIC_URL='https://ledger.example.com')
        res = await h.browser(app=app).call('POST', '/auth/register', {'email': 'tls@example.com', 'password': STRONG})
        assert len(res.set_cookie) == 3
        for c in res.set_cookie:
            assert '; Secure' in c

    async def test_closes_registration_once_an_account_exists_when_registration_is_first_only(self, h: Harness):
        app = await h.app_with(REGISTRATION='first-only')
        res = await h.browser(app=app).call('POST', '/auth/register', {'email': 'second@example.com', 'password': STRONG})
        assert res.status == 403

    async def test_walks_the_setup_authenticator_recovery_codes_once_then_a_full_session(self, h: Harness):
        b = h.browser()
        reg = await b.call('POST', '/auth/register', {'email': 'setup@example.com', 'password': STRONG})
        user_id = reg.body['user']['id']
        # recovery codes before an authenticator exists: refused
        assert (await b.call('POST', '/auth/recovery-codes', {})).status == 403
        # confirm without starting
        assert (await b.call('POST', '/auth/2fa/enable/confirm', {'code': '123456'})).status == 400

        start = await b.call('POST', '/auth/2fa/enable', {})
        assert re.fullmatch(r'[A-Z2-7]{32}', start.body['secret'])
        assert f'secret={start.body["secret"]}' in start.body['otpauthUri']
        # the secret is stored encrypted
        row = (await h.t.admin_pool.query('SELECT totp_pending_enc FROM auth.users WHERE id = $1', [user_id]))[0]
        assert start.body['secret'] not in bytes(row['totp_pending_enc']).decode('latin1')

        wrong = await b.call('POST', '/auth/2fa/enable/confirm', {'code': '000000'})
        assert wrong.status == 401
        assert wrong.body['error']['code'] == 'two_factor_invalid'
        assert wrong.body['error']['details']['attemptsLeft'] == 2

        ok = await b.call('POST', '/auth/2fa/enable/confirm', {'code': await h.code(user_id, start.body['secret'])})
        assert ok.body['setup'] == {'totpEnabled': True, 'recoveryCodes': False, 'complete': False}
        assert (await b.call('GET', '/sessions')).status == 403  # still limited: no recovery set yet

        rc = await b.call('POST', '/auth/recovery-codes', {})
        assert len(rc.body['codes']) == 10
        assert re.fullmatch(r'[a-z0-9]{5}-[a-z0-9]{5}', rc.body['codes'][0])
        assert rc.body['setup']['complete'] is True
        # stored hashed only
        stored = [r['code_hash'] for r in await h.t.admin_pool.query(
            "SELECT code_hash FROM auth.auth_factors WHERE user_id = $1 AND kind = 'recovery_code'", [user_id])]  # fmt: skip
        assert len(stored) == 10
        for c in rc.body['codes']:
            assert c not in stored

        chk = await b.internal('POST', '/internal/sessions/check', None, {'sid': b.sid()})
        assert chk.body == {'valid': True, 'limited': True}
        assert (await b.call('GET', '/sessions')).status == 200

        await h.t.admin_pool.execute(
            "INSERT INTO auth.auth_factors (user_id, kind, public_key, credential_id) VALUES ($1, 'passkey', $2, $3)",
            [user_id, b'public-key', 'test-credential'],
        )
        with_passkey = await b.internal('POST', '/internal/sessions/check', None, {'sid': b.sid()})
        assert with_passkey.body == {'valid': True, 'limited': False}

        # from now on a fresh code is required for a new set
        no_code = await b.call('POST', '/auth/recovery-codes', {})
        assert no_code.status == 401
        assert no_code.body['error']['code'] == 'two_factor_required'
        again = await b.call('POST', '/auth/recovery-codes', {'code': await h.code(user_id, start.body['secret'])})
        assert again.status == 200
        assert len(again.body['codes']) == 10
        assert again.body['codes'] != rc.body['codes']
        n = (await h.t.admin_pool.query(
            "SELECT count(*)::int AS n FROM auth.auth_factors WHERE user_id = $1 AND kind = 'recovery_code'", [user_id]))[0]['n']  # fmt: skip
        assert n == 10

    async def test_an_account_that_never_finished_setup_signs_in_to_a_setup_limited_session_never_a_full_one(self, h: Harness):
        first = h.browser()
        await first.call('POST', '/auth/register', {'email': 'abandon@example.com', 'password': STRONG})
        b = h.browser()
        res = await b.call('POST', '/auth/login', {'email': 'abandon@example.com', 'password': STRONG})
        assert res.body['twoFactorToken'] is None and res.body['setupRequired'] is True
        assert len(res.set_cookie) == 3
        assert (await b.call('GET', '/sessions')).status == 403

    async def test_with_the_authenticator_on_but_no_recovery_set_sign_in_still_needs_the_code_and_stays_limited(self, h: Harness):
        first = h.browser()
        reg = await first.call('POST', '/auth/register', {'email': 'half@example.com', 'password': STRONG})
        start = await first.call('POST', '/auth/2fa/enable', {})
        await first.call('POST', '/auth/2fa/enable/confirm', {'code': await h.code(reg.body['user']['id'], start.body['secret'])})
        b = h.browser()
        step1 = await b.call('POST', '/auth/login', {'email': 'half@example.com', 'password': STRONG})
        assert step1.body['setupRequired'] is False
        assert step1.body['twoFactorToken']
        assert len(step1.set_cookie) == 0
        step2 = await b.call(
            'POST', '/auth/2fa/verify',
            {'twoFactorToken': step1.body['twoFactorToken'], 'code': await h.code(reg.body['user']['id'], start.body['secret'])},
        )  # fmt: skip
        assert step2.status == 200
        assert step2.body['setup']['complete'] is False
        assert (await b.call('GET', '/sessions')).status == 403


class TestTwoStepSignIn:
    email = 'login@example.com'

    @pytest_asyncio.fixture(scope='class', loop_scope='session')
    async def acct(self, h: Harness) -> Account:
        return await h.browser().create_account(h, self.email)

    async def test_gives_the_same_answer_for_an_unknown_email_and_a_wrong_password_and_sets_no_cookies(self, h: Harness, acct):
        b = h.browser()
        wrong = await b.call('POST', '/auth/login', {'email': self.email, 'password': 'wrong password here'})
        unknown = await b.call('POST', '/auth/login', {'email': 'nobody@example.com', 'password': 'wrong password here'})
        assert wrong.status == 401
        assert unknown.status == 401
        assert wrong.body == unknown.body
        assert wrong.body['error']['message'] == "That email and password don't match."
        assert wrong.set_cookie == []

    async def test_login_returns_a_token_and_the_methods_the_second_step_creates_the_session(self, h: Harness, acct):
        b = h.browser()
        step1 = await b.call('POST', '/auth/login', {'email': self.email, 'password': STRONG})
        assert step1.status == 200
        assert step1.body['setupRequired'] is False and step1.body['methods'] == ['totp', 'recovery']
        assert step1.set_cookie == []  # no session yet
        assert (await b.call('GET', '/sessions')).status == 401

        bad = await b.call('POST', '/auth/2fa/verify', {'twoFactorToken': step1.body['twoFactorToken'], 'code': '000000'})
        assert bad.status == 401
        assert bad.body['error']['code'] == 'two_factor_invalid'
        assert bad.body['error']['details']['attemptsLeft'] == 2
        assert bad.set_cookie == []

        ok = await b.call(
            'POST', '/auth/2fa/verify',
            {'twoFactorToken': step1.body['twoFactorToken'], 'code': await h.code(acct.user_id, acct.secret)},
        )  # fmt: skip
        assert ok.status == 200
        assert ok.body['recoveryCodesLeft'] == 10 and ok.body['recoveryCodeUsed'] is False
        assert ok.body['deletionCancelled'] is False and ok.body['setup']['complete'] is True
        assert len(ok.set_cookie) == 3
        assert (await b.call('GET', '/sessions')).status == 200

        # the token is single use
        reuse = await b.call(
            'POST', '/auth/2fa/verify',
            {'twoFactorToken': step1.body['twoFactorToken'], 'code': await h.code(acct.user_id, acct.secret, 1)},
        )  # fmt: skip
        assert reuse.status == 401

    async def test_refuses_a_request_that_sends_none_or_several_second_step_proofs(self, h: Harness, acct):
        b = h.browser()
        step1 = await b.call('POST', '/auth/login', {'email': self.email, 'password': STRONG})
        token = step1.body['twoFactorToken']
        assert (await b.call('POST', '/auth/2fa/verify', {'twoFactorToken': token})).status == 400
        both = {'twoFactorToken': token, 'code': '123456', 'recoveryCode': 'abcde-fghjk'}
        assert (await b.call('POST', '/auth/2fa/verify', both)).status == 400

    async def test_accepts_an_authenticator_code_once_per_time_step_replay_fails_also_across_sign_ins(self, h: Harness, acct):
        b = h.browser()
        code = await h.code(acct.user_id, acct.secret)
        s1 = await b.call('POST', '/auth/login', {'email': self.email, 'password': STRONG})
        assert (await b.call('POST', '/auth/2fa/verify', {'twoFactorToken': s1.body['twoFactorToken'], 'code': code})).status == 200
        s2 = await b.call('POST', '/auth/login', {'email': self.email, 'password': STRONG})
        replay = await b.call('POST', '/auth/2fa/verify', {'twoFactorToken': s2.body['twoFactorToken'], 'code': code})
        assert replay.status == 401
        assert replay.body['error']['code'] == 'two_factor_invalid'
        # an older step than the one used is also dead
        older = totp_code(acct.secret, totp_step(datetime.now(UTC)) - 1)
        assert (await b.call('POST', '/auth/2fa/verify', {'twoFactorToken': s2.body['twoFactorToken'], 'code': older})).status == 401

    async def test_a_recovery_code_signs_in_once_is_used_up_and_the_response_says_so(self, h: Harness, acct):
        b = h.browser()
        code = acct.recovery_codes[0]
        s1 = await b.call('POST', '/auth/login', {'email': self.email, 'password': STRONG})
        ok = await b.call('POST', '/auth/2fa/verify', {'twoFactorToken': s1.body['twoFactorToken'], 'recoveryCode': code.upper()})
        assert ok.status == 200
        assert ok.body['recoveryCodeUsed'] is True and ok.body['recoveryCodesLeft'] == 9
        s2 = await h.browser().call('POST', '/auth/login', {'email': self.email, 'password': STRONG})
        again = await b.call('POST', '/auth/2fa/verify', {'twoFactorToken': s2.body['twoFactorToken'], 'recoveryCode': code})
        assert again.status == 401

    async def test_locks_the_second_step_after_three_misses_423_wait_a_minute_and_writes_audit_entries(self, h: Harness, acct):
        acct2 = await h.browser().create_account(h, 'lock2@example.com')
        b = h.browser(ip='10.9.9.9')
        s1 = await b.call('POST', '/auth/login', {'email': 'lock2@example.com', 'password': STRONG})
        t = s1.body['twoFactorToken']

        async def verify(code: str):
            return await b.call('POST', '/auth/2fa/verify', {'twoFactorToken': t, 'code': code})

        assert (await verify('111111')).body['error']['details']['attemptsLeft'] == 2
        assert (await verify('111112')).body['error']['details']['attemptsLeft'] == 1
        third = await verify('111113')
        assert third.status == 423
        assert third.body['error']['code'] == 'locked'
        assert third.body['error']['message'] == 'Too many tries. Wait a minute, then try again.'
        assert third.body['error']['details']['retryAfterSeconds'] > 0
        # even the right code is refused while locked
        right = await verify(await h.code(acct2.user_id, acct2.secret))
        assert right.status == 423
        actions = await audit_actions(h, acct2.user_id)
        assert actions.count('2fa.failed') == 3
        assert 'login.locked' in actions

    async def test_locks_password_attempts_per_email_and_ip_persisted_in_the_database_and_another_ip_is_not_affected(self, h: Harness, acct):
        who = await h.browser().create_account(h, 'lock1@example.com')
        attacker = h.browser(ip='203.0.113.7')
        for i in range(5):
            r = await attacker.call('POST', '/auth/login', {'email': 'lock1@example.com', 'password': f'wrong-password-{i}'})
            assert r.status == 401
        locked = await attacker.call('POST', '/auth/login', {'email': 'lock1@example.com', 'password': STRONG})
        assert locked.status == 423
        assert locked.body['error']['details']['retryAfterSeconds'] > 0
        rows = await h.t.admin_pool.query('SELECT failures, locked_until FROM auth.login_throttle WHERE locked_until IS NOT NULL')
        assert len(rows) > 0
        # the lock is a row, not memory: the owner on another ip signs in
        owner = h.browser(ip='198.51.100.9')
        assert (await owner.sign_in(h, who, 'lock1@example.com')).status == 200
        actions = await audit_actions(h, who.user_id)
        assert 'login.failed' in actions
        assert 'login.locked' in actions
        # expire the lock (as time would) and the attacker's ip can try again
        await h.t.admin_pool.execute("UPDATE auth.login_throttle SET locked_until = now() - interval '1 second'")
        assert (await attacker.call('POST', '/auth/login', {'email': 'lock1@example.com', 'password': STRONG})).status == 200


class TestRefreshRotationAndSignOut:
    async def test_rotates_the_refresh_token_on_every_use_and_keeps_the_csrf_token(self, h: Harness):
        b = h.browser()
        acct = await b.create_account(h, 'refresh@example.com')
        before = {'refresh': b.refresh, 'access': b.access, 'csrf': b.csrf}
        res = await b.call('POST', '/auth/refresh', {}, skip_gateway=True)
        assert res.status == 200
        assert res.body['user']['id'] == acct.user_id
        assert b.refresh != before['refresh']
        assert b.csrf == before['csrf']
        assert b.sid()
        # refresh tokens are stored hashed
        rows = [r['token_hash'] for r in await h.t.admin_pool.query('SELECT token_hash FROM auth.refresh_tokens WHERE user_id = $1', [acct.user_id])]
        assert len(rows) >= 2
        assert b.refresh not in rows

    async def test_a_reused_refresh_token_revokes_the_whole_family_401_and_the_newest_token_is_dead_too(self, h: Harness):
        b = h.browser()
        await b.create_account(h, 'reuse@example.com')
        stolen = b.refresh
        sid = b.sid()
        assert (await b.call('POST', '/auth/refresh', {}, skip_gateway=True)).status == 200
        newest = b.refresh

        thief = h.browser()
        thief.jar[COOKIES.refresh] = stolen
        res = await thief.call('POST', '/auth/refresh', {}, skip_gateway=True)
        assert res.status == 401
        assert any(c.startswith(f'{COOKIES.refresh}=;') and 'Max-Age=0' in c for c in res.set_cookie)

        # the legitimate browser's newest token no longer works either, and the gateway's check fails at once
        owner = h.browser()
        owner.jar[COOKIES.refresh] = newest
        assert (await owner.call('POST', '/auth/refresh', {}, skip_gateway=True)).status == 401
        assert (await b.internal('POST', '/internal/sessions/check', None, {'sid': sid})).body['valid'] is False
        audit = [(r['meta'] or {}).get('reason') for r in await h.t.admin_pool.query("SELECT meta FROM auth.audit_log WHERE action = 'session.revoked'")]
        assert 'refresh_token_reuse' in audit

    async def test_refuses_a_missing_or_unknown_refresh_token(self, h: Harness):
        assert (await h.browser().call('POST', '/auth/refresh', {}, skip_gateway=True)).status == 401
        b = h.browser()
        b.jar[COOKIES.refresh] = 'nope'
        assert (await b.call('POST', '/auth/refresh', {}, skip_gateway=True)).status == 401

    async def test_refresh_without_a_request_body_works_like_the_web_app_sends_it(self, h: Harness):
        b = h.browser()
        await b.create_account(h, 'refresh-nobody@example.com')
        assert (await b.call('POST', '/auth/refresh', None, skip_gateway=True)).status == 200

    async def test_logout_revokes_the_session_clears_all_three_cookies_and_is_audited(self, h: Harness):
        b = h.browser()
        acct = await b.create_account(h, 'logout@example.com')
        sid = b.sid()
        res = await b.call('POST', '/auth/logout', {})
        assert res.status == 200
        assert len(res.set_cookie) == 3
        for c in res.set_cookie:
            assert 'Max-Age=0' in c
        assert b.access is None
        assert (await b.internal('POST', '/internal/sessions/check', None, {'sid': sid})).body['valid'] is False
        assert 'logout' in await audit_actions(h, acct.user_id)


class TestResetByRecoveryCode:
    async def test_two_steps_check_without_using_the_code_then_set_the_password_code_used_up_every_session_signed_out(self, h: Harness):
        owner = h.browser()
        acct = await owner.create_account(h, 'reset@example.com')
        sid = owner.sid()
        b = h.browser()
        bad = await b.call('POST', '/auth/reset/verify', {'email': 'reset@example.com', 'recoveryCode': 'zzzzz-zzzzz'})
        assert bad.status == 422
        unknown = await b.call('POST', '/auth/reset/verify', {'email': 'ghost@example.com', 'recoveryCode': acct.recovery_codes[0]})
        assert unknown.status == 422
        assert unknown.body == bad.body

        v = await b.call('POST', '/auth/reset/verify', {'email': 'reset@example.com', 'recoveryCode': acct.recovery_codes[1]})
        assert v.status == 200

        async def used() -> int:
            r = await h.t.admin_pool.query(
                "SELECT count(*)::int AS n FROM auth.auth_factors WHERE user_id = $1 AND kind = 'recovery_code' AND used_at IS NOT NULL",
                [acct.user_id],
            )
            return r[0]['n']

        assert await used() == 0

        weak = await b.call('POST', '/auth/reset/complete', {'resetToken': v.body['resetToken'], 'newPassword': 'password1234'})
        assert weak.status == 400
        done = await b.call('POST', '/auth/reset/complete', {'resetToken': v.body['resetToken'], 'newPassword': 'a brand new passphrase 77'})
        assert done.status == 200
        assert done.set_cookie == []  # does not sign in
        assert (await owner.internal('POST', '/internal/sessions/check', None, {'sid': sid})).body['valid'] is False
        assert await used() == 1

        second = await b.call('POST', '/auth/reset/complete', {'resetToken': v.body['resetToken'], 'newPassword': 'another passphrase 88'})
        assert second.status == 422
        again = await b.call('POST', '/auth/reset/verify', {'email': 'reset@example.com', 'recoveryCode': acct.recovery_codes[1]})
        assert again.status == 422  # used up

        assert (await h.browser().call('POST', '/auth/login', {'email': 'reset@example.com', 'password': STRONG})).status == 401
        assert (await h.browser().call('POST', '/auth/login', {'email': 'reset@example.com', 'password': 'a brand new passphrase 77'})).status == 200
        actions = await audit_actions(h, acct.user_id)
        assert 'password.reset' in actions and 'recovery_code.used' in actions

    async def test_throttles_guessing_recovery_codes(self, h: Harness):
        await h.browser().create_account(h, 'resetlock@example.com')
        b = h.browser(ip='192.0.2.50')
        for i in range(5):
            r = await b.call('POST', '/auth/reset/verify', {'email': 'resetlock@example.com', 'recoveryCode': f'abcde-fghj{i}'})
            assert r.status == 422
        assert (await b.call('POST', '/auth/reset/verify', {'email': 'resetlock@example.com', 'recoveryCode': 'abcde-fghjk'})).status == 423


class TestTokensAndThrottlingDetails:
    async def test_the_access_token_carries_sub_sid_and_the_user_time_zone_and_lasts_15_minutes(self, h: Harness):
        b = h.browser()
        acct = await b.create_account(h, 'claims@example.com')
        claims = verify_access_token(ACCESS_SECRET, b.access)
        assert (claims.sub, claims.sid, claims.tz) == (acct.user_id, b.sid(), 'Asia/Kolkata')
        payload = json.loads(base64.urlsafe_b64decode(b.access.split('.')[1] + '=='))
        assert payload['exp'] - payload['iat'] == 900

    async def test_logging_out_without_any_session_is_harmless(self, h: Harness):
        res = await h.browser().call('POST', '/auth/logout', {})
        assert res.status == 200

    async def test_the_lockout_is_progressive_30_s_at_the_threshold_then_doubling_capped(self, h: Harness):
        waits = []
        for _ in range(10):
            async with h.deps.as_system() as tx:
                waits.append((await record_failure(tx, 'progressive-test', LOGIN_POLICY)).locked_seconds)
        assert waits == [0, 0, 0, 0, 30, 60, 120, 240, 480, 900]
        async with h.deps.as_system() as tx:
            assert await locked_for(tx, 'progressive-test') > 800


@pytest.mark.parametrize('value', ['', '   '])
def test_env_treats_blank_optional_variables_as_unset(value: str):
    """docker-compose passes unset optionals as empty strings; an empty MAIL_FROM must not become the sender."""
    from bt.kit.testing import test_env_values
    from bt_auth.env import Env, rp_id

    env = Env.model_validate(test_env_values('auth', ACCESS_TOKEN_SECRET='a' * 40, FIELD_KEY='b' * 44, MAIL_FROM=value, WEBAUTHN_RP_ID=value, SMTP_URL=value))
    assert env.MAIL_FROM is None and env.SMTP_URL is None
    assert rp_id(env) == 'localhost'
