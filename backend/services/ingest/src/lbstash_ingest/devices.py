import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from lbstash.common import DEFAULT_TZ, Ctx, Errors
from lbstash.contracts import CreateDeviceReq, DeviceDto, DeviceLastTest, PatchDeviceReq
from lbstash.crypto import new_hashed_token, sha256_hex
from lbstash.db import Tx
from lbstash.kit import Deps

from .parser import Parsed, ParseInput, parse_message
from .sender import normalize_sender_list

TOKEN_PREFIX = 'ledg_live_'
_TOKEN_RE = re.compile(r'ledg_live_[A-Za-z0-9_-]{43}', re.ASCII)


@dataclass(frozen=True, slots=True)
class DeviceRow:
    id: str
    user_id: str
    name: str
    tz: str
    token_hint: str
    allowed_senders: list[str]
    created_at: datetime
    rotated_at: datetime | None
    last_seen_at: datetime | None
    last_delay_seconds: int | None
    last_test_at: datetime | None
    last_test_source: Literal['device', 'web'] | None
    last_test_delay_seconds: int | None
    last_test_amount_minor: int | None
    revoked_at: datetime | None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> 'DeviceRow':
        return cls(**{k: row[k] for k in cls.__dataclass_fields__})


# Columns safe to read: never `token_hash`.
DEVICE_COLS = """id, user_id, name, tz, token_hint, allowed_senders, created_at, rotated_at, last_seen_at, last_delay_seconds,
  last_test_at, last_test_source, last_test_delay_seconds, last_test_amount_minor, revoked_at"""


def to_dto(r: DeviceRow) -> DeviceDto:
    return DeviceDto(
        id=r.id, name=r.name, created_at=r.created_at, last_seen_at=r.last_seen_at, revoked_at=r.revoked_at,
        token_hint=r.token_hint, rotated_at=r.rotated_at, last_delay_seconds=r.last_delay_seconds,
        allowed_senders=r.allowed_senders,
        last_test=DeviceLastTest(
            at=r.last_test_at, source=r.last_test_source, delay_seconds=r.last_test_delay_seconds,
            amount_minor=r.last_test_amount_minor,
        )
        if r.last_test_at and r.last_test_source
        else None,
    )  # fmt: skip


def as_ctx(ctx: Ctx) -> dict[str, str]:
    return {'user_id': ctx.user_id, 'tz': ctx.tz, 'request_id': ctx.request_id}


def _token_hint(token: str) -> str:
    return f'{TOKEN_PREFIX}{token[len(TOKEN_PREFIX) : len(TOKEN_PREFIX) + 4]}…{token[-4:]}'


def safe_tz(tz: str | None) -> str:
    """A known IANA zone, else the default: a bad zone must never break parsing."""
    if not tz:
        return DEFAULT_TZ
    try:
        ZoneInfo(tz)
    except (LookupError, ValueError, OSError):
        return DEFAULT_TZ
    return tz


async def authenticate(deps: Deps, bearer: str | None) -> DeviceRow | None:
    """Token -> device by hash on every request (no cache), so revoking or rotating takes effect at once. Runs in system scope: no user yet."""
    if not bearer or not _TOKEN_RE.fullmatch(bearer):
        return None
    async with deps.as_system() as tx:
        row = await tx.maybe_one(f'SELECT {DEVICE_COLS} FROM devices WHERE token_hash = $1', [sha256_hex(bearer)])
    if not row:
        return None
    d = DeviceRow.from_row(row)
    return None if d.revoked_at else d


async def list_devices(deps: Deps, ctx: Ctx) -> list[DeviceDto]:
    async with deps.as_user(ctx) as tx:
        rows = await tx.many(f'SELECT {DEVICE_COLS} FROM devices ORDER BY (revoked_at IS NULL) DESC, created_at DESC LIMIT 20')
    return [to_dto(DeviceRow.from_row(r)) for r in rows]


async def _active_device(tx: Tx, id: str | None = None) -> DeviceRow | None:
    if id:
        r = await tx.maybe_one(f'SELECT {DEVICE_COLS} FROM devices WHERE id = $1 AND revoked_at IS NULL', [id])
    else:
        r = await tx.maybe_one(f'SELECT {DEVICE_COLS} FROM devices WHERE revoked_at IS NULL ORDER BY created_at DESC LIMIT 1')
    return DeviceRow.from_row(r) if r else None


async def _require_code(deps: Deps, ctx: Ctx, code: str | None) -> None:
    if not code:
        raise Errors.two_factor_required()
    await deps.clients.auth.verify_totp(as_ctx(ctx), code)  # raises two_factor_invalid


async def create_or_rotate(deps: Deps, ctx: Ctx, body: CreateDeviceReq, ip: str | None) -> tuple[DeviceDto, str, bool]:
    """Create the first token or rotate the active one (needs an authenticator code). The token is returned only here; only its sha256 is stored. Returns `(device, token, rotated)`."""
    async with deps.as_user(ctx) as tx:
        existing = await _active_device(tx, body.device_id)
    if body.device_id and not existing:
        raise Errors.not_found('Device')
    if existing:
        await _require_code(deps, ctx, body.code)

    token, hashed = new_hashed_token(TOKEN_PREFIX)
    # `[]` clears the allow-list; only "not sent" (None) leaves it alone
    senders = normalize_sender_list(body.allowed_senders) if body.allowed_senders is not None else None
    tz = safe_tz(ctx.tz)

    async with deps.as_user(ctx) as tx:
        if existing:
            r = await tx.one(
                f"""UPDATE devices SET token_hash = $2, token_hint = $3, rotated_at = now(), tz = $4,
                  name = COALESCE($5, name), allowed_senders = COALESCE($6, allowed_senders)
                WHERE id = $1 AND revoked_at IS NULL RETURNING {DEVICE_COLS}""",
                [existing.id, hashed, _token_hint(token), tz, body.name, senders],
            )
        else:
            r = await tx.one(
                f'INSERT INTO devices (user_id, name, token_hash, token_hint, tz, allowed_senders) VALUES ($1, $2, $3, $4, $5, $6) RETURNING {DEVICE_COLS}',
                [ctx.user_id, body.name or 'iPhone', hashed, _token_hint(token), tz, senders or []],
            )
        await deps.bus.emit(
            tx, 'audit.record',
            {'userId': ctx.user_id, 'action': 'device.token_rotated' if existing else 'device.token_created', 'deviceId': r['id'], 'ip': ip},
        )  # fmt: skip
        row = DeviceRow.from_row(r)
    return to_dto(row), token, existing is not None


async def revoke_device(deps: Deps, ctx: Ctx, id: str, code: str | None, ip: str | None) -> DeviceDto:
    """Cancel the token now (needs an authenticator code). Repeating is harmless."""
    async with deps.as_user(ctx) as tx:
        found = await tx.maybe_one(f'SELECT {DEVICE_COLS} FROM devices WHERE id = $1', [id])
    if not found:
        raise Errors.not_found('Device')
    if found['revoked_at']:
        return to_dto(DeviceRow.from_row(found))
    await _require_code(deps, ctx, code)
    async with deps.as_user(ctx) as tx:
        r = await tx.maybe_one(f'UPDATE devices SET revoked_at = now() WHERE id = $1 AND revoked_at IS NULL RETURNING {DEVICE_COLS}', [id])
        if not r:  # revoked by someone else in the meantime
            return to_dto(DeviceRow.from_row(await tx.one(f'SELECT {DEVICE_COLS} FROM devices WHERE id = $1', [id])))
        await deps.bus.emit(tx, 'audit.record', {'userId': ctx.user_id, 'action': 'device.revoked', 'deviceId': id, 'ip': ip})
    return to_dto(DeviceRow.from_row(r))


async def patch_device(deps: Deps, ctx: Ctx, id: str, body: PatchDeviceReq) -> DeviceDto:
    senders = normalize_sender_list(body.allowed_senders) if body.allowed_senders is not None else None
    async with deps.as_user(ctx) as tx:
        r = await tx.maybe_one(
            f'UPDATE devices SET name = COALESCE($2, name), allowed_senders = COALESCE($3, allowed_senders) WHERE id = $1 RETURNING {DEVICE_COLS}',
            [id, body.name, senders],
        )
    if not r:
        raise Errors.not_found('Device')
    return to_dto(DeviceRow.from_row(r))


# What the Setup guide asks the user to send themselves.
TEST_TEXT = 'Rs 1.00 debited test'
_TEST_WORD = re.compile(r'\btest\b', re.ASCII | re.IGNORECASE)


def is_test_message(text: str, amount_minor: int) -> bool:
    """The one-rupee test text, from the phone or the Devices page. Never reaches the transactions."""
    return amount_minor == 100 and _TEST_WORD.search(text) is not None


async def test_device(deps: Deps, ctx: Ctx) -> tuple[DeviceDto, int, str]:
    """Run the test message through the real parser and record it on the active device. Returns `(device, amount_minor, type)`."""
    r = parse_message(ParseInput(text=TEST_TEXT, received_at=datetime.now(UTC), tz=safe_tz(ctx.tz)))
    if not isinstance(r, Parsed):
        raise Errors.internal('The test message could not be read')
    async with deps.as_user(ctx) as tx:
        d = await _active_device(tx)
        row = (
            await tx.one(
                f"""UPDATE devices SET last_test_at = now(), last_test_source = 'web', last_test_delay_seconds = 0, last_test_amount_minor = $2
                WHERE id = $1 RETURNING {DEVICE_COLS}""",
                [d.id, r.tx.amount_minor],
            )
            if d
            else None
        )
    if row is None:
        raise Errors.conflict('There is no active ingest token. Make one first.')
    return to_dto(DeviceRow.from_row(row)), r.tx.amount_minor, r.tx.type


test_device.__test__ = False  # type: ignore[attr-defined]  # not a pytest test
