"""Opaque token helpers for session and action-token storage."""

from __future__ import annotations

import hashlib
import secrets


def issue_opaque_token(nbytes: int = 48) -> str:
    """Return a URL-safe high-entropy opaque token."""
    return secrets.token_urlsafe(max(int(nbytes), 32))


def token_hash(token: str) -> str:
    """Return the SHA-256 hash used for persistent token lookup."""
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def constant_time_equal(left: str, right: str) -> bool:
    """Compare two token strings without early-exit timing behavior."""
    return secrets.compare_digest(str(left), str(right))
