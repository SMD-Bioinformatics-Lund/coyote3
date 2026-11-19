"""Public VEP reference isolation and diagram validation."""

import copy
import gzip
import json
from types import SimpleNamespace

import mongomock
import pytest
from api_test_support import application_sdk as sdk_fixtures
from coyote.application.public.catalog import PublicCatalogService
from coyote.contracts.public import PublicVepReferencePayload
from coyote.domain.exceptions import AppError
from coyote_api.app.deps import services
from coyote_api.interfaces.http.v1.public import routes
from coyote_atlas.bundle import ReferenceBundle
from coyote_mongo.repositories.vep_metadata import VEPMetaRepository
from mongo_test_support.writes import repository_writes  # noqa: F401

from tests.fixtures.mongo_settings import mongo_runtime

SEED = ReferenceBundle.packaged().directory / "vep_metadata.seed.ndjson.gz"

pytestmark = pytest.mark.usefixtures("repository_writes")


def test_public_reference_projects_only_reference_fields(monkeypatch):
    collection = mongomock.MongoClient().kb.vep_metadata
    with gzip.open(SEED, "rt") as stream:
        document = next(json.loads(line) for line in stream if json.loads(line)["vep_id"] == "103")
    collection.insert_one({**document, "private_field": "never expose"})
    repository = object.__new__(VEPMetaRepository)
    repository.get_collection = lambda: collection
    service = object.__new__(PublicCatalogService)
    service.vep_metadata_repository = repository
    monkeypatch.setattr(services, "get_public_catalog_service", lambda: service)
    assert routes.public_vep_versions_read(service=sdk_fixtures.public_operations()) == {
        "versions": ["103"]
    }
    payload = routes.public_vep_reference_read("103", service=sdk_fixtures.public_operations())
    PublicVepReferencePayload.model_validate(payload)
    assert not {"_id", "created_by", "created_on", "private_field"} & payload.keys()
    assert payload["consequence_diagram"]["release"] == "103"
    with pytest.raises(AppError) as error:
        routes.public_vep_reference_read("999", service=sdk_fixtures.public_operations())
    assert error.value.status_code == 404


def test_numeric_public_order():
    service = object.__new__(PublicCatalogService)
    service.vep_metadata_repository = SimpleNamespace(list_versions=lambda: ["98", "116", "103"])
    assert service.vep_reference_versions()["versions"] == ["116", "103", "98"]


def test_binary_endpoint_is_release_scoped_and_metadata_has_no_image_bytes(monkeypatch):
    database = mongomock.MongoClient().kb
    with gzip.open(SEED, "rt") as stream:
        rows = list(map(json.loads, stream))
    database.vep_metadata.insert_many(copy.deepcopy(rows))
    assets = ReferenceBundle.packaged().load_diagrams()
    database.vep_diagrams.insert_many(assets)
    assert len(assets) < len(rows)
    repository = object.__new__(VEPMetaRepository)
    repository.get_collection = lambda: database.vep_metadata
    repository.adapter = SimpleNamespace(
        app=mongo_runtime(), vep_diagrams_collection=database.vep_diagrams
    )
    service = object.__new__(PublicCatalogService)
    service.vep_metadata_repository = repository
    monkeypatch.setattr(services, "get_public_catalog_service", lambda: service)
    import hashlib

    for row in rows:
        response = routes.public_vep_diagram_read(
            row["vep_id"], service=sdk_fixtures.public_operations()
        )
        assert hashlib.sha256(response.body).hexdigest() == row["consequence_diagram"]["sha256"]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "data_base64" not in json.dumps(repository.get_public_reference(row["vep_id"]))
    with pytest.raises(AppError):
        routes.public_vep_diagram_read("999", service=sdk_fixtures.public_operations())
