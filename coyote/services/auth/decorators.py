#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
Metadata-only access decorators for Flask UI routes.

RBAC/data authorization is enforced by API endpoints.
This module only annotates Flask route handlers with access metadata that can
be used by UI code for navigation/UX hints.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def require(
    permission: str | None = None,
    min_role: str | None = None,
    min_level: int | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Attach access metadata to Flask route handlers without enforcing it."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, "required_permission", permission)
        setattr(func, "required_access_level", min_level)
        setattr(func, "required_role_name", min_role)
        return func

    return decorator

