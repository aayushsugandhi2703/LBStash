"""Which categories are "fixed" (Rent, SIP), and the months window the Trends read models use."""

import asyncio
from dataclasses import dataclass
from typing import Any

from lbstash.common import Ctx, MonthKey, display_tag, months_ending_at
from lbstash.contracts import CategoryMonthItem, MonthItem

from .common import call_as

# A category is "fixed" when its active recurring rules cover this share of its usual monthly spend (or it has no
# history): Rent is, Netflix inside Fun does not make Fun fixed.
FIXED_SHARE = 0.5


@dataclass(frozen=True)
class Window:
    keys: list[MonthKey]
    months: list[MonthItem]
    cat_months: list[CategoryMonthItem]
    # finished months with any activity: what "usual" and the averages cover
    full_months: list[MonthKey]
    fixed_ids: set[str]
    # monthly commitment summed over the fixed categories
    fixed_committed_minor: int
    fixed_names: list[str]


async def load_window(deps: Any, ctx: Ctx, end: MonthKey, count: int, current: MonthKey) -> Window:
    """`count` months ending at `end`, plus the recurring rules that decide what is fixed. `current` never counts as finished."""
    as_ = call_as(ctx)
    months, cat_months, recurring = await asyncio.gather(
        deps.clients.transactions.months(as_, end, count),
        deps.clients.transactions.category_months(as_, end, count),
        deps.clients.recurring.list(as_),
    )
    keys = months_ending_at(end, count)
    have = {m.month: m for m in months.items}
    finished_before = min(end, current)
    full_months = [
        k for k in keys
        if k < finished_before and k in have and (have[k].income_minor > 0 or have[k].spent_minor > 0)
    ]

    committed: dict[str, int] = {}
    names: dict[str, str] = {}
    for r in recurring.items:
        if not r.active:
            continue
        committed[r.category_id] = committed.get(r.category_id, 0) + r.amount_minor
        names[r.category_id] = r.category_name
    usual_spend: dict[str, int] = {}
    for c in cat_months.items:
        if c.category_id and c.month in full_months:
            usual_spend[c.category_id] = usual_spend.get(c.category_id, 0) + c.spent_minor
    fixed_ids: set[str] = set()
    fixed_committed = 0
    for cid, amount in committed.items():
        usual = usual_spend.get(cid, 0) / len(full_months) if full_months else 0
        if usual == 0 or amount >= usual * FIXED_SHARE:
            fixed_ids.add(cid)
            fixed_committed += amount
    return Window(
        keys=keys, months=months.items, cat_months=cat_months.items,
        full_months=full_months, fixed_ids=fixed_ids, fixed_committed_minor=fixed_committed,
        fixed_names=sorted(display_tag(names.get(cid, 'untagged')) for cid in fixed_ids),
    )
