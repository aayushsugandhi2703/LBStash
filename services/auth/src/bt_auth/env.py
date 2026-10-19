"""Auth-service variables on top of the shared ones."""

from typing import Any, Literal
from urllib.parse import urlsplit

from bt.common import BaseEnv
from pydantic import Field, field_validator


class Env(BaseEnv):
    # Signs the access JWT; the gateway verifies it with the same secret.
    ACCESS_TOKEN_SECRET: str = Field(min_length=32, repr=False)
    # Defaults to the host of PUBLIC_URL.
    WEBAUTHN_RP_ID: str | None = None
    WEBAUTHN_RP_NAME: str = 'Ledger'
    # `log` prints the link in development only; `smtp` sends through SMTP_URL.
    MAIL_TRANSPORT: Literal['log', 'smtp'] = 'log'
    SMTP_URL: str | None = Field(default=None, repr=False)
    MAIL_FROM: str | None = None
    # `first-only`: registration closes once a user exists. `open` allows several.
    REGISTRATION: Literal['first-only', 'open'] = 'first-only'

    @field_validator('WEBAUTHN_RP_ID', 'SMTP_URL', 'MAIL_FROM', mode='before')
    @classmethod
    def _blank_is_unset(cls, v: Any) -> Any:
        return None if isinstance(v, str) and not v.strip() else v


def rp_id(env: Env) -> str:
    """The WebAuthn relying-party id: the configured one, else the host of PUBLIC_URL."""
    return env.WEBAUTHN_RP_ID or urlsplit(env.PUBLIC_URL).hostname or 'localhost'


def web_origin(env: Env) -> str:
    """`scheme://host[:port]` of PUBLIC_URL: the WebAuthn origin."""
    u = urlsplit(env.PUBLIC_URL)
    default = 443 if u.scheme == 'https' else 80
    port = f':{u.port}' if u.port and u.port != default else ''
    return f'{u.scheme}://{u.hostname}{port}'


def is_secure_url(env: Env) -> bool:
    """True when PUBLIC_URL is https."""
    return env.PUBLIC_URL.startswith('https')
