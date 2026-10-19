"""RFC 6238 TOTP (SHA-1, 6 digits, 30 s) with once-per-time-step acceptance."""

import hmac
import re
import secrets
import struct
from datetime import UTC, datetime
from hashlib import sha1
from typing import Final
from urllib.parse import quote

_B32: Final = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
TOTP_STEP_SECONDS: Final = 30


def base32_encode(buf: bytes) -> str:
    """RFC 4648 base32 without padding."""
    bits = value = 0
    out = []
    for byte in buf:
        value = ((value << 8) | byte) & 0xFFFFFFFF
        bits += 8
        while bits >= 5:
            out.append(_B32[(value >> (bits - 5)) & 31])
            bits -= 5
    if bits > 0:
        out.append(_B32[(value << (5 - bits)) & 31])
    return ''.join(out)


def base32_decode(s: str) -> bytes:
    """Lenient base32 (case-insensitive, padding optional); `ValueError` on other characters."""
    bits = value = 0
    out = bytearray()
    for ch in s.rstrip('=').upper():
        i = _B32.find(ch)
        if i < 0:
            raise ValueError('bad base32')
        value = ((value << 5) | i) & 0xFFFFFFFF
        bits += 5
        if bits >= 8:
            out.append((value >> (bits - 8)) & 255)
            bits -= 8
    return bytes(out)


def generate_totp_secret() -> str:
    """New 160-bit secret, base32."""
    return base32_encode(secrets.token_bytes(20))


def totp_step(now: datetime) -> int:
    """The 30-second step containing `now`."""
    return int(now.timestamp()) // TOTP_STEP_SECONDS


def totp_code(secret: str, step: int, digits: int = 6) -> str:
    h = hmac.new(base32_decode(secret), struct.pack('>Q', step), sha1).digest()
    off = h[-1] & 15
    binary = struct.unpack('>I', h[off : off + 4])[0] & 0x7FFFFFFF
    return str(binary % 10**digits).zfill(digits)


def verify_totp(
    secret: str, code: str, *, now: datetime | None = None, window: int = 1, after_step: int | None = None
) -> int | None:
    """The matching time step, or None. `after_step` is the last step used, so a sniffed code cannot be replayed."""
    if not re.fullmatch(r'[0-9]{6}', code or ''):
        return None
    current = totp_step(now or datetime.now(UTC))
    for s in range(current - window, current + window + 1):
        if after_step is not None and s <= after_step:
            continue
        if hmac.compare_digest(totp_code(secret, s), code):
            return s
    return None


def otpauth_uri(issuer: str, account: str, secret: str) -> str:
    """The `otpauth://` link for authenticator apps."""
    q = lambda s: quote(s, safe="-_.!~*'()")
    return f'otpauth://totp/{q(issuer)}:{q(account)}?secret={secret}&issuer={q(issuer)}&algorithm=SHA1&digits=6&period=30'
