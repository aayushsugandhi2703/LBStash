"""Transactional outbox plus a small Postgres job queue.

Producing: `emit` / `enqueue` write to `<service>.outbox` in the caller's transaction. A relay (about every 500 ms, `FOR UPDATE SKIP LOCKED`) moves rows into `queue.job`, one job per subscriber queue `<service>.<event>`.

Consuming: workers claim jobs with `SKIP LOCKED`. A failing handler is retried with exponential backoff (2 s up to 600 s, 5 retries), then marked `failed`. Delivery is at-least-once, so consumers must be idempotent.

Cron: one row per queue; whichever replica wins the `UPDATE ... WHERE next_run_at = <old>` fires the tick.
"""

import asyncio
import contextlib
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter
from pydantic import BaseModel

from bt.common import Logger
from bt.contracts import EVENTS, JOBS, SUBSCRIPTIONS, dump, event_queue
from bt.db import Pool, Queryable, create_pool

from .bus import Handler, Payload, Policy, validate

RETRY_LIMIT = 5
RETRY_DELAY_SECONDS = 2.0
RETRY_DELAY_MAX_SECONDS = 600.0
# an active job whose worker vanished (crash, kill -9) counts as a failed attempt after this long
EXPIRE_SECONDS = 15 * 60
COMPLETED_KEEP = '1 day'

QUEUE_DDL = """
SELECT pg_advisory_xact_lock(hashtext('bt:queue-ddl'));
CREATE TABLE IF NOT EXISTS queue.job (
  id bigserial PRIMARY KEY,
  queue text NOT NULL,
  payload jsonb NOT NULL,
  singleton_key text,
  state text NOT NULL DEFAULT 'queued' CHECK (state IN ('queued','retry','active','completed','failed')),
  retry_count int NOT NULL DEFAULT 0,
  start_after timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz,
  last_error text
);
CREATE INDEX IF NOT EXISTS job_fetch ON queue.job (queue, start_after, id) WHERE state IN ('queued','retry');
CREATE INDEX IF NOT EXISTS job_active ON queue.job (queue, started_at) WHERE state = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS job_one_queued_per_key ON queue.job (queue, singleton_key)
  WHERE state = 'queued' AND singleton_key IS NOT NULL;
CREATE TABLE IF NOT EXISTS queue.schedule (
  queue text PRIMARY KEY,
  cron text NOT NULL,
  tz text NOT NULL,
  payload jsonb NOT NULL,
  next_run_at timestamptz NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now()
);
"""

OUTBOX_DDL = """
SELECT pg_advisory_xact_lock(hashtext('bt:outbox:' || current_schema()));
CREATE TABLE IF NOT EXISTS outbox (
  id bigserial PRIMARY KEY,
  kind text NOT NULL CHECK (kind IN ('event','job')),
  name text NOT NULL,
  payload jsonb NOT NULL,
  singleton_key text,
  start_after_seconds int,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);
CREATE INDEX IF NOT EXISTS outbox_unpublished ON outbox (id) WHERE published_at IS NULL;
"""

# A queued job with the same key swallows the new one, so bursts collapse into one run.
INSERT_JOB = """
INSERT INTO queue.job (queue, payload, singleton_key, start_after)
VALUES ($1, $2, $3, now() + make_interval(secs => $4::float8))
ON CONFLICT (queue, singleton_key) WHERE state = 'queued' AND singleton_key IS NOT NULL DO NOTHING
"""

CLAIM = """
UPDATE queue.job SET state = 'active', started_at = now()
WHERE id = (
  SELECT id FROM queue.job
  WHERE queue = $1 AND state IN ('queued', 'retry') AND start_after <= now()
  ORDER BY start_after, id LIMIT 1 FOR UPDATE SKIP LOCKED)
RETURNING id, payload, retry_count
"""

# One failed attempt: retry with backoff, or mark 'failed' (row kept) at the retry limit.
# $1 retry limit, $2 base delay, $3 max delay, $4 error text; the caller appends the WHERE clause ($5...).
FAIL_ATTEMPT = """
UPDATE queue.job SET
  state = CASE WHEN retry_count >= $1 THEN 'failed' ELSE 'retry' END,
  completed_at = CASE WHEN retry_count >= $1 THEN now() END,
  start_after = CASE WHEN retry_count >= $1 THEN start_after
                ELSE now() + make_interval(secs => least($3::float8, $2::float8 * power(2, retry_count))) END,
  retry_count = CASE WHEN retry_count >= $1 THEN retry_count ELSE retry_count + 1 END,
  last_error = $4
"""


def _next_run(cron: str, tz: str, after: datetime) -> datetime:
    """The first cron tick after `after` (fields read in `tz`), as a UTC instant."""
    return croniter(cron, after.astimezone(ZoneInfo(tz))).get_next(datetime).astimezone(UTC)


class Messaging:
    """The real `MessageBus`. Create it with `await Messaging.start(...)`."""

    def __init__(
        self,
        *,
        service: str,
        pool: Pool,
        queue_pool: Pool,
        log: Logger,
        relay_interval_s: float,
        poll_interval_s: float,
        retry_base_delay_s: float,
        retry_max_delay_s: float,
        expire_seconds: float,
    ) -> None:
        self.service = service
        self._pool = pool
        self._queue = queue_pool
        self._log = log
        self._relay_interval = relay_interval_s
        self._poll = poll_interval_s
        self._retry_base = retry_base_delay_s
        self._retry_max = retry_max_delay_s
        self._expire = expire_seconds
        self._stopping = asyncio.Event()
        self._tasks: list[asyncio.Task[None]] = []
        self._worker_queues: dict[str, int] = {}  # queue -> retry limit (for the expiry sweep)
        self._schedules: set[str] = set()

    @classmethod
    async def start(
        cls,
        *,
        service: str,
        pool: Pool,
        queue_url: str,
        log: Logger,
        relay_interval_s: float = 0.5,
        poll_interval_s: float = 1.0,
        retry_base_delay_s: float = RETRY_DELAY_SECONDS,
        retry_max_delay_s: float = RETRY_DELAY_MAX_SECONDS,
        expire_seconds: float = EXPIRE_SECONDS,
    ) -> 'Messaging':
        """Create the outbox and queue tables if needed, then start the relay and maintenance loops."""
        queue_pool = await create_pool(queue_url, name=f'{service}-queue', max_size=10)
        m = cls(
            service=service, pool=pool, queue_pool=queue_pool, log=log, relay_interval_s=relay_interval_s,
            poll_interval_s=poll_interval_s, retry_base_delay_s=retry_base_delay_s,
            retry_max_delay_s=retry_max_delay_s, expire_seconds=expire_seconds,
        )  # fmt: skip
        try:
            # plain DDL on purpose: every service gets the same outbox without copying SQL into its migrations
            await pool.execute(OUTBOX_DDL)
            await queue_pool.execute(QUEUE_DDL)
        except BaseException:
            await queue_pool.close()
            raise
        m._spawn(m._relay_loop())
        m._spawn(m._maintenance_loop())
        return m

    async def emit(self, tx: Queryable, event: str, payload: Payload) -> None:
        """Insert the event into the outbox inside the caller's transaction."""
        body = dump(validate(EVENTS, 'event', event, payload))
        await tx.execute("INSERT INTO outbox (kind, name, payload) VALUES ('event', $1, $2)", [event, body])

    async def enqueue(
        self,
        tx: Queryable,
        job: str,
        payload: Payload,
        *,
        key: str | None = None,
        start_after_seconds: float | None = None,
        queue: str | None = None,
    ) -> None:
        """Insert the job into the outbox inside the caller's transaction."""
        body = dump(validate(JOBS, 'job', job, payload))
        await tx.execute(
            "INSERT INTO outbox (kind, name, payload, singleton_key, start_after_seconds) VALUES ('job', $1, $2, $3, $4)",
            [queue or job, body, key, int(start_after_seconds) if start_after_seconds else None],
        )

    async def relay(self) -> int:
        """Move unpublished outbox rows to `queue.job` (one batch of up to 100); returns how many were moved."""
        try:
            async with self._pool.tx() as tx:
                rows = await tx.query(
                    'SELECT id, kind, name, payload, singleton_key, start_after_seconds FROM outbox '
                    'WHERE published_at IS NULL ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED'
                )
                if not rows:
                    return 0
                async with self._queue.tx() as q:
                    for r in rows:
                        if r['kind'] == 'event':
                            subscribers = SUBSCRIPTIONS.get(r['name'], ())
                            if not subscribers:
                                self._log.warning('event has no subscribers', event=r['name'])
                            for svc in subscribers:
                                await q.execute(INSERT_JOB, [event_queue(svc, r['name']), r['payload'], None, 0])
                        else:
                            await q.execute(
                                INSERT_JOB, [r['name'], r['payload'], r['singleton_key'], r['start_after_seconds'] or 0]
                            )
                # If this commit fails the rows are relayed again next time: duplicates, never losses (at-least-once).
                await tx.execute('UPDATE outbox SET published_at = now() WHERE id = ANY($1)', [[r['id'] for r in rows]])
                return len(rows)
        except Exception as e:  # noqa: BLE001 - the relay must survive any failure and try again
            self._log.warning('outbox relay failed, will retry', err=e)
            return 0

    async def purge_outbox(self) -> int:
        """Delete published outbox rows older than a day (call from the nightly sweep)."""
        return await self._pool.execute("DELETE FROM outbox WHERE published_at < now() - interval '1 day'")

    async def on_event(self, event: str, handler: Handler) -> None:
        """Consume this service's queue for `event` (it must be listed in SUBSCRIPTIONS for this service)."""
        if self.service not in SUBSCRIPTIONS.get(event, ()):
            raise ValueError(f'{self.service} is not subscribed to {event} (see SUBSCRIPTIONS)')
        self._start_workers(event_queue(self.service, event), EVENTS[event], handler, 1, RETRY_LIMIT)

    async def on_job(
        self,
        job: str,
        handler: Handler,
        *,
        queue: str | None = None,
        policy: Policy = 'standard',
        concurrency: int = 1,
        retry_limit: int = RETRY_LIMIT,
    ) -> None:
        """Consume a job queue. `policy` is ignored: a `key` always collapses queued jobs."""
        if job not in JOBS:
            raise ValueError(f'unknown job: {job}')
        self._start_workers(queue or job, JOBS[job], handler, max(1, concurrency), retry_limit)

    def _start_workers(
        self, queue: str, model: type[BaseModel], handler: Handler, concurrency: int, retry_limit: int
    ) -> None:
        self._worker_queues[queue] = retry_limit
        for _ in range(concurrency):
            self._spawn(self._worker_loop(queue, model, handler, retry_limit))

    async def _worker_loop(self, queue: str, model: type[BaseModel], handler: Handler, retry_limit: int) -> None:
        while not self._stopping.is_set():
            try:
                async with self._queue.tx() as tx:
                    job = await tx.maybe_one(CLAIM, [queue])
            except Exception as e:  # noqa: BLE001 - a worker loop must survive any polling failure
                self._log.warning('queue poll failed', queue=queue, err=e)
                job = None
            if job is None:
                await self._sleep(self._poll)
                continue
            try:
                await handler(model.model_validate(job['payload']))
            except Exception as e:  # noqa: BLE001 - any handler error means retry
                # only the error type in the log: its text could carry user data
                self._log.warning('job failed', queue=queue, job_id=job['id'], attempt=job['retry_count'] + 1,
                                  err_type=type(e).__name__)  # fmt: skip
                await self._finish(
                    FAIL_ATTEMPT + ' WHERE id = $5',
                    [retry_limit, self._retry_base, self._retry_max, f'{type(e).__name__}: {e}'[:500], job['id']],
                )
            else:
                await self._finish("UPDATE queue.job SET state = 'completed', completed_at = now() WHERE id = $1", [job['id']])

    async def _finish(self, sql: str, params: list[Any]) -> None:
        try:
            await self._queue.execute(sql, params)
        except Exception as e:  # noqa: BLE001 - the row stays active and the expiry sweep will retry it
            self._log.error('could not record job result', err=e)

    async def schedule(self, queue: str, cron: str, payload: dict[str, Any] | None = None, tz: str = 'UTC') -> None:
        """Run a job on `queue` on a cron (5 fields, read in `tz`). Re-registering the same cron keeps the next tick."""
        if not croniter.is_valid(cron):
            raise ValueError(f'not a cron expression: {cron}')
        first = _next_run(cron, tz, datetime.now(UTC))
        await self._queue.execute(
            'INSERT INTO queue.schedule (queue, cron, tz, payload, next_run_at) VALUES ($1, $2, $3, $4, $5) '
            'ON CONFLICT (queue) DO UPDATE SET cron = EXCLUDED.cron, tz = EXCLUDED.tz, payload = EXCLUDED.payload, '
            'next_run_at = CASE WHEN schedule.cron = EXCLUDED.cron AND schedule.tz = EXCLUDED.tz '
            'THEN schedule.next_run_at ELSE EXCLUDED.next_run_at END, updated_at = now()',
            [queue, cron, tz, payload or {}, first],
        )
        if not self._schedules:
            self._spawn(self._scheduler_loop())
        self._schedules.add(queue)

    async def tick_schedules(self) -> int:
        """Fire every due schedule of this service once; returns how many ticks this process fired."""
        if not self._schedules:
            return 0
        fired = 0
        async with self._queue.tx() as q:
            due = await q.query(
                'SELECT queue, cron, tz, payload, next_run_at FROM queue.schedule '
                'WHERE queue = ANY($1) AND next_run_at <= now()', [sorted(self._schedules)],
            )  # fmt: skip
        for s in due:
            # a long outage fires one tick, not one per missed slot
            following = _next_run(s['cron'], s['tz'], datetime.now(UTC))
            async with self._queue.tx() as q:
                won = await q.execute(
                    'UPDATE queue.schedule SET next_run_at = $1 WHERE queue = $2 AND next_run_at = $3',
                    [following, s['queue'], s['next_run_at']],
                )
                if won:
                    await q.execute(INSERT_JOB, [s['queue'], s['payload'], None, 0])
                    fired += 1
        return fired

    async def _scheduler_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.tick_schedules()
            except Exception as e:  # noqa: BLE001 - the scheduler must survive any failure
                self._log.warning('scheduler failed, will retry', err=e)
            await self._sleep(self._poll)

    async def expire_stuck(self) -> int:
        """Count jobs left `active` by a dead worker as a failed attempt; returns how many."""
        n = 0
        for queue, limit in self._worker_queues.items():
            n += await self._queue.execute(
                FAIL_ATTEMPT + " WHERE queue = $5 AND state = 'active' AND started_at < now() - make_interval(secs => $6::float8)",
                [limit, self._retry_base, self._retry_max, 'expired: worker did not finish', queue, self._expire],
            )
        return n

    async def _maintenance_loop(self) -> None:
        last_purge = 0.0
        loop = asyncio.get_running_loop()
        while not self._stopping.is_set():
            await self._sleep(30)
            try:
                await self.expire_stuck()
                if loop.time() - last_purge > 600:
                    last_purge = loop.time()
                    await self._queue.execute(
                        f"DELETE FROM queue.job WHERE state = 'completed' AND completed_at < now() - interval '{COMPLETED_KEEP}'"
                    )
            except Exception as e:  # noqa: BLE001 - maintenance must survive any failure
                self._log.warning('queue maintenance failed', err=e)

    async def _relay_loop(self) -> None:
        while not self._stopping.is_set():
            # keep going while there is a backlog, otherwise wait
            if await self.relay() < 100:
                await self._sleep(self._relay_interval)

    def _spawn(self, coro: Any) -> None:
        self._tasks.append(asyncio.create_task(coro))

    async def _sleep(self, seconds: float) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stopping.wait(), seconds)

    async def stop(self, timeout: float = 10.0) -> None:
        """Stop polling, let running handlers finish (up to `timeout`), relay what is left in the outbox, close."""
        if self._stopping.is_set():
            return
        self._stopping.set()
        _, pending = await asyncio.wait(self._tasks, timeout=timeout) if self._tasks else (set(), set())
        for t in pending:
            t.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        await self.relay()
        await self._queue.close()
