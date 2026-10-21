"""Environment loading: `BaseEnv` plus `load_env`."""

from collections.abc import Mapping
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .log import normalize_level

AppEnv = Literal['development', 'test', 'production']

# The one account the public demo may sign in to (`POST /auth/demo`). The demo seeder creates the user row with exactly this id.
DEMO_USER_ID = '5de0b1a5-0000-4000-8000-00000000d3a0'


class EnvError(ValueError):
    """Invalid environment; the message lists every problem."""


class BaseEnv(BaseModel):
    """Env every service understands; services subclass it to add their own."""

    model_config = ConfigDict(extra='ignore')

    APP_ENV: AppEnv = 'development'
    SERVICE_NAME: str = Field(min_length=1)
    HOST: str = '0.0.0.0'
    PORT: int = Field(gt=0)
    LOG_LEVEL: str = 'info'
    # Services without a database (gateway, reports) leave it empty.
    DATABASE_URL: str = Field(default='', repr=False)
    # Queue role connection (schema `queue`); needed by services with a database, see lbstash.queue.
    QUEUE_DATABASE_URL: str | None = Field(default=None, repr=False)
    # Field-encryption key (base64, 32 bytes), or `FIELD_KEYS="1:...,2:..."` for rotation. Services that encrypt need one.
    FIELD_KEY: str | None = Field(default=None, repr=False)
    FIELD_KEYS: str | None = Field(default=None, repr=False)
    # Public address of the app: WebAuthn origin, e-mail links, Telegram webhook URL; `https` turns on the Secure cookie flag.
    PUBLIC_URL: str = 'http://localhost:8088'
    # Signs the internal token on service-to-service calls.
    INTERNAL_SECRET: str = Field(min_length=32, repr=False)
    # Public read-only demo: auth accepts `POST /auth/demo` for DEMO_USER_ID and the gateway refuses that user's writes.
    # Off unless the docker-compose demo overlay turns it on; with it off nothing about sign-in or the gateway changes.
    DEMO_MODE: bool = False
    # Service addresses; defaults match docker-compose names.
    GATEWAY_URL: str = 'http://gateway:3000'
    AUTH_URL: str = 'http://auth:3001'
    TRANSACTIONS_URL: str = 'http://transactions:3002'
    INGEST_URL: str = 'http://ingest:3003'
    PLANNING_URL: str = 'http://planning:3004'
    RECURRING_URL: str = 'http://recurring:3005'
    REPORTS_URL: str = 'http://reports:3006'
    TELEGRAM_URL: str = 'http://telegram:3007'

    @field_validator('PUBLIC_URL')
    @classmethod
    def _url(cls, v: str) -> str:
        u = urlsplit(v)
        if u.scheme not in ('http', 'https') or not u.hostname:
            raise ValueError('must be an http(s) URL')
        return v

    @field_validator('LOG_LEVEL', mode='before')
    @classmethod
    def _level(cls, v: Any) -> Any:
        try:
            return normalize_level(v) if isinstance(v, str) else v
        except ValueError:
            raise ValueError('must be one of debug, info, warning, error, critical, silent') from None


def load_env[E: BaseModel](model: type[E], environ: Mapping[str, str] | None = None) -> E:
    """Validate `environ` (default `os.environ`) against `model`; raise `EnvError` listing every problem."""
    import os

    try:
        return model.model_validate(dict(os.environ if environ is None else environ))
    except ValidationError as e:
        lines = [f'  {".".join(str(p) for p in i["loc"]) or "(root)"}: {i["msg"]}' for i in e.errors()]
        raise EnvError('Invalid environment:\n' + '\n'.join(lines)) from None


def is_prod(env: BaseEnv) -> bool:
    return env.APP_ENV == 'production'
