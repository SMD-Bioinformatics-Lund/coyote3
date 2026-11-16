#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Install factory records and synthetic starters only in validated demo storage."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Bootstrap the demo target with generated private account passwords.

    Returns:
        Zero after ordinary bootstrap and synthetic starter installation succeed.

    Raises:
        ValueError: Isolation or credential-scope validation fails before writes.
        RuntimeError: Private initial account passwords are missing.
        CalledProcessError: Explicit synthetic starter installation fails.

    Notes:
        Preserves existing installations through the standard bootstrap workflow.
        Passwords enter the in-process parser, never a child command line.
    """
    from coyote_demo.deployment import validate_demo_target, validate_runtime

    validate_demo_target(os.environ)
    validate_runtime(os.environ)
    for name in ("COYOTE_DEMO_ADMIN_PASSWORD", "COYOTE_DEMO_SUPERUSER_PASSWORD"):
        if not os.environ.get(name):
            raise RuntimeError(f"Missing private demo credential: {name}")
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    from scripts.bootstrap.bootstrap_database import main as bootstrap

    previous = sys.argv
    try:
        sys.argv = [
            "bootstrap_database.py",
            "--db",
            "coyote4_demo",
            "--identity-db",
            "coyote4_demo_identity",
            "--superuser-password",
            os.environ["COYOTE_DEMO_SUPERUSER_PASSWORD"],
            "--system-admin-password",
            os.environ["COYOTE_DEMO_ADMIN_PASSWORD"],
        ]
        status = bootstrap()
    finally:
        sys.argv = previous
    if status:
        return status
    subprocess.run(
        [
            sys.executable,
            "-m",
            "coyote_demo.cli",
            "--actor",
            "coyote4.sysadmin",
            "--starter",
            "--apply",
        ],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
