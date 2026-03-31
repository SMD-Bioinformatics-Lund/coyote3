"""Lightweight in-process fixed-window rate limiter."""

from __future__ import annotations

import threading
import time


class FixedWindowRateLimiter:
    """Thread-safe per-key fixed-window limiter."""

    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = max(int(limit), 1)
        self.window_seconds = max(int(window_seconds), 1)
        self._lock = threading.Lock()
        self._state: dict[str, tuple[int, int]] = {}

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        """Check whether ``key`` may proceed.

        Returns:
            tuple[bool, int]: (allowed, retry_after_seconds)
        """
        now_ts = int(now if now is not None else time.time())
        with self._lock:
            window_start, count = self._state.get(key, (now_ts, 0))
            if now_ts - window_start >= self.window_seconds:
                window_start = now_ts
                count = 0
            if count >= self.limit:
                retry_after = self.window_seconds - max(0, now_ts - window_start)
                return False, max(retry_after, 1)
            count += 1
            self._state[key] = (window_start, count)
            self._gc(now_ts)
            return True, 0

    def _gc(self, now_ts: int) -> None:
        """Drop stale limiter windows opportunistically."""
        if len(self._state) < 2048:
            return
        cutoff = now_ts - (self.window_seconds * 2)
        for key, (window_start, _) in list(self._state.items()):
            if window_start < cutoff:
                self._state.pop(key, None)
