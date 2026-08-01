"""Small in-process sliding-window rate limiter.

Used to throttle the admin login endpoint against brute-force attempts. This is
an in-memory store keyed by client identifier (IP); it is not a replacement for
a distributed limiter, but it is sufficient for a single-node blog behind a
reverse proxy.
"""

import threading
import time

MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes


class SlidingWindowRateLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._failures: dict[str, list[float]] = {}

    def _purge(self, key: str) -> None:
        cutoff = time.time() - self.window_seconds
        recent = [t for t in self._failures.get(key, []) if t >= cutoff]
        if recent:
            self._failures[key] = recent
        else:
            self._failures.pop(key, None)

    def is_blocked(self, key: str) -> bool:
        with self._lock:
            self._purge(key)
            return len(self._failures.get(key, [])) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._failures.setdefault(key, []).append(time.time())
            self._purge(key)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)
