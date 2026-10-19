"""Row shapes and small queries shared by routes, webhook and workers. Run them inside `as_user` / `as_system`."""

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Any, Literal

from bt.contracts import TelegramSettings
from bt.db import Tx, jsonb


@dataclass
class BotRow:
    user_id: str
    token_enc: bytes
    bot_username: str | None
    path_hash: str
    header_hash: str
    tz: str
    last_update_id: int | None


@dataclass
class LinkRow:
    id: str
    user_id: str
    telegram_user_id: int
    chat_id: int
    tg_username: str | None
    linked_at: datetime
    last_seen_at: datetime | None
    signin_until: datetime | None
    signin_fail_count: int
    signin_fail_since: datetime | None
    signin_paused_until: datetime | None
    awaiting_prompt_id: str | None
    awaiting_until: datetime | None
    awaiting_msg_id: int | None


@dataclass
class SessionRow:
    id: str
    link_id: str
    user_id: str
    started_at: datetime
    last_seen_at: datetime
    ended_at: datetime | None


PromptKind = Literal['tag', 'alert', 'digest']
PromptStatus = Literal['queued', 'held', 'sent', 'tagged', 'auto_tagged', 'expired', 'failed']
Direction = Literal['debit', 'credit']


@dataclass
class PromptRow:
    id: str
    seq: int
    user_id: str
    link_id: str
    transaction_id: str | None
    kind: PromptKind
    status: PromptStatus
    dedupe_key: str
    direction: Direction | None
    occurred_at: datetime | None
    message_id: int | None
    token: str
    # [{"id": uuid, "name": text}]: category buttons on this message
    choices: list[dict[str, str]] | None
    category_name: str | None
    resolved_via: Literal['telegram', 'web', 'rule'] | None
    meta: dict[str, Any]
    nav: bool
    plan_answer: Literal['yes', 'no'] | None
    revealed_until: datetime | None
    created_at: datetime
    sent_at: datetime | None
    resolved_at: datetime | None


def make_row[T](cls: type[T], r: dict[str, Any] | None) -> T | None:
    if r is None:
        return None
    return cls(**{f.name: r[f.name] for f in fields(cls)})  # type: ignore[arg-type]


def default_settings() -> TelegramSettings:
    return TelegramSettings(allow_reveal=True, session_idle_days=30, digest_mode='daily', digest_hour=21, after_tag='line')


# Prompts whose message may still show buttons.
OPEN_STATUSES = ('queued', 'held', 'sent')

SETTINGS_COLUMNS = 'allow_reveal, session_idle_days, digest_mode, digest_hour, after_tag'


async def get_settings(tx: Tx, user_id: str) -> TelegramSettings:
    r = await tx.maybe_one(f'SELECT {SETTINGS_COLUMNS} FROM telegram_settings WHERE user_id = $1', [user_id])
    return TelegramSettings.model_validate(r) if r else default_settings()


async def get_bot(tx: Tx, user_id: str) -> BotRow | None:
    return make_row(BotRow, await tx.maybe_one('SELECT * FROM telegram_bots WHERE user_id = $1', [user_id]))


async def get_link(tx: Tx, user_id: str) -> LinkRow | None:
    return make_row(LinkRow, await tx.maybe_one('SELECT * FROM telegram_links WHERE user_id = $1', [user_id]))


async def get_prompt(tx: Tx, prompt_id: str) -> PromptRow | None:
    return make_row(PromptRow, await tx.maybe_one('SELECT * FROM telegram_prompts WHERE id = $1', [prompt_id]))


def prompt_from(r: dict[str, Any] | None) -> PromptRow | None:
    return make_row(PromptRow, r)


async def active_session(tx: Tx, link_id: str, idle_days: int, now: datetime) -> SessionRow | None:
    """The open session if still inside the idle window. Read-only."""
    r = await tx.maybe_one(
        """SELECT * FROM telegram_sessions WHERE link_id = $1 AND ended_at IS NULL
              AND last_seen_at > $2::timestamptz - ($3::int * interval '1 day')""",
        [link_id, now, idle_days],
    )
    return make_row(SessionRow, r)


async def touch_session(tx: Tx, link: LinkRow, idle_days: int, now: datetime) -> SessionRow | None:
    """Ends an idle session, else bumps `last_seen_at`. Returns the session if still active."""
    await tx.execute(
        """UPDATE telegram_sessions SET ended_at = $2, end_reason = 'idle'
            WHERE link_id = $1 AND ended_at IS NULL AND last_seen_at <= $2::timestamptz - ($3::int * interval '1 day')""",
        [link.id, now, idle_days],
    )
    r = await tx.maybe_one(
        'UPDATE telegram_sessions SET last_seen_at = $2 WHERE link_id = $1 AND ended_at IS NULL RETURNING *', [link.id, now]
    )
    await tx.execute('UPDATE telegram_links SET last_seen_at = $2 WHERE id = $1', [link.id, now])
    return make_row(SessionRow, r)


async def end_sessions(tx: Tx, link_id: str, reason: Literal['signout', 'idle', 'web', 'unlink', 'replaced'], now: datetime) -> int:
    return await tx.execute(
        'UPDATE telegram_sessions SET ended_at = $2, end_reason = $3 WHERE link_id = $1 AND ended_at IS NULL',
        [link_id, now, reason],
    )


async def insert_prompt(
    tx: Tx,
    *,
    user_id: str,
    link_id: str,
    kind: PromptKind,
    status: Literal['queued', 'held'],
    dedupe_key: str,
    token: str,
    now: datetime,
    transaction_id: str | None = None,
    direction: Direction | None = None,
    occurred_at: datetime | None = None,
    meta: dict[str, Any] | None = None,
) -> PromptRow | None:
    """Insert once per dedupe key; None if it already existed (events are delivered at least once)."""
    r = await tx.maybe_one(
        """INSERT INTO telegram_prompts (user_id, link_id, transaction_id, kind, status, dedupe_key, direction, occurred_at, token, meta, created_at)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
           ON CONFLICT (user_id, dedupe_key) DO NOTHING RETURNING *""",
        [user_id, link_id, transaction_id, kind, status, dedupe_key, direction, occurred_at, token, jsonb(meta or {}), now],
    )
    return prompt_from(r)


async def prompts_by_transaction(tx: Tx, transaction_id: str) -> list[PromptRow]:
    rows = await tx.many("SELECT * FROM telegram_prompts WHERE transaction_id = $1 AND kind = 'tag' ORDER BY seq", [transaction_id])
    return [p for r in rows if (p := prompt_from(r))]
