# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Lifecycle and bootstrap helpers for the FastAPI application."""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from importlib import import_module

from coyote_api.app.runtime_setup import create_runtime_context
from coyote_api.app.runtime_state import bind_runtime_context
from coyote_api.config.paths import initialize_storage_directories

_runtime_bootstrap_lock = threading.Lock()
_runtime_initialized = False

ROUTE_MODULE_PATHS: tuple[str, ...] = ()


def ensure_runtime_initialized(*, testing: bool, development: bool) -> None:
    """Initialize runtime dependencies once for the process.

    Args:
        testing: Whether the application is running under the test runtime.
        development: Whether development-mode runtime settings should be used.

    Raises:
        Exception: Dependency creation or runtime binding fails. The original
            exception propagates and a later call may retry initialization.

    Notes:
        Serializes initialization and marks completion only after dependencies
        have been created and bound successfully. Test hosts must supply their
        dependencies explicitly; the presence of a test runner changes no behavior.
    """
    global _runtime_initialized
    if _runtime_initialized:
        return
    with _runtime_bootstrap_lock:
        if _runtime_initialized:
            return
        runtime_context = create_runtime_context(testing=testing, development=development)
        bind_runtime_context(runtime_context)
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
        initialize_storage_directories()
        yield

    return _lifespan
