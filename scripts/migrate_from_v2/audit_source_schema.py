#!/usr/bin/env python3
"""Inventory every field and decoded BSON shape in a complete offline v2 export."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.migration_common.schema_inventory import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(2))
