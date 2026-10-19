"""Planning settings: alert level and pace warning."""

from dataclasses import dataclass
from typing import Any

from bt.common import Clock, Ctx, month_key
from bt.contracts import PlanningSettings
from bt.db import Queryable
from bt.kit import Deps

from .jobs import enqueue_evaluate


@dataclass(frozen=True, slots=True)
class SettingsRow:
    alert_level: int  # 70, 80 or 90
    warn_on_pace: bool
    tz: str | None


def _to_row(r: dict[str, Any]) -> SettingsRow:
    return SettingsRow(alert_level=r['alert_level'], warn_on_pace=r['warn_on_pace'], tz=r['tz'])


async def load_settings(tx: Queryable, user_id: str, tz: str | None = None) -> SettingsRow:
    """The user's settings row, created with defaults on first use. Saves the request's zone for event-driven work."""
    await tx.query(
        'INSERT INTO planning_settings (user_id, tz) VALUES ($1, $2) ON CONFLICT (user_id) DO NOTHING', [user_id, tz]
    )
    if tz:
        await tx.query(
            'UPDATE planning_settings SET tz = $2, updated_at = now() WHERE user_id = $1 AND tz IS DISTINCT FROM $2',
            [user_id, tz],
        )
    rows = await tx.query('SELECT alert_level, warn_on_pace, tz FROM planning_settings WHERE user_id = $1', [user_id])
    return _to_row(rows[0])


async def read_settings(tx: Queryable, user_id: str) -> SettingsRow | None:
    """The settings row, or None. Never creates one (for event handlers)."""
    rows = await tx.query('SELECT alert_level, warn_on_pace, tz FROM planning_settings WHERE user_id = $1', [user_id])
    return _to_row(rows[0]) if rows else None


def _view(s: SettingsRow) -> PlanningSettings:
    return PlanningSettings(alert_level=s.alert_level, warn_on_pace=s.warn_on_pace)


async def get_settings(deps: Deps, ctx: Ctx) -> PlanningSettings:
    async with deps.as_user(ctx) as tx:
        return _view(await load_settings(tx, ctx.user_id, ctx.tz))


async def patch_settings(deps: Deps, ctx: Ctx, patch: Any, now: Clock) -> PlanningSettings:
    """`patch` is a `PlanningSettingsPatch`; absent fields stay unchanged."""
    async with deps.as_user(ctx) as tx:
        before = await load_settings(tx, ctx.user_id, ctx.tz)
        if patch.alert_level is None and patch.warn_on_pace is None:
            return _view(before)
        rows = await tx.query(
            """UPDATE planning_settings SET alert_level = COALESCE($2, alert_level), warn_on_pace = COALESCE($3, warn_on_pace), updated_at = now()
               WHERE user_id = $1 RETURNING alert_level, warn_on_pace, tz""",
            [ctx.user_id, patch.alert_level, patch.warn_on_pace],
        )
        after = _to_row(rows[0])
        # a lower level can put a limit over it now, so re-evaluate (a higher level never un-sends)
        if after.alert_level != before.alert_level:
            period = month_key(now(), ctx.tz)
            for b in await tx.many('SELECT category_id FROM budgets WHERE active'):
                await enqueue_evaluate(deps, tx, ctx.user_id, b['category_id'], period)
        return _view(after)
