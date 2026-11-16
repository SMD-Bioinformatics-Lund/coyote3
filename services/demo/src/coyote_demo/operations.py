# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Authorized demonstration operations using core session and audit boundaries."""

from collections.abc import Callable
from typing import Any

from coyote.application.operations.runtime import ApplicationRuntime

from coyote_demo.installation import DemoInstallationService


class DemoInstallation:
    """Install only packaged synthetic resources after current permission checks."""

    def __init__(self, runtime: ApplicationRuntime, service: Callable[[], DemoInstallationService]):
        """Bind the verified session and guarded host installer.

        Args:
            runtime: Current authentication, permissions and access-audit capabilities.
            service: Host factory that verifies isolated demo targets before database use.
        """
        self._runtime, self._service = runtime, service

    def plan(self) -> dict[str, Any]:
        """Inspect installed synthetic resources with demo:install permission."""
        return self._runtime.execute(
            "installation.plan",
            ("demo:install",),
            lambda actor, sample: dict(self._service().plan()),
        )

    def starter(self) -> dict[str, Any]:
        """Install starter configuration and synthetic DNA/RNA samples with demo:install."""
        return self._runtime.execute(
            "installation.starter",
            ("demo:install",),
            lambda actor, sample: dict(self._service().install_starter(actor.username)),
        )

    def configuration(self) -> dict[str, Any]:
        """Install packaged synthetic configuration with demo:install permission."""
        return self._runtime.execute(
            "installation.configuration",
            ("demo:install",),
            lambda actor, sample: dict(self._service().install_configuration(actor.username)),
        )

    def sample(self, key: str) -> dict[str, Any]:
        """Install an allowlisted synthetic sample after scope and collision checks.

        Args:
            key: Packaged sample identifier, never an arbitrary filesystem path.

        Returns:
            Installation outcome; existing reviewed samples are preserved.

        Raises:
            AppError: Permission is denied, the key is unknown or configuration conflicts.
        """
        return self._runtime.execute(
            "installation.sample",
            ("demo:install",),
            lambda actor, sample: dict(self._service().install_sample(key, actor.username)),
        )
