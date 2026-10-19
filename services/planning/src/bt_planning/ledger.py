"""What planning asks the ledger: spend per category, category names, tag to category."""

from typing import Protocol

from bt.clients import CallAs
from bt.common import Ctx, Errors, MonthKey, month_range, normalize_tag, to_iso
from bt.kit import Deps


def call_as(c: Ctx) -> CallAs:
    """The part of a request context sent on calls to other services."""
    return CallAs(user_id=c.user_id, tz=c.tz, request_id=c.request_id)


async def month_spend(deps: Deps, ctx: Ctx, month: MonthKey) -> dict[str, int]:
    """Spend per category id for a month in the user's zone. Uncategorised is dropped (no plan line or budget)."""
    start, end = month_range(month, ctx.tz)
    res = await deps.clients.ledger.spend_by_category(call_as(ctx), to_iso(start), to_iso(end))
    out: dict[str, int] = {}
    for i in res.items:
        if i.category_id:
            out[i.category_id] = out.get(i.category_id, 0) + i.spent_minor
    return out


async def category_names(deps: Deps, ctx: Ctx) -> dict[str, str]:
    """id -> lowercase name for every category, archived included."""
    res = await deps.clients.ledger.categories(call_as(ctx), sort='name', limit=200, include_archived=True)
    return {c.id: c.name for c in res.items}


class CategoryRef(Protocol):
    """A request body naming a category by id or tag."""

    category_id: str | None
    tag: str | None


async def resolve_ref(deps: Deps, ctx: Ctx, ref: CategoryRef, names: dict[str, str]) -> tuple[str, str]:
    """Category by id (must be the user's) or by tag (created in the ledger if new): `(id, name)`."""
    if ref.category_id:
        name = names.get(ref.category_id)
        if name is None:
            raise Errors.validation({'categoryId': 'Unknown category'})
        return ref.category_id, name
    tag = normalize_tag(ref.tag or '')
    r = await deps.clients.ledger.resolve_category(call_as(ctx), tag)
    names[r.category.id] = r.category.name
    return r.category.id, r.category.name
