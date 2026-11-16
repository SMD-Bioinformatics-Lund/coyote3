# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Shared JSON reporting and exit status for reviewed database migration commands."""

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


def run_migration_command(
    operation: Callable[[], dict[str, Any]], *, report_path: Path | None
) -> int:
    """Execute a migration operation and print or save its result.

    Args:
        operation: Guarded migration or dry-run operation selected by the caller.
        report_path: Optional path for the JSON report; parent directories are created.

    Returns:
        Zero after successful reporting, or two when the operation raises a
        RuntimeError or ValueError. Failed operations do not write a report.

    Raises:
        OSError: A successful operation's report cannot be written.
        TypeError: Its result cannot be serialized as JSON.
    """
    try:
        report = operation()
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, default=str)
    print(rendered)
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(f"{rendered}\n", encoding="utf-8")
    return 0
