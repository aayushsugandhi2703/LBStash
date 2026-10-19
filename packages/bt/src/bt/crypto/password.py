"""Argon2id password hashing. Format `$argon2id$v=19$m=<KiB>,t=<passes>,p=<lanes>$<salt>$<tag>`; written with padded base64, read either way."""

import asyncio
import base64
import hmac
import re
import secrets
from typing import Final, NamedTuple

from argon2.exceptions import Argon2Error
from argon2.low_level import Type, hash_secret_raw


class Argon2Params(NamedTuple):
    """Cost parameters (memory in KiB)."""

    memory: int
    passes: int
    parallelism: int
    tag_length: int


# Argon2id, 64 MiB, 3 passes (README 15.1).
ARGON2_PARAMS: Final = Argon2Params(memory=65536, passes=3, parallelism=4, tag_length=32)

_PHC = re.compile(r'\$argon2id\$v=19\$m=([0-9]+),t=([0-9]+),p=([0-9]+)\$([^$]+)\$([^$]+)', re.ASCII)


def _b64decode(s: str) -> bytes:
    # standard or URL-safe alphabet, padding optional
    t = s.replace('-', '+').replace('_', '/').rstrip('=')
    return base64.b64decode(t + '=' * (-len(t) % 4))


def _b64encode(b: bytes) -> str:
    return base64.b64encode(b).decode()


def _raw(password: str, salt: bytes, memory: int, passes: int, parallelism: int, tag_length: int) -> bytes:
    return hash_secret_raw(
        password.encode(), salt, time_cost=passes, memory_cost=memory, parallelism=parallelism,
        hash_len=tag_length, type=Type.ID, version=19,
    )  # fmt: skip


def _parse(phc: str) -> tuple[int, int, int, bytes, bytes] | None:
    m = _PHC.fullmatch(phc)
    if not m:
        return None
    try:
        return int(m[1]), int(m[2]), int(m[3]), _b64decode(m[4]), _b64decode(m[5])
    except ValueError:  # binascii.Error is a ValueError
        return None


def _hash_sync(password: str, params: Argon2Params) -> str:
    salt = secrets.token_bytes(16)
    tag = _raw(password, salt, params.memory, params.passes, params.parallelism, params.tag_length)
    return f'$argon2id$v=19$m={params.memory},t={params.passes},p={params.parallelism}${_b64encode(salt)}${_b64encode(tag)}'


def _verify_sync(password: str, phc: str) -> bool:
    p = _parse(phc)
    if p is None:
        return False
    memory, passes, parallelism, salt, tag = p
    try:
        got = _raw(password, salt, memory, passes, parallelism, len(tag))
    except (Argon2Error, ValueError):  # parameters the library refuses (e.g. a salt under 8 bytes)
        return False
    return hmac.compare_digest(got, tag)


async def hash_password(password: str, params: Argon2Params = ARGON2_PARAMS) -> str:
    """Hash with a fresh random salt, off the event loop."""
    return await asyncio.to_thread(_hash_sync, password, params)


async def verify_password(password: str, phc: str) -> bool:
    """True if `password` matches the stored hash, off the event loop."""
    return await asyncio.to_thread(_verify_sync, password, phc)


async def needs_rehash(phc: str) -> bool:
    """True if the stored hash is weaker than today's settings or unreadable."""
    p = _parse(phc)
    return p is None or p[0] < ARGON2_PARAMS.memory or p[1] < ARGON2_PARAMS.passes


_dummy: str | None = None


async def dummy_hash() -> str:
    """Hash to verify against when the user does not exist, so a wrong email and a wrong password take similar time."""
    global _dummy
    if _dummy is None:
        _dummy = await hash_password('not-a-real-password')
    return _dummy
