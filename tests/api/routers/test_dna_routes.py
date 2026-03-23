"""Behavior tests for DNA API route helpers and endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.main import app as api_app
from api.repositories import dna_repository as dna_repo_module
from api.routers import biomarkers as biomarker_router
from api.routers import classifications as classification_router
from api.routers import small_variants as dna
from api.security import access
from api.security.access import ApiUser
from api.services import dna_service as dna_service_module
from api.services.dna_service import DnaService
from tests.fixtures.api import mock_collections as fx


def test_mutation_payload_shape():
    """Test mutation payload shape.

    Returns:
        The function result.
    """
    payload = DnaService.mutation_payload("S1", "variant", "V1", "flag")
    assert payload["status"] == "ok"
    assert payload["sample_id"] == "S1"
    assert payload["resource"] == "variant"
    assert payload["resource_id"] == "V1"
    assert payload["action"] == "flag"


def test_load_cnvs_for_sample_uses_collection_shaped_docs(monkeypatch):
    """Test load cnvs for sample uses collection shaped docs.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    sample_filters = sample["filters"]
    cnv_rows = [fx.cnv_doc()]
    service = DnaService()

    monkeypatch.setattr(
        dna_repo_module.store.cnv_handler, "get_sample_cnvs", lambda query: cnv_rows
    )
    monkeypatch.setattr(
        dna_service_module,
        "build_cnv_query",
        lambda sample_id, filters: {"sample_id": sample_id, **filters},
    )
    monkeypatch.setattr(dna_service_module, "create_cnveffectlist", lambda cnv_effects: [])
    monkeypatch.setattr(dna_service_module, "cnv_organizegenes", lambda cnvs: cnvs)

    rows = service.load_cnvs_for_sample(
        sample=sample, sample_filters=sample_filters, filter_genes=["ERBB2"]
    )
    assert rows == cnv_rows


def test_list_dna_biomarkers_success(monkeypatch):
    """Test list dna biomarkers success.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    biomarkers = [{"_id": "b1", "name": "TMB", "value": "High"}]
    service = biomarker_router.BiomarkerService()

    monkeypatch.setattr(biomarker_router, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(
        dna_repo_module.store.biomarker_handler,
        "get_sample_biomarkers",
        lambda sample_id: biomarkers,
    )
    monkeypatch.setattr(
        biomarker_router.util.common, "convert_to_serializable", lambda payload: payload
    )

    payload = biomarker_router.list_dna_biomarkers("S1", user=fx.api_user(), service=service)
    assert payload["meta"]["count"] == 1
    assert payload["biomarkers"][0]["name"] == "TMB"


def test_show_dna_variant_not_found_raises_404(monkeypatch):
    """Test show dna variant not found raises 404.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    service = DnaService()
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(dna_repo_module.store.variant_handler, "get_variant", lambda var_id: None)

    with pytest.raises(HTTPException) as exc:
        dna.show_dna_variant("S1", "V404", user=fx.api_user(), service=service)

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Variant not found"


def test_show_dna_variant_handles_list_consequence_for_oncokb(monkeypatch):
    """Test show dna variant handles list consequence for oncokb."""
    sample = fx.sample_doc()
    sample["_id"] = "sample-1"
    variant = {
        "_id": "v1",
        "SAMPLE_ID": "sample-1",
        "CHROM": "7",
        "POS": 140453136,
        "REF": "A",
        "ALT": "T",
        "INFO": {
            "selected_CSQ": {
                "SYMBOL": "TP53",
                "Consequence": ["frameshift_variant", "splice_region_variant"],
                "HGVSp": "",
            }
        },
        "transcripts": [],
    }
    captured: dict = {"hgvsp": None}
    service = DnaService()

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna, "_get_formatted_assay_config", lambda _sample: {"asp_group": "dna"})
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler, "get_variant", lambda var_id: variant
    )
    monkeypatch.setattr(
        dna_repo_module.store.blacklist_handler,
        "add_blacklist_data",
        lambda variants, assay_group: variants,
    )
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler, "get_variant_in_other_samples", lambda var: []
    )
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler, "hidden_var_comments", lambda var_id: False
    )
    monkeypatch.setattr(
        dna_repo_module.store.annotation_handler,
        "get_global_annotations",
        lambda variant, assay_group, subpanel: ({}, None, [], []),
    )
    monkeypatch.setattr(dna, "add_alt_class", lambda var, assay_group, subpanel: var)
    monkeypatch.setattr(
        dna_repo_module.store.expression_handler, "get_expression_data", lambda transcripts: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.civic_handler, "get_civic_data", lambda variant, desc: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.civic_handler, "get_civic_gene_info", lambda symbol: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.oncokb_handler,
        "get_oncokb_anno",
        lambda variant, oncokb_hgvsp: captured.__setitem__("hgvsp", oncokb_hgvsp) or {},
    )
    monkeypatch.setattr(
        dna_repo_module.store.oncokb_handler, "get_oncokb_action", lambda variant, hgvsp: {}
    )
    monkeypatch.setattr(dna_repo_module.store.oncokb_handler, "get_oncokb_gene", lambda symbol: {})
    monkeypatch.setattr(
        dna_repo_module.store.brca_handler, "get_brca_data", lambda variant, assay_group: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.iarc_tp53_handler, "find_iarc_tp53", lambda variant: {}
    )
    monkeypatch.setattr(
        dna.util.common,
        "get_case_and_control_sample_ids",
        lambda sample_doc: {"case": "sample-1"},
    )
    monkeypatch.setattr(
        dna_repo_module.store.bam_service_handler, "get_bams", lambda sample_ids: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.vep_meta_handler, "get_variant_class_translations", lambda vep: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.vep_meta_handler, "get_conseq_translations", lambda vep: {}
    )
    monkeypatch.setattr(dna_repo_module.store.asp_handler, "get_asp_group_mappings", lambda: {})
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.show_dna_variant("S1", "v1", user=fx.api_user(), service=service)

    assert payload["variant"]["_id"] == "v1"
    assert captured["hgvsp"] == ["Truncating Mutations"]


def test_list_dna_variants_does_not_require_report_path(monkeypatch):
    """Test list dna variants does not require report path.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    sample.setdefault("filters", {}).setdefault("max_freq", 1.0)
    sample["filters"].setdefault("min_freq", 0.0)
    sample["filters"].setdefault("max_control_freq", 1.0)
    sample["filters"].setdefault("min_depth", 0)
    sample["filters"].setdefault("min_alt_reads", 0)
    sample["filters"].setdefault("max_popfreq", 1.0)
    sample["filters"].setdefault("vep_consequences", [])
    sample["filters"].setdefault("genelists", [])
    sample.setdefault("subpanel", "")

    assay_config = {
        "asp_group": "tumwgs",
        "analysis_types": [],
        "reporting": {},  # intentionally missing report_path
    }

    service = DnaService()
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna, "_get_formatted_assay_config", lambda _sample: assay_config)
    monkeypatch.setattr(dna.util.common, "merge_sample_settings_with_assay_config", lambda s, a: s)
    monkeypatch.setattr(
        dna_repo_module.store.asp_handler, "get_asp", lambda asp_name: {"asp_name": asp_name}
    )
    monkeypatch.setattr(dna_repo_module.store.isgl_handler, "get_isgl_by_ids", lambda ids: {})
    monkeypatch.setattr(dna.util.common, "get_sample_effective_genes", lambda s, a, g: ([], []))
    monkeypatch.setattr(dna, "get_filter_conseq_terms", lambda values: [])
    monkeypatch.setattr(
        dna, "build_query", lambda assay_group, params: {"assay_group": assay_group, **params}
    )
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler, "get_case_variants", lambda query: []
    )
    monkeypatch.setattr(
        dna_repo_module.store.blacklist_handler,
        "add_blacklist_data",
        lambda variants, assay_group: variants,
    )
    monkeypatch.setattr(
        dna, "add_global_annotations", lambda variants, assay_group, subpanel: (variants, [])
    )
    monkeypatch.setattr(
        dna.util.common, "get_case_and_control_sample_ids", lambda s: {"case": "C1"}
    )
    monkeypatch.setattr(
        dna_repo_module.store.bam_service_handler, "get_bams", lambda sample_ids: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.vep_meta_handler, "get_variant_class_translations", lambda vep: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.vep_meta_handler, "get_conseq_translations", lambda vep: {}
    )
    monkeypatch.setattr(
        dna_repo_module.store.sample_handler, "hidden_sample_comments", lambda sample_oid: False
    )
    monkeypatch.setattr(
        dna_repo_module.store.isgl_handler, "get_isgl_by_asp", lambda assay, is_active=True: []
    )
    monkeypatch.setattr(dna.util.common, "get_assay_genelist_names", lambda docs: [])
    monkeypatch.setattr(dna, "generate_summary_text", lambda *args, **kwargs: "")
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    req = SimpleNamespace(url=SimpleNamespace(path="/api/v1/samples/S1/small-variants"))
    payload = dna.list_dna_variants(req, "S1", user=fx.api_user(), service=service)

    assert payload["sample"]["name"] == sample["name"]
    assert payload["meta"]["count"] == 0


def test_classify_variant_mutation_calls_insert(monkeypatch):
    """Test classify variant mutation calls insert.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    captured: dict = {}

    monkeypatch.setattr(
        classification_router, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc()
    )
    monkeypatch.setattr(
        classification_router.util.common, "get_tier_classification", lambda form_data: 3
    )
    monkeypatch.setattr(
        classification_router, "get_variant_nomenclature", lambda form_data: ("p", "TP53 p.R175H")
    )
    monkeypatch.setattr(
        dna_repo_module.store.annotation_handler,
        "insert_classified_variant",
        lambda variant, nomenclature, class_num, form_data, **kwargs: captured.update(
            {
                "variant": variant,
                "nomenclature": nomenclature,
                "class_num": class_num,
                "author": kwargs.get("author"),
            }
        ),
    )
    monkeypatch.setattr(
        classification_router.util.common, "convert_to_serializable", lambda payload: payload
    )

    payload = classification_router.classify_resource_mutation(
        "S1",
        payload={"id": "V1", "form_data": {"tier3": "on"}},
        user=fx.api_user(),
        service=classification_router.ResourceClassificationService(),
    )

    assert payload["status"] == "ok"
    assert captured["variant"] == "TP53 p.R175H"
    assert captured["class_num"] == 3


def test_set_variant_false_positive_bulk_prefers_json_payload(monkeypatch):
    """Test set variant false positive bulk prefers json payload.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls: dict = {"mark": None, "unmark": None}
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler,
        "mark_false_positive_var_bulk",
        lambda ids: calls.__setitem__("mark", ids),
    )
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler,
        "unmark_false_positive_var_bulk",
        lambda ids: calls.__setitem__("unmark", ids),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.set_variant_false_positive_bulk(
        "S1",
        apply=False,
        resource_ids=["ignored-query-id"],
        payload={"apply": True, "resource_ids": ["V1", "V2"]},
        user=fx.api_user(),
        service=DnaService(),
    )

    assert payload["status"] == "ok"
    assert calls["mark"] == ["V1", "V2"]
    assert calls["unmark"] is None


def test_set_variant_irrelevant_bulk_remove_uses_json_payload(monkeypatch):
    """Test set variant irrelevant bulk remove uses json payload.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls: dict = {"mark": None, "unmark": None}
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler,
        "mark_irrelevant_var_bulk",
        lambda ids: calls.__setitem__("mark", ids),
    )
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler,
        "unmark_irrelevant_var_bulk",
        lambda ids: calls.__setitem__("unmark", ids),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.set_variant_irrelevant_bulk(
        "S1",
        apply=True,
        resource_ids=["ignored-query-id"],
        payload={"apply": False, "resource_ids": ["V9"]},
        user=fx.api_user(),
        service=DnaService(),
    )

    assert payload["status"] == "ok"
    assert calls["mark"] is None
    assert calls["unmark"] == ["V9"]


def test_set_variant_tier_bulk_apply_inserts_class_and_text_docs(monkeypatch):
    """Test set variant tier bulk apply inserts class and text docs.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    sample["_id"] = "sample-1"
    captured: dict = {"docs": None}
    variant = {
        "_id": "v1",
        "SAMPLE_ID": "sample-1",
        "CHROM": "7",
        "POS": 140453136,
        "REF": "A",
        "ALT": "T",
        "INFO": {
            "selected_CSQ": {
                "Feature": "NM_0000.1",
                "SYMBOL": "BRAF",
                "HGVSp": "p.V600E",
                "Consequence": [],
            }
        },
    }

    monkeypatch.setattr(
        classification_router, "_get_sample_for_api", lambda sample_id, user: sample
    )
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler, "get_variant", lambda variant_id: variant
    )
    monkeypatch.setattr(dna_repo_module.store.oncokb_handler, "get_oncokb_gene", lambda gene: None)
    monkeypatch.setattr(
        classification_router,
        "create_annotation_text_from_gene",
        lambda *args, **kwargs: "AUTO_TEXT",
    )
    monkeypatch.setattr(
        classification_router.util.common,
        "create_classified_variant_doc",
        lambda variant, nomenclature, class_num, variant_data, **kwargs: {
            "variant": variant,
            "nomenclature": nomenclature,
            "class": class_num if "text" not in kwargs else None,
            "text": kwargs.get("text"),
            "source": kwargs.get("source"),
            "variant_data": variant_data,
        },
    )
    monkeypatch.setattr(
        dna_repo_module.store.annotation_handler,
        "insert_annotation_bulk",
        lambda docs: captured.__setitem__("docs", docs),
    )
    monkeypatch.setattr(
        classification_router.util.common, "convert_to_serializable", lambda payload: payload
    )

    payload = classification_router.set_resource_tier_bulk(
        "S1",
        payload={
            "apply": True,
            "resource_ids": ["v1"],
            "resource_type": "small_variant",
            "assay_group": "solid",
            "subpanel": "A",
            "tier": 3,
        },
        user=fx.api_user(),
        service=classification_router.ResourceClassificationService(),
    )

    assert payload["status"] == "ok"
    assert captured["docs"] is not None
    assert len(captured["docs"]) == 2
    assert any(doc.get("class") == 3 for doc in captured["docs"])
    assert any(doc.get("text") == "AUTO_TEXT" for doc in captured["docs"])


def test_set_variant_tier_bulk_remove_deletes_class_and_matching_text(monkeypatch):
    """Test set variant tier bulk remove deletes class and matching text.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    sample = fx.sample_doc()
    sample["_id"] = "sample-1"
    captured: list[dict] = []
    variant = {
        "_id": "v1",
        "SAMPLE_ID": "sample-1",
        "CHROM": "7",
        "POS": 140453136,
        "REF": "A",
        "ALT": "T",
        "INFO": {
            "selected_CSQ": {
                "Feature": "NM_0000.1",
                "SYMBOL": "BRAF",
                "HGVSp": "p.V600E",
                "Consequence": [],
            }
        },
    }

    monkeypatch.setattr(
        classification_router, "_get_sample_for_api", lambda sample_id, user: sample
    )
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler, "get_variant", lambda variant_id: variant
    )
    monkeypatch.setattr(dna_repo_module.store.oncokb_handler, "get_oncokb_gene", lambda gene: None)
    monkeypatch.setattr(
        classification_router,
        "create_annotation_text_from_gene",
        lambda *args, **kwargs: "AUTO_TEXT",
    )
    monkeypatch.setattr(
        dna_repo_module.store.annotation_handler,
        "delete_classified_variant",
        lambda **kwargs: captured.append(kwargs),
    )
    monkeypatch.setattr(
        dna_repo_module.store.annotation_handler,
        "insert_annotation_bulk",
        lambda docs: pytest.fail("insert_annotation_bulk must not be called on tier remove"),
    )
    monkeypatch.setattr(
        classification_router.util.common, "convert_to_serializable", lambda payload: payload
    )

    payload = classification_router.set_resource_tier_bulk(
        "S1",
        payload={
            "apply": False,
            "resource_ids": ["v1"],
            "resource_type": "small_variant",
            "assay_group": "solid",
            "subpanel": "A",
            "tier": 3,
        },
        user=fx.api_user(),
        service=classification_router.ResourceClassificationService(),
    )

    assert payload["status"] == "ok"
    assert len(captured) == 1
    assert captured[0]["class_num"] == 3
    assert captured[0]["annotation_text"] == "AUTO_TEXT"


def test_bulk_flag_routes_use_non_colliding_paths():
    """Test bulk flag routes use non colliding paths.

    Returns:
        The function result.
    """
    paths = {route.path for route in api_app.routes}
    assert "/api/v1/samples/{sample_id}/small-variants/flags/false-positive" in paths
    assert "/api/v1/samples/{sample_id}/small-variants/flags/irrelevant" in paths
    assert "/api/v1/samples/{sample_id}/classifications/tier" in paths
    assert "/api/v1/samples/{sample_id}/classifications" in paths
    assert "/api/v1/samples/{sample_id}/annotations" in paths
    assert "/api/v1/samples/{sample_id}/small-variants/{var_id}/flags/false-positive" in paths
    assert "/api/v1/samples/{sample_id}/small-variants/exports/snvs/context" in paths
    assert "/api/v1/samples/{sample_id}/small-variants/exports/cnvs/context" in paths
    assert "/api/v1/samples/{sample_id}/small-variants/exports/translocs/context" in paths


def _route_test_user() -> ApiUser:
    """Route test user.

    Returns:
            The  route test user result.
    """
    return ApiUser(
        id="u1",
        email="tester@example.com",
        fullname="Test User",
        username="tester",
        role="user",
        access_level=9,
        permissions=["manage_snvs"],
        denied_permissions=[],
        assays=["WGS"],
        assay_groups=["dna"],
        envs=["production"],
        asp_map={},
    )


def test_bulk_fp_endpoint_dispatches_in_real_http_route(monkeypatch):
    """Test bulk fp endpoint dispatches in real http route.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    captured: dict = {"ids": None}
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _route_test_user())
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9, "manager": 99, "admin": 999})
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler,
        "mark_false_positive_var_bulk",
        lambda ids: captured.__setitem__("ids", ids),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    client = TestClient(api_app, raise_server_exceptions=False)
    response = client.patch(
        "/api/v1/samples/S1/small-variants/flags/false-positive",
        json={"apply": True, "resource_ids": ["V1", "V2"], "resource_type": "small_variant"},
    )

    assert response.status_code == 200
    assert captured["ids"] == ["V1", "V2"]

    old_path_response = client.post(
        "/api/v1/samples/S1/small-variants/fp/bulk",
        json={"apply": True, "resource_ids": ["V1", "V2"], "resource_type": "small_variant"},
    )
    assert old_path_response.status_code >= 400


def test_bulk_irrelevant_endpoint_dispatches_in_real_http_route(monkeypatch):
    """Test bulk irrelevant endpoint dispatches in real http route.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    captured: dict = {"ids": None}
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _route_test_user())
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9, "manager": 99, "admin": 999})
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        dna_repo_module.store.variant_handler,
        "mark_irrelevant_var_bulk",
        lambda ids: captured.__setitem__("ids", ids),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    client = TestClient(api_app, raise_server_exceptions=False)
    response = client.patch(
        "/api/v1/samples/S1/small-variants/flags/irrelevant",
        json={"apply": True, "resource_ids": ["V5"], "resource_type": "small_variant"},
    )

    assert response.status_code == 200
    assert captured["ids"] == ["V5"]


def _download_test_user() -> ApiUser:
    """Build a user with download permissions for export endpoints."""
    return ApiUser(
        id="u1",
        email="tester@example.com",
        fullname="Test User",
        username="tester",
        role="user",
        access_level=9,
        permissions=["download_snvs", "download_cnvs", "download_translocs"],
        denied_permissions=[],
        assays=["WGS"],
        assay_groups=["dna"],
        envs=["production"],
        asp_map={},
    )


def test_snv_export_context_route_returns_typed_csv_payload(monkeypatch):
    """SNV export context endpoint returns generated CSV content and filename."""
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _download_test_user())
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9, "manager": 99, "admin": 999})
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        DnaService,
        "list_variants_payload",
        lambda self, **kwargs: {
            "display_sections_data": {
                "snvs": [
                    {
                        "CHROM": "chr7",
                        "POS": 140453136,
                        "REF": "A",
                        "ALT": "T",
                        "INFO": {
                            "selected_CSQ": {
                                "SYMBOL": "BRAF",
                                "HGVSp": "p.Val600Glu",
                                "HGVSc": "c.1799T>A",
                                "Consequence": ["missense_variant"],
                                "EXON": "15/18",
                                "INTRON": "",
                            }
                        },
                        "GT": [],
                        "FILTER": ["PASS"],
                        "classification": {"class": 3, "transcript": ""},
                    }
                ]
            }
        },
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    client = TestClient(api_app, raise_server_exceptions=False)
    response = client.get("/api/v1/samples/S1/small-variants/exports/snvs/context")
    assert response.status_code == 200
    body = response.json()
    assert body["filename"].endswith(".filtered.snvs.csv")
    assert "hgvsp" in body["content"]
    assert "BRAF" in body["content"]


def test_transloc_export_context_route_returns_typed_csv_payload(monkeypatch):
    """Translocation export context endpoint returns generated CSV content and filename."""
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _download_test_user())
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9, "manager": 99, "admin": 999})
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        DnaService,
        "list_variants_payload",
        lambda self, **kwargs: {
            "display_sections_data": {
                "translocs": [
                    {
                        "CHROM": "chr9",
                        "POS": 133729451,
                        "ALT": "chr22:23632628",
                        "INFO": {
                            "PANEL": "DNA",
                            "MANE_ANN": {
                                "Gene_Name": "ABL1&BCR",
                                "Annotation": ["gene_fusion"],
                                "HGVSp": "p.X",
                                "HGVSc": "c.X",
                            },
                        },
                        "interesting": True,
                    }
                ]
            }
        },
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    client = TestClient(api_app, raise_server_exceptions=False)
    response = client.get("/api/v1/samples/S1/small-variants/exports/translocs/context")
    assert response.status_code == 200
    body = response.json()
    assert body["filename"].endswith(".filtered.translocs.csv")
    assert "gene_1" in body["content"]
    assert "ABL1" in body["content"]
