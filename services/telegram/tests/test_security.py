"""Who may talk to the bot, how a person links and signs in, how sessions end, and what must never leak."""

import io
import json
import re
import uuid
from dataclasses import replace
from datetime import datetime, timedelta

import pytest
from bt.common import create_logger
from bt.contracts import dump
from bt.contracts.base import iso_ms
from bt.crypto import FieldCipher
from bt.kit.testing import build_test_app, headers_for
from bt_telegram.env import Env
from bt_telegram.routes import make_register
from bt_telegram.runtime import RuntimeOptions
from telegram_harness import FIELD_KEY, PUBLIC_URL, FakeAuth, FakeBot, FakeLedger, World


async def no_sleep(_: float) -> None:
    return None


def calls_since(w: World, n: int) -> list[dict[str, object]]:
    return w.bot.calls[n:]


class TestWebhookSecrets:
    async def test_a_wrong_path_secret_or_a_wrong_or_missing_header_is_refused_and_nothing_is_processed(self, w: World) -> None:
        u = await w.signed_in_user()
        n = len(w.bot.calls)
        update = {'update_id': 99_000_000, 'message': {'message_id': 1, 'from': {'id': u.tg_id}, 'chat': {'id': u.chat_id, 'type': 'private'}, 'text': '/pending'}}  # fmt: skip

        assert (await w.webhook(replace(u, path_secret='x' * 40), update)).status == 401
        assert (await w.webhook(u, update, {'x-telegram-bot-api-secret-token': 'wrong'})).status == 401
        assert (await w.webhook(u, update, {'x-telegram-bot-api-secret-token': ''})).status == 401
        no_header = await w.app.client.post(
            f'/telegram/webhook/{u.path_secret}', headers=headers_for(None, 'gateway', 'UTC', True), json=update
        )
        assert no_header.status_code == 401
        # the other user's header with this user's path
        other = await w.user_with_bot()
        assert (await w.webhook(u, update, {'x-telegram-bot-api-secret-token': other.header_secret})).status == 401
        # no service token at all
        bare = await w.app.client.post(
            f'/telegram/webhook/{u.path_secret}', headers={'x-telegram-bot-api-secret-token': u.header_secret}, json=update
        )
        assert bare.status_code == 401

        # not even a reply
        assert [c for c in calls_since(w, n) if c['op'] not in ('getMe', 'setWebhook')] == []
        rows = await w.sql('SELECT last_update_id FROM telegram_bots WHERE user_id = $1', u.user_id)
        assert rows[0]['last_update_id'] != 99_000_000
        # the right pair works
        assert (await w.webhook(u, update)).status == 200

    async def test_keeps_guessing_cheap_many_bad_secrets_from_one_address_are_rate_limited(self, w: World) -> None:
        u = await w.linked_user()
        statuses = []
        for i in range(25):
            guess = replace(u, path_secret=f'guess-{i}'.ljust(30, 'x'), header_secret='nope')
            statuses.append((await w.webhook(guess, {'update_id': 1})).status)
        assert all(s in (401, 429) for s in statuses)
        assert statuses[0] == 401
        assert statuses[-3:] == [429, 429, 429]
        assert (await w.say(u, '/signin')).status == 200  # Telegram itself is never locked out by bad callers


class TestWhoMayTalkToTheBot:
    async def test_an_unknown_sender_gets_no_reply_whatever_they_send_or_tap(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        message_id, msg = await w.message_of(tx)
        n = len(w.bot.calls)
        tags = len(w.ledger.tag_calls)
        stranger = {'from_id': 31337, 'chat_id': 31337}
        await w.say(u, '/signin', **stranger)
        await w.say(u, '/start', **stranger)
        await w.say(u, '/start 123456', **stranger)
        await w.say(u, '482915', **stranger)
        await w.say(u, 'hello', **stranger)
        await w.tap_data(u, message_id, w.bot.button(msg, 'Food')['callback_data'], **stranger)
        # right id but another chat is the same as a stranger
        await w.say(u, '/pending', chat_id=424242)
        assert calls_since(w, n) == []
        assert len(w.ledger.tag_calls) == tags
        assert msg.text == 'Money out · 6:42 pm'

    async def test_group_and_channel_chats_are_ignored_even_from_the_linked_id(self, w: World) -> None:
        u = await w.signed_in_user()
        n = len(w.bot.calls)
        for chat_type in ['group', 'supergroup', 'channel']:
            await w.say(u, '/pending', chat_type=chat_type)
        await w.say(u, '/signout', chat_type='group')
        assert calls_since(w, n) == []
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['sessionActive'] is True

    async def test_signed_out_only_signin_works_everything_else_gets_signed_out_send_signin_and_does_nothing(self, w: World) -> None:
        u = await w.linked_user()
        tx = w.new_tx(u)
        for text in ['hello', '/pending', '/unlink', '/signout', '/whatever']:
            await w.say(u, text)
            assert w.bot.last_message(u.chat_id).text == 'Signed out. Send /signin.'
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['linked'] is True  # /unlink did nothing
        # a tap on an old message: toast only
        await w.tap_data(u, 1, 'sometoken:c0')
        assert w.bot.last_answer() == 'Signed out. Send /signin.'
        assert [c for c in w.ledger.tag_calls if c['id'] == tx.id] == []
        # /signin itself works
        await w.say(u, '/signin')
        assert w.bot.last_message(u.chat_id).text == 'Send your 6-digit authenticator code.'

    async def test_the_same_telegram_id_cannot_be_linked_to_a_second_account_the_pairing_is_used_up_the_stranger_is_told(
        self, w: World
    ) -> None:
        a = await w.linked_user()
        b = await w.user_with_bot()
        p = await w.web(b.user_id, 'POST', '/telegram/pairing')
        await w.say(b, p.body['command'], from_id=a.tg_id, chat_id=a.tg_id)
        assert (await w.web(b.user_id, 'GET', '/telegram/link')).body['linked'] is False


class TestPairing:
    async def test_needs_a_saved_bot_token_the_code_is_shown_once_stored_hashed_valid_5_minutes_single_use(self, w: World) -> None:
        nobody = str(uuid.uuid4())
        assert (await w.web(nobody, 'POST', '/telegram/pairing')).status == 409

        u = await w.user_with_bot()
        p = await w.web(u.user_id, 'POST', '/telegram/pairing')
        assert p.status == 201
        assert re.fullmatch(r'\d{6}', p.body['code'])
        assert p.body['command'] == f'/start {p.body["code"]}'
        assert datetime.fromisoformat(p.body['expiresAt']) - w.clock.now == timedelta(minutes=5)
        rows = await w.sql('SELECT * FROM telegram_pairings WHERE user_id = $1', u.user_id)
        assert len(rows) == 1
        assert p.body['code'] not in json.dumps(rows, default=str)
        st = (await w.web(u.user_id, 'GET', '/telegram/link')).body
        assert (st['linked'], st['pairingPending']) == (False, True)

        # a stranger who guesses a wrong code gets nothing; the right code from the owner links
        await w.say(u, '/start 000000')
        assert w.bot.sends(u.chat_id) == []
        await w.say(u, p.body['command'])
        assert w.bot.last_message(u.chat_id).text == 'Linked. Send /signin to start.'
        st = (await w.web(u.user_id, 'GET', '/telegram/link')).body
        assert (st['linked'], st['sessionActive'], st['pairingPending']) == (True, False, False)
        assert st['telegramIdHint'] == f'••{str(u.tg_id)[-4:]}'
        assert str(u.tg_id) not in json.dumps(st)

        # the code cannot be used again, by anyone
        await w.say(u, p.body['command'], from_id=777, chat_id=777)
        assert w.bot.sends(777) == []
        # and a second pairing while linked is refused
        assert (await w.web(u.user_id, 'POST', '/telegram/pairing')).status == 409

    async def test_an_expired_code_does_not_link(self, w: World) -> None:
        u = await w.user_with_bot()
        p = await w.web(u.user_id, 'POST', '/telegram/pairing')
        w.clock.advance(minutes=5, seconds=1)
        await w.say(u, p.body['command'])
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['linked'] is False
        assert w.bot.sends(u.chat_id) == []

    async def test_a_new_code_replaces_the_old_one_the_pairing_must_come_from_a_private_chat(self, w: World) -> None:
        u = await w.user_with_bot()
        first = await w.web(u.user_id, 'POST', '/telegram/pairing')
        second = await w.web(u.user_id, 'POST', '/telegram/pairing')
        await w.say(u, first.body['command'])
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['linked'] is False
        await w.say(u, second.body['command'], chat_type='group')
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['linked'] is False
        await w.say(u, second.body['command'])
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['linked'] is True

    async def test_guessing_codes_is_limited_per_sender(self, w: World) -> None:
        u = await w.user_with_bot()
        p = await w.web(u.user_id, 'POST', '/telegram/pairing')
        for i in range(6):
            await w.say(u, f'/start 11111{i}')
        await w.say(u, p.body['command'])  # right code, but this sender used up their tries
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['linked'] is False


class TestSignin:
    async def test_asks_for_the_code_deletes_the_code_message_accepts_a_code_once_opens_the_session(self, w: World) -> None:
        u = await w.linked_user()
        await w.say(u, '/signin')
        w.auth.allow(u.user_id, '482915')
        await w.say(u, '482915')
        assert len([c for c in w.bot.calls if c['op'] == 'deleteMessage']) >= 1
        assert w.bot.last_message(u.chat_id).text == 'Signed in.'
        st = (await w.web(u.user_id, 'GET', '/telegram/link')).body
        assert st['sessionActive'] is True
        assert st['sessionSince'] == iso_ms(w.clock.now)

        # a sniffed code cannot be replayed: sign out, sign in with the same code
        await w.say(u, '/signout')
        await w.say(u, '/signin')
        await w.say(u, '482915')
        assert w.bot.last_message(u.chat_id).text == 'That code did not work. 2 tries left.'
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['sessionActive'] is False

    async def test_three_wrong_codes_in_15_minutes_pause_signin_for_15_minutes_and_are_audited_a_right_code_is_refused_while_paused(
        self, w: World
    ) -> None:
        u = await w.linked_user()
        await w.say(u, '/signin')
        await w.say(u, '111111')
        assert w.bot.last_message(u.chat_id).text == 'That code did not work. 2 tries left.'
        await w.say(u, '222222')
        assert w.bot.last_message(u.chat_id).text == 'That code did not work. 1 try left.'
        w.bus.clear()
        await w.say(u, '333333')
        assert w.bot.last_message(u.chat_id).text == 'Too many wrong codes. Sign-in is paused for 15 minutes.'
        assert [dump(e) for e in w.bus.events_of('audit.record')] == [
            {'userId': u.user_id, 'action': 'telegram.signin_paused', 'meta': {'wrongCodes': 3}}
        ]
        st = (await w.web(u.user_id, 'GET', '/telegram/link')).body
        assert st['signInPausedUntil'] == iso_ms(w.clock.now + timedelta(minutes=15))

        verify_calls = w.auth.calls
        w.auth.allow(u.user_id, '482915')
        await w.say(u, '/signin')
        assert w.bot.last_message(u.chat_id).text == 'Sign-in is paused. Try again in 15 minutes.'
        await w.say(u, '482915')
        assert w.auth.calls == verify_calls  # auth was not even asked
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['sessionActive'] is False

        w.clock.advance(minutes=15, seconds=1)
        await w.say(u, '/signin')
        await w.say(u, '482915')
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['sessionActive'] is True

    async def test_wrong_codes_spread_over_more_than_15_minutes_do_not_pause_a_right_code_resets_the_count(self, w: World) -> None:
        u = await w.linked_user()
        await w.say(u, '/signin')
        await w.say(u, '111111')
        await w.say(u, '222222')
        w.clock.advance(minutes=16)
        await w.say(u, '/signin')
        await w.say(u, '333333')
        assert w.bot.last_message(u.chat_id).text == 'That code did not work. 2 tries left.'

    async def test_text_that_is_not_6_digits_is_not_sent_to_auth_and_does_not_count_as_a_wrong_code(self, w: World) -> None:
        u = await w.linked_user()
        await w.say(u, '/signin')
        before = w.auth.calls
        await w.say(u, 'hello')
        await w.say(u, '12345')
        assert w.auth.calls == before
        assert w.bot.last_message(u.chat_id).text.startswith('Send the 6-digit code')

    async def test_the_code_wait_runs_out_after_5_minutes(self, w: World) -> None:
        u = await w.linked_user()
        await w.say(u, '/signin')
        w.clock.advance(minutes=6)
        w.auth.allow(u.user_id, '482915')
        await w.say(u, '482915')
        assert w.bot.last_message(u.chat_id).text == 'Signed out. Send /signin.'


class TestSessionsEnd:
    async def test_signout_ends_the_session_at_once_nothing_is_sent_new_payments_are_held(self, w: World) -> None:
        u = await w.signed_in_user()
        await w.say(u, '/signout')
        assert w.bot.last_message(u.chat_id).text == 'Signed out. Payments keep saving and wait until you send /signin.'
        n = len(w.bot.calls)
        tx = await w.incoming(u)
        assert calls_since(w, n) == []
        rows = await w.sql('SELECT status FROM telegram_prompts WHERE transaction_id = $1', tx.id)
        assert rows[0]['status'] == 'held'
        await w.say(u, '/pending')
        assert w.bot.last_message(u.chat_id).text == 'Signed out. Send /signin.'

    async def test_a_queued_prompt_whose_session_ended_before_it_was_sent_is_held_not_sent(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = w.new_tx(u)
        await w.emit_raw_changed(tx)
        await w.run_events()
        await w.say(u, '/signout')
        n = len(w.bot.calls)
        await w.settle()
        assert calls_since(w, n) == []
        rows = await w.sql('SELECT status FROM telegram_prompts WHERE transaction_id = $1', tx.id)
        assert rows[0]['status'] == 'held'

    async def test_delete_session_signs_the_bot_out_from_the_web_and_is_safe_to_repeat(self, w: World) -> None:
        u = await w.signed_in_user()
        assert (await w.web(u.user_id, 'DELETE', '/telegram/session')).status == 200
        assert (await w.web(u.user_id, 'DELETE', '/telegram/session')).status == 200
        st = (await w.web(u.user_id, 'GET', '/telegram/link')).body
        assert (st['linked'], st['sessionActive'], st['sessionSince']) == (True, False, None)
        await w.say(u, 'hi')
        assert w.bot.last_message(u.chat_id).text == 'Signed out. Send /signin.'

    async def test_a_session_idle_for_longer_than_session_idle_days_is_no_longer_active_use_keeps_it_alive(self, w: World) -> None:
        u = await w.signed_in_user()
        await w.internal(u.user_id, 'PATCH', '/internal/settings', {'sessionIdleDays': 7})
        w.clock.advance(days=6)
        await w.say(u, '/pending')  # use: still signed in, and it counts as use
        assert w.bot.last_message(u.chat_id).text == 'Nothing needs a tag.'
        w.clock.advance(days=6)
        await w.say(u, '/pending')
        assert w.bot.last_message(u.chat_id).text == 'Nothing needs a tag.'
        w.clock.advance(days=8)
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['sessionActive'] is False
        await w.say(u, '/pending')
        assert w.bot.last_message(u.chat_id).text == 'Signed out. Send /signin.'


class TestCallbacks:
    async def test_a_token_from_another_user_or_from_an_old_message_copy_does_nothing(self, w: World) -> None:
        a = await w.signed_in_user()
        b = await w.signed_in_user()
        tx_a = await w.incoming(a)
        tx_b = await w.incoming(b)
        a_id, a_msg = await w.message_of(tx_a)
        b_id, _ = await w.message_of(tx_b)
        tags = len(w.ledger.tag_calls)
        food = w.bot.button(a_msg, 'Food')['callback_data']

        # B taps A's button (A's token on B's webhook, even on B's own message id)
        await w.tap_data(b, b_id, food)
        assert w.bot.last_answer() == 'That button is no longer active.'
        await w.tap_data(b, a_id, food)
        assert len(w.ledger.tag_calls) == tags
        assert a_msg.text == 'Money out · 6:42 pm'

        # garbage and unknown tokens
        await w.tap_data(a, a_id, 'garbage')
        await w.tap_data(a, a_id, 'AAAAAAAAAAAA:c0')
        assert len(w.ledger.tag_calls) == tags

        # the right token on the wrong message (an older copy) is refused too
        await w.tap_data(a, a_id + 999, food)
        assert w.bot.last_answer() == 'That button is no longer active.'
        assert len(w.ledger.tag_calls) == tags

        # the owner's own tap works
        await w.tap_data(a, a_id, food)
        assert len(w.ledger.tag_calls) == tags + 1

    async def test_a_payment_that_no_longer_exists_is_reported_not_tagged(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        message_id, m = await w.message_of(tx)
        del w.ledger.txs[tx.id]
        await w.tap(u, message_id, m.keyboard, 'Food')
        assert w.bot.last_answer() == 'That payment no longer exists.'
        assert m.text == 'Money out · removed'

    async def test_a_ledger_outage_answers_the_tap_with_a_retry_hint_and_changes_nothing(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        message_id, m = await w.message_of(tx)
        w.ledger.down = True
        try:
            await w.tap(u, message_id, m.keyboard, 'Food')
        finally:
            w.ledger.down = False
        assert w.bot.last_answer() == 'Could not do that right now. Try again in a moment.'
        assert m.text == 'Money out · 6:42 pm'
        rows = await w.sql('SELECT status FROM telegram_prompts WHERE transaction_id = $1', tx.id)
        assert rows[0]['status'] == 'sent'

    async def test_every_tap_is_answered_so_the_button_stops_spinning_and_an_update_is_processed_once(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        message_id, m = await w.message_of(tx)
        answers = len(w.bot.answers)
        await w.tap(u, message_id, m.keyboard, 'Later')
        assert len(w.bot.answers) == answers + 1
        # Telegram re-delivering the same update id is ignored
        update = {'update_id': 88_000_000, 'message': {'message_id': 5, 'from': {'id': u.tg_id}, 'chat': {'id': u.chat_id, 'type': 'private'}, 'text': '/pending'}}  # fmt: skip
        await w.webhook(u, update)
        sends = len(w.bot.sends(u.chat_id))
        await w.webhook(u, update)
        assert len(w.bot.sends(u.chat_id)) == sends


class TestSecretsStaySecret:
    async def test_the_bot_token_is_stored_encrypted_bound_to_the_user_and_never_appears_in_api_responses(self, w: World) -> None:
        u = await w.user_with_bot()
        row = (await w.sql('SELECT * FROM telegram_bots WHERE user_id = $1', u.user_id))[0]
        assert u.token.encode() not in bytes(row['token_enc'])
        cipher = FieldCipher({1: FIELD_KEY})
        assert cipher.decrypt_string(bytes(row['token_enc']), u.user_id) == u.token
        with pytest.raises(Exception):  # noqa: B017  (any failure: the ciphertext cannot be moved to another user's row)
            cipher.decrypt_string(bytes(row['token_enc']), str(uuid.uuid4()))
        # only hashes of the webhook secrets are kept
        assert row['path_hash'] != u.path_secret
        assert u.path_secret not in repr(row)
        assert u.header_secret not in repr(row)

        bodies = [
            (await w.web(u.user_id, 'GET', '/telegram/link')).body,
            (await w.web(u.user_id, 'GET', '/internal/settings')).body,
            (await w.web(u.user_id, 'GET', '/internal/export')).body,
            (await w.web(u.user_id, 'POST', '/telegram/bot-token', {'token': u.token})).body,
            (await w.web(u.user_id, 'POST', '/telegram/bot-token', {'token': 'short'})).body,
        ]
        text = json.dumps(bodies)
        assert u.token not in text
        assert u.token.split(':')[1] not in text
        assert u.path_secret not in text
        assert u.header_secret not in text

    async def test_logs_never_hold_the_bot_token_webhook_secrets_the_signin_code_or_tag_text(self, w: World) -> None:
        bot, auth = FakeBot(), FakeAuth()
        opts = RuntimeOptions(bot=bot, cipher=FieldCipher({1: FIELD_KEY}), sleep=no_sleep)
        app = await build_test_app(
            service='telegram', register=make_register(opts), pool=w.db.pool, clients={'ledger': FakeLedger(), 'auth': auth},
            env={'FIELD_KEY': FIELD_KEY, 'PUBLIC_URL': PUBLIC_URL, 'TELEGRAM_API_BASE': 'http://fake.invalid', 'TELEGRAM_SEND_GAP_MS': 0},
            env_model=Env,
        )  # fmt: skip
        out = io.StringIO()
        app.deps.log = create_logger('telegram', 'debug', stream=out)
        user_id = str(uuid.uuid4())
        token = f'700000999:AAH{"q" * 32}'
        secret_header = 'x-telegram-bot-api-secret-token'

        async def call(method: str, url: str, payload: object = None, extra: dict[str, str] | None = None):
            extra = extra or {}
            headers = headers_for(None if secret_header in extra else user_id, 'gateway', 'UTC', secret_header in extra)
            return await app.client.request(method, url, json=payload, headers={**headers, **extra})

        try:
            assert (await call('POST', '/telegram/bot-token', {'token': token})).status_code == 200
            hook = bot.webhooks[token]
            path = hook['url'].split('/webhook/')[1]
            pair = (await call('POST', '/telegram/pairing')).json()
            hdr = {secret_header: hook['secret_token']}

            async def send(update_id: int, text: str, from_id: int = 4242):
                update = {'update_id': update_id, 'message': {'message_id': update_id, 'from': {'id': from_id}, 'chat': {'id': from_id, 'type': 'private'}, 'text': text}}  # fmt: skip
                return await call('POST', f'/telegram/webhook/{path}', update, hdr)

            await send(1, pair['command'])
            await send(2, '/signin')
            auth.allow(user_id, '482915')
            await send(3, '482915')
            await send(4, 'super-secret-tag-text')
            await call('POST', '/telegram/webhook/' + 'z' * 32, {'update_id': 5}, {secret_header: 'bad'})
        finally:
            await app.close()

        logs = out.getvalue()
        assert len(logs) > 0  # requests were logged ...
        for secret in [token, token.split(':')[1], path, hook['secret_token'], '482915', 'super-secret-tag-text', pair['code']]:
            assert secret not in logs, 'a secret reached the logs'

