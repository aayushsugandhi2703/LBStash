"""Webhook handling. Checks in order: webhook secrets, private chat, linked Telegram id, active session. Anyone who fails gets no reply."""

import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

import psycopg
from lbstash.clients import CallAs
from lbstash.common import AppError, Errors, month_key, normalize_tag
from lbstash.contracts import TelegramSettings, TelegramUpdate
from lbstash.contracts.telegram import TgCallbackQuery, TgMessage, TgUser
from lbstash.crypto import safe_equal, sha256_hex

from .botapi import ForceReply, Keyboard
from .link import is_owner, pairing_hash, unlink
from .messages import T, header_text, pay_keyboard, plan_keyboard, reveal_text, tag_keyboard
from .prompts import enqueue_sync, release_held, resend_oldest_pending, send_pending_summary, show_final
from .runtime import Runtime, quietly
from .store import (
    OPEN_STATUSES,
    BotRow,
    Direction,
    LinkRow,
    PromptRow,
    end_sessions,
    get_link,
    get_prompt,
    get_settings,
    make_row,
    touch_session,
)

CODE_WAIT = timedelta(minutes=5)
TAG_WAIT = timedelta(minutes=2)
REVEAL_SECONDS = 30
FAIL_WINDOW = timedelta(minutes=15)
PAUSE = timedelta(minutes=15)
MAX_WRONG = 3

_DUMMY_HASH = sha256_hex('no-such-bot')

_START = re.compile(r'/start(?:@\w+)?\s+(\d{6})')
_COMMAND = re.compile(r'/([A-Za-z_]+)(?:@\w+)?(?:\s+(.*))?', re.DOTALL)
# `/300` or `/300 chai` = money out, `+1500` or `+1500 salary` = money in
_AMOUNT = re.compile(r'([/+])(\d{1,9}(?:\.\d{1,2})?)(?:@\w+)?(?:\s+(.+))?', re.DOTALL)


async def authenticate_webhook(rt: Runtime, path_secret: str, header: str | None, ip: str) -> BotRow:
    """The path secret finds the owner, the header secret proves the caller is Telegram. Both must match (constant-time compare)."""
    async with rt.deps.as_system() as tx:
        row = await tx.maybe_one('SELECT * FROM telegram_bots WHERE path_hash = $1', [sha256_hex(path_secret)])
    header_ok = safe_equal(sha256_hex(header or ''), row['header_hash'] if row else _DUMMY_HASH)
    if row is None or not header or not header_ok:
        # count only failures per address: guessing is throttled, but bad calls can't lock out Telegram itself
        if not rt.bad_secret.allow(f'ip:{ip}'):
            raise Errors.too_many()
        raise Errors.unauthorized('Bad webhook secret')
    if not rt.webhook.allow(f'bot:{row["user_id"]}'):
        raise Errors.too_many()
    bot = make_row(BotRow, row)
    assert bot is not None
    return bot


@dataclass
class Cx:
    rt: Runtime
    bot: BotRow
    token: str
    link: LinkRow
    settings: TelegramSettings
    user_id: str
    chat_id: int
    as_: CallAs


async def _say(cx: Cx, text: str, keyboard: Keyboard | None = None) -> None:
    await quietly(cx.rt, lambda: cx.rt.bot.send_message(cx.token, chat_id=cx.chat_id, text=text, keyboard=keyboard), 'say')


async def handle_update(rt: Runtime, bot: BotRow, update: TelegramUpdate) -> None:
    cq = update.callback_query
    msg = update.message
    from_ = cq.from_ if cq else (msg.from_ if msg else None)
    anchor = (cq.message if cq and cq.message else None) or msg
    chat = anchor.chat if anchor else None
    if from_ is None or chat is None or from_.is_bot:
        return
    if chat.type != 'private':  # groups and channels are ignored
        return

    # Telegram retries, so process each update once
    async with rt.deps.as_user(bot.user_id) as tx:
        fresh = await tx.maybe_one(
            'UPDATE telegram_bots SET last_update_id = $2 WHERE user_id = $1 AND (last_update_id IS NULL OR last_update_id < $2) RETURNING user_id',
            [bot.user_id, update.update_id],
        )
    if fresh is None:
        return

    async with rt.deps.as_user(bot.user_id) as tx:
        link = await get_link(tx, bot.user_id)
        settings = await get_settings(tx, bot.user_id)
    if link is None:
        if msg and msg.text:
            await _try_pair(rt, bot, from_, chat.id, msg.message_id, msg.text)
        return  # not linked yet: no reply
    if from_.id != link.telegram_user_id or chat.id != link.chat_id:
        rt.strangers.allow(f'{bot.user_id}:{from_.id}')  # counted, never answered
        return
    cx = Cx(rt, bot, rt.token(bot), link, settings, bot.user_id, link.chat_id, rt.call_as(bot.user_id, bot.tz))
    if cq:
        await _handle_callback(cx, cq)
    elif msg:
        await _handle_message(cx, msg)


# pairing


async def _try_pair(rt: Runtime, bot: BotRow, from_: TgUser, chat_id: int, message_id: int, text: str) -> None:
    m = _START.fullmatch(text.strip())
    if not m:
        return
    if not rt.pair_tries.allow(f'{bot.user_id}:{from_.id}'):
        return
    if not is_owner(bot.owner_tg, from_.id, from_.username):
        return  # only the Telegram account set on the Setup page may link, whatever code is sent: no reply, code stays unused
    now = rt.clock()
    token = rt.token(bot)
    outcome: Literal['invalid', 'taken', 'linked']
    async with rt.deps.as_user(bot.user_id) as tx:
        used = await tx.maybe_one(
            'UPDATE telegram_pairings SET used_at = $3 WHERE user_id = $1 AND code_hash = $2 AND used_at IS NULL AND expires_at > $3 RETURNING id',
            [bot.user_id, pairing_hash(bot.user_id, m[1]), now],
        )
        if used is None:
            outcome = 'invalid'
        else:
            try:
                async with tx.savepoint():
                    await tx.execute(
                        'INSERT INTO telegram_links (user_id, telegram_user_id, chat_id, tg_username, linked_at, last_seen_at) VALUES ($1,$2,$3,$4,$5,$5)',
                        [bot.user_id, from_.id, chat_id, from_.username, now],
                    )
            except psycopg.errors.UniqueViolation:
                outcome = 'taken'
            else:
                await rt.deps.bus.emit(tx, 'audit.record', {'user_id': bot.user_id, 'action': 'telegram.link'})
                outcome = 'linked'
    if outcome == 'invalid':
        return  # wrong or expired code: no reply
    await quietly(rt, lambda: rt.bot.delete_message(token, chat_id, message_id), 'delete-start')
    text_out = T.linked if outcome == 'linked' else T.linked_elsewhere
    await quietly(rt, lambda: rt.bot.send_message(token, chat_id=chat_id, text=text_out), 'say')


# messages


def _parse_command(text: str) -> tuple[str, str] | None:
    m = _COMMAND.fullmatch(text)
    return (m[1].lower(), (m[2] or '').strip()) if m else None


def _minutes_left(until: datetime, now: datetime) -> int:
    return -(-int((until - now).total_seconds() * 1000) // 60_000)  # ceil


async def _handle_message(cx: Cx, msg: TgMessage) -> None:
    rt = cx.rt
    text = (msg.text or '').strip()
    cmd = _parse_command(text)
    name = cmd[0] if cmd else None
    now = rt.clock()

    if name == 'start':
        return await _say(cx, T.already_linked)
    if name == 'signin':
        return await _start_signin(cx)

    waiting_for_code = cx.link.signin_until is not None and cx.link.signin_until > now
    if waiting_for_code and cmd is None:
        return await _handle_code(cx, msg.message_id, text)
    if waiting_for_code:
        async with rt.deps.as_user(cx.user_id) as tx:
            await tx.execute('UPDATE telegram_links SET signin_until = NULL WHERE id = $1', [cx.link.id])

    async with rt.deps.as_user(cx.user_id) as tx:
        session = await touch_session(tx, cx.link, cx.settings.session_idle_days, now)
    if session is None:
        return await _say(cx, T.signed_out)

    if name == 'signout':
        return await _sign_out(cx)
    if name == 'unlink':
        r = await unlink(rt, cx.user_id)
        if r:
            chat_id, token = r
            await quietly(rt, lambda: rt.bot.send_message(token, chat_id=chat_id, text=T.unlinked), 'say')
        return
    if name == 'pending':
        if (await rt.deps.clients.transactions.pending(cx.as_, 1)).count == 0:
            return await _say(cx, T.nothing_pending)
        return await send_pending_summary(rt, cx.user_id, cx.link)
    amount = _AMOUNT.fullmatch(text)
    if amount:
        return await _record_amount(cx, msg.message_id, amount[1], amount[2], amount[3])
    if name is not None:
        return await _say(cx, T.help)
    await _handle_typed_tag(cx, msg.message_id, text)


async def _record_amount(cx: Cx, message_id: int, sign: str, amount: str, tag_text: str | None) -> None:
    """Log a payment typed in the chat. A tag after the amount files it at once, otherwise tag buttons follow. Money out also gets an Open Google Pay button."""
    rt = cx.rt
    minor = int(Decimal(amount) * 100)
    if minor <= 0:
        return await _say(cx, T.bad_amount)
    try:
        tag = normalize_tag(tag_text) if tag_text else None
    except AppError:
        return await _say(cx, T.bad_tag)
    direction: Direction = 'debit' if sign == '/' else 'credit'
    body = {'type': direction, 'amountMinor': minor, 'occurredAt': rt.clock().isoformat(), 'tag': tag}
    try:
        res = await rt.deps.clients.transactions.create_manual(cx.as_, body)
    except Exception as e:  # noqa: BLE001  (the user gets a retry line, the log gets the code)
        rt.deps.log.warning('typed amount failed', code=e.code if isinstance(e, AppError) else 'error')
        return await _say(cx, T.failed)
    await quietly(rt, lambda: rt.bot.delete_message(cx.token, cx.chat_id, message_id), 'delete-amount')  # amounts do not stay in the chat
    saved = T.typed_saved(minor, direction, res.transaction.category_name)
    keyboard = pay_keyboard(f'{rt.deps.env.PUBLIC_URL.rstrip("/")}/pay') if sign == '/' else None
    await _say(cx, saved, keyboard)


async def _start_signin(cx: Cx) -> None:
    rt = cx.rt
    now = rt.clock()
    async with rt.deps.as_user(cx.user_id) as tx:
        link = await get_link(tx, cx.user_id) or cx.link
    if link.signin_paused_until and link.signin_paused_until > now:
        return await _say(cx, T.still_paused(_minutes_left(link.signin_paused_until, now)))
    async with rt.deps.as_user(cx.user_id) as tx:
        open_ = await touch_session(tx, link, cx.settings.session_idle_days, now) is not None
        if not open_:
            await tx.execute('UPDATE telegram_links SET signin_until = $2 WHERE id = $1', [link.id, now + CODE_WAIT])
    await _say(cx, T.already_signed_in if open_ else T.ask_code)


async def _handle_code(cx: Cx, message_id: int, text: str) -> None:
    rt = cx.rt
    # the code must not stay in the chat, whatever happens
    await quietly(rt, lambda: rt.bot.delete_message(cx.token, cx.chat_id, message_id), 'delete-code')
    now = rt.clock()
    async with rt.deps.as_user(cx.user_id) as tx:
        link = await get_link(tx, cx.user_id) or cx.link
    if link.signin_paused_until and link.signin_paused_until > now:
        return await _say(cx, T.still_paused(_minutes_left(link.signin_paused_until, now)))
    if not re.fullmatch(r'\d{6}', text):
        return await _say(cx, T.code_format)

    try:
        await rt.deps.clients.auth.verify_totp(cx.as_, text)
    except AppError as e:
        if e.code == 'two_factor_invalid':
            return await _record_wrong_code(cx)
        rt.deps.log.warning('signin code check failed', code=e.code)
        return await _say(cx, T.try_again)
    except Exception:  # noqa: BLE001  (anything else is "could not check", not a wrong code)
        rt.deps.log.warning('signin code check failed', code='error')
        return await _say(cx, T.try_again)

    async with rt.deps.as_user(cx.user_id) as tx:
        await end_sessions(tx, link.id, 'replaced', now)
        await tx.execute('INSERT INTO telegram_sessions (link_id, user_id, started_at, last_seen_at) VALUES ($1,$2,$3,$3)', [link.id, cx.user_id, now])
        await tx.execute(
            """UPDATE telegram_links SET signin_until = NULL, signin_fail_count = 0, signin_fail_since = NULL, signin_paused_until = NULL, last_seen_at = $2
                WHERE id = $1""",
            [link.id, now],
        )
        await rt.deps.bus.emit(tx, 'audit.record', {'user_id': cx.user_id, 'action': 'telegram.signin'})
        released = await release_held(rt, tx, link)
    waiting = released['tags']
    if waiting > 0:
        try:
            waiting = min(waiting, (await rt.deps.clients.transactions.pending(cx.as_, 1)).count)
        except Exception:  # noqa: BLE001  (the held count is a fine answer when the transactions is slow)
            rt.deps.log.debug('pending count unavailable; reporting the held count')
    await _say(cx, T.signed_in(waiting, released['alerts'] > 0))


async def _record_wrong_code(cx: Cx) -> None:
    rt = cx.rt
    now = rt.clock()
    left, paused = 0, False
    async with rt.deps.as_user(cx.user_id) as tx:
        link = await get_link(tx, cx.user_id)
        if link is not None:
            in_window = link.signin_fail_since is not None and now - link.signin_fail_since < FAIL_WINDOW
            count = link.signin_fail_count + 1 if in_window else 1
            since = link.signin_fail_since if in_window else now
            if count >= MAX_WRONG:
                await tx.execute(
                    'UPDATE telegram_links SET signin_fail_count = 0, signin_fail_since = NULL, signin_until = NULL, signin_paused_until = $2 WHERE id = $1',
                    [link.id, now + PAUSE],
                )
                await rt.deps.bus.emit(tx, 'audit.record', {'user_id': cx.user_id, 'action': 'telegram.signin_paused', 'meta': {'wrongCodes': count}})
                paused = True
            else:
                await tx.execute('UPDATE telegram_links SET signin_fail_count = $2, signin_fail_since = $3 WHERE id = $1', [link.id, count, since])
                left = MAX_WRONG - count
    await _say(cx, T.paused(int(PAUSE.total_seconds() // 60)) if paused else T.wrong_code(left))


async def _sign_out(cx: Cx) -> None:
    rt = cx.rt
    async with rt.deps.as_user(cx.user_id) as tx:
        await end_sessions(tx, cx.link.id, 'signout', rt.clock())
        await tx.execute(
            'UPDATE telegram_links SET awaiting_prompt_id = NULL, awaiting_until = NULL, awaiting_msg_id = NULL, signin_until = NULL WHERE id = $1',
            [cx.link.id],
        )
        await rt.deps.bus.emit(tx, 'audit.record', {'user_id': cx.user_id, 'action': 'telegram.signout'})
    await _say(cx, T.signed_out_done)


async def _handle_typed_tag(cx: Cx, message_id: int, text: str) -> None:
    """The next plain message after "＋ New tag" is the tag, validated like the web."""
    rt, link = cx.rt, cx.link
    now = rt.clock()
    if not link.awaiting_prompt_id or not link.awaiting_until or link.awaiting_until <= now:
        return await _say(cx, T.help)
    try:
        tag = normalize_tag(text)
    except AppError:
        return await _say(cx, T.bad_tag)  # keep waiting
    async with rt.deps.as_user(cx.user_id) as tx:
        await tx.execute('UPDATE telegram_links SET awaiting_prompt_id = NULL, awaiting_until = NULL, awaiting_msg_id = NULL WHERE id = $1', [link.id])
        prompt = await get_prompt(tx, link.awaiting_prompt_id)
    if link.awaiting_msg_id is not None:
        ask_id = link.awaiting_msg_id
        await quietly(rt, lambda: rt.bot.delete_message(cx.token, cx.chat_id, ask_id), 'delete-ask')
    await quietly(rt, lambda: rt.bot.delete_message(cx.token, cx.chat_id, message_id), 'delete-tag')
    if prompt is None or prompt.kind != 'tag' or prompt.link_id != link.id:
        return await _say(cx, T.stale)
    await _apply_tag(cx, prompt, {'tag': tag}, None)


# taps


class _Answer:
    """Answers the callback query once (Telegram accepts one answer per tap)."""

    def __init__(self, cx: Cx, query_id: str) -> None:
        self._cx = cx
        self._id = query_id
        self.done = False

    async def __call__(self, text: str | None = None) -> None:
        if self.done:
            return
        self.done = True
        cx = self._cx
        await quietly(cx.rt, lambda: cx.rt.bot.answer_callback_query(cx.token, self._id, text), 'answer')


async def _handle_callback(cx: Cx, cq: TgCallbackQuery) -> None:
    rt = cx.rt
    answer = _Answer(cx, cq.id)
    try:
        async with rt.deps.as_user(cx.user_id) as tx:
            session = await touch_session(tx, cx.link, cx.settings.session_idle_days, rt.clock())
        if session is None:
            return await answer(T.signed_out)

        data = cq.data or ''
        sep = data.rfind(':')
        if sep < 1:
            return await answer(T.stale)
        token, action = data[:sep], data[sep + 1 :]
        # opaque token, looked up server-side within this user's link; anyone else's token is unknown
        async with rt.deps.as_user(cx.user_id) as tx:
            r = await tx.maybe_one('SELECT id FROM telegram_prompts WHERE token = $1 AND link_id = $2', [token, cx.link.id])
            prompt = await get_prompt(tx, r['id']) if r else None
        if prompt is None:
            return await answer(T.stale)

        if action in ('py', 'pn'):
            return await _plan_answer(cx, prompt, action == 'py', cq, answer)

        if prompt.message_id is not None and cq.message and cq.message.message_id != prompt.message_id:
            return await answer(T.stale)  # older copy of the message
        if prompt.status in ('tagged', 'auto_tagged'):
            await answer(T.already(prompt.category_name or ''))
            return await show_final(rt, cx.user_id, prompt)  # refresh: no stale buttons
        if prompt.status != 'sent':
            return await answer(T.stale)

        if action == 'l':
            return await answer(T.later)
        if action == 'n':
            return await _ask_new_tag(cx, prompt, answer)
        if action == 'r':
            return await _reveal(cx, prompt, answer)
        if action == 't':
            return await _apply_tag(cx, prompt, {'tag': 'transfer'}, answer)
        if action == 's':
            return await _start_walk(cx, prompt, None, answer)
        if action == 'x':
            after = (prompt.occurred_at or prompt.created_at, prompt.transaction_id) if prompt.transaction_id else None
            return await _start_walk(cx, prompt, after, answer)
        m = re.fullmatch(r'c(\d)', action)
        choice = prompt.choices[int(m[1])] if m and prompt.choices and int(m[1]) < len(prompt.choices) else None
        if choice is None or prompt.kind != 'tag':
            return await answer(T.stale)
        await _apply_tag(cx, prompt, {'category_id': choice['id']}, answer)
    except Exception as e:  # noqa: BLE001  (the tap gets a toast, the log gets the code)
        rt.deps.log.warning('callback failed', code=e.code if isinstance(e, AppError) else 'error')
        await answer(T.failed)
    finally:
        await answer()


async def _apply_tag(cx: Cx, prompt: PromptRow, spec: dict[str, str], answer: _Answer | None) -> None:
    rt = cx.rt
    if prompt.kind != 'tag' or not prompt.transaction_id:
        if answer:
            await answer(T.stale)
        return
    body: dict[str, Any] = {('categoryId' if 'category_id' in spec else 'tag'): next(iter(spec.values())), 'via': 'telegram'}
    try:
        res = await rt.deps.clients.transactions.tag(cx.as_, prompt.transaction_id, body)
    except AppError as e:
        if e.status == 404:
            async with rt.deps.as_user(cx.user_id) as tx:
                await tx.execute("UPDATE telegram_prompts SET status = 'expired', resolved_at = $2 WHERE id = $1", [prompt.id, rt.clock()])
            if answer:
                await answer(T.gone)
            await show_final(rt, cx.user_id, replace(prompt, status='expired'))
            return
        if e.status in (400, 422):
            if answer:
                await answer(T.bad_tag)
            else:
                await _say(cx, T.bad_tag)
            return
        raise
    name = res.transaction.category_name or ''
    now = rt.clock()
    via: Literal['telegram', 'web'] = 'telegram' if res.changed else 'web'
    done = replace(prompt, status='tagged', category_name=name, resolved_via=via)
    async with rt.deps.as_user(cx.user_id) as tx:
        await tx.execute(
            "UPDATE telegram_prompts SET status = 'tagged', category_name = $2, resolved_via = $3, resolved_at = $4, revealed_until = NULL WHERE id = $1",
            [prompt.id, name, via, now],
        )
        # same payee: the transactions tagged the other pending items too, so sync their messages
        for tx_id in res.also_tagged_ids:
            rows = await tx.many(
                """UPDATE telegram_prompts SET status = 'auto_tagged', category_name = $2, resolved_via = 'rule', resolved_at = $3
                    WHERE transaction_id = $1 AND kind = 'tag' AND status = ANY($4) RETURNING id""",
                [tx_id, name, now, list(OPEN_STATUSES)],
            )
            for r in rows:
                await enqueue_sync(rt, tx, r['id'])
    if answer:
        await answer(T.saved(name) if res.changed else T.already(name))
    await show_final(rt, cx.user_id, done)
    if res.changed and res.transaction.type == 'credit':
        await _say(cx, T.plan_question, plan_keyboard(prompt.token))


async def _ask_new_tag(cx: Cx, prompt: PromptRow, answer: _Answer) -> None:
    rt = cx.rt
    now = rt.clock()
    if cx.link.awaiting_msg_id is not None:
        old = cx.link.awaiting_msg_id
        await quietly(rt, lambda: rt.bot.delete_message(cx.token, cx.chat_id, old), 'delete-ask')
    ask_id = await rt.bot.send_message(cx.token, chat_id=cx.chat_id, text=T.ask_tag, force_reply=ForceReply(placeholder=T.tag_placeholder))
    async with rt.deps.as_user(cx.user_id) as tx:
        await tx.execute(
            'UPDATE telegram_links SET awaiting_prompt_id = $2, awaiting_until = $3, awaiting_msg_id = $4 WHERE id = $1',
            [cx.link.id, prompt.id, now + TAG_WAIT, ask_id],
        )
    await answer()


async def _reveal(cx: Cx, prompt: PromptRow, answer: _Answer) -> None:
    """Show amount and payee for 30 seconds; a delayed sync then restores the plain message."""
    rt = cx.rt
    if not cx.settings.allow_reveal:
        return await answer(T.reveal_off)  # the button is hidden too; refuse a stale one
    if prompt.kind != 'tag' or not prompt.transaction_id or prompt.message_id is None or not prompt.choices:
        return await answer(T.stale)
    try:
        t = (await rt.deps.clients.transactions.get_transaction(cx.as_, prompt.transaction_id)).transaction
    except AppError as e:
        if e.status == 404:
            return await answer(T.gone)
        raise
    now = rt.clock()
    head = header_text(prompt.direction or t.type, prompt.occurred_at, prompt.created_at, now, cx.bot.tz)
    async with rt.deps.as_user(cx.user_id) as tx:
        await tx.execute('UPDATE telegram_prompts SET revealed_until = $2 WHERE id = $1', [prompt.id, now + timedelta(seconds=REVEAL_SECONDS)])
        await enqueue_sync(rt, tx, prompt.id, key=f'reveal:{prompt.id}', start_after_seconds=REVEAL_SECONDS)
    await rt.bot.edit_message_text(
        cx.token, chat_id=cx.chat_id, message_id=prompt.message_id, text=reveal_text(head, t.amount_minor, t.payee),
        keyboard=tag_keyboard(prompt, prompt.choices, allow_reveal=cx.settings.allow_reveal),
    )  # fmt: skip
    await answer()


async def _start_walk(cx: Cx, prompt: PromptRow, after: tuple[datetime, str] | None, answer: _Answer) -> None:
    rt = cx.rt
    if prompt.kind != ('tag' if after else 'digest'):
        return await answer(T.stale)
    found = await resend_oldest_pending(rt, cx.user_id, cx.link, cx.bot.tz, after)
    await answer(None if found else (T.last_one if after else T.nothing_pending))


async def _plan_answer(cx: Cx, prompt: PromptRow, yes: bool, cq: TgCallbackQuery, answer: _Answer) -> None:
    rt = cx.rt
    if (
        prompt.kind != 'tag' or not prompt.transaction_id or prompt.status not in ('tagged', 'auto_tagged')
        or prompt.direction != 'credit'
    ):  # fmt: skip
        return await answer(T.stale)
    amount, month = 0, ''
    if yes:
        t = (await rt.deps.clients.transactions.get_transaction(cx.as_, prompt.transaction_id)).transaction
        amount = t.amount_minor
        month = month_key(t.occurred_at, cx.bot.tz)
    async with rt.deps.as_user(cx.user_id) as tx:
        r = await tx.maybe_one(
            'UPDATE telegram_prompts SET plan_answer = $2 WHERE id = $1 AND plan_answer IS NULL RETURNING id', [prompt.id, 'yes' if yes else 'no']
        )
        first = r is not None
        # planning adds it to the month's plan (idempotent per transaction)
        if first and yes:
            await rt.deps.bus.emit(
                tx, 'credit.added',
                {'user_id': cx.user_id, 'transaction_id': prompt.transaction_id, 'month': month, 'amount_minor': amount, 'add_to_plan': True},
            )  # fmt: skip
    await answer(None if first else T.stale)
    if cq.message:
        msg_id = cq.message.message_id
        await quietly(
            rt, lambda: rt.bot.edit_message_text(cx.token, chat_id=cx.chat_id, message_id=msg_id, text=T.plan_yes if yes else T.plan_no), 'edit-plan'
        )
