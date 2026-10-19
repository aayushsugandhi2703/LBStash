"""Public routes (through the gateway) and `/internal/*` routes (other services only). Routes without a user dependency work without a user on the token."""

from typing import Annotated, Any

import bt.contracts as C
from bt.common import COOKIES, Errors
from bt.kit import DepsDep, IdParam, OptionalCtx, ServiceClaims, UserCtx, id_param
from fastapi import APIRouter, Depends, FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse

from . import account, factors, passkeys, signin
from .audit import list_audit, record_audit
from .client_info import client_info
from .cookies import Tokens, cleared_cookies, parse_cookies, session_cookies
from .mailer import Mailer
from .sessions import check_session, current_sid, list_sessions, require_sid, revoke_family, revoke_others
from .svc import Svc, create_svc
from .users import assert_setup_complete, load_user

Id = Annotated[IdParam, Depends(id_param)]


def _set_cookies(response: Response, values: list[str]) -> None:
    for v in values:
        response.headers.append('set-cookie', v)


def make_routes(mailer: Mailer | None = None):
    """`register(app, deps)`, with a mailer that replaces the configured one (tests)."""

    def register(app: FastAPI, deps: Any) -> None:
        svc: Svc = create_svc(deps, mailer)
        router = APIRouter()

        def issue(response: Response, tokens: Tokens) -> None:
            _set_cookies(response, session_cookies(deps.env, tokens))

        def clear(response: Response) -> None:
            _set_cookies(response, cleared_cookies(deps.env))

        @router.post('/auth/register', response_model=C.RegisterRes, status_code=201)
        async def register_account(body: C.RegisterReq, request: Request, response: Response) -> C.AuthSessionRes:
            issued = await signin.register(svc, body.email, body.password, body.name, body.timezone, client_info(request))
            issue(response, issued.tokens)
            return issued.body

        @router.post('/auth/login', response_model=C.LoginRes)
        async def login(body: C.LoginReq, request: Request, response: Response) -> C.LoginRes:
            out = await signin.login(svc, body.email, body.password, client_info(request))
            if out.kind == 'setup':
                assert out.issued is not None
                issue(response, out.issued.tokens)
                return C.LoginRes(two_factor_token=None, methods=[], setup_required=True, setup=out.setup)
            return C.LoginRes(two_factor_token=out.two_factor_token, methods=list(out.methods), setup_required=False, setup=None)

        @router.post('/auth/2fa/verify', response_model=C.AuthSessionRes)
        async def verify_second_step(body: C.TwoFactorVerifyReq, request: Request, response: Response) -> C.AuthSessionRes:
            if body.code:
                proof = signin.SecondStep('totp', body.code)
            elif body.recovery_code:
                proof = signin.SecondStep('recovery', body.recovery_code)
            else:
                proof = signin.SecondStep('passkey', body.passkey)
            issued = await signin.verify_second_step(svc, body.two_factor_token, proof, client_info(request))
            issue(response, issued.tokens)
            return issued.body

        @router.post('/auth/passkey/login/options', response_model=C.PasskeyLoginOptionsRes)
        async def passkey_login_options(body: C.PasskeyLoginOptionsReq) -> C.PasskeyLoginOptionsRes:
            return await signin.passkey_login_options(svc, body.two_factor_token)

        @router.post('/auth/passkey/login/verify', response_model=C.AuthSessionRes)
        async def passkey_login_verify(body: C.PasskeyLoginVerifyReq, request: Request, response: Response) -> C.AuthSessionRes:
            issued = await signin.verify_second_step(svc, body.two_factor_token, signin.SecondStep('passkey', body.response), client_info(request))
            issue(response, issued.tokens)
            return issued.body

        @router.post('/auth/refresh', response_model=C.AuthSessionRes)
        async def refresh(request: Request, response: Response) -> Any:
            cookies = parse_cookies(request.headers.get('cookie'))
            token = cookies.get(COOKIES.refresh)
            issued = await signin.refresh(svc, token, cookies.get(COOKIES.csrf), client_info(request)) if token else None
            if issued is None:
                refused = JSONResponse(Errors.unauthorized('Signed out').to_json(), status_code=401)
                _set_cookies(refused, cleared_cookies(deps.env))
                return refused
            issue(response, issued.tokens)
            return issued.body

        @router.post('/auth/logout', response_model=C.Ok)
        async def logout(request: Request, response: Response, ctx: OptionalCtx) -> C.Ok:
            await signin.logout(
                svc, refresh_token=parse_cookies(request.headers.get('cookie')).get(COOKIES.refresh),
                access_sid=current_sid(svc, request, ctx.user_id) if ctx else None,
                user_id=ctx.user_id if ctx else None, ip=client_info(request).ip,
            )  # fmt: skip
            clear(response)
            return C.Ok(ok=True)

        # reset by recovery code

        @router.post('/auth/reset/verify', response_model=C.ResetVerifyRes)
        async def reset_verify(body: C.ResetVerifyReq, request: Request) -> C.ResetVerifyRes:
            return await account.reset_verify(svc, body.email, body.recovery_code, client_info(request))

        @router.post('/auth/reset/complete', response_model=C.Ok)
        async def reset_complete(body: C.ResetCompleteReq, request: Request) -> C.Ok:
            await account.reset_complete(svc, body.reset_token, body.new_password, client_info(request))
            return C.Ok(ok=True)

        # second factors (allowed while setup-limited)

        @router.post('/auth/2fa/enable', response_model=C.TwoFactorEnableStartRes)
        async def totp_enable(body: C.TwoFactorEnableStartReq, request: Request, ctx: UserCtx) -> C.TwoFactorEnableStartRes:
            return await factors.start_totp_enable(svc, ctx.user_id, body.current_code, client_info(request).ip)

        @router.post('/auth/2fa/enable/confirm', response_model=C.TwoFactorEnableConfirmRes)
        async def totp_confirm(body: C.TwoFactorEnableConfirmReq, request: Request, ctx: UserCtx) -> C.TwoFactorEnableConfirmRes:
            return await factors.confirm_totp_enable(svc, ctx.user_id, body.code, client_info(request).ip)

        @router.post('/auth/recovery-codes', response_model=C.RecoveryCodesRes)
        async def recovery_codes(body: C.RecoveryCodesReq, request: Request, ctx: UserCtx) -> C.RecoveryCodesRes:
            return await factors.regenerate_recovery_codes(svc, ctx.user_id, body.code, client_info(request).ip)

        @router.get('/auth/factors', response_model=C.FactorsRes)
        async def factors_of(ctx: UserCtx) -> C.FactorsRes:
            return await factors.factors_of(svc, ctx.user_id)

        @router.post('/auth/passkey/register/options', response_model=C.PasskeyRegisterOptionsRes)
        async def passkey_register_options(ctx: UserCtx) -> C.PasskeyRegisterOptionsRes:
            return await passkeys.registration_options(svc, ctx.user_id)

        @router.post('/auth/passkey/register/verify', response_model=C.PasskeyRegisterVerifyRes, status_code=201)
        async def passkey_register_verify(body: C.PasskeyRegisterVerifyReq, request: Request, ctx: UserCtx) -> C.PasskeyRegisterVerifyRes:
            return await passkeys.registration_verify(svc, ctx.user_id, body.response, body.label, client_info(request))

        @router.delete('/auth/passkey/{id}', response_model=C.Ok)
        async def passkey_remove(p: Id, request: Request, ctx: UserCtx) -> C.Ok:
            await passkeys.remove_passkey(svc, ctx.user_id, p.id, client_info(request).ip)
            return C.Ok(ok=True)

        @router.post('/auth/password', response_model=C.PasswordChangeRes)
        async def change_password(body: C.PasswordChangeReq, request: Request, ctx: UserCtx) -> C.PasswordChangeRes:
            return await account.change_password(
                svc, ctx, current_sid(svc, request, ctx.user_id), body.current_password, body.new_password, body.code,
                client_info(request).ip,
            )  # fmt: skip

        # sessions and audit

        @router.get('/sessions', response_model=C.SessionsRes)
        async def sessions(request: Request, ctx: UserCtx, deps: DepsDep) -> C.SessionsRes:
            sid = current_sid(svc, request, ctx.user_id)
            async with deps.as_user(ctx) as tx:
                assert_setup_complete(await load_user(tx, ctx.user_id))
                return C.SessionsRes(sessions=await list_sessions(tx, ctx.user_id, sid))

        @router.delete('/sessions/{id}', response_model=C.Ok)
        async def revoke_session(p: Id, request: Request, response: Response, ctx: UserCtx, deps: DepsDep) -> C.Ok:
            sid = current_sid(svc, request, ctx.user_id)
            async with deps.as_user(ctx) as tx:
                assert_setup_complete(await load_user(tx, ctx.user_id))
                if await tx.maybe_one('SELECT 1 FROM sessions WHERE id = $1 AND user_id = $2', [p.id, ctx.user_id]) is None:
                    raise Errors.not_found('Session')
                await revoke_family(tx, p.id, 'revoked_by_user')
                await record_audit(tx, ctx.user_id, 'session.revoked', ip=client_info(request).ip, meta={'current': p.id == sid})
            if p.id == sid:
                clear(response)
            return C.Ok(ok=True)

        @router.delete('/sessions', response_model=C.RevokeSessionsRes)
        async def revoke_other_sessions(request: Request, ctx: UserCtx, deps: DepsDep) -> C.RevokeSessionsRes:
            sid = require_sid(current_sid(svc, request, ctx.user_id))
            async with deps.as_user(ctx) as tx:
                assert_setup_complete(await load_user(tx, ctx.user_id))
                revoked = await revoke_others(tx, ctx.user_id, sid, 'revoked_by_user')
                await record_audit(tx, ctx.user_id, 'sessions.revoked_others', ip=client_info(request).ip, meta={'revoked': revoked})
                return C.RevokeSessionsRes(revoked=revoked)

        @router.get('/audit', response_model=C.AuditRes)
        async def audit(query: Annotated[C.AuditQuery, Query()], ctx: UserCtx, deps: DepsDep) -> C.AuditRes:
            async with deps.as_user(ctx) as tx:
                assert_setup_complete(await load_user(tx, ctx.user_id))
                return C.AuditRes(entries=await list_audit(tx, ctx.user_id, query.limit))

        @router.patch('/me', response_model=C.UpdateMeRes)
        async def update_me(body: C.UpdateMeReq, request: Request, ctx: UserCtx) -> C.UpdateMeRes:
            return await account.update_name(svc, ctx, body.name, client_info(request).ip)

        @router.post('/me/email', response_model=C.ChangeEmailRes)
        async def change_email(body: C.ChangeEmailReq, request: Request, ctx: UserCtx) -> C.ChangeEmailRes:
            return await account.request_email_change(svc, ctx, body.new_email, body.code, client_info(request).ip)

        @router.post('/me/email/confirm', response_model=C.ConfirmEmailRes)
        async def confirm_email(body: C.ConfirmEmailReq, request: Request, ctx: UserCtx) -> C.ConfirmEmailRes:
            return await account.confirm_email_change(svc, ctx, body, client_info(request).ip)

        @router.post('/account/export', response_model=C.ExportRes)
        async def export_account(body: C.ExportReq, request: Request, ctx: UserCtx) -> C.ExportRes:
            return await account.export_account(svc, ctx, body.code, client_info(request).ip)

        @router.delete('/account', response_model=C.DeleteAccountRes)
        async def delete_account(body: C.DeleteAccountReq, request: Request, ctx: UserCtx) -> C.DeleteAccountRes:
            return await account.schedule_deletion(svc, ctx, body.code, client_info(request).ip)

        @router.post('/account/restore', response_model=C.RestoreAccountRes)
        async def restore_account(request: Request, ctx: UserCtx) -> C.RestoreAccountRes:
            return await account.restore_account(svc, ctx, client_info(request).ip)

        # internal

        @router.post('/internal/totp/verify', response_model=C.VerifyTotpRes)
        async def verify_totp(body: C.VerifyTotpReq, ctx: UserCtx) -> C.VerifyTotpRes:
            await account.verify_totp_for_service(svc, ctx, body.code)
            return C.VerifyTotpRes(ok=True)

        @router.get('/internal/me', response_model=C.MeInternalRes)
        async def internal_me(ctx: UserCtx) -> C.MeInternalRes:
            return await account.me(svc, ctx)

        @router.post('/internal/sessions/check', response_model=C.SessionCheckRes)
        async def sessions_check(body: C.SessionCheckReq, _claims: ServiceClaims, deps: DepsDep) -> C.SessionCheckRes:
            async with deps.as_system() as tx:
                return await check_session(tx, body.sid)

        app.include_router(router)

    return register


register = make_routes()
