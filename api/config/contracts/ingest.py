"""Application-owned ingest parser and collection payload contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnalysisPreloadContract:
    """Map supported analyses to internal parser payload names.

    Manifest field names are centre configuration and are resolved against this
    stable application contract by :func:`manifest_file_preload_keys`.
    """

    preload_keys_by_omics: dict[str, dict[str, str | None]]


ANALYSIS_PRELOAD_CONTRACT = AnalysisPreloadContract(
    preload_keys_by_omics={
        "dna": {
            "SNV": "snvs",
            "CNV": "cnvs",
            "CNV_PROFILE": None,
            "TRANSLOCATION": "transloc",
            "BIOMARKER": "biomarkers",
            "COVERAGE": "cov",
            "FUSION": "transloc",
            "TMB": "biomarkers",
            "PGX": None,
        },
        "rna": {
            "FUSION": "fusions",
            "EXPRESSION": "rna_expr",
            "CLASSIFICATION": "rna_class",
            "QC": "rna_qc",
            "PGX": None,
        },
    }
)
