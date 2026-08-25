"""Typed clinical report snapshot row builders."""

from datetime import datetime, timezone

from api.application.reporting.snapshot_rows import (
    build_biomarker_snapshot_rows,
    build_cnv_snapshot_rows,
    build_pgx_snapshot_rows,
    build_translocation_snapshot_rows,
    flatten_pgx_records,
)
from api.contracts.schemas.dna import ReportedVariantsDoc


def test_builds_typed_cnv_biomarker_and_pgx_rows() -> None:
    cnv = build_cnv_snapshot_rows(
        [
            {
                "_id": "cnv-1",
                "chr": "7",
                "start": 100,
                "end": 300,
                "size": 200,
                "ratio": 0.75,
                "type": "gain",
                "genes": [{"gene": "EGFR"}],
                "callers": ["cnvkit", "cnvkit"],
            }
        ]
    )[0]
    biomarker = build_biomarker_snapshot_rows(
        [{"_id": "bio-1", "name": "TMB", "value": 12.4, "unit": "mut/Mb"}]
    )[0]
    pgx = build_pgx_snapshot_rows(
        [
            {
                "SAMPLE_ID": "sample-1",
                "records": [
                    {
                        "id": "pgx-1",
                        "gene": "CYP2C19",
                        "diplotype": "*1/*2",
                        "phenotype": "Intermediate metabolizer",
                    }
                ],
            }
        ]
    )[0]

    assert cnv["analysis_type"] == "CNV"
    assert cnv["gene"] == "EGFR"
    assert cnv["callers"] == ["cnvkit"]
    assert cnv["simple_id"].startswith("cnv:")
    assert biomarker["analysis_type"] == "BIOMARKER"
    assert biomarker["biomarker"] == "TMB"
    assert pgx["analysis_type"] == "PGX"
    assert pgx["gene"] == "CYP2C19"
    assert pgx["pgx_result"] == "Intermediate metabolizer"


def test_flattens_pgx_documents_without_losing_single_record_documents() -> None:
    records = flatten_pgx_records(
        [
            {"records": [{"gene": "CYP2C19"}, {"gene": "DPYD"}]},
            {"gene": "TPMT"},
        ]
    )

    assert [record["gene"] for record in records] == ["CYP2C19", "DPYD", "TPMT"]


def test_builds_typed_translocation_row_from_selected_annotation() -> None:
    row = build_translocation_snapshot_rows(
        [
            {
                "_id": "sv-1",
                "CHROM": "11",
                "POS": 118307205,
                "REF": "N",
                "ALT": "<BND>",
                "INFO": {
                    "MANE_ANN": {
                        "Gene_Name": "KMT2A&AFF1",
                        "HGVSc": "t(11;4)",
                        "HGVSp": "p.?",
                        "Annotation": ["gene_fusion"],
                    }
                },
            }
        ]
    )[0]

    assert row["analysis_type"] == "TRANSLOCATION"
    assert row["gene1"] == "KMT2A"
    assert row["gene2"] == "AFF1"
    assert row["nomenclature"] == "t"
    assert row["variant"] == row["simple_id"]
    assert row["simple_id"].startswith("translocation:")


def test_reported_finding_contract_preserves_each_analysis_specific_payload() -> None:
    rows = [
        {
            "analysis_type": "SNV",
            "finding_type": "small_variant",
            "simple_id": "snv:1:100:A:T",
            "simple_id_hash": "snv-hash",
            "gene": "TP53",
            "variant": "p.Arg175His",
        },
        build_cnv_snapshot_rows(
            [{"chr": "7", "start": 100, "end": 300, "type": "gain", "genes": []}]
        )[0],
        build_translocation_snapshot_rows(
            [{"CHROM": "11", "POS": 100, "REF": "N", "ALT": "<BND>", "INFO": {}}]
        )[0],
        {
            "analysis_type": "FUSION",
            "finding_type": "fusion",
            "simple_id": "fusion:KMT2A::AFF1",
            "simple_id_hash": "fusion-hash",
            "fusion": "KMT2A::AFF1",
            "spanning_pairs": 12,
        },
        build_biomarker_snapshot_rows([{"name": "TMB", "value": 12.4}])[0],
        build_pgx_snapshot_rows([{"gene": "DPYD", "phenotype": "Poor metabolizer"}])[0],
    ]

    validated = []
    for row in rows:
        validated.append(
            ReportedVariantsDoc.model_validate(
                {
                    **row,
                    "report_id": "report-1",
                    "sample_name": "sample-1",
                    "report_oid": "report-oid",
                    "sample_oid": "sample-oid",
                    "created_by": "reviewer",
                    "created_on": row.get("created_on") or datetime.now(timezone.utc),
                }
            ).model_dump()
        )

    assert [row["analysis_type"] for row in validated] == [
        "SNV",
        "CNV",
        "TRANSLOCATION",
        "FUSION",
        "BIOMARKER",
        "PGX",
    ]
    assert validated[1]["region"] == "7:100-300"
    assert validated[3]["fusion"] == "KMT2A::AFF1"
    assert validated[4]["biomarker"] == "TMB"
    assert validated[5]["pgx_result"] == "Poor metabolizer"
