"""Independent analysis projections of shared biomarker documents."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

BIOMARKER_FIELDS: dict[str, tuple[str, ...]] = {
    "HRD": ("HRD",),
    "MSI": ("MSIS", "MSIP"),
    "TMB": ("TMB",),
}
BIOMARKER_ANALYSES = tuple(BIOMARKER_FIELDS)


def project_biomarkers(
    documents: Iterable[dict[str, Any]], analyses: Iterable[str]
) -> list[dict[str, Any]]:
    """Select measured fields for enabled analyses without modifying stored documents.

    Args:
        documents: Shared collection documents, including optional identity metadata.
        analyses: Exact analysis identifiers to expose. An empty selection exposes none.

    Returns:
        Documents containing selected non-null measurements and their source identity.
        Unmeasured documents are omitted; zero-valued measurements are retained.
    """
    fields = tuple(
        dict.fromkeys(
            field for analysis in analyses for field in BIOMARKER_FIELDS.get(analysis, ())
        )
    )
    result = []
    for document in documents:
        values = {key: document[key] for key in fields if document.get(key) is not None}
        if values:
            result.append(
                {
                    **{
                        key: document[key]
                        for key in ("_id", "SAMPLE_ID", "name")
                        if key in document
                    },
                    **values,
                }
            )
    return result


def biomarker_counts(documents: Iterable[dict[str, Any]]) -> dict[str, int]:
    """Count source documents containing each independent analysis.

    Args:
        documents: Shared biomarker records to inspect.

    Returns:
        Lowercase analysis names mapped to measured document counts, including zeros.
    """
    rows = list(documents)
    return {
        analysis.lower(): len(project_biomarkers(rows, [analysis]))
        for analysis in BIOMARKER_ANALYSES
    }


def measurement_facts(documents: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Expose typed numeric measurements without deriving scores or thresholds.

    Args:
        documents: Validated documents restricted to selected analysis/report sections.

    Returns:
        Independent collections of measured values. MSI methods remain separate rows.
        Absent measurements are empty collections, never fabricated zero values.
    """
    result: dict[str, list[dict[str, Any]]] = {key.lower(): [] for key in BIOMARKER_ANALYSES}
    for document in documents:
        for analysis, fields in BIOMARKER_FIELDS.items():
            for field in fields:
                value = document.get(field)
                if not isinstance(value, dict):
                    continue
                score_key = "sum" if analysis == "HRD" else "per" if analysis == "MSI" else "value"
                if value.get(score_key) is None:
                    continue
                row = {
                    "analysis_type": analysis,
                    "method": field,
                    "value": value[score_key],
                    "unit": "score"
                    if analysis == "HRD"
                    else "mut/Mb"
                    if analysis == "TMB"
                    else "%",
                }
                if analysis == "HRD":
                    row.update({key: value.get(key) for key in ("tai", "hrd", "lst")})
                elif analysis == "MSI":
                    row.update(total=value.get("tot"), unstable=value.get("som"))
                result[analysis.lower()].append(row)
    return result
