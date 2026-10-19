"""Request context and the names every service shares (headers, cookies, services)."""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Final, Literal, get_args


@dataclass(frozen=True, slots=True)
class Ctx:
    """Built from the verified internal token."""

    user_id: str
    # IANA zone; month boundaries and "today" use it.
    tz: str
    request_id: str


DEFAULT_TZ: Final = 'Asia/Kolkata'

HEADERS: Final = SimpleNamespace(internal_token='x-internal-token', request_id='x-request-id', csrf='x-csrf-token')

COOKIES: Final = SimpleNamespace(access='bt_access', refresh='bt_refresh', csrf='bt_csrf')

ServiceName = Literal['gateway', 'auth', 'ledger', 'ingest', 'planning', 'recurring', 'reports', 'telegram']
SERVICES: Final[tuple[str, ...]] = get_args(ServiceName)
