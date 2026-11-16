# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Connection defaults owned once by the MongoDB adapter."""

import tomllib
from pathlib import Path
from typing import Any

with Path(__file__).with_suffix(".toml").open("rb") as _stream:
    MONGO_DEFAULTS = tomllib.load(_stream)


def mongo_default(name: str, value_type: type) -> Any:
    """Read a declared connection default without applying deployment overrides.

    Args:
        name: Pool, timeout or concern setting in the adapter's defaults catalog.
        value_type: Scalar conversion expected by the consuming configuration.

    Returns:
        The catalog value converted to the requested type.

    Raises:
        KeyError: The setting is not declared.
        ValueError: The value cannot be converted to the requested scalar type.
    """
    return value_type(MONGO_DEFAULTS[name])
