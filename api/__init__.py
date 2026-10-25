"""Standalone HTTP application and runtime adapters consuming the Coyote3 library."""

from typing import Any

from api.config.bootstrap import configure_center_from_environment

configure_center_from_environment()

__all__ = ["app", "create_api_app"]


def __getattr__(name: str) -> Any:
    """Load the web application only when its entry point is requested.

    Args:
        name: Exported application object or factory name.

    Returns:
        Requested application object or factory.

    Raises:
        AttributeError: The requested name is not an application export.
    """
    if name in {"app", "create_api_app"}:
        from .app import app, create_api_app

        return {"app": app, "create_api_app": create_api_app}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
