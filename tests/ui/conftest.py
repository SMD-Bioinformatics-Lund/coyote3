"""Shared UI role fixtures and API stubs for Flask route tests."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest

import coyote
from coyote import init_app
from coyote.services.api_client.api_client import CoyoteApiClient
from coyote.services.api_client.base import ApiPayload
from tests.fixtures.api import mock_collections as fx

_SESSION_USER_PAYLOAD_KEY = "auth_user_payload"


def _payload(value: dict[str, Any]) -> ApiPayload:
    """Wrap a dictionary in the API payload helper."""
    return ApiPayload(value)


def _role_user_payload(role: str) -> dict[str, Any]:
    """Build a realistic Flask-session user payload for a named UI role."""
    base = deepcopy(fx.user_doc())
    common = {
        "permissions": [],
        "denied_permissions": [],
        "deny_permissions": [],
        "assay_groups": ["dna", "rna"],
        "assays": ["WGS", "RNA_PANEL"],
        "auth_type": "coyote3",
        "must_change_password": False,
    }

    match role:
        case "viewer":
            common.update(
                {
                    "_id": "viewer-1",
                    "user_id": "viewer-1",
                    "username": "viewer",
                    "email": "viewer@example.com",
                    "fullname": "Viewer User",
                    "role": "viewer",
                    "access_level": 1,
                }
            )
        case "user":
            common.update(
                {
                    "_id": "user-1",
                    "user_id": "user-1",
                    "username": "user",
                    "email": "user@example.com",
                    "fullname": "Standard User",
                    "role": "user",
                    "access_level": 9,
                    "permissions": ["preview_report"],
                }
            )
        case "manager":
            common.update(
                {
                    "_id": "manager-1",
                    "user_id": "manager-1",
                    "username": "manager",
                    "email": "manager@example.com",
                    "fullname": "Manager User",
                    "role": "manager",
                    "access_level": 99,
                    "permissions": [
                        "preview_report",
                        "edit_sample",
                        "manage_snvs",
                        "manage_cnvs",
                        "assign_tier",
                    ],
                }
            )
        case "admin":
            common.update(
                {
                    "_id": "admin-1",
                    "user_id": "admin-1",
                    "username": "admin",
                    "email": "admin@example.com",
                    "fullname": "Admin User",
                    "role": "admin",
                    "access_level": 99999,
                    "permissions": [
                        "preview_report",
                        "create_report",
                        "edit_sample",
                        "view_sample_global",
                        "view_users",
                        "view_role",
                        "view_permission_policy",
                        "view_audit_logs",
                    ],
                }
            )
        case _:
            raise ValueError(f"Unsupported UI test role: {role}")

    base.update(common)
    return base


def _fixture_shaped_get(path: str, *, current_user: dict[str, Any] | None) -> ApiPayload:
    """Return realistic API payloads for UI route tests."""
    sample = fx.sample_doc()
    sample["_id"] = "s1"
    sample["name"] = "SAMPLE_001"
    assay_config = fx.assay_config_doc()
    variant = fx.variant_doc()
    variant["_id"] = "v1"
    variant["SAMPLE_ID"] = "s1"
    cnv = fx.cnv_doc()
    cnv["_id"] = "cnv1"
    cnv["SAMPLE_ID"] = "s1"
    genelist = fx.isgl_doc()
    user = deepcopy(current_user) if current_user else _role_user_payload("admin")
    translocation = {
        "_id": "tl1",
        "SAMPLE_ID": "s1",
        "gene1": "BCR",
        "gene2": "ABL1",
        "interesting": True,
    }

    if path.endswith("/internal/roles/levels"):
        return _payload(
            {
                "role_levels": {
                    "viewer": 1,
                    "user": 9,
                    "manager": 99,
                    "developer": 9999,
                    "admin": 99999,
                }
            }
        )

    if path.endswith("/auth/session"):
        return _payload({"user": user})

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

    if path.endswith("/api/v1/coverage/samples/s1"):
        sample["omics_layer"] = "dna"
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

    if path.endswith("/api/v1/resources/samples"):
        return _payload(
            {
                "samples": [sample],
                "pagination": {"page": 1, "per_page": 30, "total": 1, "has_next": False},
            }
        )

    if path.endswith("/api/v1/internal/ingest/collections"):
        return _payload({"collections": ["users", "roles", "permissions", "asp_configs"]})

    if path.endswith("/api/v1/samples/SAMPLE_001/reports/dna/preview"):
        return _payload(
            {
                "report": {
                    "template": "docs/about.html",
                    "context": {"meta": {"app_name": "Coyote3"}},
                    "snapshot_rows": [],
                }
            }
        )

    return _payload({})


@pytest.fixture
def ui_client_factory(monkeypatch) -> Callable[[str | None], Any]:
    """Build a Flask UI test client for a specific authenticated role."""

    def build(role: str | None = None):
        current_user = _role_user_payload(role) if role else None

        def fake_get(self, path, headers=None, params=None):  # noqa: ARG001
            return _fixture_shaped_get(path, current_user=current_user)

        def fake_post(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
            if path.endswith("/auth/sessions"):
                return _payload({"user": current_user or _role_user_payload("admin")})
            if path.endswith("/samples/SAMPLE_001/reports"):
                return _payload({"report": {"id": "RID1", "file": "RID1.html"}})
            return _payload({"status": "ok"})

        def fake_put(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
            return _payload({"status": "ok", "filters": (json_body or {}).get("filters", {})})

        def fake_delete(self, path, headers=None, params=None, json_body=None):  # noqa: ARG001
            return _payload({"status": "ok"})

        monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
        monkeypatch.setattr(CoyoteApiClient, "get_json", fake_get)
        monkeypatch.setattr(CoyoteApiClient, "post_json", fake_post)
        monkeypatch.setattr(CoyoteApiClient, "put_json", fake_put)
        monkeypatch.setattr(CoyoteApiClient, "delete_json", fake_delete)
        monkeypatch.setattr(CoyoteApiClient, "last_response_cookie", lambda self, name: "api-token")  # noqa: ARG005

        app = init_app(testing=True)
        app.config.update(WTF_CSRF_ENABLED=False, LOGIN_DISABLED=False)

        with app.app_context():
            from coyote.blueprints.admin import views_ingest as admin_ingest_views
            from coyote.blueprints.coverage import views as coverage_views
            from coyote.blueprints.dashboard import views as dashboard_views
            from coyote.blueprints.dna import views_cnv, views_dna_findings, views_reports
            from coyote.blueprints.home import views_samples
            from coyote.services.api_client import reports as report_client

        for module in (
            admin_ingest_views,
            coverage_views,
            dashboard_views,
            views_cnv,
            views_dna_findings,
            views_samples,
        ):
            monkeypatch.setattr(
                module, "render_template", lambda template, **ctx: f"rendered:{template}"
            )  # noqa: ARG005

        monkeypatch.setattr(
            views_reports, "render_preview_html", lambda payload: "<div>preview</div>"
        )  # noqa: ARG005
        monkeypatch.setattr(
            report_client, "render_preview_html", lambda payload: "<div>preview</div>"
        )  # noqa: ARG005

        client = app.test_client()

        if current_user is not None:
            client.set_cookie(key=app.config["API_SESSION_COOKIE_NAME"], value="ui-test-token")
            with client.session_transaction() as session:
                session["_user_id"] = str(current_user["_id"])
                session["_fresh"] = True
                session[_SESSION_USER_PAYLOAD_KEY] = current_user

        return client

    return build


@pytest.fixture
def anonymous_client(ui_client_factory):
    """Return an anonymous Flask UI test client."""
    return ui_client_factory(None)


@pytest.fixture
def viewer_client(ui_client_factory):
    """Return an authenticated viewer test client."""
    return ui_client_factory("viewer")


@pytest.fixture
def user_client(ui_client_factory):
    """Return an authenticated user test client."""
    return ui_client_factory("user")


@pytest.fixture
def manager_client(ui_client_factory):
    """Return an authenticated manager test client."""
    return ui_client_factory("manager")


@pytest.fixture
def admin_client(ui_client_factory):
    """Return an authenticated admin test client."""
    return ui_client_factory("admin")
