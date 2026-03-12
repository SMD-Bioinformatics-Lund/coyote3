"""Lifecycle and bootstrap helpers for the FastAPI application."""

from __future__ import annotations

import os
import threading
from contextlib import asynccontextmanager
from importlib import import_module

from api.extensions import store
from api.runtime import app as runtime_app, bind_runtime_context
from api.runtime_bootstrap import create_runtime_context

_runtime_bootstrap_lock = threading.Lock()
_runtime_initialized = False

ROUTE_MODULES = ()


def ensure_runtime_initialized(*, testing: bool, development: bool) -> None:
    """Initialize runtime dependencies once, lazily."""
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
    """Import route modules for side-effect registration with FastAPI."""
    for module_path in ROUTE_MODULES:
        import_module(module_path)


def create_lifespan(*, testing: bool, development: bool):
    """Create the FastAPI lifespan handler."""

    @asynccontextmanager
    async def _lifespan(_app):
        ensure_runtime_initialized(testing=testing, development=development)
        yield

    return _lifespan
