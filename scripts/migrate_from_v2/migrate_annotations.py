#!/usr/bin/env python3
"""Convert offline v2 annotations, excluding hematology owned by the v3 source."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.migration_common.commands import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run(2, "annotation"))
