"""Bot token, pairing, link status, unlink, sign-out from the web, settings, export, account purge."""

import asyncio
import re
from datetime import datetime, timedelta
from typing import Any

from lbstash.common import Ctx, Errors, to_iso
from lbstash.contracts import (
    BotTokenRes,
    ExportPart,
    PairingRes,
    TelegramLinkStatus,
    TelegramSettings,
    TelegramSettingsPatch,
)
from lbstash.crypto import random_digits, random_token, sha256_hex
from lbstash.db import Tx

from .botapi import BotApiError
from .runtime import Runtime, quietly
from .store import SETTINGS_COLUMNS, active_session, end_sessions, get_bot, get_link, get_settings

PAIRING_MINUTES = 5

_USERNAME = re.compile(r'[A-Za-z][A-Za-z0-9_]{4,31}')
_NUMERIC_ID = re.compile(r'\d{5,15}')


def normalize_owner(raw: str) -> str:
    """Stored form of "who may link": lower-case username without `@`, or a numeric id. Validation error otherwise."""
    text = re.sub(r'^(?:https?://)?(?:t|telegram)\.me/', '', raw.strip(), flags=re.IGNORECASE).removeprefix('@')  # a pasted t.me link is fine
    if _NUMERIC_ID.fullmatch(text):
        return text
    if _USERNAME.fullmatch(text):
        return text.lower()
    raise Errors.validation({'telegram': 'Enter your own Telegram @username (5 or more letters, digits or _), or your numeric id'})


def owner_label(owner: str | None) -> str | None:
    """How the Setup page shows the stored owner: "@name", or "••4821" for a numeric id (the whole id is never sent back)."""
    if not owner:
        return None
    return f'••{owner[-4:]}' if owner.isdigit() else f'@{owner}'


def is_owner(owner: str | None, user_id: int, username: str | None) -> bool:
    """Whether this Telegram account is the one allowed to link. No owner set = nobody."""
    if not owner:
        return False
    return owner == str(user_id) or (username is not None and owner == username.lower())


def pairing_hash(user_id: str, code: str) -> str:
    return sha256_hex(f'{user_id}:{code}')


async def _remember_tz(tx: Tx, user_id: str, tz: str) -> None:
    """Zone is only known on user requests; store it for digests and message times."""
    await tx.execute('UPDATE telegram_bots SET tz = $2 WHERE user_id = $1 AND tz <> $2', [user_id, tz])


async def link_status(rt: Runtime, ctx: Ctx) -> TelegramLinkStatus:
    now = rt.clock()
    async with rt.deps.as_user(ctx) as tx:
        await _remember_tz(tx, ctx.user_id, ctx.tz)
        bot = await get_bot(tx, ctx.user_id)
        link = await get_link(tx, ctx.user_id)
        settings = await get_settings(tx, ctx.user_id)
        session = await active_session(tx, link.id, settings.session_idle_days, now) if link else None
        pairing = await tx.maybe_one(
            'SELECT 1 FROM telegram_pairings WHERE user_id = $1 AND used_at IS NULL AND expires_at > $2', [ctx.user_id, now]
        )
        held = (
            await tx.maybe_one(
                "SELECT count(*)::int AS n FROM telegram_prompts WHERE link_id = $1 AND status = 'held' AND kind = 'tag'", [link.id]
            )
            if link
            else None
        )
    paused = link.signin_paused_until if link and link.signin_paused_until and link.signin_paused_until > now else None
    return TelegramLinkStatus(
        bot_saved=bot is not None,
        bot_username=bot.bot_username if bot else None,
        owner_telegram=owner_label(bot.owner_tg) if bot else None,
        linked=link is not None,
        telegram_id_hint=f'••{str(link.telegram_user_id)[-4:]}' if link else None,
        telegram_username=link.tg_username if link else None,
        linked_at=link.linked_at if link else None,
        session_active=session is not None,
        session_since=session.started_at if session else None,
        last_seen_at=link.last_seen_at if link else None,
        sign_in_paused_until=paused,
        pairing_pending=pairing is not None,
        held_count=held['n'] if held else 0,
    )


async def create_pairing(rt: Runtime, ctx: Ctx) -> PairingRes:
    if not rt.pair_create.allow(ctx.user_id):
        raise Errors.too_many()
    now = rt.clock()
    expires_at = now + timedelta(minutes=PAIRING_MINUTES)
    async with rt.deps.as_user(ctx) as tx:
        await _remember_tz(tx, ctx.user_id, ctx.tz)
        bot = await get_bot(tx, ctx.user_id)
        if not bot:
            raise Errors.conflict('Save your bot token first')
        if not bot.owner_tg:
            raise Errors.conflict('Enter your Telegram username first: only that account can link this bot')
        if await get_link(tx, ctx.user_id):
            raise Errors.conflict('Telegram is already linked. Disconnect it first to link another account')
        await tx.execute('DELETE FROM telegram_pairings WHERE user_id = $1', [ctx.user_id])
        code = random_digits(6)
        await tx.execute(
            'INSERT INTO telegram_pairings (user_id, code_hash, expires_at, created_at) VALUES ($1,$2,$3,$4)',
            [ctx.user_id, pairing_hash(ctx.user_id, code), expires_at, now],
        )
    return PairingRes(code=code, command=f'/start {code}', expires_at=expires_at)


async def set_owner(rt: Runtime, ctx: Ctx, telegram: str) -> None:
    """Choose the one Telegram account that may link. A code made earlier stays valid only for that account."""
    owner = normalize_owner(telegram)
    async with rt.deps.as_user(ctx) as tx:
        bot = await get_bot(tx, ctx.user_id)
        if not bot:
            raise Errors.conflict('Save your bot token first')
        if bot.bot_username and owner == bot.bot_username.lower():
            raise Errors.validation({'telegram': f'@{bot.bot_username} is your bot. Enter your own Telegram username instead'})
        if await get_link(tx, ctx.user_id):
            raise Errors.conflict('Telegram is already linked. Disconnect it first to change the account')
        await tx.execute('UPDATE telegram_bots SET owner_tg = $2, updated_at = $3 WHERE user_id = $1', [ctx.user_id, owner, rt.clock()])


async def save_bot_token(rt: Runtime, ctx: Ctx, token: str) -> BotTokenRes:
    """Check the token with getMe, store it encrypted and set the webhook. Replacing the bot clears the link."""
    try:
        me = await rt.bot.get_me(token)
    except BotApiError as e:
        if e.kind in ('unauthorized', 'invalid'):
            raise Errors.unprocessable('Telegram did not accept that token') from None
        raise Errors.upstream('telegram', 'Telegram is not reachable right now') from None
    path_secret = random_token(24)
    header_secret = random_token(24)
    url = f'{rt.deps.env.PUBLIC_URL.rstrip("/")}/telegram/webhook/{path_secret}'
    try:
        await rt.bot.set_webhook(token, url=url, secret_token=header_secret)
    except BotApiError as e:
        if e.kind == 'invalid':
            raise Errors.unprocessable('Telegram could not set the webhook', {'reason': str(e)}) from None
        raise Errors.upstream('telegram', 'Telegram is not reachable right now') from None
    now = rt.clock()
    previous: tuple[str, dict[str, Any] | None] | None = None
    async with rt.deps.as_user(ctx) as tx:
        old = await get_bot(tx, ctx.user_id)
        cleared = await remove_link_data(rt, tx, ctx.user_id, 'telegram.bot_replaced') if old else None
        await tx.execute(
            """INSERT INTO telegram_bots (user_id, token_enc, bot_username, path_hash, header_hash, tz, last_update_id, created_at, updated_at)
               VALUES ($1,$2,$3,$4,$5,$6,NULL,$7,$7)
               ON CONFLICT (user_id) DO UPDATE SET token_enc = EXCLUDED.token_enc, bot_username = EXCLUDED.bot_username, path_hash = EXCLUDED.path_hash,
                 header_hash = EXCLUDED.header_hash, tz = EXCLUDED.tz, last_update_id = NULL, updated_at = EXCLUDED.updated_at""",
            [ctx.user_id, rt.cipher.encrypt_string(token, ctx.user_id), me.username, sha256_hex(path_secret), sha256_hex(header_secret), ctx.tz, now],
        )
        # saving the same token again must not delete the webhook that was just set for it
        if old and rt.token(old) != token:
            previous = (rt.token(old), cleared)
    if previous:
        # best effort: drop the old bot's webhook and messages
        old_token, cleared = previous
        await quietly(rt, lambda: rt.bot.delete_webhook(old_token), 'delete-webhook')
        if cleared:
            await delete_messages(rt, old_token, cleared['chat_id'], cleared['message_ids'])
    return BotTokenRes(ok=True, bot_username=me.username)


async def remove_link_data(rt: Runtime, tx: Tx, user_id: str, audit_action: str) -> dict[str, Any] | None:
    """Delete link, sessions, pairings and prompts. Returns the chat and message ids to clean up, if there was a link."""
    await tx.execute('DELETE FROM telegram_pairings WHERE user_id = $1', [user_id])
    link = await get_link(tx, user_id)
    if not link:
        return None
    rows = await tx.many(
        'SELECT message_id FROM telegram_prompts WHERE link_id = $1 AND message_id IS NOT NULL ORDER BY seq DESC LIMIT 150', [link.id]
    )
    message_ids = [r['message_id'] for r in rows]
    if link.awaiting_msg_id is not None:
        message_ids.append(link.awaiting_msg_id)
    await tx.execute('DELETE FROM telegram_prompts WHERE link_id = $1', [link.id])
    await tx.execute('DELETE FROM telegram_links WHERE id = $1', [link.id])  # sessions go with it
    await rt.deps.bus.emit(tx, 'audit.record', {'user_id': user_id, 'action': audit_action})
    return {'chat_id': link.chat_id, 'message_ids': message_ids}


async def delete_messages(rt: Runtime, token: str, chat_id: int, ids: list[int]) -> None:
    """Delete bot messages where Telegram allows it (it refuses old ones). Never raises."""
    for i in range(0, len(ids), 10):
        await asyncio.gather(*(rt.bot.delete_message(token, chat_id, m) for m in ids[i : i + 10]), return_exceptions=True)


async def unlink(rt: Runtime, user_id: str) -> tuple[int, str] | None:
    """Disconnect, from the web or the chat `/unlink`. Idempotent."""
    async with rt.deps.as_user(user_id) as tx:
        bot = await get_bot(tx, user_id)
        removed = await remove_link_data(rt, tx, user_id, 'telegram.unlink')
    if not removed or not bot:
        return None
    token = rt.token(bot)
    await delete_messages(rt, token, removed['chat_id'], removed['message_ids'])
    return removed['chat_id'], token


async def end_session_from_web(rt: Runtime, ctx: Ctx) -> None:
    async with rt.deps.as_user(ctx) as tx:
        link = await get_link(tx, ctx.user_id)
        if link and await end_sessions(tx, link.id, 'web', rt.clock()) > 0:
            await rt.deps.bus.emit(tx, 'audit.record', {'user_id': ctx.user_id, 'action': 'telegram.signout_web'})


async def read_settings(rt: Runtime, ctx: Ctx) -> TelegramSettings:
    async with rt.deps.as_user(ctx) as tx:
        return await get_settings(tx, ctx.user_id)


async def patch_settings(rt: Runtime, ctx: Ctx, patch: TelegramSettingsPatch) -> TelegramSettings:  # type: ignore[valid-type]
    async with rt.deps.as_user(ctx) as tx:
        cur = await get_settings(tx, ctx.user_id)
        given = {k: getattr(patch, k) for k in patch.present_keys()}  # type: ignore[attr-defined]
        nxt = cur.model_copy(update=given)
        await tx.execute(
            """INSERT INTO telegram_settings (user_id, allow_reveal, session_idle_days, digest_mode, digest_hour, after_tag, updated_at) VALUES ($1,$2,$3,$4,$5,$6,$7)
               ON CONFLICT (user_id) DO UPDATE SET allow_reveal = EXCLUDED.allow_reveal, session_idle_days = EXCLUDED.session_idle_days,
                 digest_mode = EXCLUDED.digest_mode, digest_hour = EXCLUDED.digest_hour, after_tag = EXCLUDED.after_tag, updated_at = EXCLUDED.updated_at""",
            [ctx.user_id, nxt.allow_reveal, nxt.session_idle_days, nxt.digest_mode, nxt.digest_hour, nxt.after_tag, rt.clock()],
        )
        await _remember_tz(tx, ctx.user_id, ctx.tz)
        return nxt


def _json_row(r: dict[str, Any]) -> dict[str, Any]:
    return {k: to_iso(v) if isinstance(v, datetime) else v for k, v in r.items()}


async def export_part(rt: Runtime, ctx: Ctx) -> ExportPart:
    """Links and counts only: no token, webhook secrets, pairing hashes, message ids or callback tokens."""
    async with rt.deps.as_user(ctx) as tx:
        links = await tx.many('SELECT telegram_user_id, tg_username, linked_at, last_seen_at FROM telegram_links WHERE user_id = $1', [ctx.user_id])
        sessions = await tx.many(
            'SELECT started_at, last_seen_at, ended_at, end_reason FROM telegram_sessions WHERE user_id = $1 ORDER BY started_at', [ctx.user_id]
        )
        prompts = await tx.many(
            'SELECT kind, status, count(*)::int AS count FROM telegram_prompts WHERE user_id = $1 GROUP BY kind, status ORDER BY kind, status',
            [ctx.user_id],
        )
        bot = await get_bot(tx, ctx.user_id)
        settings = await tx.maybe_one(f'SELECT {SETTINGS_COLUMNS} FROM telegram_settings WHERE user_id = $1', [ctx.user_id])
    return ExportPart(
        service='telegram',
        tables={
            'telegram_bot': [{'bot_username': bot.bot_username}] if bot else [],
            'telegram_links': [_json_row(r) for r in links],
            'telegram_sessions': [_json_row(r) for r in sessions],
            'telegram_prompt_counts': prompts,
            'telegram_settings': [settings] if settings else [],
        },
    )


async def purge_user(rt: Runtime, user_id: str) -> None:
    """On `account.deleted`: delete the user's rows and the webhook. Idempotent."""
    async with rt.deps.as_user(user_id) as tx:
        bot = await get_bot(tx, user_id)
        for table in ('telegram_prompts', 'telegram_sessions', 'telegram_links', 'telegram_pairings', 'telegram_bots', 'telegram_settings'):
            await tx.execute(f'DELETE FROM {table} WHERE user_id = $1', [user_id])
    if bot:
        token = rt.token(bot)
        await quietly(rt, lambda: rt.bot.delete_webhook(token), 'delete-webhook')
