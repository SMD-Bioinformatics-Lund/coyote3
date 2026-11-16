# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Run installed deployment validators before initializing runtime connections."""

import os
from collections.abc import Mapping
from importlib.metadata import entry_points
from typing import Any


def validate_runtime_extensions(config: Mapping[str, Any]) -> None:
    """Validate installed service constraints against the selected host settings.

    Args:
        config: Resolved host settings before logger, cache or database initialization.
            Only keys declared by each validator are supplied to that package.

    Raises:
        RuntimeError: Validators have duplicate names or an installed validator fails.

    Notes:
        Extensions are trusted installed code. Validators must perform no writes;
        an enabled deployment validator may inspect its explicitly selected
        credentials before the host initializes storage. Disabled extensions
        perform no I/O and do not constrain unrelated deployments.
    """
    names: set[str] = set()
    for entry in sorted(
        entry_points(group="coyote.runtime.validators"), key=lambda item: item.name
    ):
        if entry.name in names:
            raise RuntimeError(f"Duplicate runtime validator: {entry.name}")
        names.add(entry.name)
        try:
            validator = entry.load()
            keys = validator.configuration_keys
            if not isinstance(keys, tuple) or any(not isinstance(key, str) for key in keys):
                raise TypeError("Runtime validators must declare their configuration keys")
            validator({key: config.get(key, os.getenv(key)) for key in keys})
        except Exception as exc:
            raise RuntimeError(
                f"Deployment validation failed for installed service: {entry.name}"
            ) from exc
