"""Service deps plus the pieces built once at start-up."""

from dataclasses import dataclass

from lbstash.crypto import FieldCipher
from lbstash.kit import Deps

from .env import Env
from .mailer import Mailer, create_mailer


@dataclass
class Svc:
    deps: Deps[Env]
    cipher: FieldCipher
    mailer: Mailer


def create_svc(deps: Deps[Env], mailer: Mailer | None = None) -> Svc:
    """Pass a `Mailer` to replace the configured one (tests)."""
    return Svc(deps, FieldCipher.from_keys(deps.env.FIELD_KEY, deps.env.FIELD_KEYS), mailer or create_mailer(deps.env, deps.log))
