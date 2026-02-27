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

Authorization and RBAC are enforced by API endpoints.
These decorators only annotate route handlers with metadata that can be used
for UX/navigation behavior in the web UI layer.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def require_sample_access(sample_arg: str = "sample_name") -> callable:
    """Attach sample route-param metadata without enforcing access in Flask."""

    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(view_func, "required_sample_arg", sample_arg)
        return view_func

    return decorator


def require_group_access(group_arg: str = "assay") -> callable:
    """Attach assay-group route-param metadata without enforcing access in Flask."""

    def decorator(view_func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(view_func, "required_group_arg", group_arg)
        return view_func

    return decorator
