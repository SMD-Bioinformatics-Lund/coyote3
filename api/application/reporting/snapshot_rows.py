"""Typed report snapshot row builders for clinical findings."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from api.domain.core.dna.variant_identity import build_simple_id_hash_from_simple_id


def _identity(prefix: str, *parts: Any) -> tuple[str, str]:
    values = [str(part).strip() for part in parts if part not in (None, "")]
    simple_id = ":".join((prefix.lower(), *values))
    return simple_id, build_simple_id_hash_from_simple_id(simple_id)


def build_cnv_snapshot_rows(cnvs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return immutable snapshot rows for reportable copy-number findings."""
    created_on = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for cnv in cnvs:
        genes = [
            str(item.get("gene"))
            for item in (cnv.get("genes") or [])
            if isinstance(item, dict) and item.get("gene")
        ]
        simple_id, simple_id_hash = _identity(
            "cnv", cnv.get("chr"), cnv.get("start"), cnv.get("end"), cnv.get("type")
        )
        rows.append(
            {
                "analysis_type": "CNV",
                "finding_type": "copy_number_variant",
                "var_oid": cnv.get("_id"),
                "simple_id": simple_id,
                "simple_id_hash": simple_id_hash,
                "nomenclature": "cn",
                "variant": simple_id,
                "gene": ", ".join(genes),
                "genes": genes,
                "region": f"{cnv.get('chr')}:{cnv.get('start')}-{cnv.get('end')}",
                "chromosome": cnv.get("chr"),
                "start": cnv.get("start"),
                "end": cnv.get("end"),
                "size": cnv.get("size"),
                "cnv_type": cnv.get("type"),
                "ratio": cnv.get("ratio"),
                "nprobes": cnv.get("nprobes"),
                "callers": list(dict.fromkeys(cnv.get("callers") or [])),
                "created_on": created_on,
            }
        )
    return rows


def _selected_translocation_annotation(row: dict[str, Any]) -> dict[str, Any]:
    info = row.get("INFO") if isinstance(row.get("INFO"), dict) else {}
    mane = info.get("MANE_ANN")
    if isinstance(mane, dict):
        return mane
    return next((item for item in (info.get("ANN") or []) if isinstance(item, dict)), {})


def build_translocation_snapshot_rows(
    translocations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return immutable snapshot rows for reportable DNA structural findings."""
    created_on = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for translocation in translocations:
        selected = _selected_translocation_annotation(translocation)
        genes = [value for value in str(selected.get("Gene_Name") or "").split("&") if value]
        simple_id, simple_id_hash = _identity(
            "translocation",
            translocation.get("CHROM"),
            translocation.get("POS"),
            translocation.get("REF"),
            translocation.get("ALT"),
        )
        rows.append(
            {
                "analysis_type": "TRANSLOCATION",
                "finding_type": "structural_variant",
                "var_oid": translocation.get("_id"),
                "simple_id": simple_id,
                "simple_id_hash": simple_id_hash,
                "nomenclature": "t",
                "variant": simple_id,
                "gene": "::".join(genes),
                "genes": genes,
                "gene1": genes[0] if genes else None,
                "gene2": genes[1] if len(genes) > 1 else None,
                "source_id": translocation.get("ID"),
                "chromosome": translocation.get("CHROM"),
                "position": translocation.get("POS"),
                "ref": translocation.get("REF"),
                "alt": translocation.get("ALT"),
                "breakpoint": f"{translocation.get('CHROM')}:{translocation.get('POS')}",
                "hgvsc": selected.get("HGVSc"),
                "hgvsp": selected.get("HGVSp"),
                "effect": selected.get("Annotation"),
                "created_on": created_on,
            }
        )
    return rows


def build_biomarker_snapshot_rows(
    biomarkers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return immutable snapshot rows for reportable aggregate biomarkers."""
    created_on = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for index, biomarker in enumerate(biomarkers):
        name = str(biomarker.get("name") or biomarker.get("biomarker") or f"biomarker_{index + 1}")
        values = {
            key: value
            for key, value in biomarker.items()
            if key not in {"_id", "SAMPLE_ID", "name"}
        }
        simple_id, simple_id_hash = _identity("biomarker", name)
        rows.append(
            {
                "analysis_type": "BIOMARKER",
                "finding_type": "biomarker",
                "var_oid": biomarker.get("_id"),
                "simple_id": simple_id,
                "simple_id_hash": simple_id_hash,
                "biomarker": name,
                "result": values,
                "created_on": created_on,
            }
        )
    return rows


def flatten_pgx_records(pgx_documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return individual PGX records from supported stored document shapes."""
    flattened_records: list[dict[str, Any]] = []
    for document in pgx_documents:
        nested_records = document.get("records")
        if isinstance(nested_records, list):
            flattened_records.extend(item for item in nested_records if isinstance(item, dict))
        else:
            flattened_records.append(document)
    return flattened_records


def build_pgx_snapshot_rows(pgx_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return immutable snapshot rows for reportable pharmacogenomic findings."""
    created_on = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []

    for index, record in enumerate(flatten_pgx_records(pgx_records)):
        gene = str(record.get("gene") or record.get("symbol") or record.get("hugo_symbol") or "")
        result = record.get("result") or record.get("phenotype") or record.get("diplotype")
        record_id = record.get("id") or record.get("pgx_id") or gene or index + 1
        simple_id, simple_id_hash = _identity("pgx", record_id, result)
        rows.append(
            {
                "analysis_type": "PGX",
                "finding_type": "pharmacogenomic_result",
                "var_oid": record.get("_id"),
                "simple_id": simple_id,
                "simple_id_hash": simple_id_hash,
                "gene": gene,
                "pgx_result": result,
                "diplotype": record.get("diplotype"),
                "phenotype": record.get("phenotype"),
                "activity_score": record.get("activity_score"),
                "recommendation": record.get("recommendation"),
                "created_on": created_on,
            }
        )
    return rows
