#!/usr/bin/env python3
"""Prepare v3 group-scoped D4 coverage exclusions without selecting sample data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from migrations_scripts.related import run_blacklist  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run_blacklist(3))
