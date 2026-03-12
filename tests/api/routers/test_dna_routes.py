"""Behavior tests for DNA API route helpers and endpoints."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from api.app import app as api_app
from api.routers import variants as dna
from api.security import access
from api.security.access import ApiUser
from tests.api.fixtures import mock_collections as fx


def test_mutation_payload_shape():
    payload = dna._mutation_payload("S1", "variant", "V1", "flag")
    assert payload["status"] == "ok"
    assert payload["sample_id"] == "S1"
    assert payload["resource"] == "variant"
    assert payload["resource_id"] == "V1"
    assert payload["action"] == "flag"


def test_load_cnvs_for_sample_uses_collection_shaped_docs(monkeypatch):
    sample = fx.sample_doc()
    sample_filters = sample["filters"]
    cnv_rows = [fx.cnv_doc()]

    monkeypatch.setattr(dna, "build_cnv_query", lambda sample_id, filters: {"sample_id": sample_id, **filters})
    monkeypatch.setattr(dna.store.cnv_handler, "get_sample_cnvs", lambda query: cnv_rows)
    monkeypatch.setattr(dna, "create_cnveffectlist", lambda cnv_effects: [])
    monkeypatch.setattr(dna, "cnv_organizegenes", lambda cnvs: cnvs)

    rows = dna._load_cnvs_for_sample(sample, sample_filters, ["ERBB2"])
    assert rows == cnv_rows


def test_list_dna_biomarkers_success(monkeypatch):
    sample = fx.sample_doc()
    biomarkers = [{"_id": "b1", "name": "TMB", "value": "High"}]

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna.store.biomarker_handler, "get_sample_biomarkers", lambda sample_id: biomarkers)
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.list_dna_biomarkers("S1", user=fx.api_user())
    assert payload["meta"]["count"] == 1
    assert payload["biomarkers"][0]["name"] == "TMB"


def test_show_dna_variant_not_found_raises_404(monkeypatch):
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(dna.store.variant_handler, "get_variant", lambda var_id: None)

    with pytest.raises(HTTPException) as exc:
        dna.show_dna_variant("S1", "V404", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Variant not found"


def test_list_dna_variants_does_not_require_report_path(monkeypatch):
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
        "schema_name": "schema-dna",
        "reporting": {},  # intentionally missing report_path
    }

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna, "_get_formatted_assay_config", lambda _sample: assay_config)
    monkeypatch.setattr(dna.util.common, "merge_sample_settings_with_assay_config", lambda s, a: s)
    monkeypatch.setattr(dna.store.asp_handler, "get_asp", lambda asp_name: {"asp_name": asp_name})
    monkeypatch.setattr(dna.store.isgl_handler, "get_isgl_by_ids", lambda ids: {})
    monkeypatch.setattr(dna.util.common, "get_sample_effective_genes", lambda s, a, g: ([], []))
    monkeypatch.setattr(dna, "get_filter_conseq_terms", lambda values: [])
    monkeypatch.setattr(dna, "build_query", lambda assay_group, params: {"assay_group": assay_group, **params})
    monkeypatch.setattr(dna.store.variant_handler, "get_case_variants", lambda query: [])
    monkeypatch.setattr(dna.store.blacklist_handler, "add_blacklist_data", lambda variants, assay_group: variants)
    monkeypatch.setattr(dna, "add_global_annotations", lambda variants, assay_group, subpanel: (variants, []))
    monkeypatch.setattr(dna, "hotspot_variant", lambda variants: variants)
    monkeypatch.setattr(dna.util.common, "get_case_and_control_sample_ids", lambda s: {"case": "C1"})
    monkeypatch.setattr(dna.store.bam_service_handler, "get_bams", lambda sample_ids: {})
    monkeypatch.setattr(dna.store.vep_meta_handler, "get_variant_class_translations", lambda vep: {})
    monkeypatch.setattr(dna.store.vep_meta_handler, "get_conseq_translations", lambda vep: {})
    monkeypatch.setattr(dna.store.sample_handler, "hidden_sample_comments", lambda sample_oid: False)
    monkeypatch.setattr(dna.store.isgl_handler, "get_isgl_by_asp", lambda assay, is_active=True: [])
    monkeypatch.setattr(dna.util.common, "get_assay_genelist_names", lambda docs: [])
    monkeypatch.setattr(dna.store.schema_handler, "get_schema", lambda schema_name: {})
    monkeypatch.setattr(dna, "generate_summary_text", lambda *args, **kwargs: "")
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    req = SimpleNamespace(url=SimpleNamespace(path="/api/v1/dna/samples/S1/variants"))
    payload = dna.list_dna_variants(req, "S1", user=fx.api_user())

    assert payload["sample"]["name"] == sample["name"]
    assert payload["meta"]["count"] == 0


def test_classify_variant_mutation_calls_insert(monkeypatch):
    captured: dict = {}

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(dna.util.common, "get_tier_classification", lambda form_data: 3)
    monkeypatch.setattr(dna, "get_variant_nomenclature", lambda form_data: ("p", "TP53 p.R175H"))
    monkeypatch.setattr(
        dna.store.annotation_handler,
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
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.classify_variant_mutation(
        "S1",
        payload={"id": "V1", "form_data": {"tier3": "on"}},
        user=fx.api_user(),
    )

    assert payload["status"] == "ok"
    assert captured["variant"] == "TP53 p.R175H"
    assert captured["class_num"] == 3


def test_set_variant_false_positive_bulk_prefers_json_payload(monkeypatch):
    calls: dict = {"mark": None, "unmark": None}
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        dna.store.variant_handler,
        "mark_false_positive_var_bulk",
        lambda ids: calls.__setitem__("mark", ids),
    )
    monkeypatch.setattr(
        dna.store.variant_handler,
        "unmark_false_positive_var_bulk",
        lambda ids: calls.__setitem__("unmark", ids),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.set_variant_false_positive_bulk(
        "S1",
        apply=False,
        variant_ids=["ignored-query-id"],
        payload={"apply": True, "variant_ids": ["V1", "V2"]},
        user=fx.api_user(),
    )

    assert payload["status"] == "ok"
    assert calls["mark"] == ["V1", "V2"]
    assert calls["unmark"] is None


def test_set_variant_irrelevant_bulk_remove_uses_json_payload(monkeypatch):
    calls: dict = {"mark": None, "unmark": None}
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        dna.store.variant_handler,
        "mark_irrelevant_var_bulk",
        lambda ids: calls.__setitem__("mark", ids),
    )
    monkeypatch.setattr(
        dna.store.variant_handler,
        "unmark_irrelevant_var_bulk",
        lambda ids: calls.__setitem__("unmark", ids),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.set_variant_irrelevant_bulk(
        "S1",
        apply=True,
        variant_ids=["ignored-query-id"],
        payload={"apply": False, "variant_ids": ["V9"]},
        user=fx.api_user(),
    )

    assert payload["status"] == "ok"
    assert calls["mark"] is None
    assert calls["unmark"] == ["V9"]


def test_set_variant_tier_bulk_apply_inserts_class_and_text_docs(monkeypatch):
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
        "INFO": {"selected_CSQ": {"Feature": "NM_0000.1", "SYMBOL": "BRAF", "HGVSp": "p.V600E", "Consequence": []}},
    }

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna.store.variant_handler, "get_variant", lambda variant_id: variant)
    monkeypatch.setattr(dna.store.oncokb_handler, "get_oncokb_gene", lambda gene: None)
    monkeypatch.setattr(dna, "create_annotation_text_from_gene", lambda *args, **kwargs: "AUTO_TEXT")
    monkeypatch.setattr(
        dna.util.common,
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
        dna.store.annotation_handler,
        "insert_annotation_bulk",
        lambda docs: captured.__setitem__("docs", docs),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.set_variant_tier_bulk(
        "S1",
        payload={"apply": True, "variant_ids": ["v1"], "assay_group": "solid", "subpanel": "A", "tier": 3},
        user=fx.api_user(),
    )

    assert payload["status"] == "ok"
    assert captured["docs"] is not None
    assert len(captured["docs"]) == 2
    assert any(doc.get("class") == 3 for doc in captured["docs"])
    assert any(doc.get("text") == "AUTO_TEXT" for doc in captured["docs"])


def test_set_variant_tier_bulk_remove_deletes_class_and_matching_text(monkeypatch):
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
        "INFO": {"selected_CSQ": {"Feature": "NM_0000.1", "SYMBOL": "BRAF", "HGVSp": "p.V600E", "Consequence": []}},
    }

    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: sample)
    monkeypatch.setattr(dna.store.variant_handler, "get_variant", lambda variant_id: variant)
    monkeypatch.setattr(dna.store.oncokb_handler, "get_oncokb_gene", lambda gene: None)
    monkeypatch.setattr(dna, "create_annotation_text_from_gene", lambda *args, **kwargs: "AUTO_TEXT")
    monkeypatch.setattr(
        dna.store.annotation_handler,
        "delete_classified_variant",
        lambda **kwargs: captured.append(kwargs),
    )
    monkeypatch.setattr(
        dna.store.annotation_handler,
        "insert_annotation_bulk",
        lambda docs: pytest.fail("insert_annotation_bulk must not be called on tier remove"),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    payload = dna.set_variant_tier_bulk(
        "S1",
        payload={"apply": False, "variant_ids": ["v1"], "assay_group": "solid", "subpanel": "A", "tier": 3},
        user=fx.api_user(),
    )

    assert payload["status"] == "ok"
    assert len(captured) == 1
    assert captured[0]["class_num"] == 3
    assert captured[0]["annotation_text"] == "AUTO_TEXT"


def test_bulk_flag_routes_use_non_colliding_paths():
    paths = {route.path for route in api_app.routes}
    assert "/api/v1/dna/samples/{sample_id}/variants/fp/bulk" in paths
    assert "/api/v1/dna/samples/{sample_id}/variants/irrelevant/bulk" in paths
    assert "/api/v1/dna/samples/{sample_id}/variants/bulk/fp" not in paths
    assert "/api/v1/dna/samples/{sample_id}/variants/bulk/irrelevant" not in paths


def _route_test_user() -> ApiUser:
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
    captured: dict = {"ids": None}
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _route_test_user())
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9, "manager": 99, "admin": 999})
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        dna.store.variant_handler,
        "mark_false_positive_var_bulk",
        lambda ids: captured.__setitem__("ids", ids),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    client = TestClient(api_app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/dna/samples/S1/variants/fp/bulk",
        json={"apply": True, "variant_ids": ["V1", "V2"]},
    )

    assert response.status_code == 200
    assert captured["ids"] == ["V1", "V2"]

    old_path_response = client.post(
        "/api/v1/dna/samples/S1/variants/bulk/fp",
        json={"apply": True, "variant_ids": ["V1", "V2"]},
    )
    assert old_path_response.status_code >= 400


def test_bulk_irrelevant_endpoint_dispatches_in_real_http_route(monkeypatch):
    captured: dict = {"ids": None}
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _route_test_user())
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9, "manager": 99, "admin": 999})
    monkeypatch.setattr(dna, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(
        dna.store.variant_handler,
        "mark_irrelevant_var_bulk",
        lambda ids: captured.__setitem__("ids", ids),
    )
    monkeypatch.setattr(dna.util.common, "convert_to_serializable", lambda payload: payload)

    client = TestClient(api_app, raise_server_exceptions=False)
    response = client.post(
        "/api/v1/dna/samples/S1/variants/irrelevant/bulk",
        json={"apply": True, "variant_ids": ["V5"]},
    )

    assert response.status_code == 200
    assert captured["ids"] == ["V5"]
