from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.application.public.catalog import PublicCatalogService


class _AspRepository:
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


class _AspcRepository:
    def __init__(self) -> None:
        self.aspcs = {
            "panel_a_base_production": {
                "aspc_id": "panel_a_base_production",
                "asp_id": "panel_a",
                "subpanel_id": "base",
                "display_name": "Panel A base",
                "analysis_types": ["SNV", "CNV", "SNV"],
                "reporting": {"report_sections": ["SNV", "CNV", "SNV"]},
                "catalog": {"is_public": True, "tat": "14 days"},
            },
            "panel_a_colon_production": {
                "aspc_id": "panel_a_colon_production",
                "asp_id": "panel_a",
                "subpanel_id": "colon",
                "display_name": "Colon",
                "analysis_types": ["SNV"],
                "reporting": {"report_sections": ["SNV"]},
                "catalog": {"is_public": False},
            },
        }

    def get_active_aspcs_for_asp(self, asp_id, _environment):
        return [item for item in self.aspcs.values() if item["asp_id"] == asp_id]

    def get_aspc_with_id(self, aspc_id):
        return self.aspcs.get(aspc_id)


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
        assay_configuration_repository=_AspcRepository(),
        assay_panel_repository=_AspRepository(),
        hgnc_repository=_HgncRepository(),
        gene_list_repository=_IsglRepository(),
        sample_repository=_SampleRepository(),
        vep_metadata_repository=_VepRepository(),
        public_assay_catalog_repository=_PublicCatalogRepository(),
    )


def test_draft_context_matches_public_view_without_reading_the_published_document(monkeypatch):
    service = _service()
    catalog = service.load_catalog()
    monkeypatch.setattr(service, "load_catalog", lambda **kwargs: catalog)
    key = next(iter(catalog["modalities"]))
    category = next(iter(catalog["modalities"][key]["categories"]))
    public = service.catalog_context(key, category)
    preview = service.catalog_context(key, category, preview_document=catalog)
    assert preview == public
    assert preview["genes"]
    assert preview["stats"]["total"] > 0


def test_context_uses_preview_content_for_navigation_and_heading():
    service = _service()
    preview = {
        "header": "Draft introduction",
        "description": "Draft description",
        "layout": {"order": ["draft_section"]},
        "modalities": {
            "draft_section": {
                "label": "Draft section",
                "categories": {
                    "solid": {
                        "label": "Draft solid",
                        "asp_id": "panel_a",
                        "aspc_id": "panel_a_base_production",
                    },
                },
            }
        },
    }
    original = service.public_assay_catalog_repository.get_default()
    landing = service.catalog_context(preview_document=preview)
    detail = service.catalog_context("draft_section", "solid", preview_document=preview)
    assert landing["right"]["title"] == "Draft introduction"
    assert detail["right"]["title"] == "Draft solid"
    assert detail["stats"]["total"] == 2
    assert service.public_assay_catalog_repository.get_default() == original


def test_empty_draft_does_not_show_generated_live_assays():
    service = _service()
    empty = {"header": "Empty draft", "modalities": {}, "layout": {"order": []}}
    catalog = service.load_catalog(preview_document=empty)
    assert catalog["modalities"] == {}
    assert catalog["layout"]["order"] == []
    matrix = service.assay_catalog_matrix_payload(preview_document=empty)
    assert matrix["columns"] == []
    assert matrix["genes"] == []


def test_preview_matrix_uses_selected_catalog_labels_and_covered_genes():
    service = _service()
    draft = {
        "layout": {"order": ["custom"]},
        "modalities": {
            "custom": {
                "label": "Whole Genome Sequencing",
                "categories": {
                    "entry": {"label": "Draft Solid", "asp_id": "panel_a", "gene_lists": []},
                },
            }
        },
    }
    result = service.assay_catalog_matrix_payload(preview_document=draft, per_page=1)
    assert result["order"] == ["custom"]
    assert result["total"] == 2
    assert result["has_next"] is True
    column = result["columns"][0]
    assert column["assay"] == "Draft Solid"
    assert column["modality_label"] == "Whole Genome Sequencing"
    assert column["isgl_label"] == "Covered genes"
    assert column["placeholder"] is False
    searched = service.assay_catalog_matrix_payload(preview_document=draft, gene="TP53")
    assert searched["genes"] == ["TP53"]
    assert searched["matrix"]["TP53"]["custom"]["entry"]["panel_a"] is True
    assert service.public_assay_catalog_repository.get_default() is None


def test_catalog_service_from_store_and_observed_versions():
    service = _service()
    store = SimpleNamespace(
        assay_configuration_repository=service.assay_configuration_repository,
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


def test_overlay_parsing_helpers_cover_list_dict_and_precedence():
    list_overlay = {"categories": [{"asp_id": "panel_a"}, "bad"]}
    assert PublicCatalogService._overlay_categories(list_overlay) == [{"asp_id": "panel_a"}]

    nested = {
        "modalities": {
            "dna": {
                "categories": {
                    "solid": {"asp_id": "panel_a", "subpanel_id": "base"},
                }
            },
            "rna": {"categories": [{"asp_id": "wts_a"}]},
        }
    }
    categories = PublicCatalogService._overlay_categories(nested)
    assert {item["asp_id"] for item in categories} == {"panel_a", "wts_a"}
    assert PublicCatalogService._overlay_modalities(nested)["dna"]
    assert PublicCatalogService._overlay_modalities({}) == {}

    assert (
        PublicCatalogService._category_overlay(
            nested,
            asp_id="panel_a",
            subpanel_id="base",
            aspc_id=None,
            catalog_id="missing",
        )["asp_id"]
        == "panel_a"
    )
    assert (
        PublicCatalogService._category_overlay(
            {"categories": [{"catalog_id": "catalog"}]},
            asp_id="x",
            subpanel_id="base",
            aspc_id=None,
            catalog_id="catalog",
        )["catalog_id"]
        == "catalog"
    )
    assert (
        PublicCatalogService._category_overlay(
            {"categories": [{"aspc_id": "cfg"}]},
            asp_id="x",
            subpanel_id="base",
            aspc_id="cfg",
            catalog_id="missing",
        )["aspc_id"]
        == "cfg"
    )
    assert (
        PublicCatalogService._category_overlay(
            {}, asp_id="x", subpanel_id="base", aspc_id=None, catalog_id="missing"
        )
        == {}
    )

    category = {
        "description": "overlay",
        "gene_lists": [{"isgl_id": "solid_list", "label": "Solid"}, "bad"],
    }
    assert PublicCatalogService._gene_list_overlay(category, "solid_list")["label"] == "Solid"
    assert PublicCatalogService._gene_list_overlay(category, "missing") == {}


def test_collection_catalog_builds_public_aspc_and_genelists(monkeypatch):
    service = _service()
    monkeypatch.setattr(service, "_load_catalog_document", lambda: {})

    catalog = service.load_catalog()

    assert catalog["version"] == "collections"
    assert catalog["layout"]["order"] == ["dna", "rna"]
    assert catalog["nav_groups"]
    dna_categories = catalog["modalities"]["dna"]["categories"]
    assert len(dna_categories) == 1
    category = next(iter(dna_categories.values()))
    assert category["asp_id"] == "panel_a"
    assert category["analysis"] == ["SNV", "CNV"]
    assert category["report_sections"] == ["SNV", "CNV"]
    assert [item["key"] for item in category["gene_lists"]] == ["panel_a", "solid_list"]


def test_overlay_catalog_uses_center_metadata_and_active_documents(monkeypatch):
    service = _service()
    overlay = {
        "version": "center-v1",
        "header": "Center catalog",
        "layout": {"order": ["dna"]},
        "modalities": {
            "dna": {
                "label": "DNA assays",
                "categories": {
                    "solid": {
                        "asp_id": "panel_a",
                        "aspc_id": "panel_a_base_production",
                        "title": "Solid assay",
                        "analysis": ["SNV"],
                        "gene_lists": [
                            {"isgl_id": "solid_list", "label": "Selected genes"},
                            {"label": "Display only"},
                        ],
                    }
                },
            },
            "invalid": "skip",
        },
    }
    monkeypatch.setattr(service, "_load_catalog_document", lambda: overlay)

    catalog = service.load_catalog()

    assert catalog["version"] == "center-v1"
    assert catalog["header"] == "Center catalog"
    category = catalog["modalities"]["dna"]["categories"]["solid"]
    assert category["title"] == "Solid assay"
    assert category["analysis"] == ["SNV"]
    assert category["gene_lists"][0]["description"] == "Selected solid genes"


def test_catalog_navigation_and_hydration(monkeypatch):
    service = _service()
    catalog = {
        "layout": {"order": ["dna"]},
        "modalities": {
            "dna": {
                "label": "DNA",
                "title": "DNA assays",
                "description": "DNA catalog",
                "categories": {
                    "solid": {
                        "catalog_id": "solid_catalog",
                        "label": "Solid",
                        "asp_id": "panel_a",
                        "aspc_id": "panel_a_base_production",
                        "analysis": [],
                        "gene_lists": [
                            {"key": "solid_list", "label": "Solid genes", "tat": "7 days"}
                        ],
                    }
                },
            }
        },
    }
    monkeypatch.setattr(service, "load_catalog", lambda **kwargs: catalog)

    assert service.modalities_order() == ["dna"]
    assert service.normalize_mod("DNA") == "dna"
    assert service.normalize_mod("whole genome sequencing") == "dna"
    assert service.normalize_mod("unknown") is None
    assert service.normalize_mod(None) is None
    assert service.modality_block("dna")["label"] == "DNA"
    assert service.categories_for("dna")[0]["catalog_id"] == "solid_catalog"
    assert service.category_def("dna", "solid_catalog")["asp_id"] == "panel_a"
    assert service.category_def("dna", "missing") is None

    hydrated = service.hydrate_category("dna", "solid_catalog", "solid_list")
    assert hydrated["label"] == "Solid genes"
    assert hydrated["analysis"] == ["SNV", "CNV"]
    assert hydrated["report_sections"] == ["SNV", "CNV"]
    assert service.hydrate_category("dna", "missing") is None
    assert service.hydrate_modality("dna")["title"] == "DNA assays"


@pytest.mark.parametrize(
    "visibility", [{"is_public": False}, {"is_active": False}, {"adhoc": True}]
)
def test_all_public_gene_views_exclude_private_inactive_and_adhoc_lists(visibility):
    service = _service()
    service.gene_list_repository.docs["solid_list"].update(visibility)
    assert service.genelist_view_context("solid_list") is None
    assert service.assay_catalog_gene_symbols_payload("solid_list") == {"gene_symbols": []}
    assert service.isgl_genes_for_matrix("solid_list") == set()
    assert service.resolve_gene_table("panel_a", "solid_list")[1] == []


def test_public_gene_list_projects_only_public_fields_and_sanitizes_html():
    service = _service()
    service.gene_list_repository.docs["solid_list"].update(
        private_context="synthetic private context",
        description='<p onclick="alert(1)">Public description</p><img src=x onerror="alert(2)">',
    )
    document = service.genelist_view_context("solid_list")["genelist"]
    assert "private_context" not in document
    assert document["description"] == "<p>Public description</p>"


def test_gene_table_resolution_and_public_gene_payloads(monkeypatch):
    service = _service()

    mode, rows, counts = service.resolve_gene_table("panel_a", "panel_a")
    assert mode == "covered"
    assert [row["display_symbol"] for row in rows] == ["BRCA1", "TP53"]
    assert counts["germline_total"] == 1

    mode, rows, counts = service.resolve_gene_table("panel_a", "solid_list")
    assert mode == "overlap"
    assert [row["display_symbol"] for row in rows] == ["TP53"]
    assert counts["isgl_total"] == 2

    mode, rows, _counts = service.resolve_gene_table(None, "solid_list")
    assert mode == "genelist"
    assert [row["display_symbol"] for row in rows] == ["EGFR", "TP53"]

    assert service.genelist_view_context("missing") is None
    context = service.genelist_view_context("solid_list", assay="panel_a")
    assert context["filtered_genes"] == ["TP53"]
    assert context["germline_genes"] == ["BRCA1"]

    genes = service.apply_drug_info([{"hgnc_symbol": "TP53"}, {"symbol": "EGFR"}], "drug_list")
    assert [item["drug_target"] for item in genes] == [True, False]

    monkeypatch.setattr(
        service,
        "load_catalog",
        lambda: {
            "modalities": {
                "dna": {
                    "label": "DNA",
                    "categories": {"panel": {"asp_id": "panel_a", "catalog_id": "panel_a"}},
                }
            }
        },
    )
    payload = service.asp_genes_payload("panel_a")
    assert payload["stats"] == {"covered_total": 2, "germline_total": 1, "displayed_total": 2}
    assert payload["catalog"]["modality"] == "dna"
    assert service.assay_catalog_gene_symbols_payload("solid_list") == {
        "gene_symbols": ["EGFR", "TP53"]
    }
    assert service.isgl_genes_for_matrix("solid_list") == {"EGFR", "TP53"}


def test_matrix_payload_supports_placeholders_search_and_paging(monkeypatch):
    service = _service()
    catalog = {
        "layout": {"order": ["dna", "rna", "empty"]},
        "modalities": {
            "dna": {
                "categories": {
                    "solid": {
                        "asp_id": "panel_a",
                        "label": "Solid",
                        "family": "panel",
                        "assay_group": "solid",
                        "gene_lists": [
                            {"key": "panel_a", "label": "Covered"},
                            {"key": "solid_list", "label": "Selected"},
                        ],
                    },
                    "placeholder": {"label": "No list", "gene_lists": []},
                }
            },
            "rna": {"categories": {}},
            "empty": {},
        },
    }
    monkeypatch.setattr(service, "load_catalog", lambda **kwargs: catalog)

    payload = service.assay_catalog_matrix_payload(page=1, per_page=1)
    assert payload["total"] == 3
    assert payload["genes"] == ["BRCA1"]
    assert payload["has_next"] is True
    assert any(item["placeholder"] for item in payload["columns"])

    searched = service.assay_catalog_matrix_payload(page=9, per_page=0, gene="tp")
    assert searched["genes"] == ["TP53"]
    assert searched["page"] == 1
    assert searched["has_previous"] is False
    assert searched["matrix"]["TP53"]["dna"]["solid"]["panel_a"] is True


def test_catalog_static_helpers_and_grouping():
    assert PublicCatalogService._title("panel-dna") == "Panel Dna"
    assert PublicCatalogService._family_bucket({"asp_family": "panel-rna"}) == "panel"
    assert PublicCatalogService._family_bucket({}) == "assay"
    assert PublicCatalogService._aspc_subpanel_id(None) == "base"
    assert PublicCatalogService._aspc_catalog({"catalog": "bad"}) == {}
    assert PublicCatalogService._unique(["SNV", "", "SNV", "CNV"]) == ["SNV", "CNV"]
    assert PublicCatalogService._aspc_available_analysis(None) == []
    assert PublicCatalogService._aspc_report_sections(None) == []
    assert PublicCatalogService._overlay_order(
        {"layout": {"order": ["rna", "missing"]}}, {"dna": {}, "rna": {}}
    ) == ["rna", "dna"]

    grouped = PublicCatalogService._group_isgls_by_asp_and_subpanel(
        [
            {"isgl_id": "b", "asp_ids": ["panel"], "diagnosis": ["colon"]},
            {"isgl_id": "a", "asp_ids": ["panel"], "diagnosis": []},
            {"isgl_id": "", "asp_ids": ["panel"]},
        ]
    )
    selected = PublicCatalogService._isgls_for_catalog_subpanel(grouped["panel"], "colon")
    assert [item["isgl_id"] for item in selected] == ["b", "a"]
    assert PublicCatalogService._isgls_for_catalog_subpanel({}, "colon") == []
