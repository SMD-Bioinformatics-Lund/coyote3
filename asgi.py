"""ASGI entrypoint for Coyote3 FastAPI API."""

from api.app.main import app  # noqa: TID251

__all__ = ["app"]
