"""Load the demo account into the database, and keep its dates moving.

    python /demo/seed.py            seed once and exit
    python /demo/seed.py --loop     seed, then again every DEMO_REFRESH_HOURS (default 6)
    python /demo/seed.py --remove   delete the demo user and everything it owns, then exit

Runs with the admin connection (like db-init), inside the lbstash base image. It only ever touches the one demo user
(`DEMO_USER_ID`): its sign-in row is kept (so open demo sessions survive a refresh); everything it owns is replaced.
Nothing here runs unless the demo overlay (`demo/docker-compose.demo.yml`) is used.
"""

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from lbstash.common import create_logger
from lbstash.crypto import FieldCipher, generate_recovery_codes, generate_totp_secret, hash_password, normalize_recovery_code, sha256_hex, verify_password
from lbstash.db import Tx, connect

import dataset as D

log = create_logger('demo-seed')

# every table the seed writes: the services create them when they start, so wait for them
TABLES = (
    'auth.users', 'auth.auth_factors', 'auth.audit_log',
    'transactions.transactions_settings', 'transactions.categories', 'transactions.transactions', 'transactions.tx_links',
    'transactions.tag_rules', 'transactions.balance_checks',
    'planning.planning_settings', 'planning.plans', 'planning.plan_lines', 'planning.budgets', 'planning.alerts', 'planning.plan_credits',
    'recurring.recurring_rules', 'ingest.devices', 'ingest.unparsed_messages',
)


def need(name: str) -> str:
    value = os.environ.get(name, '').strip()
    if not value:
        raise SystemExit(f'{name} is not set (run `python3 demo/setup.py`, then use --env-file demo/.env)')
    return value


async def wait_for_tables(conn: Any, timeout_s: int = 600) -> None:
    """The services run their migrations on start-up; seeding before that would fail."""
    tx = Tx(conn)
    for waited in range(0, timeout_s, 3):
        missing = [t for t in TABLES if (await tx.one('SELECT to_regclass($1) AS r', [t]))['r'] is None]
        if not missing:
            return
        if waited % 30 == 0:
            log.info('waiting for the services to create their tables', missing=len(missing))
        await asyncio.sleep(3)
    raise SystemExit(f'tables still missing after {timeout_s}s: {", ".join(missing)}')


async def upsert_user(tx: Tx, cipher: FieldCipher, ds: D.Dataset) -> None:
    """The sign-in row. Password and authenticator secret come from the environment; they are only rewritten when they changed."""
    uid = D.DEMO_USER_ID
    email, password = need('DEMO_EMAIL'), need('DEMO_PASSWORD')
    secret = os.environ.get('DEMO_TOTP_SECRET', '').strip()
    old = await tx.maybe_one('SELECT email, password_hash, totp_secret_enc FROM auth.users WHERE id = $1', [uid])
    clash = await tx.maybe_one('SELECT id FROM auth.users WHERE email = $1 AND id <> $2', [email, uid])
    if clash:
        raise SystemExit(f'{email} already belongs to another account; set DEMO_EMAIL to a different address')
    pw_hash = old['password_hash'] if old and await verify_password(password, old['password_hash']) else await hash_password(password)
    if secret:
        same = old and old['totp_secret_enc'] and cipher.decrypt_string(bytes(old['totp_secret_enc']), uid) == secret
        enc = bytes(old['totp_secret_enc']) if same else cipher.encrypt_string(secret, uid)
    else:
        enc = bytes(old['totp_secret_enc']) if old and old['totp_secret_enc'] else cipher.encrypt_string(generate_totp_secret(), uid)
    joined = D._at(D.add_months(ds.today.replace(day=1), -(D.HISTORY_MONTHS - 1)), 9)
    await tx.execute(
        """INSERT INTO auth.users (id, email, password_hash, name, timezone, totp_secret_enc, totp_enabled_at, setup_completed_at, password_changed_at, created_at)
           VALUES ($1, $2, $3, 'Demo', 'Asia/Kolkata', $4, $5, $5, $5, $5)
           ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email, password_hash = EXCLUDED.password_hash, name = 'Demo', timezone = 'Asia/Kolkata',
             totp_secret_enc = EXCLUDED.totp_secret_enc, totp_enabled_at = COALESCE(auth.users.totp_enabled_at, EXCLUDED.totp_enabled_at),
             setup_completed_at = COALESCE(auth.users.setup_completed_at, EXCLUDED.setup_completed_at), delete_after = NULL, pending_email = NULL""",
        [uid, email, pw_hash, enc, joined],
    )
    # a passkey and a recovery set make the session a full one (not "finish securing your account"); the keys are placeholders nobody holds
    await tx.execute(
        """INSERT INTO auth.auth_factors (id, user_id, kind, label, public_key, credential_id, counter)
           VALUES ($1, $2, 'passkey', 'Demo passkey', $3, 'lbstash-demo-credential', 0) ON CONFLICT DO NOTHING""",
        [D.uid('factor', 'passkey'), uid, bytes.fromhex(sha256_hex('lbstash-demo-public-key'))],
    )
    if not (await tx.one("SELECT count(*) AS n FROM auth.auth_factors WHERE user_id = $1 AND kind = 'recovery_code'", [uid]))['n']:
        for code in generate_recovery_codes(8):  # the plain codes are discarded on purpose
            await tx.execute("INSERT INTO auth.auth_factors (user_id, kind, code_hash) VALUES ($1, 'recovery_code', $2)", [uid, sha256_hex(normalize_recovery_code(code))])
    if not (await tx.one('SELECT count(*) AS n FROM auth.audit_log WHERE user_id = $1', [uid]))['n']:
        for days, action in ((D.HISTORY_MONTHS * 30, 'register'), (21, 'login.ok'), (21, '2fa.ok'), (6, 'login.ok'), (6, '2fa.ok'), (1, 'login.ok'), (1, '2fa.ok')):
            await tx.execute(
                'INSERT INTO auth.audit_log (user_id, action, ip, at) VALUES ($1, $2, $3, $4)', [uid, action, '203.0.113.7', ds.now - timedelta(days=days)],
            )


# children before parents (foreign keys), all for the one demo user
WIPE = (
    'DELETE FROM transactions.tx_links WHERE user_id = $1',
    'DELETE FROM transactions.balance_checks WHERE user_id = $1',
    'DELETE FROM transactions.transactions WHERE user_id = $1',
    'DELETE FROM transactions.tag_rules WHERE user_id = $1',
    'DELETE FROM transactions.categories WHERE user_id = $1',
    'DELETE FROM transactions.transactions_settings WHERE user_id = $1',
    'DELETE FROM planning.alerts WHERE user_id = $1',
    'DELETE FROM planning.budgets WHERE user_id = $1',
    'DELETE FROM planning.plan_lines WHERE user_id = $1',
    'DELETE FROM planning.plans WHERE user_id = $1',
    'DELETE FROM planning.plan_credits WHERE user_id = $1',
    'DELETE FROM planning.planning_settings WHERE user_id = $1',
    'DELETE FROM recurring.recurring_rules WHERE user_id = $1',
    'DELETE FROM ingest.unparsed_messages WHERE user_id = $1',
    'DELETE FROM ingest.devices WHERE user_id = $1',
)


async def replace_data(tx: Tx, cipher: FieldCipher, ds: D.Dataset) -> None:
    uid = D.DEMO_USER_ID
    for sql in WIPE:
        await tx.execute(sql, [uid])

    s = ds.settings
    await tx.execute(
        'INSERT INTO transactions.transactions_settings (user_id, opening_balance_minor, reconcile_grace_hours, last_balance_at) VALUES ($1, $2, $3, $4)',
        [uid, s['opening_balance_minor'], s['reconcile_grace_hours'], s.get('last_balance_at')],
    )
    for c in ds.categories:
        await tx.execute('INSERT INTO transactions.categories (id, user_id, name, created_at) VALUES ($1, $2, $3, $4)', [c['id'], uid, c['name'], c['created_at']])

    d = ds.device
    await tx.execute(
        """INSERT INTO ingest.devices (id, user_id, name, token_hash, token_hint, tz, created_at, last_seen_at, last_delay_seconds,
                                       last_test_at, last_test_source, last_test_delay_seconds, last_test_amount_minor)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)""",
        [d['id'], uid, d['name'], d['token_hash'], d['token_hint'], d['tz'], d['created_at'], d['last_seen_at'], d['last_delay_seconds'],
         d['last_test_at'], d['last_test_source'], d['last_test_delay_seconds'], d['last_test_amount_minor']],
    )

    for t in ds.transactions:
        made = t['captured_at'] or t['occurred_at']
        await tx.execute(
            """INSERT INTO transactions.transactions (id, user_id, type, amount_minor, occurred_at, payee, payee_key, description, reference, account_last4,
                 category_id, source, status, dedupe_key, recurring_id, match_hint, device_id, captured_at, weak_parse, classified_by, rule_pattern,
                 linked, created_at, updated_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $23)""",
            [t['id'], uid, t['type'], t['amount_minor'], t['occurred_at'], t['payee'], t['payee_key'], t['description'], t['reference'], t['account_last4'],
             t['category_id'], t['source'], t['status'], t['dedupe_key'], t['recurring_id'], t['match_hint'], t['device_id'], t['captured_at'],
             t['weak_parse'], t['classified_by'], t['rule_pattern'], t['linked'], made],
        )
    for k in ds.tx_links:
        await tx.execute('INSERT INTO transactions.tx_links (user_id, dedupe_key, transaction_id) VALUES ($1, $2, $3)', [uid, k['dedupe_key'], k['transaction_id']])
    for r in ds.tag_rules:
        await tx.execute(
            'INSERT INTO transactions.tag_rules (id, user_id, category_id, kind, pattern, hits) VALUES ($1, $2, $3, $4, $5, $6)',
            [r['id'], uid, r['category_id'], r['kind'], r['pattern'], r['hits']],
        )
    for b in ds.balance_checks:
        await tx.execute(
            """INSERT INTO transactions.balance_checks (id, user_id, bank_balance_minor, transactions_balance_minor, gap_minor, source, status, checked_at, as_of, transaction_id)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
            [b['id'], uid, b['bank_balance_minor'], b['transactions_balance_minor'], b['gap_minor'], b['source'], b['status'], b['checked_at'], b['as_of'], b['transaction_id']],
        )

    await tx.execute('INSERT INTO planning.planning_settings (user_id, alert_level, warn_on_pace, tz) VALUES ($1, 80, true, $2)', [uid, 'Asia/Kolkata'])
    for p in ds.plans:
        await tx.execute('INSERT INTO planning.plans (id, user_id, month, total_minor) VALUES ($1, $2, $3, $4)', [p['id'], uid, p['month'], p['total_minor']])
    for ln in ds.plan_lines:
        await tx.execute(
            'INSERT INTO planning.plan_lines (id, user_id, plan_id, category_id, allocated_minor, position) VALUES ($1, $2, $3, $4, $5, $6)',
            [ln['id'], uid, ln['plan_id'], ln['category_id'], ln['allocated_minor'], ln['position']],
        )
    for b in ds.budgets:
        await tx.execute('INSERT INTO planning.budgets (id, user_id, category_id, limit_minor) VALUES ($1, $2, $3, $4)', [b['id'], uid, b['category_id'], b['limit_minor']])
    for a in ds.alerts:
        await tx.execute(
            """INSERT INTO planning.alerts (id, user_id, budget_id, period_key, level, pct, category_name, sent_at, read_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            [a['id'], uid, a['budget_id'], a['period_key'], a['level'], a['pct'], a['category_name'], a['sent_at'], a['read_at']],
        )

    for r in ds.rules:
        await tx.execute(
            """INSERT INTO recurring.recurring_rules (id, user_id, name, note, category_id, amount_minor, kind, day_of_month, next_due, last_handled_due, paused, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, 'monthly', $7, $8, $9, $10, $11)""",
            [r['id'], uid, r['name'], r['note'], r['category_id'], r['amount_minor'], r['day_of_month'], r['next_due'], r['last_handled_due'], r['paused'], r['created_at']],
        )

    for m in ds.unparsed:
        await tx.execute(
            """INSERT INTO ingest.unparsed_messages (id, user_id, device_id, body_enc, reason, received_at, status, expires_at)
               VALUES ($1, $2, $3, $4, $5, $6, 'open', $7)""",
            [m['id'], uid, ds.device['id'], cipher.encrypt_string(m['text'], uid), m['reason'], m['received_at'], m['received_at'] + timedelta(days=30)],
        )


async def remove_all(url: str) -> None:
    """Take the demo out of the database: its data, its sessions and sign-in row, and its audit rows (allowed once the user is gone)."""
    conn = await connect(url, name='demo-seed')
    try:
        await wait_for_tables(conn)
        async with conn.transaction():
            tx = Tx(conn)
            await tx.execute("SELECT set_config('app.system', 'on', true)")
            for sql in WIPE:
                await tx.execute(sql, [D.DEMO_USER_ID])
            await tx.execute('DELETE FROM auth.users WHERE id = $1', [D.DEMO_USER_ID])  # sessions, tokens and factors cascade
            await tx.execute('SELECT auth.purge_user_audit($1)', [D.DEMO_USER_ID])
    finally:
        await conn.close()
    log.info('demo removed')


async def seed_once(url: str, cipher: FieldCipher) -> D.Dataset:
    ds = D.build(datetime.now(UTC))
    conn = await connect(url, name='demo-seed')
    try:
        await wait_for_tables(conn)
        async with conn.transaction():
            tx = Tx(conn)
            await tx.execute("SELECT set_config('app.system', 'on', true)")
            await upsert_user(tx, cipher, ds)
            await replace_data(tx, cipher, ds)
    finally:
        await conn.close()
    n = len(ds.transactions)
    log.info('demo data loaded', transactions=n, months=len(ds.months), today=str(ds.today), balance=ds.balance_at(ds.now) // 100)
    return ds


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--loop', action='store_true', help='keep running: reseed every DEMO_REFRESH_HOURS')
    ap.add_argument('--remove', action='store_true', help='delete the demo user and all its data, then exit')
    args = ap.parse_args()
    url = need('ADMIN_DATABASE_URL')
    if args.remove:
        await remove_all(url)
        return 0
    cipher = FieldCipher.from_keys(os.environ.get('FIELD_KEY'), os.environ.get('FIELD_KEYS'))
    hours = float(os.environ.get('DEMO_REFRESH_HOURS', '6'))
    while True:
        try:
            await seed_once(url, cipher)
        except SystemExit:
            raise
        except Exception as e:  # noqa: BLE001 - a failed refresh is logged and retried, the old data stays
            log.error('demo seed failed', err=e)
            if not args.loop:
                return 1
            await asyncio.sleep(60)
            continue
        if not args.loop:
            return 0
        await asyncio.sleep(hours * 3600)


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
