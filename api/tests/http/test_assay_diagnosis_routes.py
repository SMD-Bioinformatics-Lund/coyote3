"""Typed diagnosis endpoints delegate writes and populate traceability metadata."""

from types import SimpleNamespace

from api_test_support import application_sdk as sdk_fixtures
from api_test_support import mock_collections as fx
from coyote.application.operations import administration as sdk_administration
from coyote.contracts.schemas.diagnoses import DiagnosisCreate, DiagnosisUpdate
from coyote_api.interfaces.http.v1.admin.resources.asp import create_diagnosis, update_diagnosis
from starlette.requests import Request


def test_mutation_routes_attach_scoped_audit_identity():
    calls = []

    def save(assay, payload, **kwargs):
        calls.append((assay, payload, kwargs))
        return {"resource_id": "panel-a/myeloid", "meta": {"revision": {"new_version": 2}}}

    service = SimpleNamespace(save=save)
    user = fx.api_user()
    user.username = "reviewer"
    for operation, payload, extra in [
        (create_diagnosis, DiagnosisCreate(diagnosis_id="myeloid", display_name="Myeloid"), {}),
        (
            update_diagnosis,
            DiagnosisUpdate(display_name="Myeloid", expected_version=1),
            {"diagnosis_id": "myeloid"},
        ),
    ]:
        request = Request({"type": "http"})
        operation(
            request=request,
            assay_panel_id="panel-a",
            payload=payload,
            user=user,
            service=sdk_fixtures.authorized_operations(sdk_administration.Diagnoses, service, user),
            **extra,
        )
        assert request.state.audit_resource["id"] == "panel-a/myeloid"
        assert request.state.audit_resource["retention_class"] == "traceability"
        assert request.state.audit_resource["metadata"]["new_version"] == 2
    assert all(call[2]["actor"] == "reviewer" for call in calls)
