"""Ledger settings (opening balance, grace period) and the derived balance."""

from dataclasses import dataclass
from datetime import datetime

from bt.common import Ctx, available_balance
from bt.contracts import LedgerSettings
from bt.db import Row, Tx

from .model import D


@dataclass(frozen=True, slots=True)
class Settings:
    opening_balance_minor: int
    reconcile_grace_hours: int
    # Newest bank balance used so far: older, out-of-order messages may not supply one (README 3.6).
    last_balance_at: datetime | None


async def _row(tx: Tx, user_id: str) -> Row:
    await tx.query('INSERT INTO ledger_settings (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING', [user_id])
    return await tx.one(
        'SELECT opening_balance_minor, reconcile_grace_hours, last_balance_at FROM ledger_settings WHERE user_id = $1',
        [user_id],
    )


def to_dto(r: Row) -> LedgerSettings:
    return LedgerSettings(opening_balance_minor=r['opening_balance_minor'], reconcile_grace_hours=r['reconcile_grace_hours'])


async def get_settings(tx: Tx, user_id: str) -> Settings:
    r = await _row(tx, user_id)
    return Settings(r['opening_balance_minor'], r['reconcile_grace_hours'], r['last_balance_at'])


async def patch_settings(
    deps: D, ctx: Ctx, *, opening_balance_minor: int | None = None, reconcile_grace_hours: int | None = None
) -> LedgerSettings:
    async with deps.as_user(ctx) as tx:
        await _row(tx, ctx.user_id)
        r = await tx.one(
            """UPDATE ledger_settings SET opening_balance_minor = COALESCE($2, opening_balance_minor),
         reconcile_grace_hours = COALESCE($3, reconcile_grace_hours), updated_at = now()
       WHERE user_id = $1 RETURNING opening_balance_minor, reconcile_grace_hours, last_balance_at""",
            [ctx.user_id, opening_balance_minor, reconcile_grace_hours],
        )
        return to_dto(r)


async def balance_at(tx: Tx, user_id: str, as_of: datetime | None = None) -> int:
    """opening + credits - debits, never stored. Reversed rows are excluded, Unaccounted included; `as_of` limits to rows up to then."""
    s = await _row(tx, user_id)
    r = await tx.one(
        """SELECT COALESCE(SUM(amount_minor) FILTER (WHERE type = 'credit'), 0)::bigint AS credits,
            COALESCE(SUM(amount_minor) FILTER (WHERE type = 'debit'), 0)::bigint AS debits
       FROM transactions WHERE user_id = $1 AND status <> 'reversed' AND ($2::timestamptz IS NULL OR occurred_at <= $2)""",
        [user_id, as_of],
    )
    return available_balance(s['opening_balance_minor'], r['credits'], r['debits'])
