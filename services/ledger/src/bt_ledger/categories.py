"""Categories: created from tags, renamed, archived, merged by delete-with-reassign (README 3.3, 18)."""

from bt.common import Ctx, Errors, normalize_tag
from bt.contracts import CategoryDto, CategoryUsageDto, DeleteCategoryRes, PatchCategoryReq
from bt.db import Row, Tx

from .model import TRANSFER, D, emit_changed, get_txs


def _dto(c: Row) -> CategoryDto:
    return CategoryDto(id=c['id'], name=c['name'], archived=c['archived'])


async def resolve_category(tx: Tx, user_id: str, raw_tag: str) -> tuple[CategoryDto, bool]:
    """Find or create the category for a tag (one per user, lowercase). An archived one is revived."""
    name = normalize_tag(raw_tag)

    async def find() -> Row | None:
        return await tx.maybe_one('SELECT id, name, archived FROM categories WHERE user_id = $1 AND lower(name) = $2', [user_id, name])

    c = await find()
    if c:
        if c['archived']:
            c = await tx.maybe_one('UPDATE categories SET archived = false WHERE id = $1 RETURNING id, name, archived', [c['id']])
            assert c is not None
        return _dto(c), False
    ins = await tx.maybe_one(
        'INSERT INTO categories (user_id, name) VALUES ($1, $2) ON CONFLICT (user_id, lower(name)) DO NOTHING RETURNING id, name, archived',
        [user_id, name],
    )
    if ins:
        return _dto(ins), True
    found = await find()
    assert found is not None
    return _dto(found), False


async def get_category(tx: Tx, id: str) -> CategoryDto:
    """RLS hides other users' categories, so their ids are simply "not found"."""
    c = await tx.maybe_one('SELECT id, name, archived FROM categories WHERE id = $1', [id])
    if not c:
        raise Errors.not_found('Category')
    return _dto(c)


async def list_categories(
    tx: Tx, user_id: str, *, sort: str = 'name', limit: int | None = None, include_archived: bool = False
) -> list[CategoryUsageDto]:
    rows = await tx.many(
        f"""SELECT c.id, c.name, c.archived, COUNT(t.id)::int AS count
       FROM categories c LEFT JOIN transactions t ON t.category_id = c.id AND t.user_id = c.user_id AND t.status <> 'reversed'
      WHERE c.user_id = $1 {'' if include_archived else 'AND NOT c.archived'}
      GROUP BY c.id
      ORDER BY {'count DESC, c.name' if sort == 'usage' else 'c.name'}
      LIMIT $2""",
        [user_id, limit or 500],
    )
    return [CategoryUsageDto(id=r['id'], name=r['name'], archived=r['archived'], count=r['count']) for r in rows]


async def patch_category(deps: D, ctx: Ctx, id: str, patch: PatchCategoryReq) -> CategoryUsageDto:
    async with deps.as_user(ctx) as tx:
        c = await get_category(tx, id)
        if c.name == TRANSFER:
            raise Errors.unprocessable('#transfer is built in and cannot be renamed or archived')
        if patch.name is not None:
            name = normalize_tag(patch.name)
            if name == TRANSFER:
                raise Errors.unprocessable('#transfer is reserved')
            clash = await tx.maybe_one(
                'SELECT id FROM categories WHERE user_id = $1 AND lower(name) = $2 AND id <> $3', [ctx.user_id, name, id]
            )
            if clash:
                raise Errors.conflict(
                    'A category with that name already exists: delete this one and reassign its transactions to merge',
                    {'existingId': clash['id']},
                )
            await tx.query('UPDATE categories SET name = $2 WHERE id = $1', [id, name])
        if patch.archived is not None:
            await tx.query('UPDATE categories SET archived = $2 WHERE id = $1', [id, patch.archived])
        return next(x for x in await list_categories(tx, ctx.user_id, include_archived=True) if x.id == id)


async def delete_category(deps: D, ctx: Ctx, id: str, reassign_to: str | None = None) -> DeleteCategoryRes:
    """Blocked while transactions use the category (README 9, 18): reassign them or archive instead."""
    async with deps.as_user(ctx) as tx:
        c = await get_category(tx, id)
        if c.name == TRANSFER:
            raise Errors.unprocessable('#transfer is built in and cannot be deleted')
        used = (await tx.one('SELECT COUNT(*)::int AS n FROM transactions WHERE category_id = $1', [id]))['n']
        if used > 0 and not reassign_to:
            raise Errors.conflict(
                f'{used} transaction{"" if used == 1 else "s"} use this category: reassign them or archive it',
                {'transactions': used},
            )
        reassigned = 0
        if reassign_to:
            if reassign_to == id:
                raise Errors.validation({'reassignTo': 'Pick a different category'})
            target = await get_category(tx, reassign_to)
            if target.archived:
                raise Errors.unprocessable('That category is archived')
            moved = await tx.many(
                'UPDATE transactions SET category_id = $2, updated_at = now() WHERE category_id = $1 RETURNING id', [id, reassign_to]
            )
            await tx.query('UPDATE tag_rules SET category_id = $2 WHERE category_id = $1', [id, reassign_to])
            rows = await get_txs(tx, [m['id'] for m in moved])
            for r in rows:
                await emit_changed(deps, tx, ctx.tz, r, 'updated', before=id)
            reassigned = len(rows)
        await tx.query('DELETE FROM categories WHERE id = $1', [id])
        return DeleteCategoryRes(ok=True, reassigned=reassigned)
