# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Bind deployment-selected center configuration before importing library contracts."""

import os
from importlib.metadata import version
from pathlib import Path

from coyote.config import CenterConfiguration, configure_center
from coyote.contracts.resource_integrity import configure_resource_hasher
from coyote_mongo.resource_integrity import resource_content_hash
from dotenv import load_dotenv

from coyote_api.version import SDK_VERSION


def center_directory_from_environment() -> Path | None:
    """Select a process override or inherit the center directory used for host mounts.

    Returns:
        Expanded absolute directory from COYOTE4_CENTER_CONFIG_DIR, falling back
        to COYOTE4_CENTER_CONFIG_HOST_DIR. Blank values are ignored; None selects
        bundled defaults. Compose supplies an explicit container path, so its
        host mount source is never used as a container filesystem path.
    """
    directory = (
        os.getenv("COYOTE4_CENTER_CONFIG_DIR", "").strip()
        or os.getenv("COYOTE4_CENTER_CONFIG_HOST_DIR", "").strip()
    )
    return Path(directory).expanduser().absolute() if directory else None


def configure_center_from_environment() -> None:
    """Select center files once at startup, inheriting the host directory when needed.

    Raises:
        FileNotFoundError: A selected directory is incomplete.
        RuntimeError: The installed core differs from the API's declared dependency,
            or another profile has already initialized library contracts.
    """
    runtime_root = Path(os.getenv("COYOTE4_RUNTIME_ROOT") or Path.cwd()).resolve()
    if version("coyote-core") != SDK_VERSION:
        raise RuntimeError(
            "Installed core does not match coyote-server's dependency; install the selected core"
        )
    load_dotenv(runtime_root / ".env")
    configure_resource_hasher(resource_content_hash)
    directory = center_directory_from_environment()
    providers = os.getenv("AUTHENTICATION_PROVIDERS", "").strip()
    if directory or providers:
        configure_center(
            CenterConfiguration(
                directory=directory,
                authentication_providers=providers or None,
            )
        )
