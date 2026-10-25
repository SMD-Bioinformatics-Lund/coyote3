"""Authorized application installation commands kept outside the clinical SDK."""

from collections.abc import Callable
from typing import Any

from coyote3.application.operations.runtime import ApplicationRuntime


class InstallationServices:
    """Host factories for packaged data and synthetic demonstrations."""

    def __init__(self, *, demo: Callable[[], Any], deployment: Callable[[], Any]) -> None:
        """Bind explicitly selected host installation workflows.

        Args:
            demo: Factory for allowlisted synthetic catalog and sample installation.
            deployment: Factory for authenticated deployment-catalog maintenance.
        """
        self.demo, self.deployment = demo, deployment


class Installation:
    """Install allowlisted deployment catalogs and synthetic demonstration resources."""

    def __init__(self, runtime: ApplicationRuntime, services: InstallationServices) -> None:
        """Bind current authorization and existing atomic installation workflows.

        Args:
            runtime: Verified session, current policy and access-audit capabilities.
            services: Host factories for permitted installation workflows.
        """
        self._runtime, self._services = runtime, services

    def plan(self) -> dict[str, Any]:
        """Inspect packaged demo status with demo:install permission."""
        return self._runtime.execute(
            "installation.plan",
            ("demo:install",),
            lambda actor, sample: dict(self._services.demo().plan()),
        )

    def starter(self) -> dict[str, Any]:
        """Install starter configuration and its first synthetic sample with demo:install."""
        return self._runtime.execute(
            "installation.starter",
            ("demo:install",),
            lambda actor, sample: dict(self._services.demo().install_starter(actor.username)),
        )

    def configuration(self) -> dict[str, Any]:
        """Install synthetic testing configuration with demo:install permission."""
        return self._runtime.execute(
            "installation.configuration",
            ("demo:install",),
            lambda actor, sample: dict(self._services.demo().install_configuration(actor.username)),
        )

    def sample(self, key: str) -> dict[str, Any]:
        """Install an allowlisted synthetic sample with demo:install permission.

        Args:
            key: Packaged demonstration sample key, never a caller-selected filesystem path.

        Returns:
            Existing installation outcome, including retained identities on repeated runs.

        Raises:
            AppError: Permission is denied or the sample key is not allowlisted.
        """
        return self._runtime.execute(
            "installation.sample",
            ("demo:install",),
            lambda actor, sample: dict(self._services.demo().install_sample(key, actor.username)),
        )

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
