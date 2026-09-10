"""Application version ownership for the FastAPI/runtime stack."""

import sys

__version__ = "4.0.0"


def environment_version(environment: str) -> str:
    """Return the release version with a non-production environment suffix.

    Args:
        environment: Long or short deployment environment name.

    Returns:
        Plain version for production; otherwise a lowercase environment suffix.
    """
    name = (environment or "production").strip().lower()
    name = {"development": "dev", "testing": "test", "staging": "stage", "production": "prod"}.get(
        name, name
    )
    return __version__ if name == "prod" else f"{__version__}-{name}"


if __name__ == "__main__":
    sys.stdout.write(f"{__version__}\n")
