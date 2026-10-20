"""The posting cron: post each due occurrence to the transactions and advance `next_due`."""

from collections.abc import Awaitable, Callable
from typing import Any, Literal
from zoneinfo import ZoneInfo

from lbstash.common import DEFAULT_TZ, Clock, add_days, date_key
from lbstash.kit import Deps

from .rules import schedule_of, to_row
from .schedule import next_occurrence

TzResolver = Callable[[str], Awaitable[str]]


def make_tz_resolver(deps: Deps[Any], clock: Clock, ttl_seconds: float = 600) -> TzResolver:
    """The user's zone from auth, cached briefly. Falls back to the default so posting never blocks."""
    cache: dict[str, tuple[str, float]] = {}

    async def tz_of(user_id: str) -> str:
        hit = cache.get(user_id)
        if hit and clock().timestamp() - hit[1] < ttl_seconds:
            return hit[0]
        try:
            res = await deps.clients.auth.me({'user_id': user_id})
            tz = res.user.timezone
            ZoneInfo(tz)  # raises on an unknown zone
            cache[user_id] = (tz, clock().timestamp())
            return tz
        except Exception:  # noqa: BLE001  (auth down, unknown zone: all mean "use the default")
            return DEFAULT_TZ

    return tz_of


_DUE = 'NOT paused AND next_due <= $1 AND (ends_on IS NULL OR next_due <= ends_on)'
# Occurrences handled per rule per tick (a rule missed for months catches up over a few ticks).
MAX_CATCH_UP = 60

PostOutcome = Literal['posted', 'linked', 'already_posted', 'idle']


async def post_one(deps: Deps[Any], user_id: str, tz: str, rule_id: str, today: str) -> PostOutcome:
    """Post one due occurrence and advance `next_due` in one transaction under a row lock. The transactions call is idempotent; a failure rolls everything back."""
    async with deps.as_user(user_id) as tx:
        found = await tx.maybe_one(f'SELECT * FROM recurring_rules WHERE id = $2 AND {_DUE} FOR UPDATE SKIP LOCKED', [today, rule_id])
        if found is None:
            return 'idle'
        r = to_row(found)
        res = await deps.clients.transactions.post_recurring(
            {'user_id': user_id, 'tz': tz},
            {
                'ruleId': r.id, 'name': r.name, 'categoryId': r.category_id, 'amountMinor': r.amount_minor,
                'dueDate': r.next_due, 'matchHint': r.match_hint,
            },
        )  # fmt: skip
        await tx.execute(
            'UPDATE recurring_rules SET next_due = $2, last_handled_due = $3, updated_at = now() WHERE id = $1',
            [r.id, next_occurrence(schedule_of(r), r.next_due), r.next_due],
        )
        return res.outcome


async def post_due_rules(deps: Deps[Any], clock: Clock, tz_of: TzResolver) -> dict[str, int]:
    """One cron tick: every due rule of every user, oldest first."""
    # Local "today" is at most a day ahead of UTC, so this is a superset; each user is rechecked in their own zone.
    horizon = add_days(date_key(clock(), 'UTC'), 1)
    async with deps.as_system() as tx:
        users = await tx.many(f'SELECT DISTINCT user_id FROM recurring_rules WHERE {_DUE} LIMIT 1000', [horizon])
    handled = failed = 0
    for u in users:
        user_id = str(u['user_id'])
        tz = await tz_of(user_id)
        today = date_key(clock(), tz)
        async with deps.as_user(user_id) as tx:
            ids = await tx.many(f'SELECT id FROM recurring_rules WHERE {_DUE} ORDER BY next_due, id', [today])
        for row in ids:
            rule_id = str(row['id'])
            for _ in range(MAX_CATCH_UP):
                try:
                    if await post_one(deps, user_id, tz, rule_id, today) == 'idle':
                        break
                    handled += 1
                except Exception as e:  # noqa: BLE001  (next tick retries; ids and codes only in the log)
                    failed += 1
                    deps.log.warning('recurring post failed', rule=rule_id, uid=user_id, code=getattr(e, 'code', 'error'))
                    break
    return {'handled': handled, 'failed': failed}
