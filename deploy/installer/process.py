# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Terminal progress and subprocess execution with credential-safe diagnostics."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime

from .config import ROOT


class Console:
    """Consistent, timestamped installer output; color is limited to interactive terminals."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self.color = sys.stderr.isatty() and "NO_COLOR" not in os.environ

    def log(self, message: str, level: str = "INFO") -> None:
        """Write one progress line without rendering shell commands or configuration values."""
        prefix = f"{datetime.now().astimezone():%H:%M:%S} [{level}]"
        if self.color:
            color = {"ERROR": "31", "WARN": "33", "DONE": "32", "STEP": "36"}.get(level, "35")
            prefix = f"\033[{color}m{prefix}\033[0m"
        print(f"{prefix} {message}", file=sys.stderr, flush=True)

    def complete(self) -> None:
        """Report elapsed time after all selected operations succeed."""
        self.log(f"Completed in {time.monotonic() - self.started:.1f}s", "DONE")


def redact(text: str, environment: Mapping[str, str]) -> str:
    """Mask known credentials and URI user information in child-process diagnostics."""
    for key, value in environment.items():
        if value and any(word in key for word in ("PASSWORD", "SECRET", "TOKEN", "_URI", "_URL")):
            text = text.replace(value, "[redacted]")
    return re.sub(r"(\w+://)[^\s/@]+@", r"\1[redacted]@", text)


class Runner:
    """Execute argument arrays in this checkout, streaming normal progress output."""

    def __init__(self, environment: dict[str, str]) -> None:
        self.environment = environment
        self.redactions: dict[str, str] = {}

    def run(
        self,
        command: Sequence[str],
        *,
        label: str,
        capture: bool = False,
        extra_env: Mapping[str, str] | None = None,
        process_env: Mapping[str, str] | None = None,
    ) -> str:
        """Run one operation and stop on failure without disclosing command arguments.

        Args:
            command: Executable and arguments; never evaluated by a shell.
            label: Nonsecret description for failures.
            capture: Return stdout for machine-readable operations without displaying it.
            extra_env: Credentials or overrides scoped to this child process only.
            process_env: Complete replacement environment for a differently scoped child.

        Returns:
            Captured standard output, or an empty string for streaming operations.

        Raises:
            RuntimeError: The process fails; diagnostic output is redacted.
            OSError: The executable is unavailable.
        """
        environment = dict(self.environment if process_env is None else process_env) | dict(
            extra_env or {}
        )
        sensitive = self.redactions | self.environment | environment
        if capture:
            result = subprocess.run(
                command, cwd=ROOT, env=environment, capture_output=True, text=True, check=False
            )
            if result.returncode:
                detail = redact(result.stderr, sensitive).strip()
                raise RuntimeError(
                    f"{label} failed (exit {result.returncode})" + (f": {detail}" if detail else "")
                )
            return result.stdout
        with subprocess.Popen(
            command,
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        ) as child:
            try:
                assert child.stdout is not None
                for line in child.stdout:
                    print(redact(line.rstrip("\n"), sensitive), flush=True)
                status = child.wait()
            except BaseException:
                child.terminate()
                child.wait()
                raise
        if status:
            raise RuntimeError(f"{label} failed (exit {status}); subsequent stages were not run")
        return ""
