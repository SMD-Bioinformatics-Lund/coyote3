# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Opt in to guarded demonstration routes through installed extension metadata."""

import os
from typing import TYPE_CHECKING

from coyote_demo.deployment import runtime_validator, validate_demo_target

if TYPE_CHECKING:
    from fastapi import APIRouter


def routers() -> tuple["APIRouter", ...] | None:
    """Expose demo routes only after an explicitly enabled target passes isolation checks.

    Returns:
        None when COYOTE_DEMO_ENABLED is unset or false; otherwise the demo router.

    Raises:
        ValueError: Enabled demonstration settings could select ordinary deployment storage.
        ImportError: The optional API integration dependencies are absent.
    """
    if os.environ.get("COYOTE_DEMO_ENABLED", "").lower() not in {"1", "true"}:
        return None
    from coyote_api.config.runtime_settings import DefaultConfig

    settings = {
        key: getattr(DefaultConfig, key, os.environ.get(key))
        for key in runtime_validator.configuration_keys
    }
    validate_demo_target(settings)
    from coyote_demo.api.routes import router

    return (router,)
