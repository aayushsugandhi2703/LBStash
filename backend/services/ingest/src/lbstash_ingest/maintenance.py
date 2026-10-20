from typing import Any

from lbstash.common import Ctx
from lbstash.contracts import ExportPart, dump
from lbstash.contracts.base import iso_ms
from lbstash.db import camel
from lbstash.kit import Deps

from .devices import DEVICE_COLS, DeviceRow, to_dto

# Nonces older than this are useless (the replay window is 5 minutes).
EVENT_RETENTION_DAYS = 30


async def purge_user(deps: Deps, user_id: str) -> None:
    """`account.deleted`: delete all of the user's rows. Safe to repeat."""
    async with deps.as_system() as tx:
        await tx.execute('DELETE FROM unparsed_messages WHERE user_id = $1', [user_id])
        await tx.execute('DELETE FROM ingest_events WHERE user_id = $1', [user_id])
        await tx.execute('DELETE FROM devices WHERE user_id = $1', [user_id])


async def sweep(deps: Deps) -> dict[str, int]:
    """Nightly: purge old nonces, expire open unparsed messages past 30 days, delete finished ones."""
    async with deps.as_system() as tx:
        events = await tx.execute('DELETE FROM ingest_events WHERE received_at < now() - make_interval(days => $1)', [EVENT_RETENTION_DAYS])
        expired = await tx.execute("UPDATE unparsed_messages SET status = 'expired' WHERE status = 'open' AND expires_at <= now()")
        deleted = await tx.execute("DELETE FROM unparsed_messages WHERE status IN ('expired', 'resolved', 'dismissed')")
    return {'events': events, 'expired': expired, 'deleted': deleted}


def _json_row(row: dict[str, Any]) -> dict[str, Any]:
    """camelCase keys, ISO-millisecond timestamps."""
    return {k: iso_ms(v) if hasattr(v, 'astimezone') else v for k, v in camel(row).items()}


async def export_part(deps: Deps, ctx: Ctx) -> ExportPart:
    """Device metadata and counts only: no token hashes or hints, no message text."""
    async with deps.as_user(ctx) as tx:
        device_rows = await tx.many(f'SELECT {DEVICE_COLS} FROM devices ORDER BY created_at')
        events = await tx.many(
            'SELECT outcome, count(*)::int AS count, min(received_at) AS first_at, max(received_at) AS last_at FROM ingest_events GROUP BY outcome ORDER BY outcome'
        )
        unparsed = await tx.many('SELECT id, device_id, reason, status, received_at, expires_at FROM unparsed_messages ORDER BY received_at')
    devices = []
    for r in device_rows:
        d = dump(to_dto(DeviceRow.from_row(r)))
        d.pop('tokenHint')
        devices.append(d)
    return ExportPart(
        service='ingest',
        tables={'devices': devices, 'ingest_events': [_json_row(e) for e in events], 'unparsed_messages': [_json_row(u) for u in unparsed]},
    )
