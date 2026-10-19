"""Alerts: the list, the unread badge, marking read."""

from typing import Any

from bt.common import Ctx, Errors
from bt.contracts import AlertDto, AlertReadRes, AlertsRes
from bt.db import Queryable
from bt.kit import Deps

COLS = 'id, budget_id, category_name, level, period_key, sent_at, read_at'


def _to_dto(r: dict[str, Any]) -> AlertDto:
    return AlertDto(**{k: r[k] for k in COLS.split(', ')})


async def _unread(tx: Queryable) -> int:
    rows = await tx.query('SELECT count(*)::int AS n FROM alerts WHERE read_at IS NULL')
    return rows[0]['n']


async def list_alerts(deps: Deps, ctx: Ctx) -> AlertsRes:
    """The newest 50, plus the unread count over all alerts."""
    async with deps.as_user(ctx) as tx:
        unread = await _unread(tx)
        rows = await tx.query(f'SELECT {COLS} FROM alerts ORDER BY sent_at DESC, id LIMIT 50')
        return AlertsRes(unread_count=unread, items=[_to_dto(r) for r in rows])


async def mark_read(deps: Deps, ctx: Ctx, id: str) -> AlertReadRes:
    """Marking read twice keeps the first time."""
    async with deps.as_user(ctx) as tx:
        rows = await tx.query(
            f'UPDATE alerts SET read_at = COALESCE(read_at, now()) WHERE id = $1 RETURNING {COLS}', [id]
        )
        if not rows:
            raise Errors.not_found('Alert')
        return AlertReadRes(alert=_to_dto(rows[0]), unread_count=await _unread(tx))
