"""Load deployment identity and stylesheet metadata for the documentation site."""

import hashlib
import os
import runpy
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def on_config(config):
    """Load version and public center identity from the deployment's build inputs.

    Args:
        config: MkDocs configuration with the deployment environment in extra metadata.

    Returns:
        Configuration containing the version, center name/department, and CSS cache key.

    Raises:
        OSError: The version module, contact file, or stylesheet cannot be read.
        tomllib.TOMLDecodeError: The center contact file is not valid TOML.
    """
    root = Path(__file__).resolve().parents[2]
    version = runpy.run_path(str(root / "api/version.py"))
    config.extra["app_version"] = version["environment_version"](
        config.extra.get("environment") or "production"
    )
    stylesheet = Path(__file__).resolve().parents[1] / "stylesheets/application-theme.css"
    config.extra["docs_theme_version"] = hashlib.sha256(stylesheet.read_bytes()).hexdigest()[:12]
    with (root / "api/config/center/contact.toml").open("rb") as handle:
        organization = tomllib.load(handle)["organization"]
    config.extra["center_name"] = (
        os.getenv("ORGANIZATION_NAME", "").strip() or organization["name"].strip()
    )
    config.extra["center_department"] = organization.get("department", "").strip()
    config.extra["copyright_year"] = datetime.now(timezone.utc).year
    return config
