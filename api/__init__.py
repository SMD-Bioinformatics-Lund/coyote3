"""Top-level API package.

Keep imports side-effect free so callers can import model modules (for example
``api.models.user``) without initializing the API runtime.
"""

from typing import Any

__all__ = ["app", "create_api_app"]


def __getattr__(name: str) -> Any:
    if name in {"app", "create_api_app"}:
        from .app import app, create_api_app

        return {"app": app, "create_api_app": create_api_app}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
