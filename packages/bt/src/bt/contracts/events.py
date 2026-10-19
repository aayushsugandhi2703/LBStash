"""Events and jobs, written in the producer's transaction (outbox) and delivered through the Postgres queue.

`EVENTS` fan out to every subscriber; `JOBS` have one queue and one consumer.
"""

from typing import Annotated, Any, Final, Literal

from pydantic import BeforeValidator, Field, StringConstraints
from pydantic_core import PydanticCustomError

from .base import Bool, Int, IsoDateTime, Model, MonthKey, Opt, OptNull, Paise, TxSource, TxStatus, TxType, TzName, Uuid


def _scalar(v: Any) -> Any:
    """Audit meta values: string, number, boolean or null , nothing nested."""
    if v is None or isinstance(v, (str, bool, int, float)):
        return v
    raise PydanticCustomError('scalar', 'Invalid input')


class TransactionChangedEvent(Model):
    """Ledger: any transaction insert, update, tag change or delete."""

    user_id: Uuid
    transaction_id: Uuid
    kind: Literal['created', 'updated', 'deleted']
    type: TxType
    status: TxStatus
    source: TxSource
    occurred_at: IsoDateTime
    # Categories whose spend may have changed: the old and the new one (None = Uncategorised).
    category_ids: list[Uuid | None]
    # Set when the change was a tag: who tagged it, so Telegram can edit the message to its final state.
    tagged_via: Literal['telegram', 'web', 'rule'] | None
    # The user's IANA zone, so planning can name the budget period without a lookup.
    tz: Opt[TzName] = None


class CreditAddedEvent(Model):
    """Ledger: credit added by hand with "add to plan" on. Planning adds it to that month's plan total (idempotent)."""

    user_id: Uuid
    transaction_id: Uuid
    month: MonthKey
    amount_minor: Paise
    add_to_plan: Bool


class AlertCreatedEvent(Model):
    """Planning: a limit crossed its alert level or was exceeded (fires once per budget, period, level)."""

    user_id: Uuid
    alert_id: Uuid
    budget_id: Uuid
    category_id: Uuid
    category_name: str
    level: Literal['alert', 'exceeded']
    period_key: str
    pct: Int


class UnparsedCreatedEvent(Model):
    """Ingest: a message looked like a transaction but could not be read. Telegram sends a no-details nudge."""

    user_id: Uuid
    unparsed_id: Uuid
    failures_last24h: Int = Field(alias='failuresLast24h')  # to_camel would give `failuresLast24H`


class AccountDeletedEvent(Model):
    """Auth: the account is being deleted (after the 7-day window). Every service deletes the user's rows."""

    user_id: Uuid


class AuditRecordEvent(Model):
    """Any service -> auth: append to the audit log. Never carries amounts, payees or message text."""

    user_id: Uuid
    action: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    device_id: OptNull[Uuid] = None
    ip: OptNull[str] = None
    meta: Opt[dict[str, Annotated[Any, BeforeValidator(_scalar)]]] = None


EVENTS: Final[dict[str, type[Model]]] = {
    'transaction.changed': TransactionChangedEvent,
    'credit.added': CreditAddedEvent,
    'alert.created': AlertCreatedEvent,
    'unparsed.created': UnparsedCreatedEvent,
    'account.deleted': AccountDeletedEvent,
    'audit.record': AuditRecordEvent,
}
EventName = Literal[
    'transaction.changed', 'credit.added', 'alert.created', 'unparsed.created', 'account.deleted', 'audit.record'
]


class BudgetEvaluateJob(Model):
    """Planning, from `transaction.changed`: recompute one budget's status and insert the alert row once per level."""

    user_id: Uuid
    category_id: Uuid
    period_key: str


class BalanceReconcileJob(Model):
    """Ledger: compare bank balance with the ledger, wait the grace period, book or merge Unaccounted."""

    user_id: Uuid
    check_id: Opt[Uuid] = None


class RecurringPostJob(Model):
    """Recurring: cron tick that posts due rules (payload empty)."""


class TelegramSendJob(Model):
    """Telegram: send one prompt / alert / digest."""

    prompt_id: Uuid


class TelegramSyncPromptJob(Model):
    prompt_id: Uuid


class TelegramDigestJob(Model):
    user_id: Opt[Uuid] = None


class RetentionSweepJob(Model):
    """Every data service: nightly clean-up of its own expired rows. Queue name is `retention.sweep.<service>`."""


JOBS: Final[dict[str, type[Model]]] = {
    'budget.evaluate': BudgetEvaluateJob,
    'balance.reconcile': BalanceReconcileJob,
    'recurring.post': RecurringPostJob,
    'telegram.send': TelegramSendJob,
    'telegram.sync_prompt': TelegramSyncPromptJob,
    'telegram.digest': TelegramDigestJob,
    'retention.sweep': RetentionSweepJob,
}
JobName = Literal[
    'budget.evaluate',
    'balance.reconcile',
    'recurring.post',
    'telegram.send',
    'telegram.sync_prompt',
    'telegram.digest',
    'retention.sweep',
]

# Who consumes each event. Every service creates all queues at start-up, so an event published before its consumer
# first runs waits in its queue. Queue name = `<service>.<event>`.
SUBSCRIPTIONS: Final[dict[str, tuple[str, ...]]] = {
    'transaction.changed': ('planning', 'telegram'),
    'credit.added': ('planning',),
    'alert.created': ('telegram',),
    'unparsed.created': ('telegram',),
    'account.deleted': ('ledger', 'ingest', 'planning', 'recurring', 'telegram'),
    'audit.record': ('auth',),
}


def event_queue(service: str, event: str) -> str:
    return f'{service}.{event}'


def sweep_queue(service: str) -> str:
    """Per-service queue for the nightly sweep, e.g. `retention.sweep.ledger`."""
    return f'retention.sweep.{service}'
