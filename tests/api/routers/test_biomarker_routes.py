"""HTTP biomarker review delegates to the authorized SDK and validates user input."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app.deps.application import get_sample
from api.app.main import app_error_handler
from api.interfaces.http.v1.clinical.dna import biomarkers
from coyote3.domain.exceptions import AppError
from tests.unit import test_application_sdk, test_biomarker_assessments

sdk = test_application_sdk.sdk
review = test_biomarker_assessments.review


@pytest.fixture
def boundary(sdk, review):
    sdk.sample["_id"] = "sample"
    sdk.services.biomarkers = lambda: review.service
    sdk.runtime.edit_guard = Mock(return_value=None)
    app = FastAPI()
    app.add_exception_handler(AppError, app_error_handler)
    app.include_router(biomarkers.router)
    app.dependency_overrides[get_sample] = lambda: sdk.samples.ref("demo")
    for route in biomarkers.router.routes:
        for dependency in route.dependant.dependencies:
            if dependency.name == "user":
                app.dependency_overrides[dependency.call] = lambda: sdk.actor
    with TestClient(app) as client:
        yield SimpleNamespace(client=client, sdk=sdk, review=review)


def test_read_and_patch_preserve_measurement_and_enforce_revision(boundary):
    client = boundary.client
    read = client.get("/api/v1/samples/demo/biomarkers")
    assert read.status_code == 200
    record = read.json()["biomarkers"][0]
    assert record["TMB"]["value"] == 0
    path = f"/api/v1/samples/demo/biomarkers/{record['_id']}/assessments/TMB"
    body = {"value": "HIGH", "expected_revision": 0}
    changed = client.patch(path, json=body)
    assert changed.status_code == 200
    result = changed.json()["biomarkers"][0]["TMB"]
    assert result["value"] == 0
    assert result["clinical_assessment"]["value"] == "HIGH"
    assert result["clinical_assessment"]["assessed_by"] == boundary.sdk.actor.username
    assert client.patch(path, json=body).status_code == 409
    assert client.patch(path, json={**body, "assessed_by": "forged"}).status_code == 422
    boundary.sdk.grants.remove("sample:edit:own")
    assert client.patch(path, json={"value": "LOW", "expected_revision": 1}).status_code == 403


def test_read_denied_and_unknown_measurement_never_mutate(boundary):
    boundary.sdk.grants.remove("sample:view")
    assert boundary.client.get("/api/v1/samples/demo/biomarkers").status_code == 403
    before = boundary.review.collection.find_one()
    path = f"/api/v1/samples/demo/biomarkers/{boundary.review.identifier}/assessments/unknown"
    response = boundary.client.patch(path, json={"value": "LOW", "expected_revision": 0})
    assert response.status_code == 404
    assert boundary.review.collection.find_one() == before
