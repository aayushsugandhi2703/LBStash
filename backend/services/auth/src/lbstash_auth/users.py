"""The user row and the answers built from it."""

from dataclasses import dataclass
from datetime import datetime

from lbstash.common import AppError, Errors
from lbstash.contracts import AuthSessionRes, SetupState, UserDto
from lbstash.db import Tx

USER_COLS = (
    'id, email, password_hash, name, timezone, totp_secret_enc, totp_pending_enc, totp_enabled_at, last_totp_step, '
    'setup_completed_at, pending_email, delete_after, password_changed_at, created_at'
)


@dataclass(slots=True)
class UserRow:
    id: str
    email: str
    password_hash: str
    name: str | None
    timezone: str
    totp_secret_enc: bytes | None
    totp_pending_enc: bytes | None
    totp_enabled_at: datetime | None
    last_totp_step: int | None
    setup_completed_at: datetime | None
    pending_email: str | None
    delete_after: datetime | None
    password_changed_at: datetime
    created_at: datetime


def to_user_dto(u: UserRow) -> UserDto:
    return UserDto(
        id=u.id, email=u.email, name=u.name, timezone=u.timezone, pending_email=u.pending_email,
        delete_after=u.delete_after, created_at=u.created_at,
    )  # fmt: skip


async def load_user(tx: Tx, user_id: str, *, lock: bool = False) -> UserRow:
    """The user, or 401 when the row is gone (old token of a deleted account)."""
    row = await tx.maybe_one(f'SELECT {USER_COLS} FROM users WHERE id = $1{" FOR UPDATE" if lock else ""}', [user_id])
    if row is None:
        raise Errors.unauthorized()
    return UserRow(**row)


async def find_user_by_email(tx: Tx, email: str) -> UserRow | None:
    row = await tx.maybe_one(f'SELECT {USER_COLS} FROM users WHERE email = $1', [email])
    return UserRow(**row) if row else None


async def recovery_codes_left(tx: Tx, user_id: str) -> int:
    r = await tx.maybe_one(
        "SELECT count(*) AS n FROM auth_factors WHERE user_id = $1 AND kind = 'recovery_code' "
        'AND used_at IS NULL AND revoked_at IS NULL',
        [user_id],
    )
    return int(r['n']) if r else 0


async def recovery_codes_ever_made(tx: Tx, user_id: str) -> bool:
    r = await tx.maybe_one("SELECT 1 FROM auth_factors WHERE user_id = $1 AND kind = 'recovery_code' LIMIT 1", [user_id])
    return r is not None


async def setup_state(tx: Tx, u: UserRow) -> SetupState:
    return SetupState(
        totp_enabled=u.totp_enabled_at is not None,
        recovery_codes=await recovery_codes_ever_made(tx, u.id),
        complete=u.setup_completed_at is not None,
    )


async def session_res(
    tx: Tx, u: UserRow, *, recovery_code_used: bool = False, deletion_cancelled: bool = False
) -> AuthSessionRes:
    return AuthSessionRes(
        user=to_user_dto(u), setup=await setup_state(tx, u), recovery_codes_left=await recovery_codes_left(tx, u.id),
        recovery_code_used=recovery_code_used, deletion_cancelled=deletion_cancelled,
    )  # fmt: skip


def assert_setup_complete(u: UserRow) -> None:
    """Block routes beyond setup and sign-out until mandatory setup is finished."""
    if u.setup_completed_at is None:
        raise AppError('forbidden', 'Finish securing your account first', {'setupRequired': True})

