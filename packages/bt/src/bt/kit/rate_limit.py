"""In-memory sliding-window limiter. One process only, which is fine for a single VPS."""

import time
from collections import defaultdict
from collections.abc import Callable

_MAX_KEYS = 10_000


class MemoryRateLimiter:
    """At most `max` hits per `window_s` seconds for each key."""

    def __init__(self, max: int, window_s: float, now: Callable[[], float] = time.monotonic) -> None:
        self._max = max
        self._window = window_s
        self._now = now
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        """True if the call is allowed (and counted)."""
        t = self._now()
        recent = [x for x in self._hits[key] if t - x < self._window]
        if len(recent) >= self._max:
            self._hits[key] = recent
            return False
        recent.append(t)
        self._hits[key] = recent
        if len(self._hits) > _MAX_KEYS:
            for k in [k for k, v in self._hits.items() if not any(t - x < self._window for x in v)]:
                del self._hits[k]
        return True
