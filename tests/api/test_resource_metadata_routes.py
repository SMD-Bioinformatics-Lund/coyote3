"""Permission, scope and response contracts for batched permitted metadata."""

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
    "module,path,handler,method,metadata",
    [
        (
            samples,
            "samples/demo",
            "sample_metadata_read",
            "sample_metadata",
            {"name": "DEMO_001", "reported": False},
        ),
        (
            asp,
            "resources/asp/demo",
            "assay_metadata_read",
            "assay_metadata",
            {"asp_id": "demo", "supported_analyses": ["SNV"]},
        ),
        (
            asp,
            "resources/assay-groups/demo",
            "assay_group_metadata_read",
            "group_metadata",
            {"group_id": "demo", "is_active": True},
        ),
        (
            asp,
            "resources/diagnoses/demo",
            "diagnosis_metadata_read",
            "diagnosis_metadata",
            {"diagnosis_id": "demo", "asp_ids": []},
        ),
        (
            aspc,
            "resources/aspc/demo",
            "aspc_metadata_read",
            "configuration_metadata",
            {"aspc_id": "demo", "report_sections": ["SNV"]},
        ),
        (
            genelists,
            "resources/genelists/demo",
            "genelist_metadata_read",
            "gene_list_metadata",
            {"isgl_id": "demo", "gene_count": 0},
        ),
    ],
)
def test_metadata_contract_permissions_and_scope(
    monkeypatch, module, path, handler, method, metadata
):
    app = FastAPI()
    app.include_router(module.router)
    reader = Mock(return_value=metadata)
    app.dependency_overrides[get_reference_data] = lambda: sdk_fixtures.authorized_operations(
        ReferenceData, SimpleNamespace(**{method: reader}), api_user()
    )
    scope_check = Mock(return_value={"name": "DEMO_001"})
    app.dependency_overrides[get_sample] = lambda: sdk_fixtures.sample_operations(
        SimpleNamespace(**{method: reader}), api_user(), "demo"
    )
    if module is samples:
        monkeypatch.setattr(sdk_fixtures, "load_sample", scope_check)
    route = next(route for route in module.router.routes if route.endpoint.__name__ == handler)
    permission = next(dep.call for dep in route.dependant.dependencies if dep.name == "user")
    app.dependency_overrides[permission] = lambda: SimpleNamespace(username="synthetic")
    with TestClient(app) as client:
        response = client.get(f"/api/v1/{path}/metadata")
        assert response.status_code == 200
        body = response.json()
        assert all(body[key] == value for key, value in metadata.items())
        assert "files" not in body
        assert "filters" not in body
        assert "genes" not in body
        reader.assert_called_once()
        reader.reset_mock()
        if module is samples:
            scope_check.assert_called_once()
            for status in (403, 404):
                scope_check.side_effect = HTTPException(status_code=status)
                assert client.get(f"/api/v1/{path}/metadata").status_code == status
            reader.assert_not_called()

        for status in (401, 403):

            def deny(status=status):
                raise HTTPException(status_code=status)

            app.dependency_overrides[permission] = deny
            assert client.get(f"/api/v1/{path}/metadata").status_code == status
        reader.assert_not_called()
