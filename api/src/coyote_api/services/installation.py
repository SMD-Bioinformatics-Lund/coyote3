# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized application installation commands kept outside the clinical SDK."""

from collections.abc import Callable
from typing import Any

from coyote.application.operations.runtime import ApplicationRuntime


class InstallationServices:
    """Host factory for authenticated packaged deployment data."""

    def __init__(self, *, deployment: Callable[[], Any]) -> None:
        """Bind explicitly selected host installation workflows.

        Args:
            deployment: Factory for authenticated deployment-catalog maintenance.
        """
        self.deployment = deployment


class Installation:
    """Install allowlisted deployment catalogs."""

    def __init__(self, runtime: ApplicationRuntime, services: InstallationServices) -> None:
        """Bind current authorization and existing atomic installation workflows.

        Args:
            runtime: Verified session, current policy and access-audit capabilities.
            services: Host factories for permitted installation workflows.
        """
        self._runtime, self._services = runtime, services

    def deployment(self, modules: list[str], *, force: bool = False) -> dict[str, Any]:
        """Install supported bundled catalogs under the existing administrator policy.

        Args:
            modules: Allowlisted packaged catalog module names.
            force: Whether the installation service should refresh existing supported data.

        Returns:
            Installation outcome and affected collections.

        Raises:
            AppError: The current identity is not an administrator or inputs are invalid.
        """
        return self._runtime.execute(
            "installation.deployment",
            None,
            lambda actor, sample: dict(
                self._services.deployment().install(user=actor, modules=modules, force=force)
            ),
        )
