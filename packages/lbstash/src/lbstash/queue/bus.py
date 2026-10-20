"""What a service sees of the message system. `Messaging` is the real one; tests inject `InMemoryBus`.
Payloads are the `lbstash.contracts` models, or dicts that validate against them."""

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from lbstash.db import Queryable

Payload = BaseModel | dict[str, Any]
Handler = Callable[[Any], Awaitable[None]]
Policy = Literal['standard', 'short']


def validate(models: Mapping[str, type[BaseModel]], kind: str, name: str, payload: Payload) -> BaseModel:
    """The payload as the contract model registered under `name`; raises ValueError for an unknown name."""
    try:
        model = models[name]
    except KeyError:
        raise ValueError(f'unknown {kind}: {name}') from None
    return payload if isinstance(payload, model) else model.model_validate(payload)


class MessageBus(Protocol):
    """Publish and consume events and jobs. Delivery is at-least-once: handlers must be idempotent."""

    async def emit(self, tx: Queryable, event: str, payload: Payload) -> None:
        """Publish an event to every subscriber. Pass the open transaction so it commits with your change."""

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
        """Queue one job for its consumer. `key` collapses bursts to one queued job per queue and key; `queue` overrides the queue name."""

    async def on_event(self, event: str, handler: Handler) -> None:
        """Handle an event this service subscribes to (see SUBSCRIPTIONS). The handler gets the validated model; raise to retry."""

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
        """Handle a job queue (`queue` if it differs from the job name). Raise to retry with backoff."""

    async def schedule(self, queue: str, cron: str, payload: dict[str, Any] | None = None, tz: str = 'UTC') -> None:
        """Enqueue a job on `queue` on a 5-field cron in `tz`, once per tick across all replicas."""

    async def stop(self) -> None:
        """Stop consuming and let in-flight handlers finish."""
