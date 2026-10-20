"""Remembers for a few seconds that a session was alive, so one page load does not ask auth ten times."""

import time
from collections.abc import Callable
from dataclasses import dataclass

_PURGE_ABOVE = 5_000


@dataclass(frozen=True, slots=True)
class SessionState:
    """What auth said about a live session."""

    limited: bool


class SessionCache:
    """Only positive answers are kept ("no" is always asked again, so a revoked session dies at once)."""

    def __init__(self, ttl_s: float = 10.0, now: Callable[[], float] = time.monotonic) -> None:
        self._alive: dict[str, tuple[float, bool]] = {}
        self._ttl = ttl_s
        self._now = now

    def get(self, sid: str) -> SessionState | None:
        """Session status when `sid` was confirmed alive less than the ttl ago."""
        hit = self._alive.get(sid)
        if hit is None:
            return None
        until, limited = hit
        if until <= self._now():
            del self._alive[sid]
            return None
        return SessionState(limited)

    def has(self, sid: str) -> bool:
        return self.get(sid) is not None

    def remember(self, sid: str, limited: bool = False) -> None:
        t = self._now()
        self._alive[sid] = (t + self._ttl, limited)
        if len(self._alive) > _PURGE_ABOVE:
            for k in [k for k, (until, _) in self._alive.items() if until <= t]:
                del self._alive[k]
