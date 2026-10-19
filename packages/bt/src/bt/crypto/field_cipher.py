"""Field-level AES-256-GCM for stored secrets. Blob: [version 1][iv 12][tag 16][ciphertext]. `aad` binds a value to its row; the highest key version encrypts, any version decrypts."""

import base64
import os
import secrets
from collections.abc import Mapping

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_IV, _TAG = 12, 16


def _b64(s: str) -> bytes:
    # Lenient: standard or URL-safe alphabet, padding optional, whitespace ignored.
    t = ''.join(s.split()).replace('-', '+').replace('_', '/').rstrip('=')
    return base64.b64decode(t + '=' * (-len(t) % 4))


def _aad(aad: str | bytes | None) -> bytes | None:
    return (aad.encode() if isinstance(aad, str) else aad) or None


class FieldCipher:
    """Encrypts and decrypts short secrets with versioned keys."""

    def __init__(self, keys: Mapping[int, str | bytes]) -> None:
        self._keys: dict[int, bytes] = {}
        for version, k in keys.items():
            key = _b64(k) if isinstance(k, str) else bytes(k)
            if len(key) != 32:
                raise ValueError(f'field key v{version} must be 32 bytes')
            if not 0 < int(version) < 256:
                raise ValueError(f'field key version {version} must fit in one byte (1-255)')
            self._keys[int(version)] = key
        if not self._keys:
            raise ValueError('no field keys configured')
        self._current = max(self._keys)

    @classmethod
    def from_keys(cls, key: str | None, keys: str | None = None) -> 'FieldCipher':
        """`key` (base64, version 1) or `keys="1:base64,2:base64"` (rotation; the highest version encrypts)."""
        if keys:
            pairs = (pair.partition(':') for pair in keys.split(','))
            return cls({int(v): k for v, _, k in pairs if v and k})
        if not key:
            raise ValueError('FIELD_KEY is not set')
        return cls({1: key})

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> 'FieldCipher':
        env = os.environ if env is None else env
        return cls.from_keys(env.get('FIELD_KEY'), env.get('FIELD_KEYS'))

    def encrypt(self, plain: str | bytes, aad: str | bytes | None = None) -> bytes:
        """Encrypt with the newest key into a version-prefixed blob."""
        iv = secrets.token_bytes(_IV)
        sealed = AESGCM(self._keys[self._current]).encrypt(iv, plain.encode() if isinstance(plain, str) else plain, _aad(aad))
        body, tag = sealed[:-_TAG], sealed[-_TAG:]  # the library appends the tag; we store it before the body
        return bytes([self._current]) + iv + tag + body

    def decrypt(self, blob: bytes, aad: str | bytes | None = None) -> bytes:
        """Decrypt a blob; raises if the key, `aad` or bytes are wrong."""
        blob = bytes(blob)
        if len(blob) < 1 + _IV + _TAG:
            raise ValueError('field blob is too short')
        key = self._keys.get(blob[0])
        if key is None:
            raise ValueError(f'unknown field key version {blob[0]}')
        iv, tag, body = blob[1 : 1 + _IV], blob[1 + _IV : 1 + _IV + _TAG], blob[1 + _IV + _TAG :]
        return AESGCM(key).decrypt(iv, body + tag, _aad(aad))

    def encrypt_string(self, s: str, aad: str | bytes | None = None) -> bytes:
        """`encrypt` for text."""
        return self.encrypt(s, aad)

    def decrypt_string(self, blob: bytes, aad: str | bytes | None = None) -> str:
        """`decrypt` to text (UTF-8)."""
        return self.decrypt(blob, aad).decode()
