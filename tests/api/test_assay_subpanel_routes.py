"""Typed subpanel endpoints delegate writes and populate traceability metadata."""

from types import SimpleNamespace

from starlette.requests import Request

from api.contracts.schemas.subpanels import SubpanelCreate, SubpanelUpdate
from api.interfaces.http.admin.resources.asp import create_subpanel, update_subpanel


def test_mutation_routes_attach_scoped_audit_identity():
    calls = []

    def save(assay, payload, **kwargs):
        calls.append((assay, payload, kwargs))
        return {"resource_id": "panel-a/myeloid", "meta": {"revision": {"new_version": 2}}}

    service = SimpleNamespace(save=save)
    user = SimpleNamespace(username="reviewer")
    for operation, payload, extra in [
        (create_subpanel, SubpanelCreate(subpanel_id="myeloid", display_name="Myeloid"), {}),
        (
            update_subpanel,
            SubpanelUpdate(display_name="Myeloid", expected_version=1),
            {"subpanel_id": "myeloid"},
        ),
    ]:
        request = Request({"type": "http"})
        operation(
            request=request,
            assay_panel_id="panel-a",
            payload=payload,
            user=user,
            service=service,
            **extra,
        )
        assert request.state.audit_resource["id"] == "panel-a/myeloid"
        assert request.state.audit_resource["retention_class"] == "traceability"
        assert request.state.audit_resource["metadata"]["new_version"] == 2
    assert all(call[2]["actor"] == "reviewer" for call in calls)
