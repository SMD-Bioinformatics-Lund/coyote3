from __future__ import annotations

from coyote3.application.coverage.processing import CoverageProcessingService


class _D4CoverageBlacklistRepository:
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
    repository = _D4CoverageBlacklistRepository(
        [
            {"gene": "BRCA1", "region": "CDS", "coord": "blocked"},
            {"gene": "ALK", "region": "gene", "coord": ""},
        ]
    )
    filtered = CoverageProcessingService.find_low_covered_genes(
        _coverage_payload(), 20, "hematology", d4_coverage_blacklist_repository=repository
    )
    assert list(filtered["genes"]) == ["TP53"]

    selected = CoverageProcessingService.filter_genes_from_form(
        _coverage_payload(),
        ["TP53", "ALK", "missing"],
        "hematology",
        d4_coverage_blacklist_repository=repository,
    )
    assert list(selected["genes"]) == ["TP53"]

    empty = CoverageProcessingService.filter_genes_from_form(
        _coverage_payload(), [], "hematology", d4_coverage_blacklist_repository=repository
    )
    assert not empty.get("genes")


def test_reg_low_supports_precomputed_and_repository_blacklists() -> None:
    repository = _D4CoverageBlacklistRepository()
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
            d4_coverage_blacklist_repository=repository,
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
            d4_coverage_blacklist_repository=repository,
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


def test_low_coverage_cds_without_overlapping_probes_remains_in_summary() -> None:
    """Probe presence must not suppress independent low-coverage coding regions."""
    payload = _coverage_payload()
    table = CoverageProcessingService.coverage_table(payload, 20)
    assert table["TP53"]["2"]["cov"] == 8
    payload["genes"]["TP53"]["probes"] = {}
    table = CoverageProcessingService.coverage_table(payload, 20)
    assert table["TP53"]["2"]["cov"] == 8


def test_blacklisted_regions_do_not_return_when_another_region_keeps_the_gene() -> None:
    """Keep complete design context while excluding blocked regions from low summaries."""
    repository = _D4CoverageBlacklistRepository(
        [
            {"gene": "TP53", "region": "CDS", "coord": "200-220"},
            {"gene": "TP53", "region": "probe", "coord": "95-125"},
        ]
    )
    payload = _coverage_payload()
    filtered = CoverageProcessingService.find_low_covered_genes(
        payload, 20, "hematology", d4_coverage_blacklist_repository=repository
    )
    table = CoverageProcessingService.coverage_table(filtered, 20)
    assert set(table["TP53"]) == {"300-320"}
    assert len(filtered["genes"]["TP53"]["CDS"]) == 2
    assert filtered["genes"]["TP53"]["CDS"]["200-220"]["blacklisted"] is True
    assert "blacklisted" not in payload["genes"]["TP53"]["CDS"]["200-220"]


def test_blacklist_matches_ui_coordinates_for_numbered_exons() -> None:
    """A UI coordinate must match an interval stored under its exon number."""
    payload = {
        "genes": {
            "GENE1": {
                "CDS": {
                    "1": {"chr": "1", "start": 0, "end": 100, "cov": 5, "nbr": 1},
                }
            }
        }
    }
    repository = _D4CoverageBlacklistRepository(
        [
            {"gene": "GENE1", "region": "CDS", "coord": "1:0-100"},
        ]
    )
    filtered = CoverageProcessingService.find_low_covered_genes(
        payload, 20, "hematology", d4_coverage_blacklist_repository=repository
    )
    assert not filtered.get("genes")


def test_blocked_cds_does_not_hide_an_independent_low_probe() -> None:
    """Blacklisting an exon must not implicitly blacklist overlapping probes."""
    repository = _D4CoverageBlacklistRepository(
        [{"gene": "TP53", "region": "CDS", "coord": "100-120"}]
    )
    filtered = CoverageProcessingService.find_low_covered_genes(
        _coverage_payload(), 20, "hematology", d4_coverage_blacklist_repository=repository
    )
    table = CoverageProcessingService.coverage_table(filtered, 20)
    assert "1" not in table["TP53"]
    assert table["TP53"]["95-125"]["cov"] == 7
