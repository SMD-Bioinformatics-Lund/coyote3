"""Resolve bundled installation resources outside the installable application SDK."""

from pathlib import Path

BOOTSTRAP_ROOT = Path(__file__).resolve().parent / "catalogs"
CLINICAL_QUERY_SEED_PATH = BOOTSTRAP_ROOT / "reference" / "clinical_query_seed.toml"
