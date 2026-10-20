import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from lbstash.common import Errors
from lbstash.contracts import (
    CreateDeviceReq,
    DeviceDto,
    DevicesRes,
    DeviceTokenRes,
    DismissUnparsedRes,
    ExportPart,
    IngestBody,
    PatchDeviceReq,
    ResolveUnparsedReq,
    ResolveUnparsedRes,
    RevokeDeviceReq,
    RevokeDeviceRes,
    TestDeviceRes,
    UnparsedCountRes,
    UnparsedRes,
    dump,
    validation_details,
)
from lbstash.kit import Deps, DepsDep, IdParam, RequestId, ServiceClaims, UserCtx, id_param
from pydantic import ValidationError

from .devices import create_or_rotate, list_devices, patch_device, revoke_device, test_device
from .ingest import IngestService
from .maintenance import export_part
from .unparsed import dismiss_unparsed, list_unparsed, resolve_unparsed, unparsed_count

# Plenty for one SMS (2000 characters max); keeps the unauthenticated surface small. The kit applies one limit per service.
INGEST_BODY_LIMIT = 8 * 1024

_BEARER = re.compile(r'Bearer\s+(\S+)', re.IGNORECASE)


def _bearer_of(header: str | None) -> str | None:
    m = _BEARER.fullmatch(header or '')
    return m[1] if m else None


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else 'unknown'


def register(app: FastAPI, deps: Deps) -> None:
    ingest = IngestService(deps)
    r = APIRouter()

    # The gateway forwards with a service token (no user); the bearer ingest token is checked here, then the raw body validated (README 4.6).
    @r.post('/ingest/message')
    async def ingest_message(request: Request, _claims: ServiceClaims, rid: RequestId) -> JSONResponse:
        raw = await request.body()

        def parse_body() -> IngestBody:
            try:
                data: Any = json.loads(raw) if raw.strip() else {}
            except ValueError:
                deps.log.info('ingest body rejected', why='not valid JSON', bytes=len(raw), rid=rid)
                raise Errors.bad_request('Body is not valid JSON') from None
            try:
                return IngestBody.model_validate({} if data is None else data)
            except ValidationError as e:
                # what is wrong, never what was sent: the rule messages, which keys arrived and how long the text is
                shape = {f'{k}_chars': len(str(v)) for k, v in data.items()} if isinstance(data, dict) else type(data).__name__  # `_chars`: the logger would redact a key called text
                deps.log.info('ingest body rejected', fields=validation_details(e), sent=shape, rid=rid)
                raise Errors.validation(validation_details(e)) from None

        out = await ingest.handle(
            bearer=_bearer_of(request.headers.get('authorization')), ip=_client_ip(request), request_id=rid, parse_body=parse_body
        )
        return JSONResponse(dump(out.body), status_code=out.status)

    @r.get('/devices', response_model=DevicesRes)
    async def get_devices(ctx: UserCtx, d: DepsDep) -> DevicesRes:
        return DevicesRes(devices=await list_devices(d, ctx))

    @r.post('/devices', response_model=DeviceTokenRes, status_code=201)
    async def post_devices(ctx: UserCtx, d: DepsDep, request: Request, body: CreateDeviceReq | None = None) -> DeviceTokenRes:
        device, token, rotated = await create_or_rotate(d, ctx, body or CreateDeviceReq(), _client_ip(request))
        return DeviceTokenRes(device=device, token=token, rotated=rotated)

    @r.patch('/devices/{id}', response_model=DeviceDto)
    async def patch_devices(p: Annotated[IdParam, Depends(id_param)], body: PatchDeviceReq, ctx: UserCtx, d: DepsDep) -> DeviceDto:
        return await patch_device(d, ctx, p.id, body)

    @r.delete('/devices/{id}', response_model=RevokeDeviceRes)
    async def delete_devices(
        p: Annotated[IdParam, Depends(id_param)],
        ctx: UserCtx,
        d: DepsDep,
        request: Request,
        x_totp_code: Annotated[str | None, Header()] = None,
        body: RevokeDeviceReq | None = None,
    ) -> RevokeDeviceRes:
        code = body.code if body is not None and body.code is not None else x_totp_code
        return RevokeDeviceRes(device=await revoke_device(d, ctx, p.id, code, _client_ip(request)))

    @r.post('/devices/test', response_model=TestDeviceRes)
    async def post_devices_test(ctx: UserCtx, d: DepsDep) -> TestDeviceRes:
        device, amount_minor, type_ = await test_device(d, ctx)
        return TestDeviceRes(ok=True, device=device, amount_minor=amount_minor, type=type_)

    @r.get('/unparsed', response_model=UnparsedRes)
    async def get_unparsed(ctx: UserCtx, d: DepsDep) -> UnparsedRes:
        return await list_unparsed(d, ctx)

    @r.post('/unparsed/{id}/resolve', response_model=ResolveUnparsedRes)
    async def post_unparsed_resolve(
        p: Annotated[IdParam, Depends(id_param)], body: ResolveUnparsedReq, ctx: UserCtx, d: DepsDep
    ) -> ResolveUnparsedRes:
        return await resolve_unparsed(d, ctx, p.id, body)

    @r.post('/unparsed/{id}/dismiss', response_model=DismissUnparsedRes)
    async def post_unparsed_dismiss(p: Annotated[IdParam, Depends(id_param)], ctx: UserCtx, d: DepsDep) -> DismissUnparsedRes:
        return await dismiss_unparsed(d, ctx, p.id)

    @r.get('/internal/unparsed/count', response_model=UnparsedCountRes)
    async def get_unparsed_count(ctx: UserCtx, d: DepsDep) -> UnparsedCountRes:
        return await unparsed_count(d, ctx)

    @r.get('/internal/export', response_model=ExportPart)
    async def get_export(ctx: UserCtx, d: DepsDep) -> ExportPart:
        return await export_part(d, ctx)

    app.include_router(r)
