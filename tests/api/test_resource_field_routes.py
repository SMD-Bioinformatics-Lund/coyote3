"""HTTP contracts for single-key resource metadata reads."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.app.deps.application import get_reference_data, get_sample
from api.interfaces.http.v1.admin.resources import asp, aspc, genelists
from api.interfaces.http.v1.clinical import samples
from coyote3.application.operations.administration import ReferenceData
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api.mock_collections import api_user


@pytest.mark.parametrize(
    "module,path,method,field,value",
    [
        (samples, "/api/v1/samples/demo", "sample_field", "name", "DEMO_001"),
        (samples, "/api/v1/samples/demo", "sample_field", "reported", False),
        (samples, "/api/v1/samples/demo", "sample_field", "time_added", None),
        (asp, "/api/v1/resources/asp/demo", "assay_field", "supported_analyses", ["SNV", "CNV"]),
        (asp, "/api/v1/resources/assay-groups/demo", "group_field", "version", 2),
        (asp, "/api/v1/resources/diagnoses/demo", "diagnosis_field", "display_name", "MPN"),
        (
            aspc,
            "/api/v1/resources/aspc/demo::mpn::testing",
            "configuration_field",
            "environment",
            "testing",
        ),
        (genelists, "/api/v1/resources/genelists/demo", "gene_list_field", "gene_count", 10),
    ],
)
def test_individual_field_http_contract(monkeypatch, module, path, method, field, value):
    """One key returns its JSON type, rejects unknown keys, and requires permission."""
    app = FastAPI()
    app.include_router(module.router)
    reader = Mock(return_value=value)
    app.dependency_overrides[get_reference_data] = lambda: sdk_fixtures.authorized_operations(
        ReferenceData, SimpleNamespace(**{method: reader}), api_user()
    )
    app.dependency_overrides[get_sample] = lambda: sdk_fixtures.sample_operations(
        SimpleNamespace(**{method: reader}), api_user(), "demo"
    )
    if module is samples:
        monkeypatch.setattr(sdk_fixtures, "load_sample", lambda *args: {"name": "DEMO_001"})
    route = next(
        route
        for route in module.router.routes
        if route.endpoint.__name__
        == {
            "sample_field": "sample_field_read",
            "assay_field": "assay_field_read",
            "group_field": "assay_group_field_read",
            "diagnosis_field": "diagnosis_field_read",
            "configuration_field": "aspc_field_read",
            "gene_list_field": "genelist_field_read",
        }[method]
    )
    permission_check = next(dep.call for dep in route.dependant.dependencies if dep.name == "user")
    app.dependency_overrides[permission_check] = lambda: SimpleNamespace(username="integration")
    with TestClient(app) as client:
        response = client.get(f"{path}/fields/{field}")
        assert response.status_code == 200
        assert response.json() == value
        assert type(response.json()) is type(value)
        reader.assert_called_once()
        reader.reset_mock()
        for forbidden in ("filters", "files", "credentials", "unknown"):
            assert client.get(f"{path}/fields/{forbidden}").status_code == 422
        reader.assert_not_called()

        def denied():
            """Reject a caller lacking the endpoint's view permission."""
            raise HTTPException(status_code=403)

        app.dependency_overrides[permission_check] = denied
        assert client.get(f"{path}/fields/{field}").status_code == 403
        reader.assert_not_called()
