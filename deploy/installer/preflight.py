# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Validate resolved center configuration and storage without connecting to services."""

from __future__ import annotations

import os
from pathlib import Path

from .storage import check_directory_access


def validate(config: dict) -> None:
    """Check mounted configuration and storage as the selected container identity.

    Args:
        config: Compose's resolved settings, held only in memory.

    Raises:
        ValueError: A mount or UID/GID is invalid.
        OSError: Configured storage is inaccessible.

    Notes:
        Requires the server packages on the host. Used by the standalone CLI;
        normal deployment performs application validation inside its API image.
    """
    from coyote_mongo.config.endpoints import mongo_endpoints
    from pydantic import ValidationError

    from .checks import validate_configuration

    api = config["services"]["api"]
    settings = api["environment"]
    mounts = {
        item["target"]: Path(item["source"])
        for item in api.get("volumes", [])
        if item.get("type") == "bind"
    }
    if "/app/center-config" not in mounts:
        raise ValueError("API requires a center configuration bind mount")
    os.environ.update({key: str(value) for key, value in settings.items() if value is not None})
    os.environ["COYOTE4_CENTER_CONFIG_DIR"] = str(mounts["/app/center-config"])
    mongo_endpoints(settings)
    try:
        validate_configuration()
    except ValidationError as error:
        fields = [
            ".".join(map(str, issue["loc"])) or "configuration"
            for issue in error.errors(include_input=False, include_url=False)
        ]
        raise ValueError("Invalid center configuration fields: " + ", ".join(fields)) from None
    args = api.get("build", {}).get("args", {})
    identity = (
        api.get("user") or f"{args.get('COYOTE4_UID', 10001)}:{args.get('COYOTE4_GID', 10001)}"
    )
    if len(str(identity).split(":")) != 2 or not all(
        part.isdigit() for part in str(identity).split(":")
    ):
        raise ValueError("API container identity must use numeric UID:GID")
    uid, gid = map(int, str(identity).split(":"))
    for target in ("/data", "/app/logs"):
        if target not in mounts:
            raise ValueError(f"API requires {target} as a bind mount")
        if any(
            item.get("target") == target and item.get("read_only")
            for item in api.get("volumes", [])
        ):
            raise ValueError(f"API requires {target} to be writable")
        check_directory_access(mounts[target], uid, gid, mount_root=mounts[target])
