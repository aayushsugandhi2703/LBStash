"""What every domain module gets: deps, Bot API, clock, cipher, per-chat send queue and rate limiters."""

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from bt.clients import CallAs
from bt.common import Clock, system_clock
from bt.crypto import FieldCipher
from bt.kit import Deps, MemoryRateLimiter

from .botapi import BotApi, BotApiError, HttpBotApi
from .env import Env

Sleep = Callable[[float], Awaitable[None]]


@dataclass
class RuntimeOptions:
    """Test overrides: fake Bot API, frozen clock, no real sleeping."""

    bot: BotApi | None = None
    clock: Clock | None = None
    cipher: FieldCipher | None = None
    sleep: Sleep | None = None
    send_gap_ms: int | None = None


class ChatQueue:
    """One send per chat at a time, at least `gap_ms` apart (Telegram allows about one per second)."""

    def __init__(self, gap_ms: int, sleep: Sleep) -> None:
        self._gap = gap_ms / 1000
        self._sleep = sleep
        self._locks: dict[str, tuple[asyncio.Lock, int]] = {}
        self._last_at: dict[str, float] = {}

    async def run[T](self, chat: str, fn: Callable[[], Awaitable[T]]) -> T:
        lock, users = self._locks.get(chat) or (asyncio.Lock(), 0)
        self._locks[chat] = (lock, users + 1)
        try:
            async with lock:
                return await fn()
        finally:
            lock, users = self._locks[chat]
            if users <= 1:
                del self._locks[chat]
            else:
                self._locks[chat] = (lock, users - 1)

    async def throttle(self, chat: str) -> None:
        """Call right before a send, inside `run`."""
        last = self._last_at.get(chat)
        if last is not None:
            wait = last + self._gap - time.monotonic()
            if wait > 0:
                await self._sleep(wait)
        self._last_at[chat] = time.monotonic()

    def hold_for(self, chat: str, seconds: float) -> None:
        """Telegram asked us to wait: pause the chat for `seconds`."""
        self._last_at[chat] = time.monotonic() + seconds - self._gap


@dataclass
class Runtime:
    deps: Deps[Env]
    bot: BotApi
    clock: Clock
    cipher: FieldCipher
    sleep: Sleep
    chats: ChatQueue
    # bad webhook secrets, per caller address
    bad_secret: MemoryRateLimiter = field(default_factory=lambda: MemoryRateLimiter(20, 60))
    # all webhook calls, per bot
    webhook: MemoryRateLimiter = field(default_factory=lambda: MemoryRateLimiter(240, 60))
    # updates from senders other than the linked one, per bot and sender (never answered)
    strangers: MemoryRateLimiter = field(default_factory=lambda: MemoryRateLimiter(10, 60))
    # pairing attempts, per bot and sender
    pair_tries: MemoryRateLimiter = field(default_factory=lambda: MemoryRateLimiter(5, 15 * 60))
    # pairing codes created, per user
    pair_create: MemoryRateLimiter = field(default_factory=lambda: MemoryRateLimiter(10, 60 * 60))

    def call_as(self, user_id: str, tz: str | None = None) -> CallAs:
        return CallAs(user_id=user_id, tz=tz, request_id=str(uuid.uuid4()))

    def token(self, bot: Any) -> str:
        """Decrypted bot token. aad = user id, so ciphertext can't be moved to another user's row."""
        return self.cipher.decrypt_string(bot.token_enc, bot.user_id)


def create_runtime(deps: Deps[Env], o: RuntimeOptions | None = None) -> Runtime:
    o = o or RuntimeOptions()
    sleep = o.sleep or asyncio.sleep
    env = deps.env
    return Runtime(
        deps=deps,
        bot=o.bot or HttpBotApi(env.TELEGRAM_API_BASE, sleep=sleep),
        clock=o.clock or system_clock,
        cipher=o.cipher or FieldCipher.from_keys(env.FIELD_KEY, env.FIELD_KEYS),
        sleep=sleep,
        chats=ChatQueue(env.TELEGRAM_SEND_GAP_MS if o.send_gap_ms is None else o.send_gap_ms, sleep),
    )


def shared_runtime(deps: Deps[Env], o: RuntimeOptions | None = None) -> Runtime:
    """One runtime per app, shared by routes and workers so sends to a chat share one queue and pacing."""
    rt = getattr(deps, '_telegram_runtime', None)
    if rt is None:
        rt = create_runtime(deps, o)
        deps._telegram_runtime = rt  # type: ignore[attr-defined]
    return rt


async def quietly[T](rt: Runtime, fn: Callable[[], Awaitable[T]], what: str) -> T | None:
    """Run a Bot API call whose failure must not break the flow (edit, delete, toast). Rate limits still raise."""
    try:
        return await fn()
    except BotApiError as e:
        if e.kind == 'rate_limited':
            raise
        rt.deps.log.debug('bot call skipped', what=what, kind=e.kind)
        return None
