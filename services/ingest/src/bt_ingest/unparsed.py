from contextlib import suppress
from datetime import datetime

from bt.common import Ctx, Errors
from bt.contracts import (
    DismissUnparsedRes,
    ManualTransactionReq,
    ResolveUnparsedReq,
    ResolveUnparsedRes,
    UnparsedCountRes,
    UnparsedDto,
    UnparsedRes,
    UnparsedSuggestion,
)
from bt.db import Tx
from bt.kit import Deps

from .devices import as_ctx, safe_tz
from .ingest import cipher_of
from .parser import Parsed, ParseInput, Unreadable, parse_message

_SELECT = """SELECT u.id, u.body_enc, u.reason, u.received_at, u.expires_at, coalesce(d.tz, 'Asia/Kolkata') AS tz
  FROM unparsed_messages u LEFT JOIN devices d ON d.id = u.device_id"""


async def _open_count(tx: Tx) -> int:
    return (await tx.one("SELECT count(*)::int AS n FROM unparsed_messages WHERE status = 'open' AND expires_at > now()"))['n']


async def unparsed_count(deps: Deps, ctx: Ctx) -> UnparsedCountRes:
    async with deps.as_user(ctx) as tx:
        return UnparsedCountRes(open=await _open_count(tx))


async def list_unparsed(deps: Deps, ctx: Ctx) -> UnparsedRes:
    """Open messages, decrypted for this answer only, with what the parser can still guess."""
    async with deps.as_user(ctx) as tx:
        rows = await tx.many(f"{_SELECT} WHERE u.status = 'open' AND u.expires_at > now() ORDER BY u.received_at DESC LIMIT 100")
        open_ = await _open_count(tx)
    cipher = cipher_of(deps)
    items = []
    for r in rows:
        text = cipher.decrypt_string(r['body_enc'], ctx.user_id)
        p = parse_message(ParseInput(text=text, received_at=r['received_at'], tz=safe_tz(r['tz'])))
        if isinstance(p, Unreadable):
            suggestion = UnparsedSuggestion(type=p.hints.type, amount_minor=p.hints.amount_minor, payee=p.hints.payee)
        elif isinstance(p, Parsed):
            suggestion = UnparsedSuggestion(type=p.tx.type, amount_minor=p.tx.amount_minor, payee=p.tx.payee)
        else:
            suggestion = UnparsedSuggestion(type=None, amount_minor=None, payee=None)
        items.append(
            UnparsedDto(id=r['id'], received_at=r['received_at'], expires_at=r['expires_at'], reason=r['reason'], text=text, suggestion=suggestion)
        )
    return UnparsedRes(items=items, open=open_)


async def resolve_unparsed(deps: Deps, ctx: Ctx, id: str, body: ResolveUnparsedReq) -> ResolveUnparsedRes:
    """Add the message to the ledger as the user described it, then delete it.
    The row is claimed first (`open` -> `resolved`) so a double click cannot add it twice; a failed ledger call reopens it.
    """
    async with deps.as_user(ctx) as tx:
        claimed = await tx.maybe_one(
            """WITH c AS (UPDATE unparsed_messages SET status = 'resolved' WHERE id = $1 AND status = 'open' AND expires_at > now() RETURNING *)
             SELECT c.id, c.body_enc, c.reason, c.received_at, c.expires_at, coalesce(d.tz, 'Asia/Kolkata') AS tz FROM c LEFT JOIN devices d ON d.id = c.device_id""",
            [id],
        )
    if not claimed:
        raise Errors.not_found('Message')

    # the time written in the message beats when the phone sent it
    occurred_at: datetime = claimed['received_at']
    with suppress(Exception):  # the time is a nicety: keep received_at rather than fail the add
        text = cipher_of(deps).decrypt_string(claimed['body_enc'], ctx.user_id)
        p = parse_message(ParseInput(text=text, received_at=occurred_at, tz=safe_tz(claimed['tz'])))
        if isinstance(p, Unreadable) and p.hints.occurred_at:
            occurred_at = p.hints.occurred_at

    try:
        res = await deps.clients.ledger.create_manual(
            as_ctx(ctx),
            ManualTransactionReq(type=body.type, amount_minor=body.amount_minor, occurred_at=occurred_at, payee=body.payee, description=None),
        )
    except Exception:
        await _reopen(deps, ctx, id)
        raise
    async with deps.as_user(ctx) as tx:
        await tx.execute('DELETE FROM unparsed_messages WHERE id = $1', [id])
        open_ = await _open_count(tx)
    return ResolveUnparsedRes(transaction=res.transaction, open=open_)


async def _reopen(deps: Deps, ctx: Ctx, id: str) -> None:
    with suppress(Exception):  # the caller must see the ledger's error
        async with deps.as_user(ctx) as tx:
            await tx.execute("UPDATE unparsed_messages SET status = 'open' WHERE id = $1", [id])


async def dismiss_unparsed(deps: Deps, ctx: Ctx, id: str) -> DismissUnparsedRes:
    """"Not a payment": delete it for good."""
    async with deps.as_user(ctx) as tx:
        gone = await tx.maybe_one("DELETE FROM unparsed_messages WHERE id = $1 AND status = 'open' RETURNING id", [id])
        if gone is None:
            raise Errors.not_found('Message')
        return DismissUnparsedRes(ok=True, open=await _open_count(tx))

