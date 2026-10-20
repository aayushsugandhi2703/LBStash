import math
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from lbstash.common import AppError, Errors, system_clock
from lbstash.contracts import IngestBody, IngestMessageRes, IngestMessageTx, IngestTransactionReq
from lbstash.crypto import FieldCipher
from lbstash.kit import Deps, MemoryRateLimiter

from .devices import DeviceRow, authenticate, is_test_message, safe_tz
from .parser import Ignored, ParsedTx, ParseInput, Unreadable, is_otp_or_promo, mask_message, parse_message
from .sender import sender_allowed

# `receivedAt` must be within this of server time (README 4.6).
REPLAY_WINDOW_S = 5 * 60

_CREATED = frozenset({'created', 'replaced_unaccounted', 'saved_as_credit'})
_CIPHERS: dict[int, tuple[Any, FieldCipher]] = {}


def cipher_of(deps: Deps) -> FieldCipher:
    """The field cipher for this env, built once."""
    hit = _CIPHERS.get(id(deps.env))
    if hit is None or hit[0] is not deps.env:
        e = deps.env
        hit = (e, FieldCipher.from_keys(e.FIELD_KEY, e.FIELD_KEYS))
        _CIPHERS[id(e)] = hit
    return hit[1]


@dataclass(frozen=True, slots=True)
class IngestResult:
    status: Literal[200, 201, 202]
    body: IngestMessageRes


def _ignored(reason: Literal['otp_or_promo', 'not_a_transaction', 'sender_not_allowed']) -> IngestResult:
    return IngestResult(202, IngestMessageRes(outcome='ignored', transaction=None, reason=reason))


def _nonce_used() -> AppError:
    return AppError('replay', 'This nonce was already used', {'reason': 'nonce_used'})


class IngestService:
    """The capture endpoint, in README 4.6 order: authenticate, rate limit, timestamp and nonce, OTP/promo guard, parse, transactions.
    Never logs or stores message text; unreadable messages are stored encrypted.
    """

    def __init__(self, deps: Deps, now: Any = system_clock) -> None:
        self.deps = deps
        self.now = now
        env = deps.env
        clock = lambda: self.now().timestamp()  # late-bound so a test can swap `now`
        self.per_device = MemoryRateLimiter(getattr(env, 'INGEST_RATE_PER_DEVICE_MIN', 20), 60, clock)
        self.per_ip = MemoryRateLimiter(getattr(env, 'INGEST_RATE_PER_IP_MIN', 60), 60, clock)
        self.bad_token = MemoryRateLimiter(getattr(env, 'INGEST_BAD_TOKEN_PER_IP_MIN', 10), 60, clock)

    async def handle(self, *, bearer: str | None, ip: str, request_id: str, parse_body: Any) -> IngestResult:
        """`parse_body()` runs only after the token and rate limits pass."""
        deps = self.deps
        # 1. authenticate (bad-token guessing is rate limited per address)
        device = await authenticate(deps, bearer)
        if device is None:
            # last 4 characters of a rejected token only (to tell which old sender is calling), never the token
            deps.log.info('ingest token rejected', tail=bearer[-4:] if bearer else None, chars=len(bearer or ''), rid=request_id)
            if not self.bad_token.allow(ip):
                raise Errors.too_many()
            raise Errors.unauthorized('Bad or cancelled ingest token')
        # 2. rate limit per device and address
        if not self.per_device.allow(device.id) or not self.per_ip.allow(ip):
            raise Errors.too_many()

        body: IngestBody = parse_body()
        now: datetime = self.now()

        # 3. timestamp window, then nonce
        skew = (body.received_at - now).total_seconds()
        if abs(skew) > REPLAY_WINDOW_S:
            stale = skew < 0
            raise AppError(
                'replay',
                'receivedAt is too old: the request may have been replayed' if stale else 'receivedAt is in the future: check the phone clock',
                {'reason': 'stale_timestamp' if stale else 'clock_skew'},
            )  # fmt: skip
        async with deps.as_user(device.user_id) as tx:
            used = await tx.maybe_one('SELECT 1 FROM ingest_events WHERE device_id = $1 AND nonce = $2', [device.id, body.nonce])
        if used:
            raise _nonce_used()

        # A sender run by hand has no message: record it as the device test, like the one-rupee test text, and store nothing
        if not body.text.strip():
            event_id = await self._claim_nonce(device, body.nonce)
            async with deps.as_user(device.user_id) as t:
                await t.execute("UPDATE ingest_events SET outcome = 'test' WHERE id = $1", [event_id])
                await t.execute(
                    """UPDATE devices SET last_seen_at = $2, last_test_at = $2, last_test_source = 'device',
                      last_test_delay_seconds = 0, last_test_amount_minor = 100 WHERE id = $1""",
                    [device.id, now],
                )
            return IngestResult(200, IngestMessageRes(outcome='test', transaction=None))

        # 4. OTP / promo guard: before anything is parsed, stored or logged
        if is_otp_or_promo(body.text):
            return _ignored('otp_or_promo')
        if not sender_allowed(device.allowed_senders, body.sender):
            return _ignored('sender_not_allowed')

        # 5. parse
        parsed = parse_message(ParseInput(text=body.text, received_at=body.received_at, tz=safe_tz(device.tz)))
        if isinstance(parsed, Ignored):
            return _ignored('otp_or_promo' if parsed.reason == 'otp_or_promo' else 'not_a_transaction')
        if isinstance(parsed, Unreadable):
            return await self._store_unparsed(device, body, parsed.reason, now)

        tx_ = parsed.tx
        event_id = await self._claim_nonce(device, body.nonce)

        # The Setup guide's one-rupee test text: recorded on the device, never sent to the transactions
        if is_test_message(body.text, tx_.amount_minor):
            async with deps.as_user(device.user_id) as t:
                await t.execute("UPDATE ingest_events SET outcome = 'test' WHERE id = $1", [event_id])
                await t.execute(
                    """UPDATE devices SET last_seen_at = $2, last_test_at = $2, last_test_source = 'device',
                      last_test_delay_seconds = $3, last_test_amount_minor = $4 WHERE id = $1""",
                    [device.id, now, _delay_seconds(tx_, body.received_at), tx_.amount_minor],
                )
            return IngestResult(200, IngestMessageRes(outcome='test', transaction=None))

        # 6. transactions; a failure frees the nonce so a retry works
        try:
            res = await deps.clients.transactions.ingest(
                {'user_id': device.user_id, 'tz': safe_tz(device.tz), 'request_id': request_id}, _to_transactions_req(tx_, device, now)
            )
        except Exception:
            await self._release_nonce(device, event_id)
            raise
        async with deps.as_user(device.user_id) as t:
            await t.execute(
                'UPDATE ingest_events SET outcome = $2, transaction_id = $3 WHERE id = $1',
                [event_id, res.outcome, res.transaction.id if res.transaction else None],
            )
            await t.execute(
                'UPDATE devices SET last_seen_at = $2, last_delay_seconds = $3 WHERE id = $1',
                [device.id, now, _delay_seconds(tx_, body.received_at)],
            )
        tr = res.transaction
        return IngestResult(
            201 if res.outcome in _CREATED else 200,
            IngestMessageRes(
                outcome=res.outcome,
                transaction=IngestMessageTx(id=tr.id, type=tr.type, amount_minor=tr.amount_minor, status=tr.status) if tr else None,
            ),
        )  # fmt: skip

    async def _claim_nonce(self, device: DeviceRow, nonce: str) -> str:
        """The UNIQUE (device_id, nonce) constraint decides who used it first, even under concurrency."""
        async with self.deps.as_user(device.user_id) as tx:
            r = await tx.maybe_one(
                'INSERT INTO ingest_events (user_id, device_id, nonce) VALUES ($1, $2, $3) ON CONFLICT (device_id, nonce) DO NOTHING RETURNING id',
                [device.user_id, device.id, nonce],
            )
        if not r:
            raise _nonce_used()
        return r['id']

    async def _release_nonce(self, device: DeviceRow, event_id: str) -> None:
        with suppress(Exception):  # the caller must see the original error
            async with self.deps.as_user(device.user_id) as tx:
                await tx.execute('DELETE FROM ingest_events WHERE id = $1', [event_id])

    async def _store_unparsed(
        self, device: DeviceRow, body: IngestBody, reason: Literal['no_amount', 'direction_unclear', 'unreadable'], now: datetime
    ) -> IngestResult:
        """Keep the masked text encrypted for Needs a look, nudge Telegram, answer 422."""
        deps = self.deps
        enc = cipher_of(deps).encrypt_string(mask_message(body.text), device.user_id)
        async with deps.as_user(device.user_id) as tx:
            ev = await tx.maybe_one(
                "INSERT INTO ingest_events (user_id, device_id, nonce, outcome) VALUES ($1, $2, $3, 'unparsed') ON CONFLICT (device_id, nonce) DO NOTHING RETURNING id",
                [device.user_id, device.id, body.nonce],
            )
            if not ev:
                raise _nonce_used()
            row = await tx.one(
                'INSERT INTO unparsed_messages (user_id, device_id, body_enc, reason, received_at) VALUES ($1, $2, $3, $4, $5) RETURNING id',
                [device.user_id, device.id, enc, reason, body.received_at],
            )
            n = (
                await tx.one("SELECT count(*)::int AS n FROM ingest_events WHERE outcome = 'unparsed' AND received_at > now() - interval '24 hours'")
            )['n']
            await tx.execute('UPDATE devices SET last_seen_at = $2 WHERE id = $1', [device.id, now])
            await deps.bus.emit(tx, 'unparsed.created', {'userId': device.user_id, 'unparsedId': row['id'], 'failuresLast24h': n})
        raise Errors.unprocessable('That message could not be read. It is waiting under Needs a look.', {'reason': 'unparsed'})


def _delay_seconds(tx: ParsedTx, received_at: datetime) -> int | None:
    if not tx.time_is_exact:
        return None
    return max(0, math.floor((received_at - tx.occurred_at).total_seconds() + 0.5))  # round half up


def _to_transactions_req(tx: ParsedTx, device: DeviceRow, captured_at: datetime) -> IngestTransactionReq:
    return IngestTransactionReq(
        type=tx.type, amount_minor=tx.amount_minor, occurred_at=tx.occurred_at, payee=tx.payee, reference=tx.reference,
        account_last4=tx.account_last4, balance_after_minor=tx.balance_after_minor, device_id=device.id, captured_at=captured_at,
        weak_parse=tx.weak_parse, reversal=tx.reversal, dedupe_key=tx.dedupe_key,
    )  # fmt: skip
