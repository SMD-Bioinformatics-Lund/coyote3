"""Lifecycle and bootstrap helpers for the FastAPI application."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from importlib import import_module

from api.extensions import store
from api.runtime import app as runtime_app
from api.runtime import bind_runtime_context
from api.runtime_bootstrap import create_runtime_context

_runtime_bootstrap_lock = threading.Lock()
_runtime_initialized = False

ROUTE_MODULE_PATHS: tuple[str, ...] = ()


def ensure_runtime_initialized(*, testing: bool, development: bool) -> None:
    """Initialize shared runtime dependencies once for the process.

    Args:
        testing: Whether the application is running under the test runtime.
        development: Whether development-mode runtime settings should be used.

    Returns:
        ``None``. Runtime state is bound as a process-wide side effect.
    """
    global _runtime_initialized
    if _runtime_initialized:
        return
    with _runtime_bootstrap_lock:
        if _runtime_initialized:
            return
        store_state_before = dict(store.__dict__)
        try:
            runtime_context = create_runtime_context(testing=testing, development=development)
            bind_runtime_context(runtime_context)
        except Exception:
            if os.environ.get("PYTEST_CURRENT_TEST"):
                store.__dict__.clear()
                store.__dict__.update(store_state_before)
                runtime_app.logger.warning(
                    "Skipping runtime DB bootstrap during pytest due to initialization failure.",
                    exc_info=True,
                )
            else:
                raise
        _runtime_initialized = True


def register_route_modules() -> None:
    """Import route modules for side-effect registration with FastAPI.

    Returns:
        ``None``. Import side effects register route modules with the app.
    """
    for module_path in ROUTE_MODULE_PATHS:
        import_module(module_path)


def create_lifespan(*, testing: bool, development: bool):
    """Create the FastAPI lifespan handler.

    Args:
        testing: Whether the application is running under the test runtime.
        development: Whether development-mode runtime settings should be used.

    Returns:
        A FastAPI lifespan context manager.
    """

    @asynccontextmanager
    async def _lifespan(_app):
        """Initialize process-wide runtime dependencies on application startup."""
        ensure_runtime_initialized(testing=testing, development=development)
        yield

    return _lifespan
