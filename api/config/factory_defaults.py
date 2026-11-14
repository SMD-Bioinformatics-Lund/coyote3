"""Factory fallbacks owned by the API host, independent of live environment inputs."""

import tomllib
from copy import deepcopy
from pathlib import Path
from typing import Any

API_DEFAULTS_PATH = Path(__file__).with_name("factory_defaults.toml")

with API_DEFAULTS_PATH.open("rb") as _handle:
    _DEFAULTS = tomllib.load(_handle)
if set(_DEFAULTS) != {"runtime", "profiles", "product", "http_clients", "modes"}:
    raise ValueError("API factory catalog must contain exactly its declared sections")


def api_default(path: str, value_type: type | None = None) -> Any:
    """Read an API fallback before deployment overrides are applied.

    Args:
        path: Dotted setting path within the API catalog.
        value_type: Optional scalar conversion used by runtime consumers. Boolean
            strings accept environment spellings; None preserves the catalog type.

    Returns:
        An independent value, optionally converted to the requested scalar type.

    Raises:
        KeyError: The host setting is not declared.
        ValueError: A numeric value cannot be converted to the requested type.
    """
    value: Any = _DEFAULTS
    for part in path.split("."):
        value = value[part]
    value = deepcopy(value)
    if value_type is bool and isinstance(value, str):
        value = value.strip().lower() in {"1", "true", "yes", "on"}
    return value_type(value) if value_type is not None else value
