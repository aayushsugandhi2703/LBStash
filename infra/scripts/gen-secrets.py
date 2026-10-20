#!/usr/bin/env python3
"""Writes a .env with fresh random secrets (standard library only). Refuses to overwrite unless --force."""
import base64
import re
import secrets
import sys
from pathlib import Path

env = Path(".env")
if env.exists() and "--force" not in sys.argv:
    sys.exit(".env exists; use --force to replace it (this rotates every secret!)")

def hexs(n: int = 24) -> str:
    return secrets.token_hex(n)


generated = {
    "POSTGRES_PASSWORD": hexs(), "DB_PASSWORD_QUEUE": hexs(),
    "DB_PASSWORD_AUTH": hexs(), "DB_PASSWORD_TRANSACTIONS": hexs(), "DB_PASSWORD_INGEST": hexs(), "DB_PASSWORD_PLANNING": hexs(),
    "DB_PASSWORD_RECURRING": hexs(), "DB_PASSWORD_TELEGRAM": hexs(),
    "INTERNAL_SECRET": hexs(32), "ACCESS_TOKEN_SECRET": hexs(32), "FIELD_KEY": base64.b64encode(secrets.token_bytes(32)).decode(),
}


def fill(line: str) -> str:
    m = re.fullmatch(r"([A-Z0-9_]+)=(.*)", line)
    return f"{m[1]}={generated[m[1]]}" if m and m[1] in generated else line


env.write_text("\n".join(fill(l) for l in Path(".env.example").read_text().split("\n")))
env.chmod(0o600)
print("wrote .env (mode 600). Keep it out of git; back up FIELD_KEY: encrypted fields cannot be read without it.")
