# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Independent API package identity and the bundled application release label."""

import sys
import tomllib
from importlib.metadata import requires, version
from importlib.resources import files

__version__ = version("coyote-api")
APPLICATION_VERSION = tomllib.loads(
    files("coyote_api").joinpath("config/application_release.toml").read_text(encoding="utf-8")
)["application_version"]
_core_requirement = next(
    requirement
    for requirement in requires("coyote-api") or []
    if requirement.startswith("coyote-core==")
)
SDK_VERSION = _core_requirement.split("==", 1)[1]


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
    return APPLICATION_VERSION if name == "prod" else f"{APPLICATION_VERSION}-{name}"


if __name__ == "__main__":
    sys.stdout.write(f"{__version__}\n")
