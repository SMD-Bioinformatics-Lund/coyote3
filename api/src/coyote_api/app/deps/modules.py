# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Explicit feature requirements for API routers and individual endpoints."""

from coyote.config.application_modules import APPLICATION_MODULE_BY_KEY
from fastapi import HTTPException, Request


class RequireModules:
    """Reject a request when any declared feature is unavailable.

    Authentication and CSRF remain middleware responsibilities; endpoint permission
    and sample-scope checks still apply. No HTTP path matching is performed here.
    """

    def __init__(self, *module_keys: str) -> None:
        """Validate feature identities when a router is constructed.

        Args:
            module_keys: Features all required by the router or endpoint.

        Raises:
            ValueError: No features were supplied or an identity is unknown.
        """
        if not module_keys or set(module_keys) - APPLICATION_MODULE_BY_KEY.keys():
            raise ValueError(f"Unknown or empty application module requirement: {module_keys}")
        self.module_keys = tuple(dict.fromkeys(module_keys))

    def __call__(self, request: Request) -> None:
        """Read saved availability before resolving the endpoint's service operations.

        Args:
            request: Authenticated request, or a permitted public request.

        Raises:
            HTTPException: A required feature is disabled; returns the existing
                structured 503 with Retry-After through the standard error handler.
        """
        from coyote_api.app.deps.services import get_app_controls_service

        controls = get_app_controls_service()
        for key in self.module_keys:
            if not controls.module_enabled(key):
                request.state.disabled_module = key
                raise HTTPException(
                    503,
                    detail={"category": "module_disabled", "module": key},
                    headers={"Retry-After": "60"},
                )
