"""Random secrets, digests and recovery codes."""

import hashlib
import hmac
import secrets
from typing import NamedTuple

_RECOVERY_ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'


def random_token(nbytes: int = 32) -> str:
    """URL-safe random secret (ingest, refresh and callback tokens, nonces), base64url without padding."""
    return secrets.token_urlsafe(nbytes)


def _b(s: str | bytes) -> bytes:
    return s.encode() if isinstance(s, str) else s


def sha256_hex(s: str | bytes) -> str:
    """Hex SHA-256 of text (UTF-8) or bytes."""
    return hashlib.sha256(_b(s)).hexdigest()


def safe_equal(a: str | bytes, b: str | bytes) -> bool:
    """Constant-time compare."""
    return hmac.compare_digest(_b(a), _b(b))


class HashedToken(NamedTuple):
    """Show `token` once, store only `hash`."""

    token: str
    hash: str


def new_hashed_token(prefix: str = '', nbytes: int = 32) -> HashedToken:
    """A fresh token (optional prefix) and its SHA-256."""
    token = prefix + random_token(nbytes)
    return HashedToken(token, sha256_hex(token))


def random_digits(length: int) -> str:
    """Uniformly random digit string (pairing / short codes)."""
    return ''.join(secrets.choice('0123456789') for _ in range(length))


def generate_recovery_codes(count: int = 10) -> list[str]:
    """Codes like `k3f9a-77xqz`."""

    def part() -> str:
        return ''.join(secrets.choice(_RECOVERY_ALPHABET) for _ in range(5))

    return [f'{part()}-{part()}' for _ in range(count)]


def normalize_recovery_code(s: str) -> str:
    """Trimmed, lowercase, as codes are compared."""
    return s.strip().lower()
