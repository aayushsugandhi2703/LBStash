"""Password rules shared by the web strength meter and the auth service, so the page and server agree:
12+ characters, not common, no email name."""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Final

from ._text import utf16_len

MIN_PASSWORD_LENGTH: Final = 12

# Very common passwords of 12+ characters; the server may add a larger breached list.
_COMMON: Final = frozenset(
    {
        'password1234', '123456789012', 'qwertyuiop12', 'iloveyou1234', 'passwordpassword', 'password12345',
        'welcome12345', 'letmein12345', 'administrator', 'qwertyuiopas', 'abcdefghijkl', '111111111111',
        '1234567890123', '12345678901234', 'changeme1234', 'iloveyou12345', 'trustno1trustno1',
    }
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class PasswordChecks:
    """Which rules pass."""

    len: bool
    common: bool
    # Does not contain the email's local part (when it is 3+ characters).
    email: bool


def check_password(password: str, email: str = '', extra_common: Collection[str] | None = None) -> PasswordChecks:
    """Evaluate the three rules. Length counts UTF-16 units, as the web app does."""
    pw = password.lower()
    local = email.split('@')[0].lower()
    n = utf16_len(password)
    return PasswordChecks(
        len=n >= MIN_PASSWORD_LENGTH,
        common=n > 0 and pw not in _COMMON and not (extra_common is not None and pw in extra_common),
        email=n > 0 and not (utf16_len(local) >= 3 and local in pw),
    )


def password_acceptable(c: PasswordChecks) -> bool:
    return c.len and c.common and c.email
