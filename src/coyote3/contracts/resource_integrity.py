"""Host-supplied integrity hashing for persisted assay and gene-list release content."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Protocol


class ResourceHasher(Protocol):
    """Compute the persisted digest format without exposing its serialization provider."""

    def __call__(self, content: dict[str, Any]) -> str:
        """Return the deterministic release digest for application record content."""
        ...


_host_hasher: ResourceHasher | None = None
_scoped_hasher: ContextVar[ResourceHasher | None] = ContextVar("resource_hasher", default=None)


def configure_resource_hasher(hasher: ResourceHasher) -> None:
    """Bind the host's persistence-compatible codec before executing release workflows.

    Args:
        hasher: Trusted serializer and digest implementation for existing release records.

    Notes:
        Hosts own this capability. The library does not discover a codec, import a
        database driver or silently substitute a different persisted hash format.
    """
    global _host_hasher
    _host_hasher = hasher


@contextmanager
def using_resource_hasher(hasher: ResourceHasher) -> Iterator[None]:
    """Override the host codec for one execution context and restore it on failure.

    Args:
        hasher: Trusted codec for this execution; concurrent contexts remain independent.

    Yields:
        Control while the supplied resource-integrity capability is active.
    """
    token = _scoped_hasher.set(hasher)
    try:
        yield
    finally:
        _scoped_hasher.reset(token)


def resource_content_hash(content: dict[str, Any]) -> str:
    """Digest release content through the explicit host capability.

    Args:
        content: Application assay document or identity-keyed gene-list records.

    Returns:
        Digest produced by the host's persisted-format implementation.

    Raises:
        RuntimeError: The host did not supply a resource-integrity capability.
    """
    hasher = _scoped_hasher.get() or _host_hasher
    if hasher is None:
        raise RuntimeError("Configure a resource hasher before executing release workflows")
    return hasher(content)
