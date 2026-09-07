from __future__ import annotations

from types import SimpleNamespace

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


def test_sample_catalog_attaches_flat_biomarkers_with_one_bulk_lookup():
    calls: list[list[str]] = []

    def get_samples_biomarkers(sample_ids: list[str]):
        calls.append(sample_ids)
        return {
            "s1": [
                {
                    "SAMPLE_ID": "s1",
                    "name": "demo-biomarker",
                    "MSIS": {"tot": 120, "som": 6, "per": 5.0},
                    "HRD": {"sum": 30},
                }
            ],
            "s2": [],
        }

    service = object.__new__(SampleCatalogService)
    service.biomarker_repository = SimpleNamespace(get_samples_biomarkers=get_samples_biomarkers)
    samples = [{"_id": "s1"}, {"_id": "s2"}]

    service._attach_biomarker_values(samples)

    assert calls == [["s1", "s2"]]
    assert samples[0]["biomarker_values"] == {
        "HRD.sum": 30,
        "MSIS.per": 5.0,
        "MSIS.som": 6,
        "MSIS.tot": 120,
    }
    assert samples[1]["biomarker_values"] == {}


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
