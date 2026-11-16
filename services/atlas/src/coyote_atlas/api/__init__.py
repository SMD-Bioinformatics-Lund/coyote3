# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Optional authenticated API integration loaded only by an installed Coyote server."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import APIRouter


def routers() -> tuple["APIRouter", ...]:
    """Return administrative reference routes using the host's authorization and storage.

    Returns:
        The Atlas planning and installation router.

    Raises:
        ImportError: The optional server integration is not installed.
    """
    from coyote_atlas.api.routes import router

    return (router,)
