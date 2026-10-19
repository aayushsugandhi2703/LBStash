"""The product loop: payment event -> prompt -> tap -> tag -> message edited, plus held prompts, sync, alerts, the digest,
Telegram's delivery limits, Reveal and typed tags."""

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from bt.contracts import dump
from bt.contracts.base import iso_ms
from bt_telegram.botapi import BotApiError
from bt_telegram.prompts import send_prompt
from telegram_harness import PUBLIC_URL, START, FakeTx, TgUser, World, make_world


async def tap_on(w: World, u: TgUser, tx: FakeTx, label: str) -> None:
    message_id, msg = await w.message_of(tx)
    await w.tap(u, message_id, msg.keyboard, label)


def tags_for(w: World, tx: FakeTx) -> list[dict[str, Any]]:
    return [c for c in w.ledger.tag_calls if c['id'] == tx.id]


def labels(w: World, m: Any) -> list[str]:
    return [b['text'] for b in w.bot.buttons(m)]


class TestTheLoop:
    async def test_sends_a_no_details_prompt_tags_through_the_ledger_with_via_telegram_edits_the_message_and_a_second_tap_says_already_tagged(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        message_id, msg = await w.message_of(tx)

        assert msg.text == 'Money out · 6:42 pm'
        assert labels(w, msg) == ['Food', 'Travel', 'Fun', 'Bills', 'Sip', 'Rent', 'transfer', '＋ New tag', 'Reveal', 'Later']
        assert all(
            len(b['callback_data']) <= 64 and not re.search(r'food|swiggy|450', b['callback_data'], re.IGNORECASE) for b in w.bot.buttons(msg)
        )
        assert (await w.prompt_row(tx.id))['status'] == 'sent'

        await w.tap(u, message_id, msg.keyboard, 'Food')
        assert len(w.ledger.tag_calls) == 1
        body = w.ledger.tag_calls[0]['body']
        assert body['categoryId'] == w.ledger.category(u.user_id, 'food').id
        assert body['via'] == 'telegram'
        assert msg.text == 'Money out · Food ✓'
        assert (msg.keyboard or []) == []
        assert w.bot.last_answer() == 'Tagged Food'
        assert (await w.prompt_row(tx.id))['status'] == 'tagged'

        # a stale tap reuses the original callback token
        token = (await w.prompt_row(tx.id))['token']
        await w.tap_data(u, message_id, f'{token}:c1')
        assert w.bot.last_answer() == 'Already Food'
        assert len(w.ledger.tag_calls) == 1  # nothing was written again

    async def test_a_payment_tagged_in_telegram_at_the_same_moment_as_the_web_first_write_wins_the_tap_says_already_tagged(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        w.ledger.tag_elsewhere(tx.id, 'bills')  # web got there first, event not yet delivered
        await tap_on(w, u, tx, 'Food')
        assert w.bot.last_answer() == 'Already Bills'
        assert (await w.message_of(tx))[1].text == 'Money out · Bills ✓'

    async def test_prompts_only_credits_as_money_in_and_offers_to_add_to_the_plan_yes_emits_credit_added_answered_once(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u, type='credit', amount_minor=5_000_000, payee='ACME')
        _, msg = await w.message_of(tx)
        assert msg.text == 'Money in · 6:42 pm'
        await tap_on(w, u, tx, 'Fun')
        q = w.bot.last_message(u.chat_id)
        assert q.text == "Add to this month's plan?"
        w.bus.clear()
        no_data = w.bot.button(q, 'No')['callback_data']
        await w.tap_message(u, q, 'Yes')
        assert [dump(e) for e in w.bus.events_of('credit.added')] == [
            {'userId': u.user_id, 'transactionId': tx.id, 'month': '2026-10', 'amountMinor': 5_000_000, 'addToPlan': True}
        ]
        assert q.text == "Added to this month's plan."
        await w.tap_data(u, w.bot.id_of(q), no_data)
        assert len(w.bus.events_of('credit.added')) == 1  # the first answer stands

    async def test_no_message_ever_holds_an_amount_payee_or_bank_detail(self, w: World) -> None:
        u = await w.signed_in_user()
        await w.incoming(u, amount_minor=123_456, payee='HDFC Bank Salary')
        texts = '\n'.join(m.text + '\n' + '\n'.join(labels(w, m)) for m in w.bot.chat(u.chat_id))
        assert not re.search(r'1,?234|hdfc|salary|₹|rs\.?\s?\d|inr', texts, re.IGNORECASE)

    async def test_with_no_telegram_link_nothing_is_queued_the_payment_waits_in_the_web_app(self, w: World) -> None:
        u = await w.user_with_bot()  # bot saved, never linked
        await w.incoming(u)
        assert await w.sql('SELECT 1 FROM telegram_prompts WHERE user_id = $1', u.user_id) == []

    async def test_the_same_event_delivered_twice_creates_one_prompt_and_one_message(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = w.new_tx(u)
        await w.emit_changed(tx)
        await w.emit_changed(tx)
        assert len([m for m in w.bot.chat(u.chat_id) if m.text.startswith('Money out')]) == 1


class TestHeldPrompts:
    async def test_while_signed_out_prompts_are_held_and_nothing_is_sent_signin_says_how_many_wait_then_releases_them_oldest_first(
        self, w: World
    ) -> None:
        u = await w.linked_user()
        a = await w.incoming(u, payee='A')
        b = await w.incoming(u, payee='B')
        assert len(w.bot.sends(u.chat_id)) == 1  # only the "Linked" message
        assert (await w.prompt_row(a.id))['status'] == 'held'
        assert (await w.web(u.user_id, 'GET', '/telegram/link')).body['heldCount'] == 2

        await w.sign_in(u)
        assert w.bot.last_message(u.chat_id).text == 'Signed in. 2 payments waiting.'
        await w.settle()
        texts = [m.text for m in w.bot.chat(u.chat_id)]
        assert texts[-3:] == ['Signed in. 2 payments waiting.', 'Money out · 6:42 pm', 'Money out · 6:42 pm']
        rows = await w.sql('SELECT transaction_id FROM telegram_prompts WHERE user_id = $1 ORDER BY message_id', u.user_id)
        assert [r['transaction_id'] for r in rows] == [a.id, b.id]

    async def test_a_held_prompt_whose_payment_was_tagged_on_the_web_while_waiting_is_never_sent(self, w: World) -> None:
        u = await w.linked_user()
        tx = await w.incoming(u)
        w.ledger.tag_elsewhere(tx.id, 'food')
        await w.emit_changed(tx, 'updated', 'web')
        assert (await w.prompt_row(tx.id))['status'] == 'tagged'
        await w.sign_in(u)
        await w.settle()
        assert 'Money out · 6:42 pm' not in [m.text for m in w.bot.chat(u.chat_id)]
        assert w.bot.last_message(u.chat_id).text == 'Signed in.'

    async def test_a_held_limit_alert_is_released_with_a_one_line_note(self, w: World) -> None:
        u = await w.linked_user()
        await w.bus.emit(
            None, 'alert.created',
            {
                'userId': u.user_id, 'alertId': str(uuid.uuid4()), 'budgetId': str(uuid.uuid4()), 'categoryId': str(uuid.uuid4()),
                'categoryName': 'food', 'level': 'alert', 'periodKey': '2026-10', 'pct': 80,
            },
        )  # fmt: skip
        await w.settle()
        assert 'Food reached 80%' not in [m.text for m in w.bot.chat(u.chat_id)]
        await w.sign_in(u)
        assert w.bot.last_message(u.chat_id).text == 'Signed in.\nA limit alert was held too.'
        await w.settle()
        assert w.bot.last_message(u.chat_id).text == 'Food reached 80%'


class TestSyncTaggedElsewhere:
    async def test_a_web_tag_edits_the_telegram_message_to_its_final_state_buttons_removed_the_payee_cascade_marks_the_others_auto_tagged(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        a = await w.incoming(u, payee='Zomato')
        b = await w.incoming(u, payee='Zomato')
        c = await w.incoming(u, payee='Other')
        w.ledger.tag_elsewhere(a.id, 'food')
        w.ledger.tag_elsewhere(b.id, 'food')
        await w.emit_changed(a, 'updated', 'web')
        await w.emit_changed(b, 'updated', 'rule')
        ma = (await w.message_of(a))[1]
        mb = (await w.message_of(b))[1]
        assert ma.text == 'Money out · Food ✓'
        assert (ma.keyboard or []) == []
        assert mb.text == 'Money out · auto-tagged Food ✓'
        assert len((await w.message_of(c))[1].keyboard) > 0  # untouched

    async def test_tagging_in_telegram_auto_tags_the_same_payee_and_edits_those_messages_too(self, w: World) -> None:
        u = await w.signed_in_user()
        a = await w.incoming(u, payee='Uber')
        b = await w.incoming(u, payee='Uber')
        await tap_on(w, u, a, 'Travel')
        await w.settle()  # the queued sync_prompt for b
        assert (await w.message_of(b))[1].text == 'Money out · auto-tagged Travel ✓'
        assert (await w.prompt_row(b.id))['status'] == 'auto_tagged'

    async def test_a_deleted_payment_edits_its_message_to_removed(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        del w.ledger.txs[tx.id]
        await w.emit_changed(tx, 'deleted')
        assert (await w.message_of(tx))[1].text == 'Money out · removed'
        assert (await w.prompt_row(tx.id))['status'] == 'expired'

    async def test_after_tag_delete_removes_the_message_instead_of_editing_it(self, w: World) -> None:
        u = await w.signed_in_user()
        await w.internal(u.user_id, 'PATCH', '/internal/settings', {'afterTag': 'delete'})
        tx = await w.incoming(u)
        message_id, _ = await w.message_of(tx)
        await tap_on(w, u, tx, 'Food')
        assert w.bot.messages[message_id].deleted is True


class TestAfterTagKeep:
    async def test_keeps_the_message_as_it_was_minus_the_buttons_with_the_tag_on_a_second_line(self, w: World) -> None:
        u = await w.signed_in_user()
        await w.internal(u.user_id, 'PATCH', '/internal/settings', {'afterTag': 'keep'})
        tx = await w.incoming(u)
        await tap_on(w, u, tx, 'Food')
        m = (await w.message_of(tx))[1]
        assert m.text == 'Money out · 6:42 pm\nFood ✓'
        assert (m.keyboard or []) == []


class TestAlertsNudgesAndTheDigest:
    async def test_alerts_name_the_category_and_level_only_escaped_with_no_rupee_figure(self, w: World) -> None:
        u = await w.signed_in_user()
        ids = {'userId': u.user_id, 'budgetId': str(uuid.uuid4()), 'categoryId': str(uuid.uuid4()), 'periodKey': '2026-10'}
        await w.bus.emit(None, 'alert.created', {**ids, 'alertId': str(uuid.uuid4()), 'categoryName': 'food', 'level': 'alert', 'pct': 80})
        await w.bus.emit(
            None, 'alert.created',
            {**ids, 'alertId': str(uuid.uuid4()), 'categoryName': '<b>fun</b> & co', 'level': 'exceeded', 'pct': 104},
        )  # fmt: skip
        await w.settle()
        texts = [m.text for m in w.bot.chat(u.chat_id)]
        assert 'Food reached 80%' in texts
        assert '&lt;b&gt;fun&lt;/b&gt; &amp; co went over its limit (104%)' in texts
        assert not re.search(r'₹|rs', ' '.join(texts), re.IGNORECASE)

    async def test_an_alert_event_delivered_twice_sends_once(self, w: World) -> None:
        u = await w.signed_in_user()
        ev = {
            'userId': u.user_id, 'alertId': str(uuid.uuid4()), 'budgetId': str(uuid.uuid4()), 'categoryId': str(uuid.uuid4()),
            'categoryName': 'rent', 'level': 'alert', 'periodKey': '2026-10', 'pct': 90,
        }  # fmt: skip
        await w.bus.emit(None, 'alert.created', ev)
        await w.bus.emit(None, 'alert.created', ev)
        await w.settle()
        assert len([m for m in w.bot.chat(u.chat_id) if m.text == 'Rent reached 90%']) == 1

    async def test_the_unparsed_nudge_goes_out_on_the_first_failure_and_when_more_than_3_pile_up_in_24_hours_not_in_between(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        for n in [1, 2, 3, 4]:
            await w.bus.emit(None, 'unparsed.created', {'userId': u.user_id, 'unparsedId': str(uuid.uuid4()), 'failuresLast24h': n})
        await w.settle()
        nudges = [m.text for m in w.bot.chat(u.chat_id) if 'could not be read' in m.text]
        assert nudges == [
            '1 message could not be read. Open Needs a look in the web app.',
            '4 messages could not be read. Open Needs a look in the web app.',
        ]

    async def test_at_the_users_digest_hour_n_payments_still_need_a_tag_with_a_start_button_no_amounts_once_per_day(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        await w.incoming(u, payee='P1')
        await w.incoming(u, payee='P2')
        await w.incoming(u, payee='P3')
        before = len(w.bot.chat(u.chat_id))

        async def tick() -> None:
            await w.bus.enqueue(None, 'telegram.digest', {})
            await w.settle()

        await tick()  # 6:42 pm in Kolkata: not the digest hour (9 pm)
        assert len(w.bot.chat(u.chat_id)) == before

        w.clock.now = datetime(2026, 10, 18, 15, 30, tzinfo=UTC)  # 9:00 pm Kolkata
        await tick()
        d = w.bot.last_message(u.chat_id)
        assert d.text == '3 payments still need a tag'
        assert labels(w, d) == ['Start']
        await tick()
        assert len([m for m in w.bot.chat(u.chat_id) if 'still need a tag' in m.text]) == 1

        # Start brings the oldest pending payment to the bottom of the chat, with a Next button
        await w.tap_message(u, d, 'Start')
        await w.settle()
        resent = w.bot.last_message(u.chat_id)
        assert re.match(r'^Money out', resent.text)
        assert 'Next ▶' in labels(w, resent)

    async def test_digest_mode_off_sends_nothing_twice_also_sends_12_hours_after_the_first_hour(self, w: World) -> None:
        async def tick() -> None:
            await w.bus.enqueue(None, 'telegram.digest', {})
            await w.settle()

        def digests(u: TgUser) -> int:
            return len([m for m in w.bot.chat(u.chat_id) if re.search(r'still needs? a tag', m.text)])

        off = await w.signed_in_user()
        twice = await w.signed_in_user()
        await w.incoming(off)
        await w.incoming(twice)
        await w.internal(off.user_id, 'PATCH', '/internal/settings', {'digestMode': 'off'})
        await w.internal(twice.user_id, 'PATCH', '/internal/settings', {'digestMode': 'twice'})
        w.clock.now = datetime(2026, 10, 18, 15, 30, tzinfo=UTC)  # 9:00 pm Kolkata
        await tick()
        assert [digests(off), digests(twice)] == [0, 1]
        w.clock.now = datetime(2026, 10, 19, 3, 30, tzinfo=UTC)  # 9:00 am Kolkata, 12 hours later
        await tick()
        assert [digests(off), digests(twice)] == [0, 2]
        await tick()  # same hour again: still once per slot
        assert digests(twice) == 2

    async def test_no_digest_while_signed_out_and_none_when_nothing_needs_a_tag(self, w: World) -> None:
        u = await w.linked_user()
        await w.incoming(u)
        w.clock.now = datetime(2026, 10, 19, 15, 30, tzinfo=UTC)
        await w.bus.enqueue(None, 'telegram.digest', {})
        await w.settle()
        assert not any('still need' in m.text for m in w.bot.chat(u.chat_id))

        v = await w.signed_in_user()
        w.clock.now = datetime(2026, 10, 20, 15, 30, tzinfo=UTC)
        await w.bus.enqueue(None, 'telegram.digest', {})
        await w.settle()
        assert not any('still need' in m.text for m in w.bot.chat(v.chat_id))
        rows = await w.sql("SELECT status FROM telegram_prompts WHERE user_id = $1 AND kind = 'digest'", v.user_id)
        assert rows == [{'status': 'expired'}]

    async def test_the_weekly_balance_nudge_goes_out_with_the_sunday_digest_unless_a_check_was_made_this_week(self, w: World) -> None:
        async def tick() -> None:
            await w.bus.enqueue(None, 'telegram.digest', {})
            await w.settle()

        def nudges(user: TgUser) -> list[Any]:
            return [m for m in w.bot.chat(user.chat_id) if m.text.startswith('Time to compare your balance')]

        u = await w.signed_in_user()
        w.clock.now = datetime(2026, 10, 18, 15, 30, tzinfo=UTC)  # Sunday 9:00 pm Kolkata, the digest hour
        w.ledger.balance_checked_at = w.clock.now - timedelta(days=2)
        try:
            await tick()
            assert nudges(u) == []

            w.ledger.balance_checked_at = w.clock.now - timedelta(days=8)
            w.clock.now += timedelta(days=7)  # next Sunday
            await tick()
            assert len(nudges(u)) == 1
            assert w.bot.buttons(nudges(u)[0]) == [{'text': 'Check balance', 'url': f'{PUBLIC_URL}/ledger?check=1'}]
            await tick()
            assert len(nudges(u)) == 1  # once per day
        finally:
            w.ledger.balance_checked_at = START

    async def test_pending_sends_the_count_with_start_and_next_walks_the_rest_oldest_first(self, w: World) -> None:
        u = await w.signed_in_user()
        a = await w.incoming(u, payee='a', occurred_at='2026-10-18T08:00:00.000Z')
        b = await w.incoming(u, payee='b', occurred_at='2026-10-18T09:00:00.000Z')
        await w.say(u, '/pending')
        d = w.bot.last_message(u.chat_id)
        assert d.text == '2 payments still need a tag'
        await w.tap_message(u, d, 'Start')
        await w.settle()
        first = (await w.message_of(a))[1]
        assert w.bot.last_message(u.chat_id) is first
        await w.tap_message(u, first, 'Next ▶')
        await w.settle()
        second = (await w.message_of(b))[1]
        assert w.bot.last_message(u.chat_id) is second
        await w.tap_message(u, second, 'Next ▶')
        assert w.bot.last_answer() == 'That was the last one.'


class TestDeliveryOrderAndTelegramLimits:
    async def test_five_payments_in_a_minute_arrive_as_five_messages_oldest_first_even_if_the_jobs_run_out_of_order(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        txs: list[FakeTx] = []
        for i in range(5):
            tx = w.new_tx(u, occurred_at=iso_ms(w.clock.now + timedelta(minutes=i)), payee=f'P{i}')
            txs.append(tx)
            await w.emit_raw_changed(tx)
        await w.run_events()  # the prompts exist and their send jobs are queued
        send_jobs = [j.payload.prompt_id for j in w.bus.jobs if j.job == 'telegram.send']
        assert len(send_jobs) == 5
        w.bus.clear()
        for id_ in reversed(send_jobs):
            await send_prompt(w.runtime, id_)

        rows = await w.sql(
            "SELECT transaction_id FROM telegram_prompts WHERE user_id = $1 AND kind = 'tag' ORDER BY message_id", u.user_id
        )
        assert [r['transaction_id'] for r in rows] == [t.id for t in txs]

    async def test_spaces_messages_to_one_chat_at_least_a_gap_apart(self, w: World) -> None:
        slow = await make_world(w.db, send_gap_ms=1000)
        try:
            u = await slow.signed_in_user()
            slow.sleeps.clear()
            for i in range(3):
                await slow.incoming(u, payee=f'S{i}')
            assert len(slow.sleeps) >= 2
            assert all(0 < s <= 1 for s in slow.sleeps)
        finally:
            await slow.close()

    async def test_telegram_rate_limit_the_job_fails_so_it_retries_the_prompt_stays_queued_and_goes_out_exactly_once(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        tx = w.new_tx(u)
        w.bot.fail_next('sendMessage', BotApiError('rate_limited', 'slow down', 7))
        await w.emit_raw_changed(tx)
        await w.run_events()  # prompt created, send job queued
        prompt_id = next(j for j in w.bus.jobs if j.job == 'telegram.send').payload.prompt_id
        w.bus.clear()
        with pytest.raises(BotApiError) as e:
            await send_prompt(w.runtime, prompt_id)
        assert (e.value.kind, e.value.retry_after) == ('rate_limited', 7)
        assert (await w.prompt_row(tx.id))['status'] == 'queued'
        assert not any(m.text.startswith('Money out') for m in w.bot.chat(u.chat_id))
        await send_prompt(w.runtime, prompt_id)  # the retry
        await send_prompt(w.runtime, prompt_id)  # a duplicate job does nothing
        assert len([m for m in w.bot.chat(u.chat_id) if m.text.startswith('Money out')]) == 1
        assert (await w.prompt_row(tx.id))['status'] == 'sent'

    async def test_a_blocked_bot_marks_the_prompt_failed_and_stops_retrying_telegram_down_keeps_it_queued(self, w: World) -> None:
        u = await w.signed_in_user()

        async def make() -> tuple[FakeTx, str]:
            tx = w.new_tx(u)
            await w.emit_raw_changed(tx)
            await w.run_events()
            id_ = next(j for j in w.bus.jobs if j.job == 'telegram.send').payload.prompt_id
            w.bus.clear()
            return tx, id_

        blocked_tx, blocked_id = await make()
        w.bot.fail_next('sendMessage', BotApiError('blocked', 'forbidden'))
        await send_prompt(w.runtime, blocked_id)
        assert (await w.prompt_row(blocked_tx.id))['status'] == 'failed'

        down_tx, down_id = await make()
        w.bot.fail_next('sendMessage', BotApiError('network', 'down'))
        with pytest.raises(Exception):  # noqa: B017  (any error: the job fails so the queue retries it)
            await send_prompt(w.runtime, down_id)
        assert (await w.prompt_row(down_tx.id))['status'] == 'queued'
        await send_prompt(w.runtime, down_id)
        assert (await w.prompt_row(down_tx.id))['status'] == 'sent'


class TestReveal:
    async def test_shows_amount_and_payee_escaped_then_a_delayed_sync_puts_the_no_details_message_back(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u, amount_minor=123_456, payee='<i>Evil</i> & Co')
        message_id, msg = await w.message_of(tx)
        await w.tap(u, message_id, msg.keyboard, 'Reveal')
        assert msg.text == 'Money out · 6:42 pm\n₹1,234.56 · &lt;i&gt;Evil&lt;/i&gt; &amp; Co'
        job = next((j for j in w.bus.jobs if j.job == 'telegram.sync_prompt'), None)
        assert job is not None
        assert re.match(r'^reveal:', job.key or '')
        await w.settle()
        assert msg.text == 'Money out · 6:42 pm'
        assert 'Reveal' in labels(w, msg)

    async def test_with_reveal_off_the_button_is_absent_from_new_prompts_and_a_stale_reveal_tap_is_refused(self, w: World) -> None:
        u = await w.signed_in_user()
        first = await w.incoming(u)
        old_id, old = await w.message_of(first)
        reveal_data = w.bot.button(old, 'Reveal')['callback_data']
        assert (await w.internal(u.user_id, 'PATCH', '/internal/settings', {'allowReveal': False})).status == 200

        second = await w.incoming(u)
        assert 'Reveal' not in labels(w, (await w.message_of(second))[1])

        w.ledger.get_calls.clear()
        await w.tap_data(u, old_id, reveal_data)
        assert w.bot.last_answer() == 'Reveal is switched off.'
        assert w.ledger.get_calls == []
        assert old.text == 'Money out · 6:42 pm'


class TestTypedTags:
    async def test_new_tag_opens_a_reply_box_the_typed_tag_is_normalised_and_sent_to_the_ledger_invalid_text_is_refused_and_the_box_stays_it_expires_after_2_minutes(
        self, w: World
    ) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        await tap_on(w, u, tx, '＋ New tag')
        ask = w.bot.last_message(u.chat_id)
        assert ask.text == 'Reply with the tag.'
        assert ask.force_reply is True

        await w.say(u, '###')
        assert w.bot.last_message(u.chat_id).text.startswith('A tag can use letters')
        assert tags_for(w, tx) == []

        await w.say(u, '  #Gym Class ')
        assert tags_for(w, tx)[0]['body'] == {'tag': 'gym class', 'via': 'telegram'}
        assert (await w.message_of(tx))[1].text == 'Money out · Gym class ✓'
        assert ask.deleted is True

        tx2 = await w.incoming(u)
        await tap_on(w, u, tx2, '＋ New tag')
        w.clock.advance(minutes=3)
        await w.say(u, 'late')
        assert w.bot.last_message(u.chat_id).text.startswith('Use the buttons')
        assert tags_for(w, tx2) == []

    async def test_typed_text_that_is_only_html_noise_never_reaches_the_ledger_as_markup(self, w: World) -> None:
        u = await w.signed_in_user()
        tx = await w.incoming(u)
        await tap_on(w, u, tx, '＋ New tag')
        await w.say(u, '<b>bold</b>')
        assert tags_for(w, tx) == []
