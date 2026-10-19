"""Public routes (reached through the gateway) and `/internal/*` routes (other services only)."""

from collections.abc import Callable
from typing import Annotated

from bt.contracts import (
    BotTokenReq,
    BotTokenRes,
    ExportPart,
    Ok,
    PairingRes,
    TelegramLinkStatus,
    TelegramSettings,
    TelegramSettingsPatch,
    TelegramUpdate,
)
from bt.kit import Deps, ServiceClaims, UserCtx
from fastapi import APIRouter, FastAPI, Header, Path, Request
from pydantic import ValidationError

from .link import (
    create_pairing,
    end_session_from_web,
    export_part,
    link_status,
    patch_settings,
    read_settings,
    save_bot_token,
    unlink,
)
from .runtime import RuntimeOptions, shared_runtime
from .webhook import authenticate_webhook, handle_update


def make_register(opts: RuntimeOptions | None = None) -> Callable[[FastAPI, Deps], None]:
    """`opts` lets tests inject a fake Bot API and clock."""

    def register(app: FastAPI, deps: Deps) -> None:
        rt = shared_runtime(deps, opts)
        r = APIRouter()

        # Called by Telegram via the gateway. Path and header secrets must both match first; then always 200 (Telegram
        # retries errors, and we dedupe by update_id).
        @r.post('/telegram/webhook/{secret}', response_model=Ok)
        async def webhook(
            secret: Annotated[str, Path(min_length=16, max_length=128)],
            request: Request,
            _claims: ServiceClaims,
            x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
        ) -> Ok:
            ip = request.client.host if request.client else 'unknown'
            bot = await authenticate_webhook(rt, secret, x_telegram_bot_api_secret_token, ip)
            try:
                update = TelegramUpdate.model_validate(await request.json())
            except (ValueError, ValidationError):
                return Ok(ok=True)
            try:
                await handle_update(rt, bot, update)
            except Exception as e:  # noqa: BLE001  (Telegram retries on errors; a failed update is logged and dropped)
                # ids and codes only, never message text, tokens or payees
                deps.log.warning('update failed', uid=bot.user_id, update=update.update_id, err=getattr(e, 'code', None) or type(e).__name__)
            return Ok(ok=True)

        @r.post('/telegram/pairing', response_model=PairingRes, status_code=201)
        async def post_pairing(ctx: UserCtx) -> PairingRes:
            return await create_pairing(rt, ctx)

        @r.get('/telegram/link', response_model=TelegramLinkStatus)
        async def get_link(ctx: UserCtx) -> TelegramLinkStatus:
            return await link_status(rt, ctx)

        @r.delete('/telegram/link', response_model=Ok)
        async def delete_link(ctx: UserCtx) -> Ok:
            await unlink(rt, ctx.user_id)
            return Ok(ok=True)

        @r.delete('/telegram/session', response_model=Ok)
        async def delete_session(ctx: UserCtx) -> Ok:
            await end_session_from_web(rt, ctx)
            return Ok(ok=True)

        @r.post('/telegram/bot-token', response_model=BotTokenRes)
        async def post_bot_token(body: BotTokenReq, ctx: UserCtx) -> BotTokenRes:
            return await save_bot_token(rt, ctx, body.token)

        @r.get('/internal/settings', response_model=TelegramSettings)
        async def get_settings(ctx: UserCtx) -> TelegramSettings:
            return await read_settings(rt, ctx)

        @r.patch('/internal/settings', response_model=TelegramSettings)
        async def patch_settings_route(body: TelegramSettingsPatch, ctx: UserCtx) -> TelegramSettings:  # type: ignore[valid-type]
            return await patch_settings(rt, ctx, body)

        @r.get('/internal/export', response_model=ExportPart)
        async def get_export(ctx: UserCtx) -> ExportPart:
            return await export_part(rt, ctx)

        app.include_router(r)

    return register


register = make_register()
