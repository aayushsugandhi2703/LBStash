"""Routes the gateway answers itself by composing other services: `GET /me`, `GET|PATCH /settings`."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from bt.common import Ctx, month_key
from bt.contracts import (
    LedgerSettingsPatch,
    MeDto,
    PlanningSettingsPatch,
    SettingsDto,
    SettingsPatch,
    TelegramSettingsPatch,
    dump,
    patch_keys,
)
from bt.kit import Deps

from .env import Env

# Badge counts are optional: a slow or failing service must not take the header down.
OPTIONAL_TIMEOUT_S = 2.5


async def _optional_count[T](deps: Deps[Env], name: str, call: Callable[[], Awaitable[T]], pick: Callable[[T], int]) -> int:
    try:
        async with asyncio.timeout(OPTIONAL_TIMEOUT_S):
            return pick(await call())
    except Exception:  # noqa: BLE001  (a timeout, a refused connection and an error answer all mean "count 0")
        deps.log.warning('optional dependency failed; counting 0', dep=name)
        return 0


async def me(deps: Deps[Env], ctx: Ctx) -> dict[str, Any]:
    """`GET /me`: the user from auth, plus the three counts the header and Account menu show."""
    user = (await deps.clients.auth.me(ctx)).user
    as_ = Ctx(user_id=ctx.user_id, tz=user.timezone, request_id=ctx.request_id)
    month = month_key(datetime.now(UTC), user.timezone)
    c = deps.clients
    alerts, needs_look, untagged = await asyncio.gather(
        _optional_count(deps, 'planning', lambda: c.planning.alerts(as_), lambda r: r.unread_count),
        _optional_count(deps, 'ingest', lambda: c.ingest.unparsed_count(as_), lambda r: r.open),
        _optional_count(deps, 'ledger', lambda: c.ledger.month_summary(as_, month), lambda r: r.untagged_count),
    )
    return dump(
        MeDto(
            id=user.id, email=user.email, name=user.name, timezone=user.timezone, pending_email=user.pending_email,
            delete_after=user.delete_after, alert_badge_count=alerts, needs_look_count=needs_look, untagged_count=untagged,
        )
    )  # fmt: skip


# Fields each owner takes, read from its own Patch model, so a new setting needs no change here.
_OWNED = {
    'ledger': frozenset(patch_keys(LedgerSettingsPatch)),
    'planning': frozenset(patch_keys(PlanningSettingsPatch)),
    'telegram': frozenset(patch_keys(TelegramSettingsPatch)),
}


def _only(keys: frozenset[str], patch: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in patch.items() if k in keys}


async def settings(deps: Deps[Env], ctx: Ctx, patch: SettingsPatch | None = None) -> dict[str, Any]:
    """`GET|PATCH /settings`: each owner reads or updates its own fields; answers are merged. If one owner fails, the request fails; re-sending the PATCH is safe."""
    given = dump(patch) if patch is not None else {}
    ledger_patch, planning_patch, telegram_patch = (_only(_OWNED[n], given) for n in ('ledger', 'planning', 'telegram'))
    c = deps.clients
    a, b, t = await asyncio.gather(
        c.ledger.patch_settings(ctx, ledger_patch) if ledger_patch else c.ledger.settings(ctx),
        c.planning.patch_settings(ctx, planning_patch) if planning_patch else c.planning.settings(ctx),
        c.telegram.patch_settings(ctx, telegram_patch) if telegram_patch else c.telegram.settings(ctx),
    )
    return dump(SettingsDto.model_validate({**dump(a), **dump(b), **dump(t), 'currency': 'INR'}))
