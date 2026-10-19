"""Append-only audit log."""

from typing import Any

from bt.contracts import AuditEntryDto
from bt.db import Tx, jsonb


async def record_audit(
    tx: Tx, user_id: str, action: str, *, ip: str | None = None, device_id: str | None = None, meta: dict[str, Any] | None = None
) -> None:
    """Append an entry in the caller's transaction. `meta` holds ids, counts and outcome codes only: no amounts,
    payees, message text, e-mail addresses or tokens."""
    await tx.execute(
        'INSERT INTO audit_log (user_id, device_id, action, ip, meta) VALUES ($1, $2, $3, $4, $5)',
        [user_id, device_id, action, ip, jsonb(meta) if meta is not None else None],
    )


async def record_audit_if_user(
    tx: Tx, user_id: str, action: str, *, ip: str | None = None, device_id: str | None = None, meta: dict[str, Any] | None = None
) -> None:
    """Same, but skips a user that no longer exists (late events)."""
    await tx.execute(
        'INSERT INTO audit_log (user_id, device_id, action, ip, meta) SELECT $1, $2, $3, $4, $5 '
        'WHERE EXISTS (SELECT 1 FROM users WHERE id = $1)',
        [user_id, device_id, action, ip, jsonb(meta) if meta is not None else None],
    )


async def list_audit(tx: Tx, user_id: str, limit: int) -> list[AuditEntryDto]:
    """Newest first."""
    rows = await tx.many(
        'SELECT id, at, action, ip, device_id, meta FROM audit_log WHERE user_id = $1 ORDER BY id DESC LIMIT $2',
        [user_id, limit],
    )
    return [AuditEntryDto.model_validate(r) for r in rows]
