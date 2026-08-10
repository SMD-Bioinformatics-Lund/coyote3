from __future__ import annotations

from api.application.public.catalog import PublicCatalogService
from api.application.sample.catalog import SampleCatalogService


def test_file_rows_read_current_sample_files_shape(tmp_path):
    vcf_path = tmp_path / "sample.vcf"
    vcf_path.write_text("##fileformat=VCFv4.2\n", encoding="utf-8")

    rows = SampleCatalogService._file_rows_for_sample(
        {
            "omics_layer": "dna",
            "files": {
                "vcf_files": {
                    "path": str(vcf_path),
                    "checksum": "sha256:seed",
                    "size_bytes": 123,
                }
            },
        },
        {
            "expected_files": ["vcf_files", "cnv"],
            "required_files": ["vcf_files"],
        },
    )

    by_key = {row["key"]: row for row in rows}
    assert by_key["vcf_files"]["path"] == str(vcf_path)
    assert by_key["vcf_files"]["analysis_type"] == "SNV"
    assert by_key["vcf_files"]["present"] is True
    assert by_key["vcf_files"]["exists"] is True
    assert by_key["vcf_files"]["availability"] == "available"
    assert by_key["vcf_files"]["size_bytes"] == 123
    assert by_key["vcf_files"]["checksum"] == "sha256:seed"
    assert by_key["cnv"]["analysis_type"] == "CNV"
    assert by_key["cnv"]["availability"] == "optional_missing"


def test_public_catalog_merges_previous_symbol_without_unresolved_placeholder():
    rows = PublicCatalogService._merge_with_placeholders(
        ["OLD1"],
        [
            {
                "_id": "HGNC:1",
                "hgnc_id": "HGNC:1",
                "hgnc_symbol": "NEW1",
                "prev_symbol": ["OLD1"],
                "alias_symbol": ["ALIAS1"],
                "status": "Approved",
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["display_symbol"] == "OLD1"
    assert rows[0]["resolved_symbol"] == "NEW1"
    assert rows[0]["hgnc_id"] == "HGNC:1"
    assert rows[0]["hgnc_match_source"] == "previous_symbol"
    assert rows[0]["symbol_changed"] is True


def test_public_catalog_unresolved_gene_has_no_fake_hgnc_identifier():
    rows = PublicCatalogService._merge_with_placeholders(["MISSING1"], [])

    assert len(rows) == 1
    assert rows[0]["display_symbol"] == "MISSING1"
    assert rows[0]["hgnc_symbol"] == "MISSING1"
    assert rows[0]["hgnc_id"] is None
    assert rows[0]["_id"] is None
    assert rows[0]["status"] == "Unresolved"
