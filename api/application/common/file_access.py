"""Constrain sample artifact reads to the application's mounted data directory."""

from pathlib import Path

from api.config.paths import DATA_CONTAINER_ROOT
from api.domain.common.errors import api_error


def resolve_sample_file_path(value: str) -> Path:
    """Resolve a registered sample artifact beneath the mounted data root.

    Args:
        value: Persisted absolute artifact path, including any filesystem symlinks.

    Returns:
        Canonical path to an existing regular file beneath the data root.

    Raises:
        AppError: The path is missing, unreadable, or resolves outside the data root.
    """
    try:
        path = Path(value).expanduser().resolve(strict=True)
        if path.is_relative_to(DATA_CONTAINER_ROOT.resolve()) and path.is_file():
            return path
    except (OSError, RuntimeError, ValueError):
        pass
    raise api_error(404, "Registered sample artifact is not available")
