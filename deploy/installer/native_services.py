# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Supervise only the native processes owned by one application installation."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .config import ROOT
from .process import Runner


@contextmanager
def operation_lock(directory: Path):
    """Reject overlapping lifecycle operations before they can replace runtime settings."""
    prepare_directory(directory)
    descriptor = os.open(
        directory / "operation.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "w") as stream:
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another native application operation is in progress") from None
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def private_write(path: Path, text: str) -> None:
    """Atomically write an owner-only runtime file without following symbolic links."""
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("Native runtime files must not be symbolic links")
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            temporary.chmod(0o600)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def write_environment(path: Path, environment: dict[str, str]) -> None:
    """Save an exact private environment; the native launcher replaces inherited settings."""
    for key, value in sorted(environment.items()):
        if any(character in value for character in "\n\r\x00"):
            raise ValueError(f"Multiline native environment value: {key}")
    private_write(path, json.dumps(environment, ensure_ascii=False) + "\n")


class UserServices:
    """Use the existing systemd user manager without installing global services.

    Units are transient and explicitly started after each WSL session. A stable
    ownership marker prevents one checkout from stopping another one's processes.
    """

    def __init__(self, project: str, directory: Path, runner: Runner) -> None:
        self.project, self.directory, self.runner = project, directory, runner
        self.owner = hashlib.sha256(f"{ROOT}\n{directory}".encode()).hexdigest()[:16]

    def unit(self, service: str) -> str:
        return f"{self.project}-{service}.service"

    def description(self, service: str) -> str:
        return f"Coyote4 {service} ({self.owner})"

    def inspect(self, service: str) -> dict[str, str]:
        """Read status and reject an existing unit owned by another installation."""
        text = self.runner.run(
            [
                "systemctl",
                "--user",
                "list-units",
                "--all",
                "--full",
                "--plain",
                "--no-legend",
                "--no-pager",
                "--",
                self.unit(service),
            ],
            label="Native service ownership; systemd user services must be available",
            capture=True,
        )
        if not text.strip():
            return {"LoadState": "not-found", "ActiveState": "inactive"}
        fields = text.strip().split(maxsplit=4)
        if len(fields) != 5 or fields[0] != self.unit(service):
            raise ValueError(f"Unexpected native service status for {service}")
        state = {"LoadState": fields[1], "ActiveState": fields[2], "Description": fields[4]}
        if state["Description"] != self.description(service):
            raise ValueError(f"Native service {service} belongs to another installation")
        return state

    def assert_stopped(self, names: list[str]) -> None:
        """Refuse to replace dependencies while an application process is running."""
        for name in names:
            if self.inspect(name).get("ActiveState") in {
                "active",
                "activating",
                "deactivating",
                "reloading",
            }:
                raise ValueError(
                    "Stop this native application before deploying or starting it again"
                )

    def start(
        self, service: str, command: list[str], *, environment_file: Path | None = None
    ) -> None:
        """Start a bounded-restart service with a private environment and graceful shutdown."""
        self.inspect(service)
        self.runner.run(
            [
                "systemd-run",
                "--user",
                "--collect",
                "--service-type=exec",
                f"--unit={self.unit(service)}",
                f"--description={self.description(service)}",
                f"--working-directory={ROOT}",
                "--property=Restart=on-failure",
                "--property=RestartSec=5",
                "--property=StartLimitIntervalSec=300",
                "--property=StartLimitBurst=5",
                "--property=KillMode=mixed",
                "--property=TimeoutStopSec=7500",
                "--property=UMask=0077",
                "--",
                str(self.directory / "venv/bin/python"),
                "-I",
                "-B",
                str(ROOT / "deploy/installer/native_process.py"),
                str(environment_file or self.directory / "runtime.json"),
                *command,
            ],
            label=f"Start native {service}",
        )

    def stop(self, names: list[str]) -> None:
        """Stop only owned application units, allowing workers to finish active tasks."""
        states = {name: self.inspect(name) for name in names}
        for service in reversed(names):
            if states[service].get("LoadState") != "not-found":
                self.runner.run(
                    ["systemctl", "--user", "stop", self.unit(service)],
                    label=f"Stop native {service}",
                )

    def status(self, names: list[str]) -> dict[str, str]:
        return {name: self.inspect(name).get("ActiveState", "inactive") for name in names}

    def logs(self, names: list[str]) -> None:
        for name in names:
            self.inspect(name)
        self.runner.run(
            [
                "journalctl",
                "--user",
                "--no-pager",
                "--lines=100",
                *[f"--unit={self.unit(name)}" for name in names],
            ],
            label="Native application logs",
        )


def prepare_directory(directory: Path) -> None:
    """Create private application state without changing existing ownership or permissions."""
    if directory.is_symlink() or any(parent.is_symlink() for parent in directory.parents):
        raise ValueError("Native state must not use symbolic links")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    metadata = directory.stat()
    if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise ValueError("Native state directory must be owned by the invoking user with mode 700")
