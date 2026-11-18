# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Watch editable backend packages during local development."""

from __future__ import annotations

import argparse
import os
import sys
import tomllib
from importlib.util import find_spec
from pathlib import Path

from .config import ROOT, environment_name, native_environment
from .process import Console


class DevelopmentWatcher:
    """Run one development service under Watchdog's process supervisor."""

    def __init__(self, root: Path, environment: dict[str, str]) -> None:
        """Bind an editable checkout and the selected child environment.

        Args:
            root: Checkout containing the workspace metadata and editable sources.
            environment: Explicit child settings; ENV_NAME must select development.
        """
        self.root = root
        self.environment = environment

    def directories(self, additional: list[Path]) -> list[Path]:
        """Resolve source roots from package metadata and explicitly added directories.

        Args:
            additional: Extra editable sources, for example a separately checked-out Relay package.

        Returns:
            Existing source directories without duplicates.

        Raises:
            ValueError: No editable source tree is available.
            OSError: Workspace metadata or an explicitly selected directory is missing.
        """
        metadata = tomllib.loads((self.root / "pyproject.toml").read_text())
        tools = metadata.get("tool", {})
        package_dirs = tools.get("setuptools", {}).get("package-dir", {})
        candidates = [(self.root / path).parent for name, path in package_dirs.items() if name]
        candidates.extend(
            self.root / member / "src"
            for member in tools.get("uv", {}).get("workspace", {}).get("members", [])
        )
        selected = [path.resolve() for path in candidates if path.is_dir()]
        for path in additional:
            resolved = path.expanduser().resolve(strict=True)
            if not resolved.is_dir():
                raise ValueError("An additional watch path must be a directory")
            selected.append(resolved)
        if not selected:
            raise ValueError("Development reload requires an editable source checkout")
        return list(dict.fromkeys(selected))

    def command(self, service: list[str], additional: list[Path]) -> list[str]:
        """Build an argument-safe watcher command, restricted to development.

        Args:
            service: Executable and arguments for one long-running service.
            additional: Extra source roots to watch alongside workspace packages.

        Returns:
            Watchmedo command with graceful shutdown, debouncing and mount-safe polling.

        Raises:
            ValueError: The environment is not development or the command is empty.
            OSError: The editable checkout cannot be read.
        """
        if environment_name(self.environment.get("ENV_NAME", "production")) != "dev":
            raise ValueError("Source reload requires ENV_NAME=dev or development")
        if not service:
            raise ValueError("Supply a service command after --")
        command = [
            sys.executable,
            "-m",
            "watchdog.watchmedo",
            "auto-restart",
            "--recursive",
            "--ignore-directories",
            "--debug-force-polling",
            "--patterns=**/*.py;**/*.toml;**/*.json;**/*.yaml;**/*.yml;**/*.html;**/*.css;**/*.svg",
            "--ignore-patterns=**/__pycache__/**;**/.git/**",
            "--interval=1",
            "--debounce-interval=0.5",
            "--signal=SIGTERM",
            "--kill-after=30",
            "--no-restart-on-command-exit",
        ]
        for directory in self.directories(additional):
            command.extend(["--directory", str(directory)])
        return [*command, "--", *service]

    def run(self, service: list[str], additional: list[Path]) -> None:
        """Replace the launcher so signals reach the watcher and its service process group.

        Args:
            service: Executable and arguments, without shell evaluation.
            additional: Explicit extra source directories.

        Raises:
            ValueError: Reload is not permitted for this environment.
            RuntimeError: The development watcher dependency is not installed.
            OSError: The watcher cannot be launched.
        """
        command = self.command(service, additional)
        if find_spec("watchdog") is None:
            raise RuntimeError("Install development dependencies with uv sync --group dev")
        Console().log("Development source reload enabled; stop with Ctrl-C", "INFO")
        os.execvpe(command[0], command, self.environment)


def main(argv: list[str]) -> int:
    """Start a watched service using the existing backend configuration entry point."""
    parser = argparse.ArgumentParser(
        prog="install.sh watch",
        description="Restart a local development service when editable backend sources change.",
    )
    parser.add_argument("--env-file", type=Path, help="Optional backend environment file")
    parser.add_argument(
        "--directory",
        type=Path,
        action="append",
        default=[],
        help="Additional source directory; repeat as needed",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Service command after --")
    args = parser.parse_args(argv)
    environment = dict(os.environ)
    if args.env_file:
        env_file = args.env_file.expanduser().resolve(strict=True)
        environment = native_environment(env_file)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    DevelopmentWatcher(ROOT, environment).run(command, args.directory)
    return 0
