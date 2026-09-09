"""Distributed fixed-window rate limiting backed by the runtime Redis service."""

from __future__ import annotations


class RedisFixedWindowRateLimiter:
    """Apply one fixed-window quota consistently across all API workers."""

    def __init__(self, *, backend, limit: int, window_seconds: int) -> None:
        """Configure a counter backend and fixed-window quota.

        Args:
            backend: Backend implementing atomic ``increment_window`` calls.
            limit: Allowed requests per window, clamped to at least one.
            window_seconds: Window duration in seconds, clamped to at least one.
        """
        self.backend = backend
        self.limit = max(int(limit), 1)
        self.window_seconds = max(int(window_seconds), 1)

    def check(self, key: str) -> tuple[bool, int]:
        """Increment ``key`` and return whether it remains within quota."""
        count, retry_after = self.backend.increment_window(
            f"rate-limit:{key}", window_seconds=self.window_seconds
        )
        return count <= self.limit, (0 if count <= self.limit else retry_after)
