"""Make demo/.env: the demo user's email, password and authenticator secret. Standard library only.

    python3 demo/setup.py            create it (does nothing if it already exists)
    python3 demo/setup.py --force    replace it with new secrets

The public "Try the demo" button needs none of these: it signs in the demo user by itself, read-only. They exist so that you
can also sign in as the demo user the normal way (password, then an authenticator code from `python3 demo/totp.py`).
"""

import base64
import secrets
import sys
from pathlib import Path

ENV = Path(__file__).with_name('.env')


def main() -> int:
    if ENV.exists() and '--force' not in sys.argv:
        print(f'{ENV} already exists (use --force to replace it).')
        return 0
    password = secrets.token_urlsafe(18)
    totp = base64.b32encode(secrets.token_bytes(20)).decode().rstrip('=')
    ENV.write_text(
        '# The demo account (git-ignored). The public demo button does not use these.\n'
        'DEMO_EMAIL=demo@lbstash.site\n'
        f'DEMO_PASSWORD={password}\n'
        f'DEMO_TOTP_SECRET={totp}\n'
        'DEMO_REFRESH_HOURS=6\n',
        encoding='utf-8',
    )
    ENV.chmod(0o600)
    print(f'Wrote {ENV}\n  email     demo@lbstash.site\n  password  {password}\nAuthenticator code: python3 demo/totp.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
