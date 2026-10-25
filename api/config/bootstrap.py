"""Bind deployment-selected center configuration before importing library contracts."""

import os
from importlib.metadata import version
from pathlib import Path

from dotenv import load_dotenv

from api.infra.mongo.resource_integrity import resource_content_hash
from api.version import SDK_VERSION
from coyote3.config import CenterConfiguration, configure_center
from coyote3.contracts.resource_integrity import configure_resource_hasher


def configure_center_from_environment() -> None:
    """Select an explicit center directory once at API or worker process startup.

    Raises:
        FileNotFoundError: A selected directory is incomplete.
        RuntimeError: The installed SDK differs from the application release pin,
            or another profile has already initialized library contracts.
    """
    runtime_root = Path(os.getenv("COYOTE3_RUNTIME_ROOT") or Path.cwd()).resolve()
    if version("Coyote3") != SDK_VERSION:
        raise RuntimeError(
            "Installed Coyote3 SDK does not match release.toml; install the selected SDK"
        )
    load_dotenv(runtime_root / ".env")
    configure_resource_hasher(resource_content_hash)
    directory = os.getenv("COYOTE3_CENTER_CONFIG_DIR", "").strip()
    providers = os.getenv("AUTHENTICATION_PROVIDERS", "").strip()
    if directory or providers:
        configure_center(
            CenterConfiguration(
                directory=Path(directory) if directory else None,
                authentication_providers=providers or None,
            )
        )
