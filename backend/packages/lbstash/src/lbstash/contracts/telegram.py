"""Telegram service contracts: links, pairings, sessions, prompts, the encrypted bot token and webhook secret."""

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints

from .base import Bool, Int, IsoDateTime, Model, Opt, partial, regex_str

_DigestHour = Annotated[Int, Field(ge=0, le=23)]
_IdleDays = Annotated[Int, Field(ge=1, le=90)]


class TelegramSettings(Model):
    allow_reveal: Bool
    session_idle_days: _IdleDays
    # Daily reminder of untagged payments: Off / Daily / Twice a day (the second one goes out 12 hours after `digest_hour`).
    digest_mode: Literal['off', 'daily', 'twice']
    # Local hour of the (first) reminder, 0-23 (default 21 = "Daily, 9 pm").
    digest_hour: _DigestHour
    # After you tag: keep the message (no buttons), collapse it to one line, or delete it.
    after_tag: Literal['keep', 'line', 'delete']


TelegramSettingsPatch = partial(TelegramSettings, 'TelegramSettingsPatch')


class TelegramLinkStatus(Model):
    """`GET /telegram/link`: what the Setup guide and Devices page show. Never carries the bot token, webhook secret or a pairing code."""

    bot_saved: Bool
    bot_username: str | None
    # The Telegram account allowed to link this bot ("@name" or a numeric id); pairing codes are only made once it is set.
    owner_telegram: str | None
    linked: Bool
    # "..4821": the last four digits of the Telegram id, never the whole id.
    telegram_id_hint: str | None
    telegram_username: str | None
    linked_at: IsoDateTime | None
    session_active: Bool
    # When the current bot session started (None when signed out).
    session_since: IsoDateTime | None
    last_seen_at: IsoDateTime | None
    # Set while sign-in is paused after three wrong codes.
    sign_in_paused_until: IsoDateTime | None
    # A pairing code was created and is still valid (the Setup guide keeps polling until `linked`).
    pairing_pending: Bool
    # Prompts waiting for `/signin`.
    held_count: Int


class PairingRes(Model):
    """`POST /telegram/pairing`: shown once; only a hash is stored. `command` is what the user sends to the bot."""

    code: str
    command: str
    expires_at: IsoDateTime


_BotToken = Annotated[
    regex_str(r'\d+:[A-Za-z0-9_-]+', 'That does not look like a bot token'),
    StringConstraints(min_length=20, max_length=200),
]


class BotTokenReq(Model):
    """`POST /telegram/bot-token`: saved encrypted, never echoed back."""

    token: _BotToken


class OwnerReq(Model):
    """`PUT /telegram/owner`: your Telegram @username (5-32 letters, digits, underscore) or numeric id. Only that account can link."""

    telegram: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class BotTokenRes(Model):
    ok: Literal[True]
    bot_username: str | None


# The parts of a webhook update the service reads; the rest is ignored. Telegram's own snake_case names, no camelCase alias.
class _Loose(Model):
    model_config = ConfigDict(alias_generator=None, extra='allow')


class TgUser(_Loose):
    id: Int
    is_bot: Opt[Bool] = None
    username: Opt[str] = None


class TgChat(_Loose):
    id: Int
    type: str


class TgMessage(_Loose):
    message_id: Int
    from_: Opt[TgUser] = Field(default=None, alias='from')
    chat: TgChat
    text: Opt[str] = None


class TgCallbackQuery(_Loose):
    id: str
    from_: TgUser = Field(alias='from')
    message: Opt[TgMessage] = None
    data: Opt[str] = None


class TelegramUpdate(_Loose):
    update_id: Int
    message: Opt[TgMessage] = None
    callback_query: Opt[TgCallbackQuery] = None
