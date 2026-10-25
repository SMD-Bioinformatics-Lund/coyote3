"""Transport, permission and selection contracts for the sample tiered-variant read."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.app.deps.application import get_application
from api.app.deps.services import get_dna_service
from api.interfaces.http.v1.clinical.dna import small_variants
from coyote3.application.interpretation.annotation_enrichment import add_global_annotations
from coyote3.application.operations import ApplicationRuntime, ClinicalServices
from coyote3.application.operations.samples import Samples


@pytest.fixture
def tiered_route(monkeypatch):
    app = FastAPI()
    app.include_router(small_variants.router)
    sample = {"_id": "demo", "name": "DEMO_001"}
    sample_lookup = Mock(return_value=sample)
    selected = [{"_id": f"demo-{i}", "classification": {"class": 2}} for i in range(75)]
    service = SimpleNamespace(
        list_variants_payload=Mock(return_value={"meta": {"tiered": selected}})
    )
    app.dependency_overrides[get_dna_service] = lambda: service
    actor = SimpleNamespace(username="synthetic", is_superuser=True)
    runtime = ApplicationRuntime(
        authenticate=lambda: actor,
        policy_factory=Mock(),
        sample_loader=sample_lookup,
        assay_loader=Mock(),
        audit_access=Mock(),
    )
    services = ClinicalServices(
        dna=lambda: service,
        structural=Mock(),
        rna=Mock(),
        classification=Mock(),
        classification_document=Mock(),
        annotations=Mock(),
        public_annotations=Mock(),
        catalog=Mock(),
        fields=Mock(),
        common_queries=Mock(),
        coverage=Mock(),
        biomarkers=Mock(),
        artifacts=Mock(),
    )
    app.dependency_overrides[get_application] = lambda: SimpleNamespace(
        samples=Samples(runtime, services)
    )
    route = next(
        route
        for route in small_variants.router.routes
        if route.endpoint.__name__ == "list_tiered_dna_variants"
    )
    permission = next(dep.call for dep in route.dependant.dependencies if dep.name == "user")
    app.dependency_overrides[permission] = lambda: SimpleNamespace(username="synthetic")
    with TestClient(app) as client:
        yield client, app, permission, service, sample_lookup, selected


def test_tiered_route_uses_complete_existing_selection(tiered_route):
    client, _, _, service, sample_lookup, selected = tiered_route
    response = client.get("/api/v1/samples/demo/small-variants/tiered?intent=germline&q=gene")
    assert response.status_code == 200
    assert response.json() == selected
    sample_lookup.assert_called_once()
    kwargs = service.list_variants_payload.call_args.kwargs
    assert kwargs["paginate"] is False
    assert kwargs["sample"] == sample_lookup.return_value
    assert kwargs["query"].parameters["intent"] == "germline"
    assert kwargs["query"].parameters["q"] == "gene"


@pytest.mark.parametrize("status", [401, 403])
def test_tiered_route_permission_denial(tiered_route, status):
    client, app, permission, service, sample_lookup, _ = tiered_route

    def deny():
        raise HTTPException(status_code=status)

    app.dependency_overrides[permission] = deny
    assert client.get("/api/v1/samples/demo/small-variants/tiered").status_code == status
    sample_lookup.assert_not_called()
    service.list_variants_payload.assert_not_called()


@pytest.mark.parametrize("status", [403, 404])
def test_tiered_route_sample_scope_and_existence(tiered_route, status):
    client, _, _, service, sample_lookup, _ = tiered_route
    sample_lookup.side_effect = HTTPException(status_code=status)
    assert client.get("/api/v1/samples/demo/small-variants/tiered").status_code == status
    service.list_variants_payload.assert_not_called()


def test_tiered_route_propagates_unavailable_intent(tiered_route):
    client, _, _, service, _, _ = tiered_route
    service.list_variants_payload.side_effect = HTTPException(status_code=422)
    response = client.get("/api/v1/samples/demo/small-variants/tiered?intent=unavailable")
    assert response.status_code == 422


@pytest.mark.parametrize(
    "classification,flags,selected",
    [
        ({"class": 1}, {}, True),
        ({"class": 2}, {}, True),
        ({"class": 3}, {}, True),
        ({"class": 4}, {}, True),
        ({"class": 999}, {}, False),
        ({"class": None}, {}, False),
        (None, {}, False),
        ({"class": 2}, {"fp": True}, False),
        ({"class": 2}, {"irrelevant": True}, False),
        ({"class": 2}, {"blacklist": True}, False),
        ({"class": 2}, {"blacklist": True, "override_blacklist": True}, False),
    ],
)
def test_existing_tiered_selection_rules_are_preserved(classification, flags, selected):
    repository = SimpleNamespace(
        get_global_annotations=Mock(return_value=([], classification, [], {})),
        get_additional_classifications=Mock(return_value=[]),
    )
    variant = {"_id": "demo-variant", **flags}
    context = {"assay_id": "demo-assay", "namespace": "clinical"}
    _, tiered = add_global_annotations(
        [variant],
        "demo-group",
        "demo-diagnosis",
        annotation_repository=repository,
        sample_context=context,
    )
    assert bool(tiered) is selected
    repository.get_global_annotations.assert_called_once_with(
        variant, "demo-group", "demo-diagnosis", sample_context=context
    )
