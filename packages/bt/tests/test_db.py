import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from bt.db import NoRows, Where, bootstrap_database, camel, camel_all, jsonb, migrate
from bt.db.adapters import bind, rewrite_placeholders
from bt.db.testing import admin_url, url_for

MIGRATIONS = str(Path(__file__).parent / 'migrations')


class TestRowLevelSecurity:
    a, b = str(uuid.uuid4()), str(uuid.uuid4())

    async def test_a_user_only_sees_their_own_rows_even_with_no_where_clause(self, db):
        async with db.pool.user_tx(self.a) as tx:
            await tx.execute("INSERT INTO notes (user_id, body) VALUES ($1, 'mine')", [self.a])
        async with db.pool.user_tx(self.b) as tx:
            await tx.execute("INSERT INTO notes (user_id, body) VALUES ($1, 'theirs')", [self.b])
        async with db.pool.user_tx(self.a) as tx:
            assert [r['body'] for r in await tx.many('SELECT body FROM notes')] == ['mine']
        async with db.pool.user_tx(self.b) as tx:
            assert [r['body'] for r in await tx.many('SELECT body FROM notes')] == ['theirs']

    async def test_writing_another_users_row_is_refused(self, db):
        with pytest.raises(Exception, match='row-level security'):
            async with db.pool.user_tx(self.a) as tx:
                await tx.execute("INSERT INTO notes (user_id, body) VALUES ($1, 'sneaky')", [self.b])

    async def test_no_user_and_no_system_flag_sees_nothing(self, db):
        assert await db.pool.query('SELECT * FROM notes') == []

    async def test_system_scope_sees_everyone(self, db):
        async with db.pool.system_tx() as tx:
            assert len(await tx.many('SELECT * FROM notes')) >= 2

    async def test_the_scope_ends_with_the_transaction(self, db):
        async with db.pool.user_tx(self.a) as tx:
            assert (await tx.one("SELECT current_setting('app.user_id') AS u"))['u'] == self.a
        async with db.pool.tx() as tx:
            assert (await tx.one("SELECT coalesce(current_setting('app.user_id', true), '') AS u"))['u'] == ''


class TestLeastPrivilegeAndAppendOnly:
    async def test_the_service_role_cannot_read_another_service_schema(self, db):
        with pytest.raises(Exception, match='permission denied|does not exist'):
            await db.pool.query('SELECT * FROM auth._migrations')

    async def test_audit_rows_cannot_be_updated_or_deleted(self, db):
        u = str(uuid.uuid4())
        async with db.pool.user_tx(u) as tx:
            await tx.execute("INSERT INTO audit (user_id, action) VALUES ($1, 'login')", [u])
        for sql in ("UPDATE audit SET action = 'x'", 'DELETE FROM audit'):
            with pytest.raises(Exception, match='permission denied'):
                async with db.pool.user_tx(u) as tx:
                    await tx.execute(sql)

    async def test_migrations_run_once(self, db):
        assert await migrate(db.pool, schema='ledger', dir=MIGRATIONS) == []

    async def test_the_queue_role_owns_its_schema_and_cannot_create_in_the_database(self, db):
        from bt.db import create_pool

        q = await create_pool(db.queue_url, name='t-queue', max_size=1)
        try:
            await q.execute('CREATE TABLE queue.probe (id int)')
            await q.execute('DROP TABLE queue.probe')
            with pytest.raises(Exception, match='permission denied'):
                await q.execute('CREATE SCHEMA pgboss')
        finally:
            await q.close()

    async def test_bootstrap_is_idempotent_and_demands_every_password(self, db):
        with pytest.raises(ValueError, match='no database password for auth'):
            await bootstrap_database(admin_url=db.admin_db_url, passwords={'queue': 'x'})
        from bt.db.bootstrap import DATA_SERVICES

        await bootstrap_database(
            admin_url=db.admin_db_url, passwords={s: 'test-password' for s in (*DATA_SERVICES, 'queue')}
        )


class TestMigrationFailure:
    async def test_a_failing_file_rolls_back_and_names_itself(self, db, tmp_path):
        (tmp_path / '001_ok.sql').write_text('CREATE TABLE mig_ok (id int);')
        (tmp_path / '002_bad.sql').write_text('CREATE TABLE mig_half (id int); SELECT nope;')
        with pytest.raises(Exception, match='migration 002_bad.sql failed'):
            await migrate(db.pool, schema='ledger', dir=tmp_path)
        assert (await db.pool.one("SELECT to_regclass('mig_ok') IS NOT NULL AS t"))['t'] is True
        assert (await db.pool.one("SELECT to_regclass('mig_half') IS NULL AS t"))['t'] is True
        names = [r['name'] for r in await db.pool.query('SELECT name FROM ledger._migrations')]
        assert '001_ok.sql' in names and '002_bad.sql' not in names


class TestAdapters:
    async def test_bigint_is_an_int_and_date_a_string(self, db):
        r = await db.pool.one("SELECT 4500000::bigint AS amount_minor, DATE '2026-10-18' AS d, gen_random_uuid() AS u")
        assert camel(r)['amountMinor'] == 4500000 and r['d'] == '2026-10-18' and isinstance(r['u'], str)

    async def test_numeric_is_an_int_when_integral(self, db):
        r = await db.pool.one('SELECT SUM(x)::numeric AS s, 1.5::numeric AS f FROM generate_series(1, 4) x')
        assert r['s'] == 10 and isinstance(r['s'], int) and r['f'] == Decimal('1.5')

    async def test_timestamptz_is_aware_utc(self, db):
        r = await db.pool.one("SELECT TIMESTAMPTZ '2026-10-18 10:00:00+05:30' AS t")
        assert r['t'] == datetime(2026, 10, 18, 4, 30, tzinfo=UTC) and r['t'].utcoffset().total_seconds() == 0

    async def test_dict_is_jsonb_and_jsonb_helper_takes_arrays(self, db):
        r = await db.pool.one(
            'SELECT $1::jsonb AS a, $2 AS b, jsonb_typeof($2) AS tb, $3 AS c',
            [{'k': [1, 2], 'when': datetime(2026, 1, 2, tzinfo=UTC)}, jsonb([1, 'x', None]), {'n': uuid.UUID(int=1)}],
        )
        assert r['a'] == {'k': [1, 2], 'when': '2026-01-02T00:00:00+00:00'}
        assert r['b'] == [1, 'x', None] and r['tb'] == 'array' and r['c'] == {'n': str(uuid.UUID(int=1))}

    async def test_lists_are_untyped_arrays_so_any_works_on_uuid_and_int(self, db):
        ids = [str(uuid.uuid4()) for _ in range(3)]
        r = await db.pool.one(
            'SELECT (SELECT count(*) FROM unnest($1::uuid[])) AS n, $2::uuid = ANY($1) AS hit, 5 = ANY($3) AS five, '
            'cardinality($4::text[]) AS empty, $5::text[] AS txt',
            [ids, ids[1], [3, 5], [], ['a"b', 'c\\d', None, 'e,f']],
        )
        assert (r['n'], r['hit'], r['five'], r['empty']) == (3, True, True, 0)
        assert r['txt'] == ['a"b', 'c\\d', None, 'e,f']

    async def test_ints_are_untyped_like_node_pg(self, db):
        r = await db.pool.one('SELECT make_interval(days => $1) AS i, $2::bigint * 3 AS big', [3, 2**40])
        assert r['i'].days == 3 and r['big'] == 3 * 2**40
        rows = await db.pool.query('SELECT x FROM generate_series(1, 10) x LIMIT $1', [2])
        assert len(rows) == 2

    async def test_percent_signs_in_sql_are_literal(self, db):
        r = await db.pool.one("SELECT 'a' LIKE 'a%' AS hit, $1::text || '%' AS s, 7 % 4 AS m", ['x'])
        assert (r['hit'], r['s'], r['m']) == (True, 'x%', 3)


class TestTx:
    async def test_one_maybe_one_execute_and_savepoint(self, db):
        async with db.pool.system_tx() as tx:
            u = str(uuid.uuid4())
            assert await tx.execute("INSERT INTO notes (user_id, body) VALUES ($1, 'a'), ($1, 'b')", [u]) == 2
            assert await tx.maybe_one('SELECT 1 FROM notes WHERE body = $1', ['nope']) is None
            with pytest.raises(NoRows):
                await tx.one('SELECT 1 FROM notes WHERE body = $1', ['nope'])
            with pytest.raises(Exception, match='violates not-null'):
                async with tx.savepoint():
                    await tx.execute('INSERT INTO notes (user_id, body) VALUES ($1, NULL)', [u])
            assert await tx.execute('DELETE FROM notes WHERE user_id = $1', [u]) == 2  # transaction still usable

    async def test_a_raised_error_rolls_everything_back(self, db):
        u = str(uuid.uuid4())
        with pytest.raises(RuntimeError):
            async with db.pool.user_tx(u) as tx:
                await tx.execute("INSERT INTO notes (user_id, body) VALUES ($1, 'gone')", [u])
                raise RuntimeError('boom')
        async with db.pool.user_tx(u) as tx:
            assert await tx.many('SELECT * FROM notes') == []

    async def test_wrong_parameter_counts_are_refused(self, db):
        with pytest.raises(ValueError):
            await db.pool.query('SELECT $1, $2', [1])
        with pytest.raises(ValueError):
            await db.pool.query('SELECT $1', [1, 2])

    async def test_admin_pool_sees_behind_rls(self, db):
        assert (await db.admin_pool.one('SELECT count(*) AS n FROM ledger.notes'))['n'] >= 2


class TestPlaceholders:
    def test_rewrites_and_escapes(self):
        sql, used = rewrite_placeholders('SELECT $1, $1, $2 WHERE a LIKE \'5%\' AND b % 2 = 0')
        assert sql == "SELECT %(p1)s, %(p1)s, %(p2)s WHERE a LIKE '5%%' AND b %% 2 = 0" and used == (1, 2)

    def test_leaves_literals_comments_and_dollar_quotes_alone(self):
        src = (
            "SELECT 'it''s $1', \"col$1\", $$ body $1 % $$, $tag$ $2 $tag$, e'\\' $3', x$1 "
            '/* $4 /* nested $5 */ still $6 */ -- $7\n, $2'
        )
        sql, used = rewrite_placeholders(src)
        assert used == (2,)
        assert sql.count('%(p2)s') == 1 and '$1' in sql and '$7' in sql and '$6' in sql

    def test_no_params_means_sql_goes_through_untouched(self):
        assert bind('SELECT 1; SELECT 2 % 3', None) == ('SELECT 1; SELECT 2 % 3', None)
        assert bind('DO $$ BEGIN RAISE NOTICE \'%\', 1; END $$', []) == ('DO $$ BEGIN RAISE NOTICE \'%\', 1; END $$', None)

    def test_gaps_are_refused(self):
        with pytest.raises(ValueError):
            bind('SELECT $1, $3', [1, 2, 3])


class TestHelpers:
    def test_where_builds_placeholders(self):
        w = Where().add('a = $?', 1).add('b = $? OR b = $?', 2, 3)
        assert w.sql == 'WHERE a = $1 AND b = $2 OR b = $3'
        assert w.params == [1, 2, 3]
        assert w.and_ == 'AND a = $1 AND b = $2 OR b = $3'
        assert Where().sql == '' and Where().and_ == ''

    def test_where_continues_after_existing_params(self):
        w = Where(['user']).add('x = $?', 9)
        assert w.sql == 'WHERE x = $2' and w.params == ['user', 9]

    def test_camel(self):
        assert camel({'amount_minor': 1, 'a1_b2': 2, 'id': 3}) == {'amountMinor': 1, 'a1B2': 2, 'id': 3}
        assert camel_all([{'x_y': 1}]) == [{'xY': 1}]

    def test_test_urls(self):
        assert url_for('postgres://a:b@h:1/d', database='x') == 'postgres://a:b@h:1/x'
        assert url_for('postgres://a:b@h:1/d', user='u', password='p w') == 'postgres://u:p%20w@h:1/d'
        assert admin_url().startswith('postgres')
