"""Application release identity for API, frontend and worker deployments."""

import re
import sys
from pathlib import Path

_source_release = Path(__file__).resolve().parents[1] / "release.toml"
_release_path = (
    _source_release if _source_release.is_file() else Path(__file__).with_name("release.toml")
)
_release = _release_path.read_text()
_version_match = re.search(r'^application_version\s*=\s*"([^"]+)"', _release, re.MULTILINE)
if _version_match is None:
    raise RuntimeError("release.toml must declare application_version")
__version__ = _version_match.group(1)
_sdk_match = re.search(r'^sdk_version\s*=\s*"([^"]+)"', _release, re.MULTILINE)
if _sdk_match is None:
    raise RuntimeError("release.toml must declare sdk_version")
SDK_VERSION = _sdk_match.group(1)


def environment_version(environment: str) -> str:
    """Label an application release for its deployment environment.

    Args:
        environment: Long or short deployment environment name; production has no suffix.

    Returns:
        Application release with the existing dev, test or stage image suffix.
    """
    name = (environment or "production").strip().lower()
    name = {"development": "dev", "testing": "test", "staging": "stage", "production": "prod"}.get(
        name, name
    )
    return __version__ if name == "prod" else f"{__version__}-{name}"


if __name__ == "__main__":
    sys.stdout.write(f"{__version__}\n")
