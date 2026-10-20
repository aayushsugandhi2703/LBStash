"""`db-init` container entrypoint (`python -m lbstash.db.init`): creates roles and schemas, then exits. Idempotent."""

import asyncio
import os
import sys

from lbstash.common import create_logger

from .bootstrap import DATA_SERVICES, bootstrap_database


async def main() -> int:
    """Bootstrap from `ADMIN_DATABASE_URL` and `DB_PASSWORD_<SERVICE>` / `DB_PASSWORD_QUEUE`; returns the exit code."""
    log = create_logger('db-init')
    admin_url = os.environ.get('ADMIN_DATABASE_URL')
    if not admin_url:
        log.error('db-init failed', err='ADMIN_DATABASE_URL is not set')
        return 1
    passwords = {'queue': os.environ.get('DB_PASSWORD_QUEUE')}
    passwords.update({s: os.environ.get(f'DB_PASSWORD_{s.upper()}') for s in DATA_SERVICES})
    try:
        await bootstrap_database(admin_url=admin_url, passwords=passwords, log=log)
    except Exception as e:  # noqa: BLE001 - the entrypoint reports any failure and exits non-zero
        log.error('db-init failed', err=e)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
