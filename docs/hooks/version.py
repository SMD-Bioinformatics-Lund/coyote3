"""Display the deployment version in the documentation site."""

import runpy
from pathlib import Path


def on_config(config):
    """Set documentation metadata using the canonical application version function."""
    version = runpy.run_path(str(Path(__file__).resolve().parents[2] / "api/version.py"))
    config.extra["app_version"] = version["environment_version"](
        config.extra.get("environment") or "production"
    )
    return config
