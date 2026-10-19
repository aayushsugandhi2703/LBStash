"""Row shapes and helpers shared by the ledger modules: the money row, DTOs, the outbox event, inserts, the user lock."""

import uuid
from datetime import datetime
from typing import Any, Final, Literal, TypedDict

from bt.common import payee_key
from bt.contracts import LedgerRowDto, TransactionDto
from bt.db import Row, Tx
from bt.kit import Deps

D = Deps[Any]

# The category whose name excludes a row from "spent", "income", plans and budgets (README 3.1).
TRANSFER: Final = 'transfer'
# SQL fragment for queries that join `categories c` onto `transactions t`.
NOT_TRANSFER: Final = f"COALESCE(c.name, '') <> '{TRANSFER}'"
# A gap smaller than Rs 1 is ignored (README 3.6).
MIN_GAP: Final = 100


class TxRow(TypedDict):
    """A `transactions` row plus the joined category name (`TX_SELECT`)."""

    id: str
    user_id: str
    type: Literal['debit', 'credit']
    amount_minor: int
    occurred_at: datetime
    payee: str | None
    payee_key: str | None
    description: str | None
    reference: str | None
    category_id: str | None
    category_name: str | None
    source: Literal['captured', 'recurring', 'manual', 'unaccounted']
    status: Literal['pending', 'confirmed', 'reversed']
    dedupe_key: str
    recurring_id: str | None
    match_hint: str | None
    device_id: str | None
    captured_at: datetime | None
    weak_parse: bool
    classified_by: Literal['memory', 'rule', 'user', 'recurring'] | None
    rule_pattern: str | None
    linked: bool


TX_SELECT: Final = (
    'SELECT t.*, c.name AS category_name FROM transactions t '
    'LEFT JOIN categories c ON c.id = t.category_id AND c.user_id = t.user_id'
)


def to_dto(r: Row) -> TransactionDto:
    return TransactionDto.model_validate(r)


def to_row_dto(r: Row) -> LedgerRowDto:
    """A Ledger list row: the transaction plus how it got its category."""
    return LedgerRowDto.model_validate(
        {**r, 'matched_rule': r['rule_pattern'] if r['classified_by'] == 'rule' else None}
    )


async def get_tx(tx: Tx, id: str, *, lock: bool = False) -> TxRow | None:
    return await tx.maybe_one(f'{TX_SELECT} WHERE t.id = $1{" FOR UPDATE OF t" if lock else ""}', [id])  # type: ignore[return-value]


async def get_txs(tx: Tx, ids: list[str]) -> list[TxRow]:
    if not ids:
        return []
    return await tx.many(f'{TX_SELECT} WHERE t.id = ANY($1::uuid[])', [ids])  # type: ignore[return-value]


async def lock_user(tx: Tx, user_id: str) -> None:
    """Serialise one user's money writes inside the open transaction."""
    await tx.query('SELECT pg_advisory_xact_lock(hashtext($1))', [f'ledger:{user_id}'])


async def emit_changed(
    deps: D,
    tx: Tx,
    tz: str | None,
    row: Row,
    kind: Literal['created', 'updated', 'deleted'],
    *,
    before: str | None = None,
    tagged_via: Literal['telegram', 'web', 'rule'] | None = None,
) -> None:
    """Emit `transaction.changed` in the writer's transaction. `before` is the previous category (updates only)."""
    ids = [row['category_id']] if kind == 'created' else [before, row['category_id']]
    await deps.bus.emit(
        tx,
        'transaction.changed',
        {
            'user_id': row['user_id'],
            'transaction_id': row['id'],
            'kind': kind,
            'type': row['type'],
            'status': row['status'],
            'source': row['source'],
            'occurred_at': row['occurred_at'],
            'category_ids': list(dict.fromkeys(ids)),
            'tagged_via': tagged_via,
            **({'tz': tz} if tz else {}),
        },
    )


def key_of(payee: str | None) -> str | None:
    """Payee -> match key; None when there is nothing to match on."""
    return (payee_key(payee) if payee else '') or None


async def insert_tx(
    tx: Tx,
    user_id: str,
    *,
    type: str,
    amount_minor: int,
    occurred_at: datetime,
    source: str,
    status: str,
    dedupe_key: str,
    payee: str | None = None,
    description: str | None = None,
    reference: str | None = None,
    account_last4: str | None = None,
    category_id: str | None = None,
    recurring_id: str | None = None,
    match_hint: str | None = None,
    device_id: str | None = None,
    captured_at: datetime | None = None,
    weak_parse: bool = False,
    classified_by: str | None = None,
    rule_pattern: str | None = None,
    linked: bool = False,
) -> TxRow | None:
    """Insert one money row; None when the (user, dedupe key) already exists (the idempotency guard)."""
    r = await tx.maybe_one(
        """INSERT INTO transactions (user_id, type, amount_minor, occurred_at, payee, payee_key, description, reference, account_last4, category_id, source, status,
                               dedupe_key, recurring_id, match_hint, device_id, captured_at, weak_parse, classified_by, rule_pattern, linked)
     VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
     ON CONFLICT (user_id, dedupe_key) DO NOTHING RETURNING id""",
        [user_id, type, amount_minor, occurred_at, payee, key_of(payee), description, reference, account_last4,
         category_id, source, status, dedupe_key, recurring_id, match_hint, device_id, captured_at, weak_parse,
         classified_by, rule_pattern, linked],
    )  # fmt: skip
    return await get_tx(tx, r['id']) if r else None


async def find_by_key(tx: Tx, user_id: str, key: str) -> TxRow | None:
    """The row saved under this dedupe key, directly or through an alias (a message merged into another row)."""
    return await tx.maybe_one(  # type: ignore[return-value]
        f"""{TX_SELECT} WHERE t.user_id = $1 AND (t.dedupe_key = $2 OR t.id IN (SELECT transaction_id FROM tx_links WHERE user_id = $1 AND dedupe_key = $2)) LIMIT 1""",
        [user_id, key],
    )


async def add_alias(tx: Tx, user_id: str, key: str, transaction_id: str) -> None:
    await tx.query(
        'INSERT INTO tx_links (user_id, dedupe_key, transaction_id) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING',
        [user_id, key, transaction_id],
    )


def new_key(prefix: str, *parts: object) -> str:
    """A fresh dedupe key for rows with no external identity (`manual:<uuid>`, `split:<id>:<i>:<uuid>`)."""
    return ':'.join([prefix, *(str(p) for p in parts), str(uuid.uuid4())])
