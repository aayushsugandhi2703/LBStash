"""Export, account deletion and the nightly retention sweep."""

from datetime import datetime
from typing import Any

from lbstash.common import Ctx
from lbstash.contracts import ExportPart

from .model import D


async def export_rows(deps: D, ctx: Ctx) -> ExportPart:
    """All of the user's rows, minus our own bookkeeping column (payee_key)."""
    async with deps.as_user(ctx) as tx:

        async def dump(table: str, order: str, drop: str = '') -> list[dict[str, Any]]:
            rows = await tx.many(
                f"SELECT to_jsonb(t) - 'user_id'{drop} AS j FROM {table} t WHERE user_id = $1 ORDER BY {order}", [ctx.user_id]
            )
            return [r['j'] for r in rows]

        return ExportPart(
            service='transactions',
            tables={
                'transactions_settings': await dump('transactions_settings', 'updated_at'),
                'categories': await dump('categories', 'name'),
                'transactions': await dump('transactions', 'occurred_at, id', " - 'payee_key'"),
                'tag_rules': await dump('tag_rules', 'pattern'),
                'balance_checks': await dump('balance_checks', 'checked_at, id'),
            },
        )


async def purge_user(deps: D, user_id: str) -> None:
    """`account.deleted`: remove every row of the user. Safe to repeat. Children first (transactions reference categories)."""
    async with deps.as_system() as tx:
        for t in ('balance_checks', 'tx_links', 'tag_rules', 'transactions', 'categories', 'transactions_settings'):
            await tx.query(f'DELETE FROM {t} WHERE user_id = $1', [user_id])


async def sweep(deps: D, now: datetime) -> dict[str, int]:
    """Nightly: delete closed balance checks older than 90 days and purge published outbox rows. Money rows never expire."""
    async with deps.as_system() as tx:
        checks = await tx.execute(
            "DELETE FROM balance_checks WHERE status IN ('resolved', 'ignored') AND checked_at < $1::timestamptz - interval '90 days'",
            [now],
        )
    # not part of the MessageBus protocol; only the real bus has it
    purge = getattr(deps.bus, 'purge_outbox', None)
    outbox = await purge() if callable(purge) else 0
    return {'checks': checks, 'outbox': outbox}
