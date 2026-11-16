# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Resolve bundled installation resources outside the installable application SDK."""

from pathlib import Path

BOOTSTRAP_ROOT = Path(__file__).resolve().parent / "catalogs"
REFERENCE_CATALOG_DIR = BOOTSTRAP_ROOT / "reference"
CLINICAL_QUERY_SEED_PATH = REFERENCE_CATALOG_DIR / "clinical_query_seed.toml"
