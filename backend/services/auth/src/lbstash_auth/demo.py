"""The public demo: a session for the one demo account, with no password or second step (off unless DEMO_MODE is on)."""

from lbstash.common import DEMO_USER_ID, AppError, Errors

from .audit import record_audit
from .client_info import ClientInfo
from .sessions import start_session
from .signin import Issued
from .svc import Svc
from .users import find_user, session_res


async def demo_login(svc: Svc, info: ClientInfo) -> Issued:
    """Start a normal session (address list, cookies and refresh rotation as for anyone) for DEMO_USER_ID, and for no one else.
    The gateway then refuses that user's writes."""
    if not svc.deps.env.DEMO_MODE:
        raise AppError('not_found', 'No such route')  # same answer as a route that does not exist
    async with svc.deps.as_system() as tx:
        user = await find_user(tx, DEMO_USER_ID)
        if user is None:
            raise Errors.not_found('The demo data')
        started = await start_session(svc, tx, user.id, user.timezone, info)
        await record_audit(tx, user.id, 'demo.login', ip=info.ip)
        return Issued(await session_res(tx, user), started.tokens)
