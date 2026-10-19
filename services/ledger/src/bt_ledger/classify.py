"""Automatic classification (payee memory, keyword rules) and learning from a tag."""

from dataclasses import dataclass
from typing import Literal

from bt.db import Row, Tx

from .model import key_of


@dataclass(frozen=True, slots=True)
class Classification:
    category_id: str
    by: Literal['memory', 'rule']
    pattern: str


async def classify(tx: Tx, user_id: str, payee: str | None) -> Classification | None:
    """README 3.3, first match wins: payee memory, then keyword rule, else nothing (stays Needs a tag). Archived categories never match."""
    key = key_of(payee)
    if not key:
        return None

    async def hit(kind: str, where: str, order: str = '') -> Row | None:
        return await tx.maybe_one(
            f"""SELECT r.id, r.category_id, r.pattern FROM tag_rules r JOIN categories c ON c.id = r.category_id
        WHERE r.user_id = $1 AND r.kind = $2 AND {where} AND NOT c.archived {order} LIMIT 1""",
            [user_id, kind, key],
        )

    memory = await hit('payee', 'r.pattern = $3')
    rule = memory or await hit('keyword', 'position(r.pattern in $3) > 0', 'ORDER BY length(r.pattern) DESC')
    if not rule:
        return None
    await tx.query('UPDATE tag_rules SET hits = hits + 1 WHERE id = $1', [rule['id']])
    return Classification(rule['category_id'], 'memory' if memory else 'rule', rule['pattern'])


async def remember_payee(tx: Tx, user_id: str, payee: str | None, category_id: str) -> None:
    """Remember the payee so it is tagged automatically next time. Re-tagging moves the rule."""
    key = key_of(payee)
    if not key:
        return
    await tx.query(
        """INSERT INTO tag_rules (user_id, category_id, kind, pattern, hits) VALUES ($1, $2, 'payee', $3, 1)
     ON CONFLICT (user_id, kind, pattern) DO UPDATE SET category_id = EXCLUDED.category_id, hits = tag_rules.hits + 1""",
        [user_id, category_id, key],
    )
