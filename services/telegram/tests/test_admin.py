"""Settings, bot token, disconnecting, retention and the export."""

import json
import uuid

from bt_telegram.workers import sweep
from telegram_harness import PUBLIC_URL, World

DEFAULTS = {'allowReveal': True, 'sessionIdleDays': 30, 'digestMode': 'daily', 'digestHour': 21, 'afterTag': 'line'}


class TestSettings:
    async def test_defaults_first_then_a_partial_patch_changes_only_what_was_sent_invalid_values_are_refused(self, w: World) -> None:
        u = str(uuid.uuid4())
        assert (await w.internal(u, 'GET', '/internal/settings')).body == DEFAULTS
        patched = {**DEFAULTS, 'allowReveal': False, 'sessionIdleDays': 7}
        assert (await w.internal(u, 'PATCH', '/internal/settings', {'allowReveal': False, 'sessionIdleDays': 7})).body == patched
        patch = {'digestMode': 'twice', 'digestHour': 9, 'afterTag': 'delete'}
        again = {**patched, **patch}
        assert (await w.internal(u, 'PATCH', '/internal/settings', patch)).body == again
        assert (await w.internal(u, 'GET', '/internal/settings')).body == again
        for bad in [
            {'sessionIdleDays': 0}, {'sessionIdleDays': 91}, {'digestHour': 24}, {'afterTag': 'edit'},
            {'digestMode': 'hourly'}, {'allowReveal': 'yes'},
        ]:  # fmt: skip
            assert (await w.internal(u, 'PATCH', '/internal/settings', bad)).status == 400, bad

    async def test_is_per_user_needs_a_user_and_refuses_calls_the_gateway_forwarded_from_outside(self, w: World) -> None:
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        await w.internal(a, 'PATCH', '/internal/settings', {'digestHour': 6})
        assert (await w.internal(b, 'GET', '/internal/settings')).body['digestHour'] == 21
        assert (await w.internal(None, 'GET', '/internal/settings')).status == 401
        assert (await w.internal(a, 'GET', '/internal/settings', proxied=True)).status == 403
        assert (await w.internal(a, 'GET', '/internal/export', proxied=True)).status == 403

    async def test_settings_survive_unlink_and_a_new_link(self, w: World) -> None:
        u = await w.signed_in_user()
        await w.internal(u.user_id, 'PATCH', '/internal/settings', {'allowReveal': False})
        await w.web(u.user_id, 'DELETE', '/telegram/link')
        assert (await w.internal(u.user_id, 'GET', '/internal/settings')).body['allowReveal'] is False


class TestBotToken:
    async def test_validates_with_get_me_points_the_webhook_at_public_url_with_a_secret_path_and_a_secret_token_header_and_reports_the_bot_name(
        self, w: World
    ) -> None:
        u = await w.user_with_bot()
        hook = w.bot.webhooks[u.token]
        assert hook['url'].startswith(f'{PUBLIC_URL}/telegram/webhook/')
        assert len(u.path_secret) >= 32
        assert len(hook['secret_token']) >= 32
        assert hook['secret_token'] != u.path_secret
        assert [c['op'] for c in w.bot.calls if c['token'] == u.token][:2] == ['getMe', 'setWebhook']
        st = (await w.web(u.user_id, 'GET', '/telegram/link')).body
        assert st['botSaved'] is True
        assert st['botUsername'] == f'bot_{u.token.split(":")[0]}'
        assert st['linked'] is False
        assert st['sessionActive'] is False

    async def test_refuses_a_token_telegram_rejects_a_malformed_token_and_saves_nothing(self, w: World) -> None:
        user_id = str(uuid.uuid4())
        bad = f'700123456:AAH{"b" * 30}'
        w.bot.rejected.add(bad)
        assert (await w.web(user_id, 'POST', '/telegram/bot-token', {'token': bad})).status == 422
        assert (await w.web(user_id, 'POST', '/telegram/bot-token', {'token': 'nope'})).status == 400
        assert (await w.web(user_id, 'POST', '/telegram/bot-token', {})).status == 400
        assert (await w.web(user_id, 'GET', '/telegram/link')).body['botSaved'] is False
        assert bad not in w.bot.webhooks

    async def test_replacing_the_bot_clears_the_link_and_the_session_takes_the_old_webhook_down_and_the_old_secrets_stop_working(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        _, old_msg = await w.message_of(tx)
        fresh = f'700555555:AAH{"c" * 30}'
        assert (await w.web(u.user_id, 'POST', '/telegram/bot-token', {'token': fresh})).status == 200
        assert u.token not in w.bot.webhooks
        assert old_msg.deleted is True
        st = (await w.web(u.user_id, 'GET', '/telegram/link')).body
        assert (st['botSaved'], st['linked'], st['sessionActive']) == (True, False, False)
        assert (await w.webhook(u, {'update_id': 5})).status == 401
        assert await w.sql('SELECT 1 FROM telegram_prompts WHERE user_id = $1', u.user_id) == []

    async def test_saving_the_same_token_again_keeps_its_new_webhook(self, w: World) -> None:
        user_id = str(uuid.uuid4())
        token = f'700777777:AAH{"d" * 30}'
        assert (await w.web(user_id, 'POST', '/telegram/bot-token', {'token': token})).status == 200
        first = w.bot.webhooks[token]['url']
        assert (await w.web(user_id, 'POST', '/telegram/bot-token', {'token': token})).status == 200
        assert w.bot.webhooks[token]['url'] != first  # a fresh secret path is registered and still in place
        assert [c for c in w.bot.calls if c['op'] == 'deleteWebhook' and c['token'] == token] == []


class TestDisconnecting:
    async def test_delete_link_deletes_the_link_sessions_pairings_and_prompt_records_removes_bot_messages_where_possible_and_the_id_is_a_stranger_afterwards(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        _, m = await w.message_of(tx)
        await w.web(u.user_id, 'POST', '/telegram/pairing')
        w.bus.clear()
        assert (await w.web(u.user_id, 'DELETE', '/telegram/link')).status == 200
        for table in ['telegram_links', 'telegram_sessions', 'telegram_pairings', 'telegram_prompts']:
            assert await w.sql(f'SELECT 1 FROM {table} WHERE user_id = $1', u.user_id) == [], table
        assert m.deleted is True
        assert [e.action for e in w.bus.events_of('audit.record')] == ['telegram.unlink']
        st = (await w.web(u.user_id, 'GET', '/telegram/link')).body
        assert (st['botSaved'], st['linked'], st['sessionActive'], st['heldCount']) == (True, False, False, 0)

        n = len(w.bot.calls)
        await w.say(u, '/signin')
        await w.say(u, '/pending')
        assert w.bot.calls[n:] == []
        assert (await w.web(u.user_id, 'DELETE', '/telegram/link')).status == 200  # safe to repeat

    async def test_messages_telegram_will_not_delete_stay_the_user_can_delete_the_chat_and_do_not_fail_the_disconnect(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        _, m = await w.message_of(tx)
        w.bot.too_old_to_delete = True
        try:
            assert (await w.web(u.user_id, 'DELETE', '/telegram/link')).status == 200
        finally:
            w.bot.too_old_to_delete = False
        assert m.deleted is False

    async def test_unlink_in_the_chat_does_the_same_then_confirms(self, w: World) -> None:
        u = await w.signed_in_user()
        await w.incoming(u)
        await w.say(u, '/unlink')
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['linked'] is False
        assert w.bot.last_message(u.chat_id).text == 'Disconnected. This bot will not send or accept anything now.'
        # re-linking needs a new code
        p = await w.web(u.user_id, 'POST', '/telegram/pairing')
        assert p.status == 201
        await w.say(u, p.body['command'])
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['linked'] is True


class TestRetentionAndDeletion:
    async def test_the_nightly_sweep_ends_idle_sessions_per_user_setting_and_removes_expired_pairings(self, w: World) -> None:
        idle = await w.signed_in_user()
        fresh = await w.signed_in_user()
        await w.internal(idle.user_id, 'PATCH', '/internal/settings', {'sessionIdleDays': 7})
        waiting = await w.user_with_bot()
        await w.web(waiting.user_id, 'POST', '/telegram/pairing')

        w.clock.advance(days=8)
        await w.say(fresh, '/signin')  # fresh user (30 days) is still inside its window; this just proves it is active
        out = await sweep(w.runtime)
        assert out['sessions'] == 1
        assert out['pairings'] >= 1
        rows = await w.sql('SELECT ended_at, end_reason FROM telegram_sessions WHERE user_id = $1', idle.user_id)
        assert rows[0]['end_reason'] == 'idle'
        assert (await w.sql('SELECT ended_at FROM telegram_sessions WHERE user_id = $1', fresh.user_id))[0]['ended_at'] is None
        assert await w.sql('SELECT 1 FROM telegram_pairings WHERE user_id = $1', waiting.user_id) == []
        assert (await w.web(idle.user_id, 'GET', '/telegram/link')).body['sessionActive'] is False

    async def test_registers_its_jobs_hourly_digest_nightly_sweep_queue_and_every_event_it_consumes(self, w: World) -> None:
        queues = [s.queue for s in w.bus.schedules]
        assert 'telegram.digest' in queues
        assert 'retention.sweep.telegram' in queues
        for e in ['transaction.changed', 'alert.created', 'unparsed.created', 'account.deleted']:
            assert e in w.bus._event_handlers, e
        for j in ['telegram.send', 'telegram.sync_prompt', 'telegram.digest', 'retention.sweep.telegram']:
            assert j in w.bus._job_handlers, j

    async def test_account_deleted_purges_every_row_for_that_user_only_and_takes_the_webhook_down(self, w: World) -> None:
        gone = await w.signed_in_user()
        kept = await w.signed_in_user()
        await w.incoming(gone)
        await w.incoming(kept)
        await w.internal(gone.user_id, 'PATCH', '/internal/settings', {'digestHour': 5})
        await w.bus.emit(None, 'account.deleted', {'userId': gone.user_id})
        await w.settle()
        for table in [
            'telegram_bots', 'telegram_links', 'telegram_sessions', 'telegram_pairings', 'telegram_prompts', 'telegram_settings',
        ]:  # fmt: skip
            assert await w.sql(f'SELECT 1 FROM {table} WHERE user_id = $1', gone.user_id) == [], table
        assert len(await w.sql('SELECT 1 FROM telegram_prompts WHERE user_id = $1', kept.user_id)) == 1
        assert gone.token not in w.bot.webhooks
        assert kept.token in w.bot.webhooks
        assert (await w.webhook(gone, {'update_id': 1})).status == 401


class TestExport:
    async def test_has_links_and_counts_but_no_token_secrets_hashes_callback_tokens_or_message_ids(self, w: World) -> None:
        u = await w.signed_in_user()
        await w.incoming(u)
        await w.web(u.user_id, 'POST', '/telegram/pairing')
        res = await w.internal(u.user_id, 'GET', '/internal/export')
        assert res.status == 200
        assert res.body['service'] == 'telegram'
        assert len(res.body['tables']['telegram_links']) == 1
        assert len(res.body['tables']['telegram_sessions']) == 1
        assert res.body['tables']['telegram_prompt_counts'] == [{'kind': 'tag', 'status': 'sent', 'count': 1}]
        text = json.dumps(res.body)
        prompt = (await w.sql('SELECT token, message_id FROM telegram_prompts WHERE user_id = $1', u.user_id))[0]
        for secret in [
            u.token, u.token.split(':')[1], u.path_secret, u.header_secret, prompt['token'],
            'token_enc', 'path_hash', 'header_hash', 'code_hash',
        ]:  # fmt: skip
            assert secret not in text, secret
        assert (await w.internal(str(uuid.uuid4()), 'GET', '/internal/export')).body['tables']['telegram_links'] == []
