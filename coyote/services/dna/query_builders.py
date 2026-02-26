"""Service-level access to DNA query builders without blueprint import side effects."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to load module: {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_dna_blueprints_dir = Path(__file__).resolve().parents[2] / "blueprints" / "dna"
_varqueries = _load_module("coyote_services_dna_varqueries", _dna_blueprints_dir / "varqueries.py")
_cnvqueries = _load_module("coyote_services_dna_cnvqueries", _dna_blueprints_dir / "cnvqueries.py")

build_query = _varqueries.build_query
build_cnv_query = _cnvqueries.build_cnv_query

