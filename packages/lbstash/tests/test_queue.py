import asyncio
import itertools
import time
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
import pytest_asyncio
from lbstash.common import create_logger
from lbstash.contracts import BudgetEvaluateJob, CreditAddedEvent
from lbstash.db import create_pool
from lbstash.db.testing import create_test_database
from lbstash.queue import InMemoryBus, Messaging
from pydantic import ValidationError

MIGRATIONS = str(Path(__file__).parent / 'migrations')
LOG = create_logger('test', 'silent')


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def qdb():
    """A database for service `planning`, which is a real subscriber of `credit.added`."""
    t = await create_test_database('planning', MIGRATIONS)
    yield t
    await t.drop()


@pytest_asyncio.fixture(scope='module', loop_scope='session')
async def qpool(qdb):
    """The queue role's pool, to look at `queue.job` and `queue.schedule`."""
    p = await create_pool(qdb.queue_url, name='t-queue-peek', max_size=2)
    yield p
    await p.close()


@pytest_asyncio.fixture(loop_scope='session')
async def bus(qdb):
    """Factory for `Messaging` instances (several = several replicas); all are stopped after the test."""
    made: list[Messaging] = []

    async def make(**kw) -> Messaging:
        opts = {'relay_interval_s': 0.05, 'poll_interval_s': 0.05, 'retry_base_delay_s': 0.1, 'retry_max_delay_s': 0.4}
        m = await Messaging.start(service='planning', pool=qdb.pool, queue_url=qdb.queue_url, log=LOG, **(opts | kw))
        made.append(m)
        return m

    yield make
    for m in made:
        await m.stop()


async def wait_for(fn: Callable[[], bool | Awaitable[bool]], seconds: float = 10) -> None:
    deadline = time.monotonic() + seconds
    while True:
        r = fn()
        if (await r) if isinstance(r, Awaitable) else r:
            return
        if time.monotonic() > deadline:
            raise TimeoutError('condition not met')
        await asyncio.sleep(0.02)


def job(period: str = 'p') -> BudgetEvaluateJob:
    return BudgetEvaluateJob(user_id=str(uuid.uuid4()), category_id=str(uuid.uuid4()), period_key=period)


def qname() -> str:
    return f'test.{uuid.uuid4().hex[:8]}'


async def enqueue(qdb, m: Messaging, queue: str, period: str = 'p', **kw) -> None:
    async with qdb.pool.tx() as tx:
        await m.enqueue(tx, 'budget.evaluate', job(period), queue=queue, **kw)


async def jobs(qpool, queue: str) -> list[dict]:
    return await qpool.query('SELECT * FROM queue.job WHERE queue = $1 ORDER BY id', [queue])


class TestOutboxToQueue:
    async def test_an_event_emitted_in_a_transaction_reaches_a_subscriber_after_commit(self, qdb, bus):
        m = await bus()
        got: list[str] = []

        async def handler(p: CreditAddedEvent) -> None:
            got.append(p.transaction_id)

        await m.on_event('credit.added', handler)
        tx_id = str(uuid.uuid4())
        async with qdb.pool.tx() as tx:
            await m.emit(tx, 'credit.added', CreditAddedEvent(
                user_id=str(uuid.uuid4()), transaction_id=tx_id, month='2026-10', amount_minor=100, add_to_plan=True))
            await asyncio.sleep(0.3)  # the relay is running, but the row is not committed yet
            assert got == []
        await wait_for(lambda: tx_id in got)

    async def test_an_event_fans_out_to_one_job_per_subscriber_queue(self, qdb, qpool, bus):
        m = await bus()
        u = str(uuid.uuid4())
        async with qdb.pool.tx() as tx:
            await m.emit(tx, 'account.deleted', {'userId': u})

        async def everywhere() -> bool:
            for svc in ('transactions', 'ingest', 'planning', 'recurring', 'telegram'):
                if not any(r['payload']['userId'] == u for r in await jobs(qpool, f'{svc}.account.deleted')):
                    return False
            return True

        await wait_for(everywhere)
        assert not any(r['payload'].get('userId') == u for r in await jobs(qpool, 'auth.account.deleted'))

    async def test_a_rolled_back_transaction_emits_nothing(self, qdb, bus):
        m, q = await bus(), qname()
        got: list[str] = []

        async def handler(p: BudgetEvaluateJob) -> None:
            got.append(p.period_key)

        await m.on_job('budget.evaluate', handler, queue=q)
        with pytest.raises(RuntimeError, match='boom'):
            async with qdb.pool.tx() as tx:
                await m.enqueue(tx, 'budget.evaluate', job('rolled-back'), queue=q)
                raise RuntimeError('boom')
        await enqueue(qdb, m, q, 'kept', key='k1')
        await wait_for(lambda: 'kept' in got)
        assert got == ['kept']

    async def test_rejects_payloads_that_break_the_contract(self, qdb, bus):
        m = await bus()
        with pytest.raises(ValidationError):
            await m.enqueue(qdb.pool, 'budget.evaluate', {'userId': 'nope'})
        with pytest.raises(ValueError, match='unknown job'):
            await m.enqueue(qdb.pool, 'no.such.job', {})
        with pytest.raises(ValueError, match='unknown event'):
            await m.emit(qdb.pool, 'no.such.event', {})

    async def test_on_event_refuses_an_event_the_service_does_not_subscribe_to(self, bus):
        m = await bus()

        async def handler(p) -> None: ...

        with pytest.raises(ValueError, match='not subscribed'):
            await m.on_event('audit.record', handler)

    async def test_purge_outbox_deletes_only_old_published_rows(self, qdb, bus):
        m = await bus()
        await qdb.pool.execute("INSERT INTO outbox (kind, name, payload, published_at) VALUES ('job', 'old', '{}', now() - interval '2 days')")
        await qdb.pool.execute("INSERT INTO outbox (kind, name, payload, published_at) VALUES ('job', 'new', '{}', now())")
        assert await m.purge_outbox() >= 1
        assert await qdb.pool.query("SELECT 1 FROM outbox WHERE name = 'old'") == []
        assert len(await qdb.pool.query("SELECT 1 FROM outbox WHERE name = 'new'")) == 1


class TestRetries:
    async def test_a_failing_handler_is_retried_with_doubling_backoff_then_succeeds(self, qdb, bus):
        m, q = await bus(retry_base_delay_s=0.2, retry_max_delay_s=5), qname()
        times: list[float] = []

        async def handler(p: BudgetEvaluateJob) -> None:
            times.append(time.monotonic())
            if len(times) < 4:
                raise RuntimeError('try again')

        await m.on_job('budget.evaluate', handler, queue=q)
        await enqueue(qdb, m, q)
        await wait_for(lambda: len(times) == 4)
        gaps = [b - a for a, b in itertools.pairwise(times)]
        assert 0.2 <= gaps[0] < 0.5 and 0.4 <= gaps[1] < 0.8 and 0.8 <= gaps[2] < 1.4  # 0.2, 0.4, 0.8 plus polling slack

    async def test_the_delay_is_capped(self, qdb, qpool, bus):
        m, q = await bus(retry_base_delay_s=0.1, retry_max_delay_s=0.15), qname()
        calls = []

        async def handler(p) -> None:
            calls.append(time.monotonic())
            raise RuntimeError('x')

        await m.on_job('budget.evaluate', handler, queue=q, retry_limit=3)
        await enqueue(qdb, m, q)
        await wait_for(lambda: len(calls) == 4)
        assert calls[3] - calls[2] < 0.4  # would be 0.4 s uncapped

    async def test_gives_up_after_the_retry_limit_and_keeps_the_failed_row(self, qdb, qpool, bus):
        m, q = await bus(), qname()
        calls: list[int] = []

        async def handler(p) -> None:
            calls.append(1)
            raise ValueError('never works')

        await m.on_job('budget.evaluate', handler, queue=q, retry_limit=2)
        await enqueue(qdb, m, q)

        async def failed() -> bool:
            return [r['state'] for r in await jobs(qpool, q)] == ['failed']

        await wait_for(failed)
        (row,) = await jobs(qpool, q)
        assert len(calls) == 3 and row['retry_count'] == 2 and row['last_error'] == 'ValueError: never works'
        await asyncio.sleep(0.3)
        assert len(calls) == 3

    async def test_a_payload_that_does_not_validate_fails_like_a_handler_error(self, qdb, qpool, bus):
        m, q = await bus(), qname()
        seen = []

        async def handler(p) -> None:
            seen.append(p)

        await m.on_job('budget.evaluate', handler, queue=q, retry_limit=0)
        await qpool.execute("INSERT INTO queue.job (queue, payload) VALUES ($1, '{\"bad\": 1}')", [q])
        await wait_for(lambda: _state(qpool, q, 'failed'))
        assert seen == []

    async def test_a_job_abandoned_by_a_dead_worker_is_retried(self, qdb, qpool, bus):
        m, q = await bus(expire_seconds=0.2), qname()
        got: list[str] = []

        async def handler(p: BudgetEvaluateJob) -> None:
            got.append(p.period_key)

        await qpool.execute(
            "INSERT INTO queue.job (queue, payload, state, started_at) VALUES ($1, $2, 'active', now() - interval '1 hour')",
            [q, {'userId': str(uuid.uuid4()), 'categoryId': str(uuid.uuid4()), 'periodKey': 'stuck'}],
        )
        await m.on_job('budget.evaluate', handler, queue=q)
        assert await m.expire_stuck() == 1
        await wait_for(lambda: got == ['stuck'])


async def _state(qpool, q: str, state: str) -> bool:
    return [r['state'] for r in await jobs(qpool, q)] == [state]


class TestKeyCollapseAndDelay:
    async def test_a_burst_with_one_key_collapses_to_one_queued_job(self, qdb, qpool, bus):
        m, q = await bus(), qname()
        for i in range(5):
            await enqueue(qdb, m, q, f'p{i}', key='same', start_after_seconds=1)
        await enqueue(qdb, m, q, 'other', key='different', start_after_seconds=1)
        await wait_for(lambda: _count(qpool, q, 2))
        await asyncio.sleep(0.3)
        assert await _count(qpool, q, 2)

    async def test_a_new_job_with_the_key_is_accepted_once_the_first_has_started(self, qdb, qpool, bus):
        m, q = await bus(), qname()
        started, release, done = asyncio.Event(), asyncio.Event(), []

        async def handler(p: BudgetEvaluateJob) -> None:
            started.set()
            await release.wait()
            done.append(p.period_key)

        await m.on_job('budget.evaluate', handler, queue=q, policy='short')
        await enqueue(qdb, m, q, 'first', key='k')
        await asyncio.wait_for(started.wait(), 5)
        await enqueue(qdb, m, q, 'second', key='k')
        await enqueue(qdb, m, q, 'third', key='k')  # collapses into 'second'

        async def relayed() -> bool:
            return (await qdb.pool.one('SELECT count(*) AS n FROM outbox WHERE published_at IS NULL'))['n'] == 0

        await wait_for(relayed)  # both reached the queue while 'first' is still running
        release.set()
        await wait_for(lambda: done == ['first', 'second'])
        await asyncio.sleep(0.3)
        assert done == ['first', 'second']

    async def test_start_after_seconds_delays_the_job(self, qdb, bus):
        m, q = await bus(), qname()
        times: list[float] = []

        async def handler(p) -> None:
            times.append(time.monotonic())

        await m.on_job('budget.evaluate', handler, queue=q)
        t0 = time.monotonic()
        await enqueue(qdb, m, q, start_after_seconds=1)
        await asyncio.sleep(0.6)
        assert times == []
        await wait_for(lambda: len(times) == 1)
        assert times[0] - t0 >= 0.9


async def _count(qpool, q: str, n: int) -> bool:
    return len(await jobs(qpool, q)) == n


class TestWorkers:
    async def test_two_workers_never_take_the_same_job(self, qdb, qpool, bus):
        a, b, q = await bus(), await bus(), qname()
        seen: dict[str, list[str]] = {'a': [], 'b': []}

        def handler(who: str):
            async def h(p: BudgetEvaluateJob) -> None:
                seen[who].append(p.period_key)
                await asyncio.sleep(0.02)

            return h

        await a.on_job('budget.evaluate', handler('a'), queue=q)
        await b.on_job('budget.evaluate', handler('b'), queue=q)
        for i in range(30):
            await enqueue(qdb, a, q, f'job-{i}')
        await wait_for(lambda: len(seen['a']) + len(seen['b']) == 30)
        await asyncio.sleep(0.3)
        every = seen['a'] + seen['b']
        assert sorted(every) == sorted(f'job-{i}' for i in range(30))  # each exactly once
        assert seen['a'] and seen['b']

    async def test_concurrency_runs_handlers_in_parallel(self, qdb, bus):
        m, q = await bus(), qname()
        running = peak = 0

        async def handler(p) -> None:
            nonlocal running, peak
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0.2)
            running -= 1

        await m.on_job('budget.evaluate', handler, queue=q, concurrency=3)
        for i in range(6):
            await enqueue(qdb, m, q, f'c{i}')
        await wait_for(lambda: running == 0 and peak > 0, 10)
        await asyncio.sleep(0.5)
        assert peak == 3

    async def test_stop_lets_the_running_handler_finish(self, qdb, qpool, bus):
        m, q = await bus(), qname()
        started, finished = asyncio.Event(), []

        async def handler(p) -> None:
            started.set()
            await asyncio.sleep(0.5)
            finished.append(1)

        await m.on_job('budget.evaluate', handler, queue=q)
        await enqueue(qdb, m, q)
        await asyncio.wait_for(started.wait(), 5)
        await m.stop()
        assert finished == [1]
        assert [r['state'] for r in await jobs(qpool, q)] == ['completed']

    async def test_stop_publishes_what_is_left_in_the_outbox(self, qdb, qpool, bus):
        m, q = await bus(relay_interval_s=30), qname()
        await asyncio.sleep(0.1)  # let the relay loop do its first (empty) pass and go to sleep
        await enqueue(qdb, m, q, 'late')
        await m.stop()
        assert [r['payload']['periodKey'] for r in await jobs(qpool, q)] == ['late']


class TestCron:
    async def test_a_due_schedule_enqueues_one_job_and_moves_to_the_next_tick(self, qdb, qpool, bus):
        m, q = await bus(), qname()
        got: list[dict] = []

        async def handler(p) -> None:
            got.append(p)

        await m.on_job('retention.sweep', handler, queue=q)
        await m.schedule(q, '*/5 * * * *', {}, 'Asia/Kolkata')
        (s,) = await qpool.query('SELECT * FROM queue.schedule WHERE queue = $1', [q])
        assert s['tz'] == 'Asia/Kolkata' and s['next_run_at'].minute % 5 == 0 and s['next_run_at'] > s['updated_at']
        await asyncio.sleep(0.2)
        assert got == []
        await qpool.execute("UPDATE queue.schedule SET next_run_at = now() - interval '1 second' WHERE queue = $1", [q])
        await wait_for(lambda: len(got) == 1)
        await asyncio.sleep(0.3)
        assert len(got) == 1
        (s2,) = await qpool.query('SELECT next_run_at > now() AS future FROM queue.schedule WHERE queue = $1', [q])
        assert s2['future']

    async def test_a_tick_fires_once_across_replicas(self, qdb, qpool, bus):
        a, b, c, q = await bus(), await bus(), await bus(), qname()
        for m in (a, b, c):
            await m.schedule(q, '0 3 * * *')
        await qpool.execute("UPDATE queue.schedule SET next_run_at = now() - interval '1 second' WHERE queue = $1", [q])
        fired = await asyncio.gather(*(m.tick_schedules() for m in (a, b, c)))
        assert sum(fired) == 1
        assert len(await jobs(qpool, q)) == 1

    async def test_reregistering_the_same_cron_keeps_the_next_tick_and_changing_it_moves_it(self, qdb, qpool, bus):
        m, q = await bus(), qname()
        await m.schedule(q, '0 3 * * *')
        (first,) = await qpool.query('SELECT next_run_at FROM queue.schedule WHERE queue = $1', [q])
        await qpool.execute("UPDATE queue.schedule SET next_run_at = next_run_at + interval '1 day' WHERE queue = $1", [q])
        await m.schedule(q, '0 3 * * *')
        (same,) = await qpool.query('SELECT next_run_at FROM queue.schedule WHERE queue = $1', [q])
        assert same['next_run_at'] > first['next_run_at']
        await m.schedule(q, '0 4 * * *')
        (moved,) = await qpool.query('SELECT next_run_at FROM queue.schedule WHERE queue = $1', [q])
        assert moved['next_run_at'].hour in (4, 3, 22, 23) and moved['next_run_at'] != same['next_run_at']

    async def test_a_bad_cron_is_refused(self, bus):
        m = await bus()
        with pytest.raises(ValueError, match='cron'):
            await m.schedule(qname(), 'every day')

    async def test_timezone_decides_the_tick(self, qdb, qpool, bus):
        m, q = await bus(), qname()
        await m.schedule(q, '30 2 * * *', {}, 'Asia/Kolkata')
        (s,) = await qpool.query("SELECT (next_run_at AT TIME ZONE 'Asia/Kolkata')::time AS t FROM queue.schedule WHERE queue = $1", [q])
        assert str(s['t']) == '02:30:00'


class TestInMemoryBus:
    async def test_records_and_drains(self):
        bus = InMemoryBus()
        seen: list[str] = []

        async def on_deleted(p) -> None:
            seen.append(p.user_id)

        await bus.on_event('account.deleted', on_deleted)
        u = str(uuid.uuid4())
        await bus.emit(None, 'account.deleted', {'userId': u})  # type: ignore[arg-type]
        assert [p.user_id for p in bus.events_of('account.deleted')] == [u]
        assert bus.events[0].event == 'account.deleted'
        await bus.drain()
        assert seen == [u] and bus.events == []

    async def test_validates_payloads_and_names(self):
        bus = InMemoryBus()
        with pytest.raises(ValidationError):
            await bus.enqueue(None, 'budget.evaluate', {'userId': 'nope'})  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            await bus.emit(None, 'no.such.event', {})  # type: ignore[arg-type]

    async def test_jobs_go_to_their_queue_and_drain_runs_them(self):
        bus = InMemoryBus()
        got: list[str] = []

        async def handler(p) -> None:
            got.append(p.period_key)

        await bus.on_job('budget.evaluate', handler, queue='q1')
        await bus.enqueue(None, 'budget.evaluate', job('a'), key='k', queue='q1')  # type: ignore[arg-type]
        await bus.enqueue(None, 'budget.evaluate', job('ignored'))  # type: ignore[arg-type]  # no handler on that queue
        assert [(j.job, j.queue, j.key) for j in bus.jobs] == [('budget.evaluate', 'q1', 'k'), ('budget.evaluate', 'budget.evaluate', None)]
        assert [p.period_key for p in bus.jobs_of('budget.evaluate')] == ['a', 'ignored']
        await bus.drain()
        assert got == ['a'] and bus.jobs == []

    async def test_schedules_are_recorded_and_clear_keeps_them(self):
        bus = InMemoryBus()
        await bus.schedule('retention.sweep.transactions', '30 3 * * *', {}, 'Asia/Kolkata')
        await bus.emit(None, 'account.deleted', {'userId': str(uuid.uuid4())})  # type: ignore[arg-type]
        bus.clear()
        assert bus.events == [] and [(s.queue, s.cron, s.tz) for s in bus.schedules] == [('retention.sweep.transactions', '30 3 * * *', 'Asia/Kolkata')]
