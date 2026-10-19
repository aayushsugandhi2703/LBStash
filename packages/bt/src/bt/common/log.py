"""JSON-lines logger. Log only ids and outcome codes, never message text, amounts, payees or secrets (README 15.3);
redaction is a backstop."""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import IO, Any, Final

LEVELS: Final[dict[str, int]] = {'debug': 10, 'info': 20, 'warning': 30, 'error': 40, 'critical': 50, 'silent': 100}
# Alternate spellings accepted for a level.
LEVEL_ALIASES: Final[dict[str, str]] = {'trace': 'debug', 'warn': 'warning', 'fatal': 'critical'}

# Matched case-insensitively at any depth.
REDACT_KEYS: Final = frozenset(
    {
        'password', 'newpassword', 'new_password', 'code', 'token', 'text', 'body', 'payee', 'description',
        'amount', 'amountminor', 'amount_minor', 'balance', 'balanceminor', 'balance_minor', 'email', 'secret',
        'authorization', 'cookie', 'set-cookie', 'x-internal-token', 'x-csrf-token',
    }
)  # fmt: skip
CENSOR: Final = '[redacted]'


def normalize_level(level: str) -> str:
    """Canonical level name; raises `ValueError` if unknown."""
    name = LEVEL_ALIASES.get(level.lower(), level.lower())
    if name not in LEVELS:
        raise ValueError(f'unknown log level: {level}')
    return name


def redact(value: Any) -> Any:
    """Copy of `value` with sensitive keys censored and exceptions rendered as text."""
    if isinstance(value, dict):
        return {k: CENSOR if str(k).lower() in REDACT_KEYS else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    if isinstance(value, BaseException):
        return f'{type(value).__name__}: {value}'
    return value


class Logger:
    """`log.info('req', status=200)` writes one JSON line."""

    def __init__(
        self, service: str, level: str = 'info', *, stream: IO[str] | None = None, bindings: dict[str, Any] | None = None
    ) -> None:
        self.service = service
        self._level = LEVELS[normalize_level(level)]
        self._stream = stream
        self._bindings = dict(bindings or {})

    def bind(self, **fields: Any) -> 'Logger':
        """Child logger that adds `fields` to every line."""
        return Logger(
            self.service,
            next(k for k, v in LEVELS.items() if v == self._level),
            stream=self._stream,
            bindings={**self._bindings, **fields},
        )

    def enabled(self, level: str) -> bool:
        """True if a line at `level` would be written."""
        return LEVELS[level] >= self._level

    def log(self, level: str, msg: str, **fields: Any) -> None:
        """Write one line at `level`."""
        if LEVELS[level] < self._level:
            return
        line = {
            'level': level,
            'time': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'service': self.service,
            'msg': msg,
            **redact({**self._bindings, **fields}),
        }
        out = self._stream or sys.stdout
        out.write(json.dumps(line, default=str, ensure_ascii=False) + '\n')
        out.flush()

    def debug(self, msg: str, **fields: Any) -> None:
        self.log('debug', msg, **fields)

    def info(self, msg: str, **fields: Any) -> None:
        self.log('info', msg, **fields)

    def warning(self, msg: str, **fields: Any) -> None:
        self.log('warning', msg, **fields)

    def error(self, msg: str, **fields: Any) -> None:
        self.log('error', msg, **fields)

    def critical(self, msg: str, **fields: Any) -> None:
        self.log('critical', msg, **fields)


def create_logger(service: str, level: str = 'info', *, stream: IO[str] | None = None) -> Logger:
    """Logger for `service` writing to stdout (or `stream`)."""
    return Logger(service, level, stream=stream)


class _StdlibBridge(logging.Handler):
    """Sends stdlib records (uvicorn, psycopg) through our logger so they are JSON and redacted."""

    def __init__(self, log: Logger) -> None:
        super().__init__()
        self._log = log

    def emit(self, record: logging.LogRecord) -> None:
        level = 'critical' if record.levelno >= 50 else 'error' if record.levelno >= 40 else (
            'warning' if record.levelno >= 30 else 'info' if record.levelno >= 20 else 'debug'
        )
        self._log.log(level, record.name, detail=record.getMessage())


def route_stdlib_logging(log: Logger) -> None:
    """Send the root stdlib logger into `log` (call once at start)."""
    root = logging.getLogger()
    root.handlers[:] = [_StdlibBridge(log)]
    root.setLevel(logging.WARNING)
