#!/usr/bin/env python3
"""Convert only hematology annotations from the offline v3 source."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.migration_common.commands import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run(3, "annotation"))
