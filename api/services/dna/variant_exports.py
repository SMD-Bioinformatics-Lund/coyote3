"""Export helpers for DNA service workflows."""

from __future__ import annotations

from typing import Any

from api.services.dna.export import build_cnv_export_rows as _build_cnv_export_rows
from api.services.dna.export import build_snv_export_rows as _build_snv_export_rows
from api.services.dna.export import build_transloc_export_rows as _build_transloc_export_rows
from api.services.dna.export import export_rows_to_csv as _export_rows_to_csv


def export_rows_to_csv(rows: list[Any]) -> str:
    """Serialize export rows into CSV text with stable column ordering."""
    return _export_rows_to_csv(rows)


def build_snv_export_rows(variants: list[dict[str, Any]]) -> list[Any]:
    """Build typed SNV export rows from filtered variant documents."""
    return _build_snv_export_rows(variants)


def build_cnv_export_rows(
    cnvs: list[dict[str, Any]], sample: dict[str, Any], assay_group: str
) -> list[Any]:
    """Build typed CNV export rows from filtered CNV documents."""
    return _build_cnv_export_rows(cnvs, sample, assay_group)


def build_transloc_export_rows(translocs: list[dict[str, Any]]) -> list[Any]:
    """Build typed translocation export rows from filtered translocation documents."""
    return _build_transloc_export_rows(translocs)
