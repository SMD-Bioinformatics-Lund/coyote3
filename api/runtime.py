"""Runtime context helpers for API-owned services."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape


@dataclass
class _RuntimeApp:
    config: dict[str, Any]
    logger: logging.Logger


app = _RuntimeApp(config={}, logger=logging.getLogger("api.runtime"))
_runtime_user: ContextVar[Any | None] = ContextVar("api_runtime_user", default=None)
_jinja_env: Environment | None = None


def bind_flask_app(flask_app) -> None:
    """Bind runtime config/logger from the API bootstrap Flask app."""
    app.config = dict(flask_app.config)
    app.logger = flask_app.logger


def _template_dirs() -> list[str]:
    root = Path(__file__).resolve().parents[1]
    dirs: list[Path] = [root / "coyote" / "templates"]
    dirs.extend(sorted((root / "coyote" / "blueprints").glob("*/templates")))
    return [str(d) for d in dirs if d.is_dir()]


def _get_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(_template_dirs()),
            autoescape=select_autoescape(["html", "xml"]),
        )
    return _jinja_env


def render_template(template_name: str, **context: Any) -> str:
    """Render templates without Flask request/app context."""
    return _get_env().get_template(template_name).render(**context)


def flash(message: str, category: str = "info") -> None:
    """No-op flash replacement for API runtime."""
    app.logger.debug("flash[%s]: %s", category, message)


def set_current_user(user: Any) -> Token:
    """Set request-local API user context."""
    return _runtime_user.set(user)


def reset_current_user(token: Token) -> None:
    """Reset request-local API user context."""
    _runtime_user.reset(token)


def current_user() -> Any | None:
    """Get request-local API user context."""
    return _runtime_user.get()


def current_username(default: str = "api") -> str:
    """Resolve current request username, with safe fallback."""
    user = current_user()
    username = getattr(user, "username", None) if user is not None else None
    return str(username) if username else default


def current_user_is_admin() -> bool:
    """Resolve current request admin flag."""
    user = current_user()
    role = getattr(user, "role", None) if user is not None else None
    if role is not None:
        return str(role) == "admin"
    is_admin = getattr(user, "is_admin", None) if user is not None else None
    return bool(is_admin)

