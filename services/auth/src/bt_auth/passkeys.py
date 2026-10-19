"""Passkeys (WebAuthn): registration, removal, and the passkey as a sign-in second step. Option JSON is what `@simplewebauthn/browser` consumes."""

from typing import Any

from bt.common import Errors
from bt.contracts import (
    PasskeyDto,
    PasskeyLoginOptionsRes,
    PasskeyRegisterOptionsRes,
    PasskeyRegisterVerifyRes,
)
from bt.db import Row, Tx, jsonb
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json_dict
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    AuthenticatorTransport,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from .audit import record_audit
from .client_info import ClientInfo
from .env import rp_id, web_origin
from .limits import PASSKEY_CHALLENGE_MINUTES
from .svc import Svc
from .users import UserRow, load_user, setup_state

# EdDSA, ES256, RS256
ALGORITHMS = [
    COSEAlgorithmIdentifier.EDDSA,
    COSEAlgorithmIdentifier.ECDSA_SHA_256,
    COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
]
COLS = 'id, label, public_key, credential_id, counter, transports, created_at, last_used_at'
_KNOWN_TRANSPORTS = {t.value for t in AuthenticatorTransport}


def _dto(p: Row) -> PasskeyDto:
    return PasskeyDto(id=p['id'], label=p['label'] or 'Passkey', created_at=p['created_at'], last_used_at=p['last_used_at'])


def _descriptors(keys: list[Row]) -> list[PublicKeyCredentialDescriptor]:
    out = []
    for k in keys:
        transports = [AuthenticatorTransport(t) for t in (k['transports'] or []) if t in _KNOWN_TRANSPORTS]
        out.append(PublicKeyCredentialDescriptor(id=base64url_to_bytes(k['credential_id']), transports=transports or None))
    return out


async def passkeys_of(tx: Tx, user_id: str) -> list[Row]:
    return await tx.many(f"SELECT {COLS} FROM auth_factors WHERE user_id = $1 AND kind = 'passkey' ORDER BY created_at", [user_id])


async def passkey_count(tx: Tx, user_id: str) -> int:
    r = await tx.maybe_one("SELECT count(*) AS n FROM auth_factors WHERE user_id = $1 AND kind = 'passkey'", [user_id])
    return int(r['n']) if r else 0


async def registration_options(svc: Svc, user_id: str) -> PasskeyRegisterOptionsRes:
    """Options for navigator.credentials.create(). Allowed during first-time setup."""
    env = svc.deps.env
    async with svc.deps.as_user(user_id) as tx:
        user = await load_user(tx, user_id)
        existing = await passkeys_of(tx, user_id)
        options = generate_registration_options(
            rp_id=rp_id(env), rp_name=env.WEBAUTHN_RP_NAME,
            user_name=user.email, user_display_name=user.name or user.email.split('@')[0], user_id=user.id.encode(),
            exclude_credentials=_descriptors(existing),
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED, user_verification=UserVerificationRequirement.REQUIRED
            ),
            supported_pub_key_algs=ALGORITHMS,
        )  # fmt: skip
        body = options_to_json_dict(options)
        body['extensions'] = {'credProps': True}
        await tx.execute("DELETE FROM challenges WHERE user_id = $1 AND kind = 'passkey_register'", [user_id])
        await tx.execute(
            "INSERT INTO challenges (user_id, kind, webauthn_challenge, expires_at) "
            "VALUES ($1, 'passkey_register', $2, now() + make_interval(mins => $3))",
            [user_id, body['challenge'], PASSKEY_CHALLENGE_MINUTES],
        )
        return PasskeyRegisterOptionsRes(options=body)


async def registration_verify(
    svc: Svc, user_id: str, response: dict[str, Any], label: str | None, info: ClientInfo
) -> PasskeyRegisterVerifyRes:
    """Verify the browser's answer and store the public key."""
    env = svc.deps.env
    async with svc.deps.as_user(user_id) as tx:
        ch = await tx.maybe_one(
            "SELECT id, webauthn_challenge FROM challenges WHERE user_id = $1 AND kind = 'passkey_register' "
            'AND used_at IS NULL AND expires_at > now() ORDER BY created_at DESC LIMIT 1 FOR UPDATE',
            [user_id],
        )
        if ch is None:
            raise Errors.bad_request('Start adding the passkey again')
        try:
            verified = verify_registration_response(
                credential=response, expected_challenge=base64url_to_bytes(ch['webauthn_challenge']),
                expected_origin=web_origin(env), expected_rp_id=rp_id(env), require_user_verification=True,
                supported_pub_key_algs=ALGORITHMS,
            )  # fmt: skip
        except Exception:  # noqa: BLE001 - the library raises many types; the answer is the same
            raise Errors.unprocessable('That passkey could not be verified') from None
        credential_id = bytes_to_base64url(verified.credential_id)
        if await tx.maybe_one('SELECT 1 FROM auth_factors WHERE credential_id = $1', [credential_id]):
            raise Errors.conflict('That passkey is already added')
        transports = _transports(response)
        row = await tx.one(
            f"INSERT INTO auth_factors (user_id, kind, label, public_key, credential_id, counter, transports) "
            f"VALUES ($1, 'passkey', $2, $3, $4, $5, $6) RETURNING {COLS}",
            [user_id, label or f'Passkey on {info.device}', verified.credential_public_key, credential_id,
             verified.sign_count, jsonb(transports) if transports else None],
        )  # fmt: skip
        await tx.execute('UPDATE challenges SET used_at = now() WHERE id = $1', [ch['id']])
        await record_audit(tx, user_id, 'passkey.added', ip=info.ip)
        user = await load_user(tx, user_id)
        return PasskeyRegisterVerifyRes(passkey=_dto(row), setup=await setup_state(tx, user))


def _transports(response: dict[str, Any]) -> list[str]:
    inner = response.get('response')
    raw = inner.get('transports') if isinstance(inner, dict) else None
    return [t for t in raw if isinstance(t, str)] if isinstance(raw, list) else []


async def remove_passkey(svc: Svc, user_id: str, passkey_id: str, ip: str | None) -> None:
    async with svc.deps.as_user(user_id) as tx:
        n = await tx.execute("DELETE FROM auth_factors WHERE id = $1 AND user_id = $2 AND kind = 'passkey'", [passkey_id, user_id])
        if n == 0:
            raise Errors.not_found('Passkey')
        await record_audit(tx, user_id, 'passkey.removed', ip=ip)


async def login_options(svc: Svc, tx: Tx, challenge_id: str, user_id: str) -> PasskeyLoginOptionsRes:
    """Passkey sign-in options; the challenge is stored on the sign-in challenge row."""
    keys = await passkeys_of(tx, user_id)
    if not keys:
        raise Errors.bad_request('No passkeys on this account')
    options = generate_authentication_options(
        rp_id=rp_id(svc.deps.env), user_verification=UserVerificationRequirement.REQUIRED, allow_credentials=_descriptors(keys)
    )
    body = options_to_json_dict(options)
    await tx.execute('UPDATE challenges SET webauthn_challenge = $2 WHERE id = $1', [challenge_id, body['challenge']])
    return PasskeyLoginOptionsRes(options=body)


async def verify_login(svc: Svc, tx: Tx, challenge: Row, user: UserRow, response: dict[str, Any]) -> bool:
    """Verify a passkey assertion for the sign-in challenge. A counter that did not grow means a cloned authenticator."""
    stored = challenge['webauthn_challenge']
    if not stored:
        return False
    key = next((k for k in await passkeys_of(tx, user.id) if k['credential_id'] == response.get('id')), None)
    if key is None:
        return False
    # one assertion per challenge, whatever the outcome
    await tx.execute('UPDATE challenges SET webauthn_challenge = NULL WHERE id = $1', [challenge['id']])
    env = svc.deps.env
    try:
        v = verify_authentication_response(
            credential=response, expected_challenge=base64url_to_bytes(stored), expected_origin=web_origin(env),
            expected_rp_id=rp_id(env), credential_public_key=bytes(key['public_key']),
            credential_current_sign_count=int(key['counter']), require_user_verification=True,
        )  # fmt: skip
    except Exception:  # noqa: BLE001 - any failure means "not verified"
        return False
    await tx.execute('UPDATE auth_factors SET counter = $2, last_used_at = now() WHERE id = $1', [key['id'], v.new_sign_count])
    return True
