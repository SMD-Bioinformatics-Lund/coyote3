# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Optional Coyote API extension discovered from installed distribution metadata."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter


def routers() -> tuple["APIRouter", ...]:
    """Provide Relay routes using the installed server's authenticated composition.

    Returns:
        The sample, collection and durable-job router. Its existing server
        dependencies enforce permissions, module availability and actor scope.

    Raises:
        ImportError: The server integration dependencies are not installed.
    """
    from coyote_relay.api.routes import router

    return (router,)
