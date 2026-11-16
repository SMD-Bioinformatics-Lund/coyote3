# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Resolve deployment profiles without executing an environment file."""

from __future__ import annotations

import os
import re
import shlex
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENTS = {"development": "dev", "production": "prod", "testing": "test", "staging": "stage"}
STEPS = ("network", "directories", "build", "validate", "bootstrap", "indexes", "start", "health")


def read_environment(path: Path) -> dict[str, str]:
    """Read single-line dotenv settings as data, without shell evaluation.

    Args:
        path: Explicit environment file.

    Returns:
        Literal values; Compose remains responsible for interpolation at execution.

    Raises:
        ValueError: A line is malformed or a key is repeated.
    """
    settings = {}
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=(.*)", line)
        if not match:
            raise ValueError(f"Invalid environment assignment on line {number}")
        key, value = match.groups()
        if key in settings:
            raise ValueError(f"Duplicate environment key: {key}")
        value = value.strip()
        try:
            # Compose treats a hash inside an unquoted value literally unless
            # preceded by whitespace. Preserve backslashes in unquoted paths too.
            settings[key] = (
                " ".join(shlex.split(value, comments=True))
                if value.startswith(("'", '"'))
                else re.split(r"\s+#", value, maxsplit=1)[0].rstrip()
            )
        except ValueError:
            raise ValueError(f"Invalid quoting for {key} on line {number}") from None
    return settings


def validate_secrets(settings: dict[str, str]) -> None:
    """Reject missing, placeholder or unsafe deployment secrets without displaying values.

    Args:
        settings: Explicit file values or the environment resolved by Compose.

    Raises:
        ValueError: Required credentials are absent or unsafe.
    """
    required = (
        "SECRET_KEY",
        "INTERNAL_API_TOKEN",
        "PASSWORD_TOKEN_SALT",
        "REDIS_PASSWORD",
        "COYOTE4_MONGO_URI",
    )
    errors = []
    for key in required:
        value = str(settings.get(key) or "")
        if not value:
            errors.append(f"missing required key: {key}")
        elif "CHANGE_ME" in value or "${" in value:
            errors.append(f"placeholder or unresolved value for {key}")
        elif key != "COYOTE4_MONGO_URI" and len(value) < 16:
            errors.append(f"{key} must contain at least 16 characters")
        elif key == "REDIS_PASSWORD" and not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            errors.append(
                "REDIS_PASSWORD must use URL-safe letters, digits, underscores or hyphens"
            )
    for key in ("IDENTITY_MONGO_URI", "KNOWLEDGEBASE_MONGO_URI", "BAM_MONGO_URI", "LDAP_SECRET"):
        value = str(settings.get(key) or "")
        if "CHANGE_ME" in value or "${" in value:
            errors.append(f"placeholder or unresolved value for {key}")
    if errors:
        raise ValueError("; ".join(errors))


def environment_name(value: str) -> str:
    """Normalize a supported environment name or reject an unknown profile."""
    value = value.strip().lower()
    value = ENVIRONMENTS.get(value, value)
    if value not in ENVIRONMENTS.values():
        raise ValueError(
            "ENV_NAME must select prod, dev, stage or test; use the demo command for isolation"
        )
    return value


@dataclass(frozen=True)
class Profile:
    """Explicit deployment selections, with version metadata from this checkout."""

    env_file: Path
    environment: str
    project: str
    files: tuple[Path, ...]
    process_env: dict[str, str]
    service_profiles: tuple[str, ...] = ()

    @classmethod
    def load(
        cls,
        env_file: Path,
        *,
        environment: str | None = None,
        project: str | None = None,
        files: list[Path] | None = None,
        overlays: list[Path] | None = None,
        legacy: bool = False,
        service_profiles: list[str] | None = None,
    ) -> Profile:
        """Resolve one target, rejecting profile mismatches before any subprocess runs.

        Args:
            env_file: Reviewed deployment settings.
            environment: Optional explicit profile; must agree with ENV_NAME when set.
            project: Stable Compose project identity for this installation.
            files: Complete ordered Compose file selection instead of the defaults.
            overlays: Additional ordered files appended to the selection.
            legacy: Select the maintained Compose definitions for older Docker hosts.
            service_profiles: Optional Compose service groups such as mongo or docs.

        Returns:
            Resolved metadata and child environment without changing the parent process.

        Raises:
            ValueError: The environment, log level or project name is invalid.
            OSError: An explicitly selected file cannot be read.
        """
        env_file = env_file.expanduser().resolve(strict=True)
        values = read_environment(env_file)
        process_env = dict(os.environ)
        configured = process_env.get("ENV_NAME", values.get("ENV_NAME"))
        selected = environment_name(environment or configured or "production")
        if environment and configured and selected != environment_name(configured):
            raise ValueError(
                "--environment disagrees with ENV_NAME; select the matching environment file"
            )
        project = project or f"coyote4-{selected}"
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", project):
            raise ValueError(
                "Project names must use lowercase letters, digits, underscores or hyphens"
            )
        version = tomllib.loads((ROOT / "release.toml").read_text())["application_version"]
        process_env.update(
            COYOTE4_VERSION=version,
            COYOTE4_IMAGE_TAG=version if selected == "prod" else f"{version}-{selected}",
        )
        process_env["ENV_NAME"] = selected
        for key in ("LOG_LEVEL", "CELERY_LOG_LEVEL"):
            fallback = process_env.get("LOG_LEVEL", "INFO" if selected == "prod" else "DEBUG")
            level = (process_env.get(key) or values.get(key) or fallback).upper()
            if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "FATAL", "WARN"}:
                raise ValueError(f"{key} must be a literal logging level name")
            process_env[key] = level
        if files:
            selected_files = files
        else:
            folder = ROOT / "deploy" / ("legacy" if legacy else "compose")
            selected_files = [folder / "docker-compose.yml"]
            if selected != "prod":
                selected_files.append(folder / f"docker-compose.{selected}.yml")
        resolved = tuple(
            path.expanduser().resolve(strict=True) for path in [*selected_files, *(overlays or [])]
        )
        return cls(
            env_file, selected, project, resolved, process_env, tuple(service_profiles or ())
        )

    def validate(self) -> None:
        """Check selected file credentials with Compose's process-environment precedence."""
        validate_secrets(read_environment(self.env_file) | self.process_env)

    def arguments(self) -> list[str]:
        """Return global Compose selections without including secret values."""
        args = ["--project-name", self.project, "--env-file", str(self.env_file)]
        for path in self.files:
            args.extend(["--file", str(path)])
        for name in self.service_profiles:
            args.extend(["--profile", name])
        return args
