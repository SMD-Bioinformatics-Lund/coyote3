from __future__ import annotations

from api.application.coverage.processing import CoverageProcessingService


class _GroupedCoverageRepository:
    def __init__(self, entries: list[dict] | None = None) -> None:
        self.entries = entries or []
        self.lookups: list[tuple[str, str, str, str]] = []

    def get_regions_per_group(self, group: str) -> list[dict]:
        assert group == "hematology"
        return self.entries

    def is_region_blacklisted(self, gene: str, region: str, coord: str, group: str) -> bool:
        self.lookups.append((gene, region, coord, group))
        return coord == "blocked"


def _coverage_payload() -> dict:
    return {
        "genes": {
            "TP53": {
                "exons": {"e1": {"nbr": "1", "cov": 45}},
                "CDS": {
                    "100-120": {"nbr": "1", "start": 100, "end": 120, "cov": 45},
                    "200-220": {"nbr": "2", "start": 200, "end": 220, "cov": 8},
                },
                "probes": {
                    "95-125": {"start": 95, "end": 125, "cov": 7},
                    "300-320": {"start": 300, "end": 320, "cov": 5},
                },
            },
            "BRCA1": {"CDS": {"blocked": {"nbr": "3", "start": 1, "end": 2, "cov": 2}}},
            "ALK": {"CDS": {"500": {"nbr": "4", "start": 1, "end": 2, "cov": 200}}},
        }
    }


def test_coverage_helpers_handle_invalid_payloads_and_blacklists() -> None:
    assert CoverageProcessingService._genes_map(None) == {}
    assert CoverageProcessingService._genes_map({"genes": []}) == {}
    genes, regions = CoverageProcessingService._blacklist_index(
        [
            {},
            {"gene": "TP53", "region": "gene"},
            {"gene": "BRCA1", "region": "CDS", "coord": "blocked"},
            {"gene": "ALK", "region": "CDS"},
        ]
    )
    assert genes == {"TP53"}
    assert regions == {("BRCA1", "CDS", "blocked")}


def test_find_and_filter_low_covered_genes_respects_region_and_gene_blacklists() -> None:
    repository = _GroupedCoverageRepository(
        [
            {"gene": "BRCA1", "region": "CDS", "coord": "blocked"},
            {"gene": "ALK", "region": "gene", "coord": ""},
        ]
    )
    filtered = CoverageProcessingService.find_low_covered_genes(
        _coverage_payload(), 20, "hematology", grouped_coverage_repository=repository
    )
    assert list(filtered["genes"]) == ["TP53"]

    selected = CoverageProcessingService.filter_genes_from_form(
        _coverage_payload(),
        ["TP53", "ALK", "missing"],
        "hematology",
        grouped_coverage_repository=repository,
    )
    assert list(selected["genes"]) == ["TP53"]

    unrestricted = CoverageProcessingService.filter_genes_from_form(
        _coverage_payload(),
        [],
        "hematology",
        grouped_coverage_repository=repository,
    )
    assert list(unrestricted["genes"]) == ["TP53", "BRCA1"]


def test_reg_low_supports_precomputed_and_repository_blacklists() -> None:
    repository = _GroupedCoverageRepository()
    regions = {
        "high": {"cov": 100},
        "missing": {"cov": None},
        "blocked": {"cov": 1},
        "low": {"cov": "2.5"},
    }
    assert (
        CoverageProcessingService.reg_low(
            regions,
            "CDS",
            10,
            "TP53",
            "hematology",
            grouped_coverage_repository=repository,
        )
        is True
    )
    assert repository.lookups == [
        ("TP53", "CDS", "blocked", "hematology"),
        ("TP53", "CDS", "low", "hematology"),
    ]
    assert (
        CoverageProcessingService.reg_low(
            {"blocked": {"cov": 1}},
            "CDS",
            10,
            "TP53",
            "hematology",
            grouped_coverage_repository=repository,
            region_blacklist={("TP53", "CDS", "blocked")},
        )
        is False
    )


def test_organize_data_for_d3_normalizes_present_and_missing_region_groups() -> None:
    payload = _coverage_payload()
    result = CoverageProcessingService.organize_data_for_d3(payload)
    assert result["genes"]["TP53"]["exons"] == [{"nbr": "1", "cov": 45}]
    assert len(result["genes"]["TP53"]["CDS"]) == 2
    assert len(result["genes"]["TP53"]["probes"]) == 2
    assert result["genes"]["BRCA1"]["exons"] == []
    assert result["genes"]["BRCA1"]["probes"] == []


def test_assign_to_exon_and_coverage_table_cover_probe_and_cds_paths() -> None:
    payload = _coverage_payload()
    tp53 = payload["genes"]["TP53"]
    assert CoverageProcessingService.assign_to_exon("missing", tp53) == []
    assert [row["nbr"] for row in CoverageProcessingService.assign_to_exon("95-125", tp53)] == ["1"]

    table = CoverageProcessingService.coverage_table(payload, 20)
    assert table["TP53"]["1"]["cov"] == 45
    assert table["TP53"]["300-320"]["cov"] == 5
    assert table["BRCA1"]["3"]["cov"] == 2
    assert "ALK" not in table
