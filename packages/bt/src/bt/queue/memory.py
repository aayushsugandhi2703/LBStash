"""Test double for `MessageBus`."""

from dataclasses import dataclass
from typing import Any

from bt.contracts import EVENTS, JOBS
from bt.db import Queryable

from .bus import Handler, Payload, Policy, validate


@dataclass(frozen=True, slots=True)
class RecordedEvent:
    event: str
    payload: Any


@dataclass(frozen=True, slots=True)
class RecordedJob:
    job: str
    queue: str
    payload: Any
    key: str | None = None
    start_after_seconds: float | None = None


@dataclass(frozen=True, slots=True)
class RecordedSchedule:
    queue: str
    cron: str
    payload: dict[str, Any]
    tz: str


class InMemoryBus:
    """Records emitted events and enqueued jobs (validated like the real bus); `drain()` delivers them to handlers."""

    def __init__(self) -> None:
        self.events: list[RecordedEvent] = []
        self.jobs: list[RecordedJob] = []
        self.schedules: list[RecordedSchedule] = []
        self._event_handlers: dict[str, list[Handler]] = {}
        self._job_handlers: dict[str, Handler] = {}

    async def emit(self, tx: Queryable, event: str, payload: Payload) -> None:
        """Record an event."""
        self.events.append(RecordedEvent(event, validate(EVENTS, 'event', event, payload)))

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
        """Record a job."""
        body = validate(JOBS, 'job', job, payload)
        self.jobs.append(RecordedJob(job, queue or job, body, key, start_after_seconds))

    async def on_event(self, event: str, handler: Handler) -> None:
        """Register an event handler (several per event are allowed)."""
        self._event_handlers.setdefault(event, []).append(handler)

    async def on_job(
        self,
        job: str,
        handler: Handler,
        *,
        queue: str | None = None,
        policy: Policy = 'standard',
        concurrency: int = 1,
        retry_limit: int = 5,
    ) -> None:
        """Register the handler of a job queue."""
        self._job_handlers[queue or job] = handler

    async def schedule(self, queue: str, cron: str, payload: dict[str, Any] | None = None, tz: str = 'UTC') -> None:
        """Record a schedule; nothing fires in tests, call the handler yourself."""
        self.schedules.append(RecordedSchedule(queue, cron, payload or {}, tz))

    async def stop(self) -> None:
        """Nothing to stop."""

    async def drain(self) -> None:
        """Deliver the recorded events and jobs to their handlers, then clear them."""
        events, self.events = self.events, []
        for e in events:
            for h in self._event_handlers.get(e.event, []):
                await h(e.payload)
        jobs, self.jobs = self.jobs, []
        for j in jobs:
            handler = self._job_handlers.get(j.queue)
            if handler:
                await handler(j.payload)

    def events_of(self, event: str) -> list[Any]:
        """Payloads of the recorded events with this name."""
        return [e.payload for e in self.events if e.event == event]

    def clear(self) -> None:
        """Forget recorded events and jobs; handlers and schedules stay."""
        self.events.clear()
        self.jobs.clear()
