"""Auth service contracts: users, sessions, factors (TOTP, passkeys, recovery codes), audit log, export and deletion."""

import re
from typing import Annotated, Any, Final, Literal

from pydantic import AfterValidator, Field, StringConstraints, model_validator
from pydantic_core import PydanticCustomError

from .base import (
    Bool,
    CoerceInt,
    Int,
    IsoDateTime,
    Model,
    Opt,
    TimeStr,
    TzName,
    Uuid,
    refine_fail,
    regex_str,
)
from .common import ExportPart


class UserDto(Model):
    id: Uuid
    email: str
    name: str | None
    timezone: TzName
    pending_email: str | None
    delete_after: TimeStr | None
    # ISO time the account was created ("member since").
    created_at: Opt[TimeStr] = None


_SixDigitsPlain = regex_str(r'\d{6}', r'Invalid string: must match pattern /^\d{6}$/')


# Internal: any service asks auth to check an authenticator code for the token's user (once per time step).
class VerifyTotpReq(Model):
    code: _SixDigitsPlain


class VerifyTotpRes(Model):
    ok: Literal[True]


# Internal: who is this user (name, email, zone).
class MeInternalRes(Model):
    user: UserDto


class SessionCheckReq(Model):
    """Internal: the gateway asks auth whether a browser session is still alive, since the access token stays valid up to 15 minutes after "sign out everywhere else"."""

    sid: Uuid
    # The caller's address, so auth can apply the user's address list. Missing = unknown (refused when a list exists).
    ip: Opt[str] = None


class SessionCheckRes(Model):
    valid: Bool
    # True until mandatory setup is done (authenticator and recovery codes); the gateway lets only `/auth/*`, `/me` and logout through.
    limited: Bool = False


# ── Public auth API (browser <-> gateway <-> auth). Cookies: see lbstash_auth/cookies.py.
TotpCode = regex_str(r'\d{6}', 'Enter the 6-digit code')
RecoveryCodeInput = Annotated[str, StringConstraints(strip_whitespace=True, min_length=9, max_length=40)]

# Practical e-mail address pattern (not full RFC 5322).
_EMAIL_RE: Final = re.compile(
    r"(?:[A-Za-z0-9_'+\-]+\.)*[A-Za-z0-9_'+\-]*[A-Za-z0-9_+-]@(?:[A-Za-z0-9][A-Za-z0-9\-]*\.)+[A-Za-z]{2,}"
)


def _email_check(v: str) -> str:
    if not _EMAIL_RE.fullmatch(v):
        raise PydanticCustomError('email', 'Invalid email address')
    return v


# trim, lower-case, at most 254 characters, then must be an e-mail address.
EmailInput = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, max_length=254),
    AfterValidator(_email_check),
]
PasswordInput = Annotated[str, StringConstraints(min_length=1, max_length=256)]
# A WebAuthn JSON payload from @simplewebauthn/browser; the server validates it.
WebAuthnJson = dict[str, Any]

AuthMethod = Literal['totp', 'passkey', 'recovery']


class SetupState(Model):
    """Mandatory setup: authenticator enabled AND a recovery set made. Until `complete`, the session is setup-limited."""

    totp_enabled: Bool
    recovery_codes: Bool
    complete: Bool


RECOVERY_CODE_COUNT: Final = 10


class AuthSessionRes(Model):
    """Answer of every call that starts or renews a browser session (register, 2fa/verify, passkey login, refresh)."""

    user: UserDto
    setup: SetupState
    recovery_codes_left: Int
    # A recovery code was used to sign in: ask the user to make a fresh set.
    recovery_code_used: Bool
    # Signing in cancelled a scheduled account deletion.
    deletion_cancelled: Bool


class RegisterReq(Model):
    email: EmailInput
    password: PasswordInput
    name: Opt[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]] = None
    timezone: Opt[TzName] = None


# Sets cookies (setup-limited session).
RegisterRes = AuthSessionRes


class LoginReq(Model):
    email: EmailInput
    password: PasswordInput


class LoginRes(Model):
    """Step 1. No session yet unless `setup_required` (the account never finished setup: then cookies are set for a
    setup-limited session and `two_factor_token` is None)."""

    two_factor_token: str | None
    methods: list[AuthMethod]
    setup_required: Bool
    setup: SetupState | None


TwoFactorToken = Annotated[str, StringConstraints(min_length=10, max_length=200)]


class TwoFactorVerifyReq(Model):
    """Step 2: exactly one of code, recoveryCode, passkey. A wrong code is 401 with `attemptsLeft`; a lockout is 423 with `retryAfterSeconds`."""

    two_factor_token: TwoFactorToken
    code: Opt[TotpCode] = None
    recovery_code: Opt[RecoveryCodeInput] = None
    passkey: Opt[WebAuthnJson] = None

    @model_validator(mode='after')
    def _exactly_one(self) -> 'TwoFactorVerifyReq':
        if sum(x is not None for x in (self.code, self.recovery_code, self.passkey)) != 1:
            refine_fail('Send exactly one of code, recoveryCode, passkey')
        return self


class TwoFactorEnableStartReq(Model):
    current_code: Opt[TotpCode] = None


class TwoFactorEnableStartRes(Model):
    """`secret` is the base32 key to type in; `otpauth_uri` is what the QR code encodes."""

    secret: str
    otpauth_uri: str


class TwoFactorEnableConfirmReq(Model):
    code: TotpCode


class TwoFactorEnableConfirmRes(Model):
    setup: SetupState


class RecoveryCodesReq(Model):
    """`code` is required once setup is complete; during first-time setup it is not needed. Codes are shown once."""

    code: Opt[TotpCode] = None


class RecoveryCodesRes(Model):
    codes: list[str]
    remaining: Int
    setup: SetupState


class PasskeyDto(Model):
    id: Uuid
    label: str
    created_at: TimeStr
    last_used_at: TimeStr | None


class TotpFactor(Model):
    enabled: Bool
    since: TimeStr | None


class RecoveryCodesFactor(Model):
    remaining: Int
    total: Int


class FactorsRes(Model):
    totp: TotpFactor
    passkeys: list[PasskeyDto]
    recovery_codes: RecoveryCodesFactor
    password_changed_at: TimeStr
    setup: SetupState


class PasswordChangeReq(Model):
    current_password: PasswordInput
    new_password: PasswordInput
    code: TotpCode


class PasswordChangeRes(Model):
    ok: Literal[True]
    signed_out_others: Int


class AllowedIpsReq(Model):
    """`PUT /auth/allowed-ips`: the whole new list (empty = any address), confirmed with a fresh authenticator code."""

    ips: Annotated[list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]], Field(max_length=20)]
    code: TotpCode


class AllowedIpsRes(Model):
    ips: list[str]
    # The address this request came from, to offer "add my address" and to refuse a list that would lock the user out.
    your_ip: str | None


class PasskeyRegisterOptionsRes(Model):
    options: WebAuthnJson


class PasskeyRegisterVerifyReq(Model):
    response: WebAuthnJson
    label: Opt[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]] = None


class PasskeyRegisterVerifyRes(Model):
    passkey: PasskeyDto
    setup: SetupState


class PasskeyLoginOptionsReq(Model):
    two_factor_token: TwoFactorToken


class PasskeyLoginOptionsRes(Model):
    options: WebAuthnJson


class PasskeyLoginVerifyReq(Model):
    """Same effect as TwoFactorVerifyReq with `passkey`. Sets cookies, answers AuthSessionRes."""

    two_factor_token: TwoFactorToken
    response: WebAuthnJson


class SessionDto(Model):
    id: Uuid
    device: str
    ip: str | None
    created_at: TimeStr
    last_active_at: TimeStr
    current: Bool


class SessionsRes(Model):
    sessions: list[SessionDto]


class RevokeSessionsRes(Model):
    revoked: Int


class AuditQuery(Model):
    limit: CoerceInt = Field(default=50, ge=1, le=200)


class AuditEntryDto(Model):
    id: Int
    at: TimeStr
    action: str
    ip: str | None
    device_id: Uuid | None
    meta: dict[str, Any] | None


class AuditRes(Model):
    entries: list[AuditEntryDto]


class UpdateMeReq(Model):
    """Empty string clears the name."""

    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]


class UpdateMeRes(Model):
    user: UserDto


class ChangeEmailReq(Model):
    new_email: EmailInput
    code: TotpCode


class ChangeEmailRes(Model):
    pending_email: str


class ConfirmEmailReq(Model):
    """The link in the mail opens a web page that posts the token here (signed in)."""

    token: Annotated[str, StringConstraints(min_length=10, max_length=200)]


class ConfirmEmailRes(Model):
    user: UserDto


class ExportReq(Model):
    code: TotpCode


class ExportRes(Model):
    """`parts[0]` is auth's own part; then transactions, planning, recurring, ingest, telegram. Secrets are never included."""

    exported_at: IsoDateTime
    filename: str
    entries: Int
    parts: list[ExportPart]


class DeleteAccountReq(Model):
    confirm: Literal['DELETE']
    code: TotpCode


class DeleteAccountRes(Model):
    delete_after: IsoDateTime


class RestoreAccountRes(Model):
    user: UserDto


class ResetVerifyReq(Model):
    """Reset by recovery code, two steps. Step 1 checks email + code without using the code; step 2 sets the password."""

    email: EmailInput
    recovery_code: RecoveryCodeInput


class ResetVerifyRes(Model):
    reset_token: str


class ResetCompleteReq(Model):
    reset_token: Annotated[str, StringConstraints(min_length=10, max_length=200)]
    new_password: PasswordInput


# Audit actions auth writes itself (other services send their own through the `audit.record` event).
AUDIT_ACTIONS: Final = (
    'register', 'login.ok', 'login.failed', 'login.locked', '2fa.ok', '2fa.failed', '2fa.enabled', '2fa.replaced',
    'password.changed', 'password.reset', 'passkey.added', 'passkey.removed', 'recovery_codes.regenerated',
    'recovery_code.used', 'session.revoked', 'sessions.revoked_others', 'logout', 'email.change_requested',
    'email.changed', 'profile.updated', 'export', 'delete.scheduled', 'delete.restored',
)
