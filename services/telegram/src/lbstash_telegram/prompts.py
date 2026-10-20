"""Create, send, sync and release prompts. Their text never holds amounts or payees."""

import dataclasses
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from lbstash.common import AppError, date_key, tz_parts
from lbstash.contracts import (
    AlertCreatedEvent,
    TelegramDigestJob,
    TelegramSendJob,
    TelegramSyncPromptJob,
    TransactionChangedEvent,
    UnparsedCreatedEvent,
)
from lbstash.crypto import random_token
from lbstash.db import Tx, jsonb

from .botapi import BotApiError, Keyboard
from .messages import T, balance_keyboard, final_text, header_text, start_keyboard, tag_keyboard
from .runtime import Runtime, quietly
from .store import (
    OPEN_STATUSES,
    Direction,
    LinkRow,
    PromptKind,
    PromptRow,
    active_session,
    get_bot,
    get_link,
    get_prompt,
    get_settings,
    insert_prompt,
    prompts_by_transaction,
)

# Balance nudge: weekly, on this local weekday (Sunday; Monday is 0), in the first reminder slot.
BALANCE_NUDGE_WEEKDAY = 6
BALANCE_NUDGE_EVERY_DAYS = 7


def _new_token() -> str:
    return random_token(9)


async def _enqueue_send(rt: Runtime, tx: Tx, prompt_id: str) -> None:
    # same key per prompt, so a retried event doesn't queue twice
    await rt.deps.bus.enqueue(tx, 'telegram.send', TelegramSendJob(prompt_id=prompt_id), key=f'send:{prompt_id}')


async def enqueue_sync(
    rt: Runtime, tx: Tx, prompt_id: str, *, key: str | None = None, start_after_seconds: float | None = None
) -> None:
    await rt.deps.bus.enqueue(
        tx, 'telegram.sync_prompt', TelegramSyncPromptJob(prompt_id=prompt_id),
        key=key or f'sync:{prompt_id}', start_after_seconds=start_after_seconds,
    )  # fmt: skip


async def create_prompt(
    rt: Runtime,
    user_id: str,
    *,
    kind: PromptKind,
    dedupe_key: str,
    transaction_id: str | None = None,
    direction: Direction | None = None,
    occurred_at: datetime | None = None,
    meta: dict[str, Any] | None = None,
) -> PromptRow | None:
    """Insert a prompt for a linked user: `queued` with an active session, else `held`. Does not send."""
    async with rt.deps.as_user(user_id) as tx:
        link = await get_link(tx, user_id)
        if not link:
            return None  # not linked: the payment waits in the web app
        now = rt.clock()
        settings = await get_settings(tx, user_id)
        session = await active_session(tx, link.id, settings.session_idle_days, now)
        p = await insert_prompt(
            tx, user_id=user_id, link_id=link.id, kind=kind, status='queued' if session else 'held', dedupe_key=dedupe_key,
            token=_new_token(), now=now, transaction_id=transaction_id, direction=direction, occurred_at=occurred_at, meta=meta,
        )  # fmt: skip
        if p and p.status == 'queued':
            await _enqueue_send(rt, tx, p.id)
        return p


# events


async def on_transaction_changed(rt: Runtime, ev: TransactionChangedEvent) -> None:
    if ev.kind != 'deleted' and ev.status == 'pending':
        if ev.tagged_via is None:
            await create_prompt(
                rt, ev.user_id, kind='tag', dedupe_key=f'tx:{ev.transaction_id}', transaction_id=ev.transaction_id,
                direction=ev.type, occurred_at=ev.occurred_at,
            )  # fmt: skip
        return
    # tagged elsewhere, reversed or deleted: bring the message to its final state
    async with rt.deps.as_user(ev.user_id) as tx:
        for p in await prompts_by_transaction(tx, ev.transaction_id):
            if p.status not in OPEN_STATUSES:
                continue
            if ev.tagged_via and ev.tagged_via != 'telegram':
                await tx.execute('UPDATE telegram_prompts SET resolved_via = COALESCE(resolved_via, $2) WHERE id = $1', [p.id, ev.tagged_via])
            await enqueue_sync(rt, tx, p.id)


async def on_alert_created(rt: Runtime, ev: AlertCreatedEvent) -> None:
    await create_prompt(
        rt, ev.user_id, kind='alert', dedupe_key=f'alert:{ev.alert_id}',
        meta={'category': ev.category_name, 'level': ev.level, 'pct': ev.pct},
    )  # fmt: skip


async def on_unparsed_created(rt: Runtime, ev: UnparsedCreatedEvent) -> None:
    """Nudge on the first failure, then whenever there are more than 3 in 24 hours."""
    if not (ev.failures_last24h == 1 or ev.failures_last24h > 3):
        return
    await create_prompt(
        rt, ev.user_id, kind='alert', dedupe_key=f'unparsed:{ev.unparsed_id}', meta={'nudge': 'unparsed', 'count': ev.failures_last24h}
    )


# sending


async def _set_status(
    tx: Tx, prompt_id: str, status: str, *, category_name: str | None = None, via: str | None = None, now: datetime | None = None
) -> None:
    await tx.execute(
        """UPDATE telegram_prompts SET status = $2, category_name = COALESCE($3, category_name), resolved_via = COALESCE($4, resolved_via),
                resolved_at = CASE WHEN $2 IN ('tagged','auto_tagged','expired','failed') THEN COALESCE($5, now()) ELSE resolved_at END WHERE id = $1""",
        [prompt_id, status, category_name, via, now],
    )


async def send_prompt(rt: Runtime, prompt_id: str) -> None:
    """`telegram.send`: deliver this prompt after any older queued ones for the chat, oldest first."""
    async with rt.deps.as_system() as tx:
        head = await tx.maybe_one('SELECT user_id, link_id, seq, status FROM telegram_prompts WHERE id = $1', [prompt_id])
    if not head or head['status'] != 'queued':
        return  # already handled

    async def drain() -> None:
        while True:
            async with rt.deps.as_user(head['user_id']) as tx:
                nxt = await tx.maybe_one(
                    "SELECT id FROM telegram_prompts WHERE link_id = $1 AND status = 'queued' AND seq <= $2 ORDER BY seq LIMIT 1",
                    [head['link_id'], head['seq']],
                )
            if not nxt:
                return
            await _deliver(rt, head['user_id'], nxt['id'])

    await rt.chats.run(head['link_id'], drain)


async def _deliver(rt: Runtime, user_id: str, prompt_id: str) -> None:
    """Deliver one queued prompt. Sets its status in every outcome except a transient failure, which raises so the job retries."""
    async with rt.deps.as_user(user_id) as tx:
        prompt = await get_prompt(tx, prompt_id)
        if not prompt or prompt.status != 'queued':
            return
        link = await get_link(tx, user_id)
        bot = await get_bot(tx, user_id)
        if not link or not bot:
            await _set_status(tx, prompt_id, 'expired', now=rt.clock())
            return
        settings = await get_settings(tx, user_id)
        if not await active_session(tx, link.id, settings.session_idle_days, rt.clock()):
            if _is_balance_nudge(prompt):
                await _set_status(tx, prompt_id, 'expired', now=rt.clock())  # a reminder is not worth holding
            else:
                await tx.execute("UPDATE telegram_prompts SET status = 'held' WHERE id = $1", [prompt_id])
            return
    as_ = rt.call_as(user_id, bot.tz)
    now = rt.clock()

    async def resolve(status: str, category_name: str | None = None, via: str | None = None) -> None:
        async with rt.deps.as_user(user_id) as tx:
            await _set_status(tx, prompt_id, status, category_name=category_name, via=via, now=now)

    keyboard: Keyboard | None = None
    choices: list[dict[str, str]] | None = None

    if prompt.kind == 'tag':
        try:
            t = (await rt.deps.clients.transactions.get_transaction(as_, prompt.transaction_id)).transaction
        except AppError as e:
            if e.status == 404:
                return await resolve('expired')
            raise
        if t.status == 'reversed':
            return await resolve('expired')
        if t.status != 'pending' or t.category_id:  # tagged while it waited
            return await resolve('tagged', t.category_name, 'web')
        cats = (await rt.deps.clients.transactions.categories(as_, sort='usage', limit=6)).items
        choices = [{'id': c.id, 'name': c.name} for c in cats if c.name != 'transfer'][:6]
        direction = prompt.direction or t.type
        text = header_text(direction, prompt.occurred_at, prompt.created_at, now, bot.tz)
        keyboard = tag_keyboard(prompt, choices, allow_reveal=settings.allow_reveal)
    elif prompt.kind == 'digest':
        count = (await rt.deps.clients.transactions.pending(as_, 1)).count
        if count == 0:
            return await resolve('expired')
        text = T.digest(count)
        keyboard = start_keyboard(prompt.token)
    elif prompt.meta.get('nudge') == 'unparsed':
        text = T.unparsed(int(prompt.meta.get('count') or 1))
    elif prompt.meta.get('nudge') == 'balance':
        text = T.balance_nudge
        keyboard = balance_keyboard(f'{rt.deps.env.PUBLIC_URL.rstrip("/")}/transactions?check=1')
    else:
        level = 'exceeded' if prompt.meta.get('level') == 'exceeded' else 'alert'
        text = T.alert(str(prompt.meta.get('category') or ''), level, int(prompt.meta.get('pct') or 0))

    await rt.chats.throttle(link.id)
    try:
        message_id = await rt.bot.send_message(rt.token(bot), chat_id=link.chat_id, text=text, keyboard=keyboard)
        async with rt.deps.as_user(user_id) as tx:
            await tx.execute(
                "UPDATE telegram_prompts SET status = 'sent', message_id = $2, sent_at = $3, choices = $4 WHERE id = $1",
                [prompt_id, message_id, now, jsonb(choices) if choices else None],
            )
    except BotApiError as e:
        if e.kind == 'rate_limited':
            rt.chats.hold_for(link.id, e.retry_after or 1)
        if not e.transient:
            # blocked bot, bad token, refused text: stop trying, the payment is still in the web app
            rt.deps.log.warning('prompt not delivered', prompt_id=prompt_id, kind=e.kind)
            async with rt.deps.as_user(user_id) as tx:
                await _set_status(tx, prompt_id, 'failed', now=now)
            return
        raise  # Telegram down or rate limited: the job retries, the prompt stays queued


def _is_balance_nudge(p: PromptRow) -> bool:
    return p.kind == 'alert' and p.meta.get('nudge') == 'balance'


# syncing: edit a sent message to its final state


async def show_final(rt: Runtime, user_id: str, prompt: PromptRow) -> None:
    """Edit or delete a finished prompt's message, following `after_tag`."""
    if prompt.message_id is None:
        return
    async with rt.deps.as_user(user_id) as tx:
        link = await get_link(tx, user_id)
        bot = await get_bot(tx, user_id)
        settings = await get_settings(tx, user_id) if link and bot else None
    if not link or not bot or not settings:
        return
    token = rt.token(bot)
    message_id = prompt.message_id
    tagged = prompt.status in ('tagged', 'auto_tagged')
    if settings.after_tag == 'delete' and tagged and await quietly(rt, lambda: rt.bot.delete_message(token, link.chat_id, message_id), 'delete'):
        return
    # 'keep': the message stays, minus the buttons, with the tag added; 'line' collapses it
    if settings.after_tag == 'keep' and tagged:
        head = header_text(prompt.direction, prompt.occurred_at, prompt.created_at, rt.clock(), bot.tz)
        text = f'{head}\n{" · ".join(final_text(prompt).split(" · ")[1:])}'
    else:
        text = final_text(prompt)
    await quietly(rt, lambda: rt.bot.edit_message_text(token, chat_id=link.chat_id, message_id=message_id, text=text), 'edit')


async def sync_prompt(rt: Runtime, prompt_id: str) -> None:
    """`telegram.sync_prompt`: make the message match the transactions, the source of truth."""
    async with rt.deps.as_system() as tx:
        head = await tx.maybe_one('SELECT user_id FROM telegram_prompts WHERE id = $1', [prompt_id])
    if not head:
        return
    user_id = head['user_id']
    async with rt.deps.as_user(user_id) as tx:
        prompt = await get_prompt(tx, prompt_id)
        bot = await get_bot(tx, user_id)
        link = await get_link(tx, user_id)
        settings = await get_settings(tx, user_id) if prompt and bot and link else None
    if not prompt or not bot or not link or not settings or prompt.kind != 'tag' or not prompt.transaction_id:
        return
    as_ = rt.call_as(user_id, bot.tz)

    try:
        t = (await rt.deps.clients.transactions.get_transaction(as_, prompt.transaction_id)).transaction
    except AppError as e:
        if e.status != 404:
            raise
        t = None
    now = rt.clock()
    nxt = prompt
    if t is None or t.status == 'reversed':
        nxt = dataclasses.replace(prompt, status='expired')
        async with rt.deps.as_user(user_id) as tx:
            await _set_status(tx, prompt_id, 'expired', now=now)
    elif t.status == 'confirmed' and t.category_id:
        status = 'auto_tagged' if prompt.resolved_via == 'rule' or prompt.status == 'auto_tagged' else 'tagged'
        nxt = dataclasses.replace(prompt, status=status, category_name=t.category_name)
        async with rt.deps.as_user(user_id) as tx:
            await _set_status(tx, prompt_id, status, category_name=t.category_name, via=prompt.resolved_via or 'web', now=now)
    else:
        # still pending: only a Reveal needs undoing
        if prompt.status == 'sent' and prompt.message_id is not None and prompt.choices:
            async with rt.deps.as_user(user_id) as tx:
                await tx.execute('UPDATE telegram_prompts SET revealed_until = NULL WHERE id = $1', [prompt_id])
            message_id = prompt.message_id
            await quietly(
                rt,
                lambda: rt.bot.edit_message_text(
                    rt.token(bot), chat_id=link.chat_id, message_id=message_id,
                    text=header_text(prompt.direction or t.type, prompt.occurred_at, prompt.created_at, now, bot.tz),
                    keyboard=tag_keyboard(prompt, prompt.choices or [], allow_reveal=settings.allow_reveal),
                ),
                'restore',
            )  # fmt: skip
        return
    await show_final(rt, user_id, nxt)


# release held prompts on sign-in


async def release_held(rt: Runtime, tx: Tx, link: LinkRow) -> dict[str, int]:
    """Queue held prompts, oldest first. Returns the counts for the "Signed in" line."""
    rows = await tx.many("UPDATE telegram_prompts SET status = 'queued' WHERE link_id = $1 AND status = 'held' RETURNING id, kind, seq, meta", [link.id])
    rows.sort(key=lambda r: r['seq'])
    for r in rows:
        await _enqueue_send(rt, tx, r['id'])
    return {
        'tags': sum(1 for r in rows if r['kind'] == 'tag'),
        # a held "could not be read" nudge is not a limit alert
        'alerts': sum(1 for r in rows if r['kind'] == 'alert' and not r['meta'].get('nudge')),
    }


# digest


async def digest_tick(rt: Runtime) -> int:
    """Hourly: queue a `telegram.digest` job for each linked user whose digest hour it is in their zone."""
    now = rt.clock()
    async with rt.deps.as_system() as tx:
        users = await tx.many(
            """SELECT l.user_id, b.tz, COALESCE(s.digest_hour, 21) AS digest_hour, COALESCE(s.digest_mode, 'daily') AS digest_mode
                 FROM telegram_links l JOIN telegram_bots b ON b.user_id = l.user_id LEFT JOIN telegram_settings s ON s.user_id = l.user_id"""
        )
        n = 0
        for u in users:
            h = tz_parts(now, u['tz']).h
            if u['digest_mode'] == 'off':
                continue
            if h != u['digest_hour'] and not (u['digest_mode'] == 'twice' and h == (u['digest_hour'] + 12) % 24):
                continue
            await rt.deps.bus.enqueue(
                tx, 'telegram.digest', TelegramDigestJob(user_id=u['user_id']), key=f'digest:{u["user_id"]}:{date_key(now, u["tz"])}:{h}'
            )
            n += 1
        return n


async def digest_for(rt: Runtime, user_id: str) -> None:
    """"N payments still need a tag" with a Start button, only with an active session."""
    now = rt.clock()
    async with rt.deps.as_user(user_id) as tx:
        link = await get_link(tx, user_id)
        bot = await get_bot(tx, user_id)
        if not link or not bot:
            return
        settings = await get_settings(tx, user_id)
        if settings.digest_mode == 'off':
            return
        if not await active_session(tx, link.id, settings.session_idle_days, now):
            return  # signed out: stay silent
    parts = tz_parts(now, bot.tz)
    day = date_key(now, bot.tz)
    async with rt.deps.as_user(user_id) as tx:
        p = await insert_prompt(
            tx, user_id=user_id, link_id=link.id, kind='digest', status='queued', dedupe_key=f'digest:{day}:{parts.h}',
            token=_new_token(), now=now,
        )  # fmt: skip
        if p:
            await _enqueue_send(rt, tx, p.id)
    if parts.h == settings.digest_hour and now.astimezone(ZoneInfo(bot.tz)).weekday() == BALANCE_NUDGE_WEEKDAY:
        await _balance_nudge(rt, user_id, link, bot.tz, day, now)


async def _balance_nudge(rt: Runtime, user_id: str, link: LinkRow, tz: str, day: str, now: datetime) -> None:
    """Weekly nudge with a button to the web app's balance check. Skipped if a check was made within the week."""
    try:
        recent = (await rt.deps.clients.transactions.balance_checks(rt.call_as(user_id, tz), 1)).items
    except AppError:
        recent = []  # can't tell; a reminder is cheap
    if recent and now - recent[0].checked_at < timedelta(days=BALANCE_NUDGE_EVERY_DAYS):
        return
    async with rt.deps.as_user(user_id) as tx:
        p = await insert_prompt(
            tx, user_id=user_id, link_id=link.id, kind='alert', status='queued', dedupe_key=f'balance:{day}',
            token=_new_token(), now=now, meta={'nudge': 'balance'},
        )  # fmt: skip
        if p:
            await _enqueue_send(rt, tx, p.id)


async def send_pending_summary(rt: Runtime, user_id: str, link: LinkRow) -> None:
    """`/pending`: send the digest's count message now."""
    now = rt.clock()
    async with rt.deps.as_user(user_id) as tx:
        p = await insert_prompt(
            tx, user_id=user_id, link_id=link.id, kind='digest', status='queued', dedupe_key=f'pending:{_new_token()}',
            token=_new_token(), now=now,
        )  # fmt: skip
    if p:
        await send_prompt(rt, p.id)


# Start / Next: bring the oldest pending payment to the bottom of the chat


async def resend_oldest_pending(
    rt: Runtime, user_id: str, link: LinkRow, tz: str, after: tuple[datetime, str] | None
) -> bool:
    """Re-send the oldest pending payment after `after` (or the oldest overall). False if none."""
    as_ = rt.call_as(user_id, tz)
    items = (await rt.deps.clients.transactions.pending(as_, 200)).items
    ordered = sorted(items, key=lambda t: (t.occurred_at, t.id))
    target = next((t for t in ordered if after is None or (t.occurred_at, t.id) > after), None)
    if target is None:
        return False
    now = rt.clock()
    async with rt.deps.as_user(user_id) as tx:
        existing = await tx.maybe_one('SELECT * FROM telegram_prompts WHERE user_id = $1 AND dedupe_key = $2', [user_id, f'tx:{target.id}'])
        if existing:
            await tx.execute(
                """UPDATE telegram_prompts SET status = 'queued', nav = true, message_id = NULL, sent_at = NULL, resolved_at = NULL,
                          revealed_until = NULL, created_at = $2 WHERE id = $1""",
                [existing['id'], now],
            )
            await _enqueue_send(rt, tx, existing['id'])
            old_message_id = existing['message_id']
        else:
            p = await insert_prompt(
                tx, user_id=user_id, link_id=link.id, kind='tag', status='queued', dedupe_key=f'tx:{target.id}',
                transaction_id=target.id, direction=target.type, occurred_at=target.occurred_at, token=_new_token(), now=now,
            )  # fmt: skip
            if p:
                await tx.execute('UPDATE telegram_prompts SET nav = true WHERE id = $1', [p.id])
                await _enqueue_send(rt, tx, p.id)
            old_message_id = None
    if old_message_id is not None:
        async with rt.deps.as_user(user_id) as tx:
            bot = await get_bot(tx, user_id)
        if bot:
            token = rt.token(bot)
            await quietly(rt, lambda: rt.bot.delete_message(token, link.chat_id, old_message_id), 'delete-old')
    return True

