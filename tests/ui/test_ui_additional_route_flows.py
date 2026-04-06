"""Additional Flask route-flow tests using fixture-shaped API payloads."""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import coyote
from coyote import init_app
from coyote.services.api_client.api_client import CoyoteApiClient
from coyote.services.api_client.base import ApiPayload
from tests.fixtures.api import mock_collections as fx


def _payload(value: dict) -> ApiPayload:
    """Wrap a dictionary in the API payload helper."""
    return ApiPayload(value)


def _load_web_module(module_name: str):
    """Import a web module under an app context when it binds current_app at import time."""
    app = init_app(testing=True)
    with app.app_context():
        module = importlib.import_module(module_name)
    return module


def _fixture_shaped_get(path: str) -> ApiPayload:
    """Return realistic API payloads for Flask-side route smoke tests."""
    sample = fx.sample_doc()
    assay_config = fx.assay_config_doc()
    variant = fx.variant_doc()
    fusion = fx.fusion_doc()
    cnv = fx.cnv_doc()
    genelist = fx.isgl_doc()
    user = fx.user_doc()
    translocation = {
        "_id": "tl1",
        "SAMPLE_ID": "s1",
        "gene1": "BCR",
        "gene2": "ABL1",
        "interesting": True,
    }

    if path.endswith("/internal/roles/levels"):
        return _payload({"role_levels": {"admin": 99999}})

    if path.endswith("/dashboard/summary"):
        return _payload(
            {
                "total_samples": 1,
                "analysed_samples": 1,
                "pending_samples": 0,
                "user_samples_stats": {"tester": 1},
                "variant_stats": {"snv": 1},
                "unique_gene_count_all_panels": 2,
                "assay_gene_stats_grouped": {"dna": {"WGS": 2}},
                "sample_stats": {"production": 1},
            }
        )

    if path.endswith("/api/v1/samples"):
        return _payload(
            {
                "live_samples": [sample],
                "done_samples": [],
                "sample_view": "all",
                "profile_scope": "production",
                "page": 1,
                "per_page": 30,
                "live_page": 1,
                "live_per_page": 30,
                "done_page": 1,
                "done_per_page": 30,
                "has_next_live": False,
                "has_next_done": False,
            }
        )

    if path.endswith("/api/v1/samples/s1/edit-context"):
        return _payload(
            {
                "sample": sample,
                "asp": assay_config,
                "assay_groups": ["dna", "rna"],
                "panel_types": ["dna"],
                "panel_techs": ["wgs"],
                "profile_choices": ["production"],
                "variant_stats_raw": {"snv": 1, "cnv": 1},
                "variant_stats_filtered": {"snv": 1, "cnv": 1},
            }
        )

    if path.endswith("/api/v1/samples/s1/genelists"):
        return _payload({"items": [genelist]})

    if path.endswith("/api/v1/samples/s1/effective-genes"):
        return _payload({"items": ["TP53", "NPM1"], "asp_covered_genes_count": 2})

    if path.endswith("/api/v1/samples/s1/small-variants"):
        return _payload(
            {
                "sample": sample,
                "filters": sample["filters"],
                "assay_config": assay_config,
                "sample_ids": {"case": "s1", "control": "ctrl1"},
                "assay_group": "dna",
                "analysis_sections": ["SNV", "CNV", "BIOMARKER"],
                "display_sections_data": {
                    "snvs": [variant],
                    "cnvs": [cnv],
                    "biomarkers": [{"_id": "bio1", "name": "TMB", "value": "High"}],
                },
                "ai_text": "Summary",
                "assay_panels": [genelist],
                "all_panel_genelist_names": ["gl1"],
                "checked_genelists": ["gl1"],
                "checked_genelists_dict": {"gl1": ["TP53", "NPM1"]},
                "verification_sample_used": None,
                "hidden_comments": False,
                "vep_var_class_translations": {},
                "vep_conseq_translations": {},
                "bam_id": [],
                "oncokb_genes": ["TP53"],
            }
        )

    if path.endswith("/api/v1/samples/s1/small-variants/v1"):
        return _payload(
            {
                "variant": variant,
                "in_other": [],
                "annotations": [],
                "hidden_comments": False,
                "latest_classification": {"class": 2},
                "expression": {},
                "civic": {},
                "civic_gene": {},
                "oncokb": {},
                "oncokb_action": {},
                "oncokb_gene": {},
                "sample": sample,
                "brca_exchange": {},
                "iarc_tp53": {},
                "assay_group": "dna",
                "pon": "",
                "other_classifications": [],
                "subpanel": sample.get("subpanel"),
                "sample_ids": {"case": "s1", "control": "ctrl1"},
                "bam_id": [],
                "annotations_interesting": [],
                "vep_var_class_translations": {},
                "vep_conseq_translations": {},
                "assay_group_mappings": {},
            }
        )

    if path.endswith("/api/v1/samples/s1/cnvs/cnv1"):
        return _payload(
            {
                "cnv": cnv,
                "sample": sample,
                "assay_group": "dna",
                "annotations": [],
                "sample_ids": {"case": "s1", "control": "ctrl1"},
                "bam_id": [],
                "hidden_comments": False,
            }
        )

    if path.endswith("/api/v1/samples/s1/translocations/tl1"):
        return _payload(
            {
                "translocation": translocation,
                "sample": sample,
                "assay_group": "dna",
                "annotations": [],
                "bam_id": [],
                "vep_conseq_translations": {},
                "hidden_comments": False,
            }
        )

    if path.endswith("/api/v1/samples/s1/small-variants/exports/snvs/context"):
        return _payload({"content": "gene\nTP53\n", "filename": "SAMPLE_001.filtered.snvs.csv"})

    if path.endswith("/api/v1/samples/s1/small-variants/exports/cnvs/context"):
        return _payload({"content": "gene\nERBB2\n", "filename": "SAMPLE_001.filtered.cnvs.csv"})

    if path.endswith("/api/v1/samples/s1/small-variants/exports/translocs/context"):
        return _payload(
            {"content": "gene\nBCR-ABL1\n", "filename": "SAMPLE_001.filtered.translocs.csv"}
        )

    if path.endswith("/api/v1/samples/s1/fusions"):
        return _payload(
            {
                "sample": sample,
                "assay_config": {"asp_group": "rna"},
                "assay_group": "rna",
                "subpanel": sample.get("subpanel"),
                "fusionlist_options": [genelist],
                "filters": {"fusionlist_id": ["gl1"]},
                "filter_context": {
                    "fusion_callers": ["arriba"],
                    "fusion_effect_form_keys": ["in-frame"],
                    "checked_fusionlists": ["gl1"],
                },
                "checked_fusionlists": ["gl1"],
                "checked_fusionlists_dict": {"gl1": ["EML4", "ALK"]},
                "hidden_comments": False,
                "fusions": [fusion],
                "ai_text": "RNA summary",
            }
        )

    if path.endswith("/api/v1/samples/s1/fusions/fus1"):
        return _payload(
            {
                "fusion": fusion,
                "in_other": [],
                "sample": sample,
                "annotations": [],
                "latest_classification": {"class": 2},
                "annotations_interesting": [],
                "other_classifications": [],
                "hidden_comments": False,
                "assay_group": "rna",
                "subpanel": sample.get("subpanel"),
                "assay_group_mappings": {},
            }
        )

    if path.endswith("/api/v1/coverage/samples/s1"):
        return _payload(
            {
                "coverage": [{"gene": "TP53", "mean_depth": 650}],
                "cov_cutoff": 500,
                "sample": sample,
                "genelists": [genelist],
                "smp_grp": "dna",
                "cov_table": [{"gene": "TP53", "depth": 650, "status": "ok"}],
            }
        )

    if path.endswith("/api/v1/coverage/blacklisted/dna"):
        return _payload(
            {
                "blacklisted": [
                    {
                        "_id": "blk1",
                        "gene": "TP53",
                        "group": "dna",
                        "reason": "test",
                    }
                ],
                "group": "dna",
            }
        )

    if path.endswith("/api/v1/public/asp/asp1/genes"):
        return _payload(
            {
                "asp_id": "asp1",
                "gene_details": [{"symbol": "TP53", "gene": "TP53"}],
                "germline_gene_symbols": ["BRCA1"],
            }
        )

    if path.endswith("/api/v1/public/assay-catalog-matrix/context"):
        return _payload(
            {
                "matrix_rows": [{"gene": "TP53", "hits": 1}],
                "modalities": ["dna"],
                "categories": ["wgs"],
                "meta": {"count": 1},
            }
        )

    if path.endswith("/api/v1/public/assay-catalog/context"):
        return _payload(
            {
                "meta": {"count": 1},
                "order": ["dna"],
                "modalities": {"dna": {"label": "DNA"}},
                "selected_mod": "dna",
                "categories": ["wgs"],
                "selected_cat": "wgs",
                "selected_isgl": None,
                "right": {"title": "DNA"},
                "gene_mode": "all",
                "genes": ["TP53", "NPM1"],
                "stats": {"genes": 2},
            }
        )

    if path.endswith("/api/v1/public/assay-catalog/genes.csv/context"):
        return _payload({"content": "gene\nTP53\n", "filename": "catalog_genes.csv"})

    if path.endswith("/api/v1/public/assay-catalog/genes/gl1/view_context"):
        return _payload({"gene_symbols": ["TP53", "NPM1"]})

    if path.endswith("/api/v1/public/genelists/gl1/view_context"):
        return _payload(
            {
                "genelist": genelist,
                "selected_assay": None,
                "filtered_genes": ["TP53", "NPM1"],
                "germline_genes": [],
                "is_public": True,
            }
        )

    if path.endswith("/api/v1/common/gene/TP53/info"):
        return _payload({"gene": {"symbol": "TP53", "summary": "Tumor suppressor"}})

    if path.endswith("/api/v1/common/reported_variants/variant/v1/2"):
        return _payload(
            {
                "docs": [{"sample_id": "s1", "tier": 2}],
                "variant": variant,
                "tier": 2,
            }
        )

    if path.endswith("/api/v1/common/search/tiered_variants"):
        return _payload(
            {
                "docs": [{"sample_id": "s1", "tier": 2, "variant": variant["simple_id"]}],
                "search_str": "TP53",
                "search_mode": "gene",
                "include_annotation_text": False,
                "tier_stats": {"total": {"tier2": 1}, "by_assay": {"WGS": {"tier2": 1}}},
                "assays": ["WGS"],
                "assay_choices": [("WGS", "WGS")],
            }
        )

    if path.endswith("/api/v1/auth/session"):
        return _payload({"user": user})

    return _payload({})


def test_additional_ui_routes_smoke_with_fixture_shaped_api(monkeypatch):
    """Smoke-test web routes that were previously under-covered."""

    def _fake_get(self, path, headers=None, params=None):  # noqa: ARG001
        return _fixture_shaped_get(path)

    def _fake_post(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        if path.endswith("/auth/password/reset/request"):
            return _payload({"status": "queued"})
        if path.endswith("/auth/password/reset/confirm"):
            return _payload({"status": "ok"})
        if path.endswith("/auth/sessions"):
            return _payload({"user": fx.user_doc()})
        if path.endswith("/coverage/blacklist/entries"):
            return _payload({"message": "updated"})
        return _payload({"status": "ok"})

    def _fake_put(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return _payload({"status": "ok", "filters": (json_body or {}).get("filters", {})})

    def _fake_delete(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return _payload({"status": "ok"})

    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    monkeypatch.setattr(CoyoteApiClient, "get_json", _fake_get)
    monkeypatch.setattr(CoyoteApiClient, "post_json", _fake_post)
    monkeypatch.setattr(CoyoteApiClient, "put_json", _fake_put)
    monkeypatch.setattr(CoyoteApiClient, "delete_json", _fake_delete)
    monkeypatch.setattr(CoyoteApiClient, "last_response_cookie", lambda self, name: "api-token")
    app = init_app(testing=True)
    app.config.update(WTF_CSRF_ENABLED=False)
    with app.app_context():
        coverage_views = importlib.import_module("coyote.blueprints.coverage.views")
        dna_views = importlib.import_module("coyote.blueprints.dna.views_dna_findings")
        login_views = importlib.import_module("coyote.blueprints.login.views")
        public_catalog_views = importlib.import_module("coyote.blueprints.public.views_catalog")
        public_genelist_views = importlib.import_module("coyote.blueprints.public.views_genelists")
        public_misc_views = importlib.import_module("coyote.blueprints.public.views_misc")
        rna_views = importlib.import_module("coyote.blueprints.rna.views_fusions")
    for module in (
        coverage_views,
        dna_views,
        login_views,
        public_catalog_views,
        public_genelist_views,
        public_misc_views,
        rna_views,
    ):
        monkeypatch.setattr(
            module,
            "render_template",
            lambda template, **ctx: f"rendered:{template}",
        )
    client = app.test_client()

    responses = {
        "/login": client.get("/login"),
        "/forgot-password": client.get("/forgot-password"),
        "/reset-password?token=test-token": client.get("/reset-password?token=test-token"),
        "/public/contact": client.get("/public/contact"),
        "/public/asp/genes/asp1": client.get("/public/asp/genes/asp1"),
        "/public/assay-catalog": client.get("/public/assay-catalog"),
        "/public/assay-catalog-matrix": client.get("/public/assay-catalog-matrix"),
        "/public/genelists/gl1/view": client.get("/public/genelists/gl1/view"),
        "/public/assay-catalog/genes/gl1/view": client.get("/public/assay-catalog/genes/gl1/view"),
        "/cov/s1": client.get("/cov/s1"),
        "/cov/blacklisted/dna": client.get("/cov/blacklisted/dna"),
        "/dna/sample/s1": client.get("/dna/sample/s1"),
        "/dna/sample/s1/exports/snvs.csv": client.get("/dna/sample/s1/exports/snvs.csv"),
        "/dna/sample/s1/exports/cnvs.csv": client.get("/dna/sample/s1/exports/cnvs.csv"),
        "/dna/sample/s1/exports/translocs.csv": client.get("/dna/sample/s1/exports/translocs.csv"),
        "/dna/s1/var/v1": client.get("/dna/s1/var/v1"),
        "/rna/sample/s1": client.get("/rna/sample/s1"),
        "/rna/s1/fusion/fus1": client.get("/rna/s1/fusion/fus1"),
    }

    failures = {
        path: response.status_code
        for path, response in responses.items()
        if response.status_code >= 500
    }
    assert not failures, failures
    assert (
        responses["/dna/sample/s1/exports/snvs.csv"].headers["Content-Type"].startswith("text/csv")
    )
    assert responses["/dna/s1/var/v1"].status_code == 200
    assert responses["/rna/s1/fusion/fus1"].status_code == 200

    forgot = client.post("/forgot-password", data={"username": "tester@example.com"})
    reset = client.post(
        "/reset-password?token=test-token",
        data={
            "token": "test-token",
            "new_password": "Coyote3.Admin",
            "confirm_password": "Coyote3.Admin",
        },
    )
    login = client.post(
        "/login",
        data={"username": "tester@example.com", "password": "Coyote3.Admin"},
        follow_redirects=False,
    )
    coverage_update = client.post("/update-gene-status", json={"gene": "TP53", "group": "dna"})

    assert forgot.status_code == 302
    assert reset.status_code == 302
    assert login.status_code == 302
    assert "coyote3_api_session=api-token" in login.headers.get("Set-Cookie", "")
    assert coverage_update.status_code == 200


def test_additional_ui_route_groups_with_fixture_shaped_api(monkeypatch, tmp_path):
    """Smoke-test home, common, docs, dashboard, and DNA detail routes."""

    def _fake_get(self, path, headers=None, params=None):  # noqa: ARG001
        return _fixture_shaped_get(path)

    def _fake_post(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return _payload({"status": "ok"})

    def _fake_put(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return _payload({"status": "ok", "filters": (json_body or {}).get("filters", {})})

    def _fake_delete(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
        return _payload({"status": "ok"})

    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    monkeypatch.setattr(CoyoteApiClient, "get_json", _fake_get)
    monkeypatch.setattr(CoyoteApiClient, "post_json", _fake_post)
    monkeypatch.setattr(CoyoteApiClient, "put_json", _fake_put)
    monkeypatch.setattr(CoyoteApiClient, "delete_json", _fake_delete)

    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("# Changelog\n\n- ok\n", encoding="utf-8")
    license_file = tmp_path / "LICENSE.txt"
    license_file.write_text("MIT\n", encoding="utf-8")
    report = tmp_path / "report.pdf"
    report.write_text("ok", encoding="utf-8")

    app = init_app(testing=True)
    app.config.update(
        WTF_CSRF_ENABLED=False,
        CHANGELOG_FILE=str(changelog),
        LICENSE_FILE=str(license_file),
    )
    with app.app_context():
        common_views = importlib.import_module("coyote.blueprints.common.views")
        dashboard_views = importlib.import_module("coyote.blueprints.dashboard.views")
        dna_cnv_views = importlib.import_module("coyote.blueprints.dna.views_cnv")
        dna_transloc_views = importlib.import_module("coyote.blueprints.dna.views_transloc")
        docs_meta_views = importlib.import_module("coyote.blueprints.docs.views_meta")
        home_reports_views = importlib.import_module("coyote.blueprints.home.views_reports")
        home_samples_views = importlib.import_module("coyote.blueprints.home.views_samples")
    for module in (
        common_views,
        dashboard_views,
        dna_cnv_views,
        dna_transloc_views,
        docs_meta_views,
        home_samples_views,
    ):
        monkeypatch.setattr(
            module,
            "render_template",
            lambda template, **ctx: f"rendered:{template}",
        )
    monkeypatch.setattr(home_reports_views, "fetch_report_path", lambda _s, _r: report)

    client = app.test_client()

    responses = {
        "/dashboard/": client.get("/dashboard/"),
        "/samples": client.get("/samples"),
        "/samples/edit/s1": client.get("/samples/edit/s1"),
        "/samples/s1/isgls": client.get("/samples/s1/isgls"),
        "/samples/s1/effective-genes/all": client.get("/samples/s1/effective-genes/all"),
        "/samples/s1/reports/r1": client.get("/samples/s1/reports/r1"),
        "/samples/s1/reports/r1/download": client.get("/samples/s1/reports/r1/download"),
        "/gene/TP53/info": client.get("/gene/TP53/info"),
        "/reported_variants/variant/v1/2": client.get("/reported_variants/variant/v1/2"),
        "/search/tiered_variants?search_str=TP53": client.get(
            "/search/tiered_variants?search_str=TP53"
        ),
        "/handbook/about": client.get("/handbook/about"),
        "/handbook/changelog": client.get("/handbook/changelog"),
        "/handbook/license": client.get("/handbook/license"),
        "/dna/s1/cnv/cnv1": client.get("/dna/s1/cnv/cnv1"),
        "/dna/s1/transloc/tl1": client.get("/dna/s1/transloc/tl1"),
    }

    failures = {
        path: response.status_code
        for path, response in responses.items()
        if response.status_code >= 500
    }
    assert not failures, failures
    assert responses["/samples/s1/isgls"].get_json()["items"][0]["_id"] == "gl1"
    assert responses["/samples/s1/effective-genes/all"].get_json()["asp_covered_genes_count"] == 2
    assert responses["/samples/s1/reports/r1"].status_code == 200
    assert responses["/samples/s1/reports/r1/download"].status_code == 200


def test_profile_password_route_flows(monkeypatch):
    """Exercise profile password route success and provider-managed branches."""
    from flask import Flask

    app = Flask(__name__)
    app.config.update(SECRET_KEY="test")
    with app.app_context():
        profile_views = importlib.import_module("coyote.blueprints.userprofile.views")

    flashes: list[str] = []

    class _Client:
        def post_json(self, path, headers=None, params=None, json_body=None):  # noqa: ARG002
            assert path.endswith("/api/v1/auth/password/change")
            assert json_body == {
                "current_password": "old",
                "new_password": "new-pass",
            }
            return _payload({"status": "ok"})

    monkeypatch.setattr(profile_views, "get_web_api_client", lambda: _Client())
    monkeypatch.setattr(profile_views, "forward_headers", lambda: {"Accept": "application/json"})
    monkeypatch.setattr(
        profile_views, "redirect", lambda location: SimpleNamespace(location=location)
    )
    monkeypatch.setattr(profile_views, "url_for", lambda endpoint, **values: f"{endpoint}:{values}")
    monkeypatch.setattr(profile_views, "flash_api_success", lambda message: flashes.append(message))
    monkeypatch.setattr(
        profile_views,
        "flash_api_failure",
        lambda message, exc: flashes.append(f"{message}:{exc}"),
    )
    monkeypatch.setattr(
        profile_views,
        "render_template",
        lambda template, **ctx: {"template": template, **ctx},
    )

    with app.test_request_context(
        "/profile/tester/password",
        method="POST",
        data={
            "current_password": "old",
            "new_password": "new-pass",
            "confirm_password": "new-pass",
        },
    ):
        monkeypatch.setattr(
            profile_views,
            "current_user",
            SimpleNamespace(username="tester", auth_type="coyote3"),
        )
        response = profile_views.change_password.__wrapped__("tester")

    assert response.location.startswith("profile_bp.user_profile")
    assert flashes[-1] == "Password updated successfully."

    with app.test_request_context("/profile/tester/password", method="GET"):
        monkeypatch.setattr(
            profile_views,
            "current_user",
            SimpleNamespace(username="tester", auth_type="ldap"),
        )
        response = profile_views.change_password.__wrapped__("tester")

    assert response.location.startswith("profile_bp.user_profile")
