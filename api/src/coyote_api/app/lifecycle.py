# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Lifecycle and bootstrap helpers for the FastAPI application."""

from __future__ import annotations

import atexit
import threading
from contextlib import asynccontextmanager
from importlib import import_module

from coyote_api.app.runtime_setup import ApiRuntimeContext, create_runtime_context
from coyote_api.app.runtime_state import bind_runtime_context, clear_runtime_context
from coyote_api.config.paths import initialize_storage_directories

_runtime_bootstrap_lock = threading.RLock()
_runtime_initialized = False
_runtime_context: ApiRuntimeContext | None = None
_runtime_mode: tuple[bool, bool] | None = None
_lifespan_owners = 0
_process_owner = False

ROUTE_MODULE_PATHS: tuple[str, ...] = ()


def ensure_runtime_initialized(*, testing: bool, development: bool) -> ApiRuntimeContext:
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
    global _runtime_initialized, _runtime_context, _runtime_mode, _process_owner
    with _runtime_bootstrap_lock:
        if _runtime_initialized:
            if _runtime_mode != (testing, development):
                raise RuntimeError("Active runtimes in one process must use the same mode")
            assert _runtime_context is not None
            return _runtime_context
        runtime_context = create_runtime_context(testing=testing, development=development)
        try:
            bind_runtime_context(runtime_context)
        except BaseException:
            try:
                runtime_context.close()
            except Exception:
                runtime_context.logger.exception("Runtime cleanup failed after binding error")
            finally:
                clear_runtime_context()
            raise
        _runtime_context = runtime_context
        _runtime_mode = (testing, development)
        _process_owner = _lifespan_owners == 0
        _runtime_initialized = True
        return runtime_context


def shutdown_runtime() -> None:
    """Release a worker's process ownership without closing active ASGI lifespans."""
    global _process_owner
    with _runtime_bootstrap_lock:
        _process_owner = False
        if _lifespan_owners == 0:
            _close_runtime()


def _close_runtime() -> None:
    """Clear shared composition and close connections while holding the runtime lock."""
    global _runtime_initialized, _runtime_context, _runtime_mode
    if _runtime_context is None:
        return
    from coyote_api.app.deps.services import clear_service_caches

    runtime, _runtime_context = _runtime_context, None
    _runtime_initialized = False
    _runtime_mode = None
    clear_service_caches()
    clear_runtime_context()
    if runtime is not None:
        runtime.close()


atexit.register(shutdown_runtime)


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
        """Share the process runtime until its final owner finishes serving requests.

        Existing providers remain process-scoped. App state exposes the owned
        context explicitly; concurrent applications must use identical settings.
        """
        global _lifespan_owners
        acquired = False
        try:
            with _runtime_bootstrap_lock:
                _lifespan_owners += 1
                acquired = True
                runtime = ensure_runtime_initialized(testing=testing, development=development)
                _app.state.runtime = runtime
            initialize_storage_directories()
            yield
        finally:
            if acquired:
                if _app is not None:
                    _app.state.runtime = None
                with _runtime_bootstrap_lock:
                    _lifespan_owners -= 1
                    if _lifespan_owners == 0 and not _process_owner:
                        _close_runtime()

    return _lifespan
