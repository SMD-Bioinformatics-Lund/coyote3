"""Report HTTP/SDK parity, authorization, snapshots and preview concurrency."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.application import get_application
from api.app.main import app_error_handler
from api.interfaces.http.v1.clinical.reporting import reports
from coyote3.application.common.release_resources import capture_assay_resource
from coyote3.application.operations import ApplicationRuntime, ReportingServices
from coyote3.application.operations.reporting import Reports
from coyote3.domain.exceptions import AppError
from tests.fixtures.api.mock_collections import api_user


@pytest.fixture
def boundary():
    actor = api_user()
    actor.roles = ["synthetic-reviewer"]
    actor.must_change_password = False
    actor.asp_groups = []
    grants = {"report:preview", "report:create", "report:view"}
    policy = SimpleNamespace(
        permission_allowed=lambda user, permission, **kwargs: permission in grants,
        scope_allowed=lambda *args: True,
    )
    sample = {
        "_id": "synthetic-sample",
        "name": "SYNTHETIC_001",
        "asp_id": "synthetic",
        "asp_category": "dna",
        "environment": "testing",
    }
    panel = {"asp_id": "synthetic", "asp_group": "synthetic-group"}
    config = {**panel, "assay_resource_release": capture_assay_resource(panel)}
    context = {"sample": deepcopy(sample), "assay_config": config}
    rows = [{"resource_id": "synthetic-finding", "analysis": "snv"}]
    workflow = Mock()
    workflow.build_report_payload.side_effect = lambda **kwargs: (
        "dna_report.html" if kwargs["sample"]["asp_category"] == "dna" else "report_fusion.html",
        deepcopy(context),
        deepcopy(rows),
    )
    workflow.next_report_num.return_value = 3
    workflow.build_report_location.return_value = ("synthetic-report", "reports", "synthetic.html")
    workflow.persist_report.return_value = ("synthetic-report-storage", "synthetic.pdf")
    library = Mock()
    library.list_payload.return_value = {
        "reports": [],
        "total": 0,
        "page": 1,
        "per_page": 30,
        "has_next": False,
    }
    authenticate = Mock(return_value=actor)
    sample_loader = Mock(return_value=sample)
    render = Mock(return_value="<p>Synthetic report</p>")
    pdf = Mock(return_value=b"synthetic-pdf")
    runtime = ApplicationRuntime(
        authenticate=authenticate,
        policy_factory=lambda user: policy,
        sample_loader=sample_loader,
        assay_loader=Mock(),
        audit_access=Mock(),
    )
    sdk = Reports(
        runtime,
        ReportingServices(
            workflow=lambda analyte: workflow,
            configuration=lambda sample: config,
            render_html=render,
            organization_name="Synthetic",
            reports_base_path="reports",
            logger=Mock(),
            library=lambda: library,
            render_pdf=pdf,
            render_trial_html=lambda **inputs: f"<article>{render(**inputs)}</article>",
        ),
    )
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(reports.router)
    app.dependency_overrides[get_application] = lambda: SimpleNamespace(reports=sdk)
    for route in reports.router.routes:
        for dependency in route.dependant.dependencies:
            if dependency.name == "user":
                app.dependency_overrides[dependency.call] = lambda: actor
    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            sdk=sdk,
            actor=actor,
            grants=grants,
            sample=sample,
            context=context,
            workflow=workflow,
            library=library,
            authenticate=authenticate,
            sample_loader=sample_loader,
            render=render,
            pdf=pdf,
            config=config,
        )


@pytest.mark.parametrize("include", [True, False])
def test_http_preview_uses_sdk_results_and_retains_snapshot_contract(boundary, include):
    direct = boundary.sdk.preview(
        "synthetic-sample", "dna", include_snapshot=include, layout="modern"
    )
    response = boundary.client.get(
        "/api/v1/samples/synthetic-sample/reports/dna/preview",
        params={"include_snapshot": str(include).lower()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["html"] == direct.html
    assert payload["meta"]["preview_fingerprint"] == direct.fingerprint
    assert payload["meta"]["snapshot_count"] == direct.snapshot_count == 1
    assert payload["report"]["snapshot_rows"] == direct.snapshot_rows
    assert bool(direct.snapshot_rows) is include


def test_save_presentation_preview_does_not_persist(boundary):
    response = boundary.client.get("/api/v1/samples/synthetic-sample/reports/dna/preview?save=true")
    assert response.status_code == 200
    assert boundary.workflow.build_report_payload.call_args.kwargs["save"] == 1
    assert boundary.render.call_args.kwargs["preview"] is False
    boundary.workflow.persist_report.assert_not_called()


def test_trial_returns_matching_temporary_outputs_and_never_allocates_a_report(boundary):
    from base64 import b64decode

    response = boundary.client.get("/api/v1/samples/synthetic-sample/reports/dna/try-new")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert "without an automatically generated summary" in result["reporting_warning"]
    assert result["html"] == "<article><p>Synthetic report</p></article>"
    assert b64decode(result["pdf_base64"]) == b"synthetic-pdf"
    boundary.pdf.assert_called_once_with(result["html"])
    boundary.workflow.next_report_num.assert_not_called()
    boundary.workflow.build_report_location.assert_not_called()
    boundary.workflow.prepare_report_output.assert_not_called()
    boundary.workflow.persist_report.assert_not_called()
    boundary.grants.remove("report:preview")
    denied = boundary.client.get("/api/v1/samples/synthetic-sample/reports/dna/try-new")
    assert denied.status_code == 403
    assert boundary.pdf.call_count == 1


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_saved_report_preserves_author_snapshot_and_resolution_receipt(boundary, analyte):
    boundary.sample["asp_category"] = analyte
    preview = boundary.sdk.preview("synthetic-sample", analyte, layout="modern")
    response = boundary.client.post(
        f"/api/v1/samples/synthetic-sample/reports/{analyte}",
        json={"preview_fingerprint": preview.fingerprint},
    )
    assert response.status_code == 201
    assert response.json()["report"]["oid"] == "synthetic-report-storage"
    values = boundary.workflow.persist_report.call_args.kwargs
    assert values["created_by"] == boundary.actor.username
    assert values["snapshot_rows"][0]["resource_id"] == "synthetic-finding"
    assert values["resolution_snapshot"]["configuration"] == boundary.config
    leaf = "dna_report.html" if analyte == "dna" else "report_fusion.html"
    assert values["resolution_snapshot"]["rendering"]["template"] == f"modern/{leaf}"
    assert values["resolution_snapshot"]["rendering"]["configured_template"] == leaf
    assert response.json()["report"]["snapshot_count"] == 1


def test_stale_preview_fails_before_any_artifact_or_number_allocation(boundary):
    preview = boundary.sdk.preview("synthetic-sample", "dna", layout="modern")
    boundary.context["sample"]["version"] = 2
    response = boundary.client.post(
        "/api/v1/samples/synthetic-sample/reports/dna",
        json={"preview_fingerprint": preview.fingerprint},
    )
    assert response.status_code == 409
    boundary.workflow.next_report_num.assert_not_called()
    boundary.workflow.prepare_report_output.assert_not_called()
    boundary.workflow.persist_report.assert_not_called()


def test_report_format_is_fingerprinted_and_saved_as_rendering_provenance(boundary):
    modern = boundary.sdk.preview("synthetic-sample", "dna", layout="modern")
    legacy = boundary.client.get(
        "/api/v1/samples/synthetic-sample/reports/dna/preview?format=legacy"
    ).json()
    fingerprint = legacy["meta"]["preview_fingerprint"]
    assert fingerprint != modern.fingerprint
    mismatch = boundary.client.post(
        "/api/v1/samples/synthetic-sample/reports/dna",
        json={"preview_fingerprint": fingerprint, "report_format": "modern"},
    )
    assert mismatch.status_code == 409
    boundary.workflow.next_report_num.assert_not_called()
    saved = boundary.client.post(
        "/api/v1/samples/synthetic-sample/reports/dna",
        json={"preview_fingerprint": fingerprint, "report_format": "legacy"},
    )
    assert saved.status_code == 201
    receipt = boundary.workflow.persist_report.call_args.kwargs["resolution_snapshot"]
    assert receipt["rendering"]["template"] == "dna_report.html"
    assert receipt["rendering"]["configured_template"] == "dna_report.html"
    assert receipt["rendering"]["content_hash"]


def test_invalid_report_format_is_rejected_before_rendering(boundary):
    response = boundary.client.get(
        "/api/v1/samples/synthetic-sample/reports/dna/preview?format=unknown"
    )
    assert response.status_code == 422
    boundary.render.assert_not_called()


def test_changed_presentation_source_invalidates_a_reviewed_preview(boundary, monkeypatch):
    preview = boundary.sdk.preview("synthetic-sample", "dna", layout="modern")
    monkeypatch.setattr(
        "coyote3.application.reporting.report_service.template_content_hash",
        lambda template: "changed-synthetic-presentation",
    )
    response = boundary.client.post(
        "/api/v1/samples/synthetic-sample/reports/dna",
        json={"preview_fingerprint": preview.fingerprint},
    )
    assert response.status_code == 409
    boundary.workflow.next_report_num.assert_not_called()
    boundary.workflow.persist_report.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 404, 422])
def test_denials_stop_report_generation(boundary, status):
    if status == 401:
        boundary.authenticate.return_value = None
    elif status == 403:
        boundary.grants.clear()
    elif status == 404:
        boundary.sample_loader.return_value = None
    else:
        boundary.sample["asp_category"] = "rna"
    response = boundary.client.get("/api/v1/samples/synthetic-sample/reports/dna/preview")
    assert response.status_code == status
    boundary.workflow.build_report_payload.assert_not_called()
    boundary.render.assert_not_called()


def test_report_contract_errors_are_safe_validation_responses(boundary):
    boundary.workflow.build_report_payload.side_effect = ValueError("Synthetic invalid rule source")
    response = boundary.client.get("/api/v1/samples/synthetic-sample/reports/dna/preview")
    assert response.status_code == 422
    assert response.json()["error"] == "DNA report data does not satisfy the reporting contract"


def test_library_uses_the_sdk_scope_and_does_not_generate_reports(boundary):
    response = boundary.client.get("/api/v1/reports?q=ignored&search=GENE&page=2&per_page=15")
    assert response.status_code == 200
    boundary.library.list_payload.assert_called_once()
    values = boundary.library.list_payload.call_args.kwargs
    assert values["user"] is boundary.actor
    assert values["search"] == "GENE" and values["page"] == 2 and values["per_page"] == 15
    boundary.workflow.build_report_payload.assert_not_called()


def test_pdf_is_an_http_attachment_of_the_authorized_sdk_artifact(boundary):
    response = boundary.client.get("/api/v1/samples/synthetic-sample/reports/dna/preview/pdf")
    assert response.status_code == 200
    assert response.content == b"synthetic-pdf"
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["cache-control"] == "no-store"
    assert "SYNTHETIC_001_dna_preview.pdf" in response.headers["content-disposition"]
    boundary.pdf.assert_called_once_with("<p>Synthetic report</p>")
    boundary.workflow.persist_report.assert_not_called()
