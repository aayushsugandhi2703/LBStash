"""Telegram test harness: app and workers over a real (RLS-enforced) database, a fake Bot API, fake transactions and auth. Named `telegram_harness` so several services' tests never import the wrong one."""

import base64
import itertools
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from lbstash.common import Errors, normalize_tag
from lbstash.contracts import (
    BalanceCheckDto,
    BalanceCheckRes,
    BalanceChecksRes,
    CategoriesRes,
    CategoryDto,
    PendingRes,
    TagRes,
    TransactionDto,
    TransactionRes,
    VerifyTotpRes,
)
from lbstash.contracts.base import iso_ms
from lbstash.crypto import FieldCipher
from lbstash.db.testing import TempDatabase
from lbstash.kit.testing import AppHarness, build_test_app, headers_for
from lbstash_telegram.botapi import BotApiError, BotMe, ForceReply, Keyboard
from lbstash_telegram.env import Env
from lbstash_telegram.routes import make_register
from lbstash_telegram.runtime import Runtime, RuntimeOptions, shared_runtime
from lbstash_telegram.workers import make_workers

FIELD_KEY = base64.b64encode(os.urandom(32)).decode()
PUBLIC_URL = 'https://lbstash.example.com'
TZ = 'Asia/Kolkata'
START = datetime(2026, 10, 18, 13, 12, tzinfo=UTC)


@dataclass
class FakeMessage:
    chat_id: int
    text: str
    keyboard: Keyboard | None
    force_reply: bool
    token: str
    deleted: bool = False


class FakeBot:
    """In-process Bot API that keeps each message's current text and buttons, so tests read the chat as the user sees it."""

    def __init__(self) -> None:
        self.messages: dict[int, FakeMessage] = {}
        self.calls: list[dict[str, Any]] = []
        self.webhooks: dict[str, dict[str, str]] = {}
        self.answers: list[dict[str, Any]] = []
        self.rejected: set[str] = set()
        # errors to raise on the next calls of an operation, in order
        self.failures: dict[str, list[BotApiError]] = {}
        self._next_id = 1000
        self.too_old_to_delete = False

    def fail_next(self, op: str, e: BotApiError) -> None:
        self.failures.setdefault(op, []).append(e)

    def _maybe_fail(self, op: str) -> None:
        if self.failures.get(op):
            raise self.failures[op].pop(0)

    async def get_me(self, token: str) -> BotMe:
        self.calls.append({'op': 'getMe', 'token': token})
        if token in self.rejected:
            raise BotApiError('unauthorized', 'token rejected')
        bot_id = token.split(':')[0]
        return BotMe(int(bot_id), f'bot_{bot_id}')

    async def set_webhook(self, token: str, *, url: str, secret_token: str) -> None:
        self.calls.append({'op': 'setWebhook', 'token': token, 'url': url})
        self.webhooks[token] = {'url': url, 'secret_token': secret_token}

    async def delete_webhook(self, token: str) -> None:
        self.calls.append({'op': 'deleteWebhook', 'token': token})
        self.webhooks.pop(token, None)

    async def send_message(
        self, token: str, *, chat_id: int, text: str, keyboard: Keyboard | None = None, force_reply: ForceReply | None = None
    ) -> int:
        self._maybe_fail('sendMessage')
        message_id = self._next_id
        self._next_id += 1
        self.calls.append({'op': 'sendMessage', 'token': token, 'chatId': chat_id, 'messageId': message_id})
        self.messages[message_id] = FakeMessage(chat_id, text, keyboard, force_reply is not None, token)
        return message_id

    async def edit_message_text(
        self, token: str, *, chat_id: int, message_id: int, text: str, keyboard: Keyboard | None = None
    ) -> None:
        self._maybe_fail('editMessageText')
        self.calls.append({'op': 'editMessageText', 'token': token, 'messageId': message_id})
        m = self.messages.get(message_id)
        if m is None or m.deleted:
            raise BotApiError('gone', 'message gone')
        m.text = text
        m.keyboard = keyboard

    async def delete_message(self, token: str, chat_id: int, message_id: int) -> bool:
        self.calls.append({'op': 'deleteMessage', 'token': token, 'chatId': chat_id, 'messageId': message_id})
        m = self.messages.get(message_id)
        if m is None or self.too_old_to_delete:
            return False
        m.deleted = True
        return True

    async def answer_callback_query(self, token: str, callback_query_id: str, text: str | None = None) -> None:
        self.calls.append({'op': 'answerCallbackQuery', 'token': token, 'id': callback_query_id})
        self.answers.append({'id': callback_query_id, 'text': text})

    # the chat as shown now (deleted messages gone), oldest first
    def chat(self, chat_id: int) -> list[FakeMessage]:
        return [m for m in self.messages.values() if m.chat_id == chat_id and not m.deleted]

    def last_message(self, chat_id: int) -> FakeMessage | None:
        c = self.chat(chat_id)
        return c[-1] if c else None

    def sends(self, chat_id: int | None = None) -> list[dict[str, Any]]:
        return [c for c in self.calls if c['op'] == 'sendMessage' and (chat_id is None or c['chatId'] == chat_id)]

    def last_answer(self) -> str | None:
        return self.answers[-1]['text'] if self.answers else None

    @staticmethod
    def buttons(m: FakeMessage | None) -> list[dict[str, str]]:
        return [b for row in (m.keyboard or []) for b in row] if m else []

    def button(self, m: FakeMessage | None, text: str) -> dict[str, str]:
        for b in self.buttons(m):
            if b['text'] == text:
                return b
        raise AssertionError(f'no button "{text}" in [{", ".join(b["text"] for b in self.buttons(m))}]')

    def id_of(self, m: FakeMessage) -> int:
        for id_, x in self.messages.items():
            if x is m:
                return id_
        raise AssertionError('unknown message')


@dataclass
class FakeTx:
    id: str
    user_id: str
    occurred_at: str
    type: str = 'debit'
    amount_minor: int = 45_000
    payee: str | None = 'Swiggy'
    category_id: str | None = None
    category_name: str | None = None
    status: str = 'pending'


def dto(t: FakeTx) -> TransactionDto:
    return TransactionDto(
        id=t.id, type=t.type, amount_minor=t.amount_minor, occurred_at=t.occurred_at, payee=t.payee, description=None,
        category_id=t.category_id, category_name=t.category_name, source='captured', status=t.status, recurring_id=None,
        captured_at=t.occurred_at, weak_parse=False,
    )  # fmt: skip


@dataclass
class FakeCategory:
    id: str
    user_id: str
    name: str
    usage: int


class FakeTransactions:
    """The slice of the transactions this service calls: transactions, tagging, pending list, categories."""

    def __init__(self) -> None:
        self.txs: dict[str, FakeTx] = {}
        self.cats: dict[str, FakeCategory] = {}
        self.tag_calls: list[dict[str, Any]] = []
        self.get_calls: list[str] = []
        self.down = False
        # last balance check; a recent one skips the weekly nudge
        self.balance_checked_at: datetime | None = None

    def seed_categories(self, user_id: str) -> None:
        for name, usage in [('food', 10), ('travel', 9), ('fun', 8), ('bills', 7), ('sip', 6), ('rent', 5), ('gym', 1)]:
            self.category(user_id, name, usage)

    def category(self, user_id: str, name: str, usage: int = 0) -> FakeCategory:
        key = f'{user_id}:{name}'
        if key not in self.cats:
            self.cats[key] = FakeCategory(str(uuid.uuid4()), user_id, name, usage)
        return self.cats[key]

    def add(self, user_id: str, occurred_at: str, **fields: Any) -> FakeTx:
        t = FakeTx(id=str(uuid.uuid4()), user_id=user_id, occurred_at=occurred_at, **fields)
        self.txs[t.id] = t
        return t

    def tag_elsewhere(self, id_: str, name: str) -> None:
        """Tag from the web or a rule without any event; the test emits it."""
        t = self.txs[id_]
        c = self.category(t.user_id, name)
        t.category_id, t.category_name, t.status = c.id, c.name, 'confirmed'

    def _get(self, user_id: str | None, id_: str) -> FakeTx:
        if self.down:
            raise Errors.upstream('transactions')
        t = self.txs.get(id_)
        if t is None or t.user_id != user_id:
            raise Errors.not_found('Transaction')
        return t

    async def get_transaction(self, as_: Any, id_: str) -> TransactionRes:
        self.get_calls.append(id_)
        return TransactionRes(transaction=dto(self._get(as_.user_id, id_)))

    async def tag(self, as_: Any, id_: str, body: dict[str, Any]) -> TagRes:
        t = self._get(as_.user_id, id_)
        self.tag_calls.append({'user_id': as_.user_id, 'id': id_, 'body': body})
        if t.category_id:
            return TagRes(
                transaction=dto(t), changed=False, previous_category_id=None, also_tagged_ids=[], category_created=False
            )
        cat = next((c for c in self.cats.values() if c.id == body.get('categoryId') and c.user_id == as_.user_id), None)
        created = False
        if cat is None:
            if not body.get('tag'):
                raise Errors.not_found('Category')
            name = normalize_tag(body['tag'])
            created = f'{as_.user_id}:{name}' not in self.cats
            cat = self.category(as_.user_id, name)
        cat.usage += 1
        t.category_id, t.category_name, t.status = cat.id, cat.name, 'confirmed'
        also = [
            o for o in self.txs.values()
            if o.user_id == as_.user_id and o.id != id_ and o.status == 'pending' and t.payee and o.payee == t.payee
        ]  # fmt: skip
        for o in also:
            o.category_id, o.category_name, o.status = cat.id, cat.name, 'confirmed'
        return TagRes(
            transaction=dto(t), changed=True, previous_category_id=None, also_tagged_ids=[o.id for o in also],
            category_created=created,
        )  # fmt: skip

    async def create_manual(self, as_: Any, body: dict[str, Any]) -> TransactionRes:
        """A payment typed in the chat: filed under `tag` at once, or left pending without one."""
        t = self.add(as_.user_id, body['occurredAt'], type=body['type'], amount_minor=body['amountMinor'], payee=None)
        if body.get('tag'):
            cat = self.category(as_.user_id, normalize_tag(body['tag']))
            t.category_id, t.category_name, t.status = cat.id, cat.name, 'confirmed'
        return TransactionRes(transaction=dto(t))

    async def pending(self, as_: Any, limit: int = 50) -> PendingRes:
        if self.down:
            raise Errors.upstream('transactions')
        mine = [t for t in self.txs.values() if t.user_id == as_.user_id and t.status == 'pending']
        return PendingRes(count=len(mine), items=[dto(t) for t in mine[:limit]])

    async def categories(self, as_: Any, *, sort: str | None = None, limit: int | None = None, **_: Any) -> CategoriesRes:
        if self.down:
            raise Errors.upstream('transactions')
        mine = sorted((c for c in self.cats.values() if c.user_id == as_.user_id), key=lambda c: -c.usage)
        return CategoriesRes(items=[CategoryDto(id=c.id, name=c.name, archived=False) for c in mine[: limit or 200]])

    async def balance_check(self, as_: Any, bank_balance_minor: int) -> BalanceCheckRes:
        """Tracked balance = credits - debits of this user's rows; a gap leaves an open check."""
        if self.down:
            raise Errors.upstream('transactions')
        tracked = sum(t.amount_minor * (1 if t.type == 'credit' else -1) for t in self.txs.values() if t.user_id == as_.user_id)
        gap = bank_balance_minor - tracked
        at = iso_ms(self.balance_checked_at or datetime.now(UTC))
        check = BalanceCheckDto(
            id=str(uuid.uuid4()), bank_balance_minor=bank_balance_minor, transactions_balance_minor=tracked, gap_minor=gap, source='manual',
            status='resolved' if abs(gap) < 100 else 'open', checked_at=at, as_of=at, transaction_id=None,
            grace_ends_at=None if abs(gap) < 100 else at,
        )  # fmt: skip
        return BalanceCheckRes(check=check, matches=abs(gap) < 100, transactions_balance_minor=tracked, transaction=None)

    async def balance_checks(self, as_: Any, limit: int = 1) -> BalanceChecksRes:
        if self.down:
            raise Errors.upstream('transactions')
        if self.balance_checked_at is None:
            return BalanceChecksRes(items=[])
        at = iso_ms(self.balance_checked_at)
        check = BalanceCheckDto(
            id=str(uuid.uuid4()), bank_balance_minor=0, transactions_balance_minor=0, gap_minor=0, source='manual', status='resolved',
            checked_at=at, as_of=at, transaction_id=None, grace_ends_at=None,
        )  # fmt: skip
        return BalanceChecksRes(items=[check][:limit])


class FakeAuth:
    def __init__(self) -> None:
        self._valid: dict[str, set[str]] = {}
        self.calls = 0

    def allow(self, user_id: str, code: str) -> None:
        self._valid.setdefault(user_id, set()).add(code)

    async def verify_totp(self, as_: Any, code: str) -> VerifyTotpRes:
        self.calls += 1
        codes = self._valid.get(as_.user_id, set())
        if code not in codes:
            raise Errors.two_factor_invalid()
        codes.discard(code)  # a code works once
        return VerifyTotpRes(ok=True)


@dataclass
class TgUser:
    user_id: str
    token: str
    tg_id: int
    chat_id: int
    path_secret: str
    header_secret: str
    username: str


@dataclass
class Res:
    status: int
    body: Any


class Clock:
    """A controllable "now": 18 Oct 2026, 6:42 pm in Kolkata."""

    def __init__(self) -> None:
        self.now = START

    def reset(self) -> None:
        self.now = START

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


_update_seq = itertools.count(1)
_user_seq = itertools.count(1)
_cb_seq = itertools.count(1)


@dataclass
class World:
    db: TempDatabase
    app: AppHarness
    bot: FakeBot
    transactions: FakeTransactions
    auth: FakeAuth
    clock: Clock
    # waits the service asked for (seconds), recorded instead of slept
    sleeps: list[float] = field(default_factory=list)

    @property
    def bus(self) -> Any:
        return self.app.bus

    @property
    def deps(self) -> Any:
        return self.app.deps

    @property
    def runtime(self) -> Runtime:
        """The shared runtime, for calling job handlers directly."""
        return shared_runtime(self.deps)

    def reset(self) -> None:
        self.clock.reset()
        self.bus.clear()

    async def close(self) -> None:
        await self.app.close()

    async def sql(self, text: str, *params: Any) -> list[dict[str, Any]]:
        """Query as the system; row-level security would hide every row otherwise."""
        async with self.deps.as_system() as tx:
            return await tx.query(text, list(params))

    async def settle(self) -> None:
        """Run queued events and jobs, including ones they queue, until none are left."""
        for _ in range(12):
            if not (self.bus.events or self.bus.jobs):
                break
            await self.bus.drain()

    async def run_events(self) -> None:
        """Deliver queued events only; jobs they queue stay in `bus.jobs`."""
        events, self.bus.events[:] = list(self.bus.events), []
        for e in events:
            for fn in self.bus._event_handlers.get(e.event, []):
                await fn(e.payload)

    async def internal(
        self, user_id: str | None, method: str, url: str, payload: Any = None, proxied: bool = False
    ) -> Res:
        res = await self.app.client.request(method, url, headers=headers_for(user_id, 'gateway', TZ, proxied), json=payload)
        return Res(res.status_code, res.json() if res.content else None)

    async def web(self, user_id: str, method: str, url: str, payload: Any = None) -> Res:
        return await self.internal(user_id, method, url, payload)

    async def webhook(self, u: TgUser, update: dict[str, Any], headers: dict[str, str] | None = None) -> Res:
        res = await self.app.client.post(
            f'/telegram/webhook/{u.path_secret}',
            headers={
                **headers_for(None, 'gateway', TZ, True),
                'x-telegram-bot-api-secret-token': u.header_secret,
                **(headers or {}),
            },
            json=update,
        )
        return Res(res.status_code, res.json() if res.content else None)

    async def say(
        self, u: TgUser, text: str, *, from_id: int | None = None, chat_id: int | None = None, chat_type: str = 'private'
    ) -> Res:
        seq = next(_update_seq)
        return await self.webhook(
            u,
            {
                'update_id': seq,
                'message': {
                    'message_id': 50_000 + seq, 'from': {'id': from_id or u.tg_id, 'username': 'someone'},
                    'chat': {'id': chat_id or u.chat_id, 'type': chat_type}, 'text': text,
                },
            },
        )  # fmt: skip

    async def tap_data(self, u: TgUser, message_id: int, data: str, *, from_id: int | None = None, chat_id: int | None = None) -> None:
        await self.webhook(
            u,
            {
                'update_id': next(_update_seq),
                'callback_query': {
                    'id': f'cb{next(_cb_seq)}', 'from': {'id': from_id or u.tg_id},
                    'message': {'message_id': message_id, 'chat': {'id': chat_id or u.chat_id, 'type': 'private'}},
                    'data': data,
                },
            },
        )  # fmt: skip

    async def tap(self, u: TgUser, message_id: int, keyboard: Keyboard | None, label: str) -> None:
        for b in (b for row in keyboard or [] for b in row):
            if b['text'] == label:
                return await self.tap_data(u, message_id, b['callback_data'])
        raise AssertionError(f'no button {label}')

    async def tap_message(self, u: TgUser, m: FakeMessage, label: str) -> None:
        """Tap a button on a message the fake bot holds."""
        await self.tap(u, self.bot.id_of(m), m.keyboard, label)

    async def user_with_bot(self, *, pin: bool = True) -> TgUser:
        """A user with a saved bot token, not yet linked. By default their own Telegram id is the account allowed to link."""
        n = next(_user_seq)
        user_id = str(uuid.uuid4())
        token = f'{700000000 + n}:AAH{os.urandom(18).hex()}'
        res = await self.web(user_id, 'POST', '/telegram/bot-token', {'token': token})
        if res.status != 200:
            raise AssertionError(f'bot-token failed: {res.status} {res.body}')
        hook = self.bot.webhooks[token]
        u = TgUser(
            user_id, token, 9_000_000 + n, 9_000_000 + n, hook['url'].split('/telegram/webhook/')[1],
            hook['secret_token'], f'user{n}',
        )  # fmt: skip
        if pin:
            await self.pin_owner(u)
        return u

    async def pin_owner(self, u: TgUser, telegram: str | None = None) -> None:
        """Choose who may link (default: this user's own Telegram id). Pairing codes need it."""
        res = await self.web(u.user_id, 'PUT', '/telegram/owner', {'telegram': telegram or str(u.tg_id)})
        if res.status != 200:
            raise AssertionError(f'owner failed: {res.status} {res.body}')

    async def linked_user(self, tg_id: int | None = None) -> TgUser:
        """A user with a bot, linked via pairing but not signed in."""
        u = await self.user_with_bot()
        if tg_id:
            u.tg_id = u.chat_id = tg_id
        await self.pin_owner(u)
        p = await self.web(u.user_id, 'POST', '/telegram/pairing')
        if p.status != 201:
            raise AssertionError(f'pairing failed {p.status}')
        await self.say(u, p.body['command'])
        self.transactions.seed_categories(u.user_id)
        return u

    async def sign_in(self, u: TgUser) -> None:
        await self.say(u, '/signin')
        self.auth.allow(u.user_id, '482915')
        await self.say(u, '482915')

    async def signed_in_user(self) -> TgUser:
        """A linked user with an active /signin session."""
        u = await self.linked_user()
        await self.sign_in(u)
        return u

    async def emit_changed(self, tx: FakeTx, kind: str = 'created', tagged_via: str | None = None) -> None:
        await self.emit_raw_changed(tx, kind, tagged_via)
        await self.settle()

    async def emit_raw_changed(self, tx: FakeTx, kind: str = 'created', tagged_via: str | None = None) -> None:
        """Emit `transaction.changed` without delivering it."""
        await self.bus.emit(
            None, 'transaction.changed',
            {
                'userId': tx.user_id, 'transactionId': tx.id, 'kind': kind, 'type': tx.type, 'status': tx.status,
                'source': 'captured', 'occurredAt': tx.occurred_at, 'categoryIds': [tx.category_id], 'taggedVia': tagged_via,
            },
        )  # fmt: skip

    def new_tx(self, u: TgUser, **fields: Any) -> FakeTx:
        """A pending debit for the user (no event yet); `occurred_at` defaults to now."""
        return self.transactions.add(u.user_id, **({'occurred_at': iso_ms(self.clock.now)} | fields))

    async def incoming(self, u: TgUser, **fields: Any) -> FakeTx:
        """A new pending debit plus its delivered `transaction.changed` event."""
        tx = self.new_tx(u, **fields)
        await self.emit_changed(tx)
        return tx

    async def message_of(self, tx: FakeTx) -> tuple[int, FakeMessage]:
        """The chat message for a transaction, found via its prompt."""
        rows = await self.sql('SELECT message_id FROM telegram_prompts WHERE transaction_id = $1', tx.id)
        message_id = int(rows[0]['message_id']) if rows and rows[0]['message_id'] is not None else None
        m = self.bot.messages.get(message_id) if message_id is not None else None
        if m is None:
            raise AssertionError('no message for transaction')
        return message_id, m

    async def prompt_row(self, tx_id: str) -> dict[str, Any]:
        return (await self.sql('SELECT * FROM telegram_prompts WHERE transaction_id = $1', tx_id))[0]


def runtime_options(bot: FakeBot, clock: Callable[[], datetime], sleeps: list[float] | None = None, gap_ms: int = 0) -> RuntimeOptions:
    async def sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    return RuntimeOptions(bot=bot, clock=clock, sleep=sleep, send_gap_ms=gap_ms, cipher=FieldCipher({1: FIELD_KEY}))


async def make_world(db: TempDatabase, send_gap_ms: int = 0) -> World:
    bot, transactions, auth, clock = FakeBot(), FakeTransactions(), FakeAuth(), Clock()
    # a recent check, so the Sunday balance nudge doesn't add a message to digest tests
    transactions.balance_checked_at = START
    sleeps: list[float] = []
    opts = runtime_options(bot, clock, sleeps, send_gap_ms)
    app = await build_test_app(
        service='telegram', register=make_register(opts), pool=db.pool, clients={'transactions': transactions, 'auth': auth},
        env={'FIELD_KEY': FIELD_KEY, 'PUBLIC_URL': PUBLIC_URL, 'TELEGRAM_API_BASE': 'http://fake.invalid', 'TELEGRAM_SEND_GAP_MS': 0},
        env_model=Env,
    )  # fmt: skip
    await make_workers(opts)(app.deps)
    return World(db, app, bot, transactions, auth, clock, sleeps)

