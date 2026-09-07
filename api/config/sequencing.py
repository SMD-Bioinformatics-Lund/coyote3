"""Software-owned sequencing platform capabilities.

Platform names describe validated technology families, not instrument models.
The read technology and permitted read modes are derived from this registry so
an ASP or sample cannot claim an incompatible combination.
"""

from __future__ import annotations

from typing import Final

PLATFORM_CAPABILITIES: Final[dict[str, dict[str, object]]] = {
    "illumina": {"read_technology": "short_read", "read_modes": ("SE", "PE")},
    "iontorrent": {"read_technology": "short_read", "read_modes": ()},
    "pacbio": {"read_technology": "long_read", "read_modes": ()},
    "nanopore": {"read_technology": "long_read", "read_modes": ()},
}

PLATFORM_OPTIONS: Final[tuple[str, ...]] = tuple(PLATFORM_CAPABILITIES)
READ_MODE_OPTIONS: Final[tuple[str, ...]] = tuple(
    dict.fromkeys(
        mode for capability in PLATFORM_CAPABILITIES.values() for mode in capability["read_modes"]
    )
)


def supported_read_modes(platform: str | None) -> tuple[str, ...]:
    """Return the read modes available for one supported platform."""
    if not platform:
        return ()
    capability = PLATFORM_CAPABILITIES.get(str(platform).strip().lower())
    if capability is None:
        raise ValueError(f"platform '{platform}' is not supported by the application")
    return tuple(str(mode) for mode in capability["read_modes"])


def derived_read_technology(platform: str | None) -> str | None:
    """Return the immutable read technology derived from a platform."""
    if not platform:
        return None
    capability = PLATFORM_CAPABILITIES.get(str(platform).strip().lower())
    if capability is None:
        raise ValueError(f"platform '{platform}' is not supported by the application")
    return str(capability["read_technology"])


def validate_platform_read_mode(platform: str | None, read_mode: str | None) -> None:
    """Reject a read mode that is not available for the selected platform."""
    if not read_mode:
        return
    if not platform:
        raise ValueError("read_mode requires a platform")
    capability = PLATFORM_CAPABILITIES.get(str(platform).strip().lower())
    if capability is None:
        raise ValueError(f"platform '{platform}' is not supported by the application")
    allowed = set(capability["read_modes"])
    if str(read_mode).strip().upper() not in allowed:
        allowed_text = ", ".join(sorted(allowed)) or "no selectable read mode"
        raise ValueError(
            f"read_mode '{read_mode}' is not supported for platform '{platform}'; allowed: {allowed_text}"
        )
