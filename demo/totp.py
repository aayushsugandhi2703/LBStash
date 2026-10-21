"""Print the current authenticator code for the demo user (from demo/.env). Standard library only.

    python3 demo/totp.py
"""

import base64
import hashlib
import hmac
import struct
import sys
import time
from pathlib import Path


def code(secret_b32: str, at: float | None = None) -> str:
    """RFC 6238: 6 digits, 30-second steps, SHA-1."""
    key = base64.b32decode(secret_b32.upper() + '=' * (-len(secret_b32) % 8))
    step = int((time.time() if at is None else at) // 30)
    mac = hmac.new(key, struct.pack('>Q', step), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    return f'{(struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000:06d}'


def main() -> int:
    env = Path(__file__).with_name('.env')
    if not env.exists():
        print('demo/.env is missing: run python3 demo/setup.py first.')
        return 1
    values = dict(line.split('=', 1) for line in env.read_text(encoding='utf-8').splitlines() if '=' in line and not line.startswith('#'))
    secret = values.get('DEMO_TOTP_SECRET', '').strip()
    if not secret:
        print('DEMO_TOTP_SECRET is not set in demo/.env.')
        return 1
    left = 30 - int(time.time()) % 30
    print(f'{code(secret)}  (valid for about {left} more seconds)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
