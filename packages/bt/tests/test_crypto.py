import base64
import re
import secrets
from datetime import UTC, datetime

import jwt as pyjwt
import pytest
from bt.crypto import (
    Argon2Params,
    FieldCipher,
    InternalClaims,
    TokenError,
    base32_encode,
    dummy_hash,
    generate_recovery_codes,
    generate_totp_secret,
    hash_password,
    needs_rehash,
    new_hashed_token,
    otpauth_uri,
    random_digits,
    random_token,
    safe_equal,
    sha256_hex,
    sign_access_token,
    sign_internal_token,
    totp_code,
    verify_access_token,
    verify_internal_token,
    verify_password,
    verify_totp,
)
from cryptography.exceptions import InvalidTag

# Fixed vectors: what existing database rows and live tokens hold.
FIXED_HASH = '$argon2id$v=19$m=65536,t=3,p=4$6JnEJ6dA3yqKy6rFyn8fcw==$m00LvTjoveRLgLpDVO3JfSrJ83RxydxQ+PpqnHGkBXg='
FIXED_FIELD_KEY = 'BwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc='
FIXED_BLOB = 'AWK067G906P+4mA43WNRGuBJI3ZsYsg1EP/OKq3kUNEM9g2Qe82LQuYHfEzhJA=='
FIXED_BLOB_NO_AAD = 'Af+Xp19S6s3t2nSK+XwcjHSnkR4tkjIGuIewN61USexefA=='
FIXED_TOTP_SECRET = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'
FIXED_SECRET = 's' * 40
FIXED_ACCESS = (
    'eyJhbGciOiJIUzI1NiJ9.eyJzaWQiOiJzMSIsInR6IjoiQXNpYS9Lb2xrYXRhIiwic3ViIjoidTEiLCJpc3MiOiJidC1hdXRoIiwiaWF0IjoxNzkyMzM4NTMxLCJleHAiOjQ5NDU5Mzg1MzF9'
    '.nwNwW8UQ1RZc9YEk9Ym0nLgabIHtmiAgRi2sdPBtHOQ'
)
FIXED_INTERNAL = (
    'eyJhbGciOiJIUzI1NiJ9.eyJzdmMiOiJnYXRld2F5IiwidHoiOiJVVEMiLCJyaWQiOiJyMSIsInB4IjoxLCJpc3MiOiJidC1pbnRlcm5hbCIsImlhdCI6MTc5MjMzODUzMSwiZXhwIjo0OTQ1OTM4NTMxLCJzdWIiOiJ1MSJ9'
    '.5mWgL5vc55rubWortg_IVlbXMPqjAikbjkqhTXjDFmE'
)
FIXED_INTERNAL_SYSTEM = (
    'eyJhbGciOiJIUzI1NiJ9.eyJzdmMiOiJsZWRnZXIiLCJpc3MiOiJidC1pbnRlcm5hbCIsImlhdCI6MTc5MjMzODUzMSwiZXhwIjo0OTQ1OTM4NTMxfQ'
    '.-mzGhWJbWCS7xqoSGzvyGMESpo5vGHQTWIF_w3uGibA'
)

# cheap parameters for tests that just need a valid hash
FAST = Argon2Params(memory=64, passes=1, parallelism=1, tag_length=32)


class TestTotp:
    secret = base32_encode(b'12345678901234567890')

    def test_matches_the_rfc_test_vector(self):
        assert totp_code(self.secret, 1) == '287082'

    def test_accepts_a_code_once_per_time_step(self):
        now = datetime.fromtimestamp(59, UTC)
        assert verify_totp(self.secret, '287082', now=now) == 1
        assert verify_totp(self.secret, '287082', now=now, after_step=1) is None
        assert verify_totp(self.secret, '000000', now=now) is None
        assert verify_totp(self.secret, '28708', now=now) is None
        assert verify_totp(self.secret, '287082\n', now=now) is None

    def test_accepts_a_neighbouring_step_only_inside_the_window(self):
        at_step_3 = datetime.fromtimestamp(3 * 30 + 1, UTC)
        assert verify_totp(self.secret, totp_code(self.secret, 2), now=at_step_3) == 2
        assert verify_totp(self.secret, totp_code(self.secret, 1), now=at_step_3) is None

    def test_generated_secrets_are_base32_and_uri_is_escaped(self):
        s = generate_totp_secret()
        assert len(s) == 32 and set(s) <= set('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')
        assert otpauth_uri('Budget Tracker', 'a@b.co', s).startswith('otpauth://totp/Budget%20Tracker:a%40b.co?secret=')

    def test_accepts_a_code_made_by_the_typescript_implementation(self):
        assert totp_code(FIXED_TOTP_SECRET, 57000000) == '168705'
        now = datetime.fromtimestamp(57000000 * 30 + 5, UTC)
        assert verify_totp(FIXED_TOTP_SECRET, '168705', now=now) == 57000000


class TestFieldCipher:
    key = base64.b64encode(secrets.token_bytes(32)).decode()

    def test_round_trips_and_binds_to_aad(self):
        c = FieldCipher({1: self.key})
        blob = c.encrypt_string('secret text', 'user-1')
        assert c.decrypt_string(blob, 'user-1') == 'secret text'
        with pytest.raises(InvalidTag):
            c.decrypt_string(blob, 'user-2')
        with pytest.raises(InvalidTag):
            c.decrypt_string(blob)

    def test_decrypts_old_versions_after_rotation(self):
        blob = FieldCipher({1: self.key}).encrypt_string('x')
        rotated = FieldCipher({1: self.key, 2: secrets.token_bytes(32)})
        assert rotated.decrypt_string(blob) == 'x'
        assert rotated.encrypt_string('y')[0] == 2

    def test_layout_is_version_iv_tag_ciphertext(self):
        blob = FieldCipher({1: self.key}).encrypt(b'abcd')
        assert len(blob) == 1 + 12 + 16 + 4 and blob[0] == 1

    def test_from_env(self):
        assert FieldCipher.from_env({'FIELD_KEY': self.key}).decrypt(FieldCipher({1: self.key}).encrypt(b'a')) == b'a'
        c = FieldCipher.from_env({'FIELD_KEYS': f'1:{self.key},2:{self.key}'})
        assert c.encrypt(b'a')[0] == 2
        with pytest.raises(ValueError):
            FieldCipher.from_env({})

    def test_rejects_bad_keys(self):
        with pytest.raises(ValueError):
            FieldCipher({1: 'AAAA'})
        with pytest.raises(ValueError):
            FieldCipher({})

    def test_decrypts_blobs_made_by_the_typescript_implementation(self):
        c = FieldCipher({1: FIXED_FIELD_KEY})
        assert c.decrypt_string(base64.b64decode(FIXED_BLOB), 'user-1') == 'secret text ünï'
        assert c.decrypt_string(base64.b64decode(FIXED_BLOB_NO_AAD)) == 'plain'
        with pytest.raises(InvalidTag):
            c.decrypt_string(base64.b64decode(FIXED_BLOB), 'user-2')


class TestPasswordHashing:
    async def test_argon2id_verifies_right_and_rejects_wrong(self):
        h = await hash_password('correct horse battery')
        assert h.startswith('$argon2id$v=19$m=65536,t=3,p=4$')
        assert h.endswith('=')  # padded standard base64, like stored hashes
        assert await verify_password('correct horse battery', h)
        assert not await verify_password('wrong', h)
        assert not await needs_rehash(h)

    async def test_verifies_a_hash_written_by_the_typescript_implementation(self):
        assert await verify_password('correct horse battery', FIXED_HASH)
        assert not await verify_password('Correct horse battery', FIXED_HASH)
        assert not await needs_rehash(FIXED_HASH)

    async def test_reads_padded_and_unpadded_base64(self):
        head, salt, tag = FIXED_HASH.rsplit('$', 2)
        assert await verify_password('correct horse battery', f'{head}${salt.rstrip("=")}${tag.rstrip("=")}')

    async def test_weaker_or_unreadable_hashes_need_a_rehash(self):
        weak = await hash_password('pw', FAST)
        assert await needs_rehash(weak)
        assert await verify_password('pw', weak)
        assert await needs_rehash('not a hash')
        assert not await verify_password('pw', 'not a hash')
        assert not await verify_password('pw', '$argon2id$v=19$m=64,t=1,p=1$AAAA$AAAA')  # salt too short for Argon2

    async def test_each_hash_has_its_own_salt_and_dummy_hash_is_stable(self):
        a, b = await hash_password('pw', FAST), await hash_password('pw', FAST)
        assert a != b
        d = await dummy_hash()
        assert d is await dummy_hash()
        assert not await verify_password('anything', d)


class TestTokens:
    def test_signs_and_verifies_access_and_internal_tokens(self):
        s = 'x' * 40
        t = sign_access_token(s, sub='u1', sid='s1', tz='Asia/Kolkata')
        c = verify_access_token(s, t)
        assert (c.sub, c.sid, c.tz) == ('u1', 's1', 'Asia/Kolkata')
        with pytest.raises(TokenError):
            verify_access_token('y' * 40, t)
        i = sign_internal_token(s, svc='ledger', user_id='u1', tz='UTC')
        assert verify_internal_token(s, i).user_id == 'u1'
        with pytest.raises(TokenError):
            verify_access_token(s, i)  # different issuer
        with pytest.raises(TokenError):
            verify_internal_token(s, t)

    def test_internal_claims_round_trip(self):
        s = 'x' * 40
        full = verify_internal_token(s, sign_internal_token(s, svc='gateway', user_id='u', tz='UTC', request_id='r', proxied=True))
        assert full == InternalClaims(svc='gateway', user_id='u', tz='UTC', request_id='r', proxied=True)
        system = verify_internal_token(s, sign_internal_token(s, svc='ledger'))
        assert system == InternalClaims(svc='ledger', user_id=None, tz=None, request_id=None, proxied=False)

    def test_expired_and_forged_tokens_are_refused(self):
        s = 'x' * 40
        with pytest.raises(TokenError):
            verify_internal_token(s, sign_internal_token(s, svc='ledger', ttl_seconds=-5))
        none_alg = pyjwt.encode({'svc': 'x', 'iss': 'bt-internal', 'exp': 9999999999}, None, algorithm='none')
        with pytest.raises(TokenError):
            verify_internal_token(s, none_alg)
        no_exp = pyjwt.encode({'svc': 'x', 'iss': 'bt-internal'}, s, algorithm='HS256')
        with pytest.raises(TokenError):
            verify_internal_token(s, no_exp)
        with pytest.raises(TokenError):
            verify_internal_token(s, 'garbage')

    def test_verifies_tokens_signed_by_the_typescript_implementation(self):
        a = verify_access_token(FIXED_SECRET, FIXED_ACCESS)
        assert (a.sub, a.sid, a.tz) == ('u1', 's1', 'Asia/Kolkata')
        i = verify_internal_token(FIXED_SECRET, FIXED_INTERNAL)
        assert i == InternalClaims(svc='gateway', user_id='u1', tz='UTC', request_id='r1', proxied=True)
        assert verify_internal_token(FIXED_SECRET, FIXED_INTERNAL_SYSTEM) == InternalClaims(svc='ledger')

    def test_hashed_tokens_and_recovery_codes(self):
        token, hash_ = new_hashed_token('btk_')
        assert token.startswith('btk_') and hash_ == sha256_hex(token)
        codes = generate_recovery_codes()
        assert len(set(codes)) == 10
        assert all(re.fullmatch(r'[a-z2-9]{5}-[a-z2-9]{5}', c) for c in codes)

    def test_random_helpers(self):
        assert len(random_token()) == 43 and '=' not in random_token()
        assert len(random_digits(6)) == 6 and random_digits(8).isdigit()
        assert safe_equal('abc', 'abc') and not safe_equal('abc', 'abd') and not safe_equal('abc', 'ab')
        assert sha256_hex('') == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
