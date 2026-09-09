"""Lifecycle and bootstrap helpers for the FastAPI application."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from importlib import import_module

from api.app.container import store
from api.app.runtime_setup import create_runtime_context
from api.app.runtime_state import app as runtime_app
from api.app.runtime_state import bind_runtime_context

_runtime_bootstrap_lock = threading.Lock()
_runtime_initialized = False

ROUTE_MODULE_PATHS: tuple[str, ...] = ()


def ensure_runtime_initialized(*, testing: bool, development: bool) -> None:
    """Initialize runtime dependencies once for the process.

    Args:
        testing: Whether the application is running under the test runtime.
        development: Whether development-mode runtime settings should be used.

    Notes:
        Serializes first initialization with a lock. Bootstrap failures normally
        propagate; during PYTEST_CURRENT_TEST they are logged, the store's prior
        attribute mapping is restored, and initialization is still marked complete.
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

    Notes:
        Imports each configured ROUTE_MODULE_PATHS entry for its side effects.
        The empty default registry performs no imports.
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
        """Initialize runtime dependencies before serving requests.

        Args:
            _app: FastAPI application supplied by the lifespan protocol, unused.

        Yields:
            None after bootstrap, allowing the application to serve requests.

        Notes:
            Uses the factory's testing/development flags and performs no teardown.
        """
        ensure_runtime_initialized(testing=testing, development=development)
        yield

    return _lifespan
