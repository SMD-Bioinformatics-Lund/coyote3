from __future__ import annotations

from types import SimpleNamespace

import pytest

from coyote3.application.public.catalog import PublicCatalogService


class _AspRepository:
    def group_options(self):
        return ["solid", "wts"]

    def __init__(self) -> None:
        self.asps = [
            {
                "asp_id": "panel_a",
                "display_name": "Panel A",
                "description": "DNA panel",
                "asp_category": "dna",
                "asp_family": "panel-dna",
                "asp_group": "solid",
                "platform": "illumina",
                "covered_genes": ["TP53", "BRCA1"],
                "germline_genes": ["BRCA1"],
                "covered_genes_count": 2,
                "germline_genes_count": 1,
            },
            {
                "asp_id": "wts_a",
                "display_name": "WTS A",
                "asp_category": "rna",
                "asp_family": "wts",
                "asp_group": "wts",
                "covered_genes": [],
                "germline_genes": [],
            },
        ]

    def get_all_asps(self, **_kwargs):
        return self.asps

    def get_asp_genes(self, asp_id):
        asp = next((item for item in self.asps if item["asp_id"] == asp_id), {})
        return asp.get("covered_genes", []), asp.get("germline_genes", [])

    def get_asp(self, asp_id):
        return next((item for item in self.asps if item["asp_id"] == asp_id), None)


class _IsglRepository:
    def __init__(self) -> None:
        self.docs = {
            "solid_list": {
                "isgl_id": "solid_list",
                "is_public": True,
                "is_active": True,
                "adhoc": False,
                "name": "Solid list",
                "description": "Selected solid genes",
                "genes": ["TP53", "EGFR"],
                "asp_ids": ["panel_a"],
                "diagnosis": ["base"],
                "list_type": ["snv"],
            },
            "drug_list": {"isgl_id": "drug_list", "genes": ["TP53"]},
        }

    def get_all_isgl(self, **_kwargs):
        return [self.docs["solid_list"]]

    def get_isgl(self, key, **_kwargs):
        return self.docs.get(key)


class _HgncRepository:
    def get_metadata_by_symbols(self, symbols):
        rows = {
            "TP53": {
                "hgnc_id": "HGNC:11998",
                "hgnc_symbol": "TP53",
                "prev_symbol": ["P53"],
                "alias_symbol": ["BCC7"],
            },
            "BRCA1": {"hgnc_id": "HGNC:1100", "hgnc_symbol": "BRCA1"},
            "EGFR": {"hgnc_id": "HGNC:3236", "hgnc_symbol": "EGFR"},
        }
        return [rows[item] for item in symbols if item in rows]


class _SampleRepository:
    def get_observed_software_versions(self):
        return {"pipelines": {"SomaticPanelPipeline": ["1.0"]}}

    def get_observed_database_versions(self):
        return {"vep": ["110"]}


class _VepRepository:
    def list_versions(self):
        return ["110"]


class _PublicCatalogRepository:
    def __init__(self, document=None) -> None:
        self.document = document

    def get_default(self):
        return self.document


class _KnowledgebaseVersionRepository:
    def list_active_releases(self):
        return [
            {
                "source": "cosmic_actionability",
                "release": "v21",
                "records": 12,
                "status": "active",
            }
        ]


def _service() -> PublicCatalogService:
    return PublicCatalogService(
        assay_panel_repository=_AspRepository(),
        hgnc_repository=_HgncRepository(),
        gene_list_repository=_IsglRepository(),
        sample_repository=_SampleRepository(),
        vep_metadata_repository=_VepRepository(),
        public_assay_catalog_repository=_PublicCatalogRepository(),
    )


def test_catalog_service_from_store_and_observed_versions():
    service = _service()
    store = SimpleNamespace(
        assay_panel_repository=service.assay_panel_repository,
        hgnc_repository=service.hgnc_repository,
        gene_list_repository=service.gene_list_repository,
        sample_repository=service.sample_repository,
        vep_metadata_repository=service.vep_metadata_repository,
        public_assay_catalog_repository=service.public_assay_catalog_repository,
    )
    built = PublicCatalogService.from_store(store)
    assert built.observed_software_versions() == {"pipelines": {"SomaticPanelPipeline": ["1.0"]}}
    assert built.observed_reference_versions() == {
        "sample_database_versions": {"vep": ["110"]},
        "vep_metadata": ["110"],
    }


def test_knowledgebase_status_aggregates_active_release_counts():
    service = _service()
    service.knowledgebase_version_repository = _KnowledgebaseVersionRepository()

    assert service.knowledgebase_status() == {
        "releases": [
            {
                "source": "cosmic_actionability",
                "release": "v21",
                "records": 12,
                "status": "active",
            }
        ],
        "summary": {"installed_products": 1, "total_records": 12},
    }


def test_public_gene_markers_are_resolved_in_batches():
    service = _service()
    service.oncokb_public_cache_repository = SimpleNamespace(
        get_gene_records=lambda genes: {"TP53": {"gene": "TP53"}}
    )
    service.clinpgx_public_repository = SimpleNamespace(
        get_gene_records=lambda genes: {
            "BRCA1": {"symbol": "BRCA1", "pharmgkb_accession_id": "PA1"}
        }
    )
    service.civic_repository = SimpleNamespace(get_gene_records=lambda genes: {})
    service.cosmic_repository = SimpleNamespace(
        get_cancer_gene_census_records=lambda genes: {"TP53": {"gene": "TP53"}}
    )

    markers = service.knowledgebase_gene_markers(["TP53", "BRCA1"])

    assert markers["TP53"]["oncokb"] is True
    assert markers["TP53"]["cosmic_cgc"] is True
    assert markers["BRCA1"]["clinpgx_accession"] == "PA1"


@pytest.mark.parametrize(
    "visibility", [{"is_public": False}, {"is_active": False}, {"adhoc": True}]
)
def test_all_public_gene_views_exclude_private_inactive_and_adhoc_lists(visibility):
    service = _service()
    service.gene_list_repository.docs["solid_list"].update(visibility)
    assert service.genelist_view_context("solid_list") is None
    assert service.assay_catalog_gene_symbols_payload("solid_list") == {"gene_symbols": []}
    assert service.published_matrix()["genes"] == []


def test_public_gene_list_projects_only_public_fields_and_sanitizes_html():
    service = _service()
    service.gene_list_repository.docs["solid_list"].update(
        private_context="synthetic private context",
        description='<p onclick="alert(1)">Public description</p><img src=x onerror="alert(2)">',
    )
    document = service.genelist_view_context("solid_list")["genelist"]
    assert "private_context" not in document
    assert document["description"] == "<p>Public description</p>"


@pytest.mark.parametrize("family", ["wgs", "wts"])
def test_genome_and_transcriptome_genelists_are_not_restricted_to_panel_genes(family):
    service = _service()
    service.assay_panel_repository.asps[0].update(asp_family=family, covered_genes=[])
    context = service.genelist_view_context("solid_list", assay="panel_a")
    assert sorted(context["filtered_genes"]) == ["EGFR", "TP53"]


def test_public_assay_genes_preserve_covered_symbols_without_hgnc_metadata(monkeypatch):
    service = _service()
    monkeypatch.setattr(
        service.hgnc_repository,
        "get_metadata_by_symbols",
        lambda symbols: [{"hgnc_symbol": "TP53"}],
    )
    payload = service.asp_genes_payload("panel_a")
    assert [row["display_symbol"] for row in payload["gene_details"]] == ["BRCA1", "TP53"]
    assert payload["gene_details"][0]["status"] == "Unresolved"
    assert payload["gene_details"][0]["hgnc_id"] is None
    assert payload["stats"]["displayed_total"] == 2
