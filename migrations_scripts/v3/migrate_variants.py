#!/usr/bin/env python3
"""Prepare v3 variants, VEP transcripts and finding comments offline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from migrations_scripts.variants import run  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(run(3))
