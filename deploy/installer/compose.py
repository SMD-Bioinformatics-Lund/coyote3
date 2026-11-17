# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Version-aware Compose execution shared by installation and lifecycle commands."""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence

from scripts.release.build_sdk import ClientArtifact

from .config import ROOT, Profile, read_environment, validate_secrets
from .process import Runner
from .storage import prepare


class Compose:
    """Resolve one Compose configuration and preserve its storage before execution."""

    def __init__(self, profile: Profile, runner: Runner) -> None:
        self.profile = profile
        self.runner = runner
        self.runner.redactions.update(read_environment(profile.env_file))
        self._executable: list[str] | None = None
        self._config: dict | None = None

    @property
    def executable(self) -> list[str]:
        """Select the Compose plugin, with the maintained older-host executable fallback."""
        if self._executable is None:
            try:
                self.runner.run(
                    ["docker", "compose", "version"], label="Compose availability", capture=True
                )
                self._executable = ["docker", "compose"]
            except (RuntimeError, FileNotFoundError):
                if not shutil.which("docker-compose"):
                    raise RuntimeError(
                        "Docker Compose is required; install the plugin before deployment"
                    ) from None
                self._executable = ["docker-compose"]
        return self._executable

    def config(self) -> dict:
        """Render settings in memory; resolved secrets are never written to a file."""
        if self._config is None:
            text = self.runner.run(
                [*self.executable, *self.profile.arguments(), "config", "--format", "json"],
                label="Compose configuration",
                capture=True,
            )
            self._config = json.loads(text)
            if not isinstance(self._config, dict) or not isinstance(
                self._config.get("services"), dict
            ):
                raise ValueError("Resolved Compose configuration must contain a services mapping")
            for service in self._config.get("services", {}).values():
                if not isinstance(service, dict):
                    raise ValueError("Resolved Compose services must be mappings")
                self.runner.redactions.update(
                    {
                        key: str(value)
                        for key, value in (service.get("environment") or {}).items()
                        if value is not None
                    }
                )
        return self._config

    def validate(self) -> None:
        """Validate actual API credentials and Redis settings after Compose interpolation."""
        config = self.config()
        if "api" not in config["services"]:
            raise ValueError("Selected Compose files must define the API service")
        settings = dict(config["services"]["api"]["environment"])
        # The API uses Redis URLs; the Redis service receives the raw password.
        # Validate the explicit file secret too, even if Compose embeds it in a command.
        self.profile.validate()
        settings.setdefault(
            "REDIS_PASSWORD",
            self.profile.process_env.get("REDIS_PASSWORD")
            or read_environment(self.profile.env_file).get("REDIS_PASSWORD"),
        )
        validate_secrets(settings)

    def run(
        self,
        arguments: Sequence[str],
        *,
        capture: bool = False,
        extra_env: Mapping[str, str] | None = None,
    ) -> str:
        """Execute a top-level Compose operation, preserving named volumes and bind storage.

        Args:
            arguments: Compose command followed by its own arguments.
            capture: Capture machine-readable output instead of displaying it.
            extra_env: Overrides limited to one maintenance container.

        Returns:
            Captured output when requested.

        Raises:
            ValueError: The operation would remove persistent volumes.
            RuntimeError: A subprocess fails.
        """
        if not arguments:
            raise ValueError("A Compose command is required")
        operation = arguments[0]
        if operation == "build" or (operation == "up" and "--build" in arguments):
            source_targets = {
                "coyote4_source_api",
                "coyote4_dev_api",
                "coyote4_dev_all",
                "demo_source",
            }
            if any(
                isinstance(service.get("build"), dict)
                and service["build"].get("target") in source_targets
                for service in self.config()["services"].values()
            ):
                ClientArtifact(ROOT).prepare()
        if operation == "down" and any(
            arg in {"-v", "--volumes"}
            or arg.startswith("--volumes=")
            or (arg.startswith("-") and not arg.startswith("--") and "v" in arg[1:])
            for arg in arguments[1:]
        ):
            raise ValueError(
                "Refusing down -v/--volumes: installation commands never remove deployment data"
            )
        if operation in {"up", "start", "create", "run"}:
            if operation in {"up", "start"}:
                self.validate()
            prepare(self.config())
        return self.runner.run(
            [*self.executable, *self.profile.arguments(), *arguments],
            label=f"Compose {operation}",
            capture=capture,
            extra_env=extra_env,
        )
