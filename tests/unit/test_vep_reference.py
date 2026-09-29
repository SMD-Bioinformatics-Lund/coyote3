"""Public VEP reference isolation and diagram validation."""

import base64
import copy
import gzip
import io
import json
from types import SimpleNamespace

import mongomock
import pytest
from PIL import Image

from api.application.public.catalog import PublicCatalogService
from api.contracts.public import PublicVepReferencePayload
from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories.vep_metadata import VEPMetaRepository
from api.interfaces.http.public import routes
from scripts import update_vep_diagrams
from scripts.update_vep_metadata import SEED, diagram_document
from scripts.vep_diagram_storage import load_seed_diagrams


def test_public_reference_projects_only_reference_fields(monkeypatch):
    collection = mongomock.MongoClient().kb.vep_metadata
    with gzip.open(SEED, "rt") as stream:
        document = next(json.loads(line) for line in stream if json.loads(line)["vep_id"] == "103")
    collection.insert_one({**document, "private_field": "never expose"})
    repository = object.__new__(VEPMetaRepository)
    repository.get_collection = lambda: collection
    service = object.__new__(PublicCatalogService)
    service.vep_metadata_repository = repository
    monkeypatch.setattr(routes, "get_public_catalog_service", lambda: service)
    assert routes.public_vep_versions_read() == {"versions": ["103"]}
    payload = routes.public_vep_reference_read("103")
    PublicVepReferencePayload.model_validate(payload)
    assert not {"_id", "created_by", "created_on", "private_field"} & payload.keys()
    assert payload["consequence_diagram"]["release"] == "103"
    with pytest.raises(AppError) as error:
        routes.public_vep_reference_read("999")
    assert error.value.status_code == 404


def test_numeric_public_order():
    service = object.__new__(PublicCatalogService)
    service.vep_metadata_repository = SimpleNamespace(list_versions=lambda: ["98", "116", "103"])
    assert service.vep_reference_versions()["versions"] == ["116", "103", "98"]


def test_png_diagram_preserves_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (12, 8)).save(buffer, format="PNG")
    result = diagram_document(buffer.getvalue(), "https://example.org/image.png", 103)
    assert result["width"] == 12 and result["height"] == 8
    assert base64.b64decode(result["data_base64"]) == buffer.getvalue()


@pytest.mark.parametrize(
    "content",
    [
        b'<svg viewBox="0 0 10 10"><script>alert(1)</script></svg>',
        b'<svg viewBox="0 0 10 10" onload="alert(1)"/>',
        b'<svg viewBox="0 0 10 10"><image href="https://example.org/image"/></svg>',
        b'<svg viewBox="0 0 10 10"><rect style="fill:url(https://example.org)"/></svg>',
        b'<!DOCTYPE svg><svg viewBox="0 0 10 10"/>',
    ],
)
def test_unsafe_svg_rejected(content):
    with pytest.raises(ValueError):
        diagram_document(content, "https://example.org/image.svg", 116)


def test_diagram_install_does_not_change_103_definitions(tmp_path, monkeypatch):
    collection = mongomock.MongoClient().kb.vep_metadata
    original = {"vep_id": "103", "consequence_groups": {"test": ["term"]}, "created_by": "original"}
    collection.insert_one(original)
    original = copy.deepcopy(collection.find_one())
    diagram = diagram_document(
        b'<svg viewBox="0 0 20 10"><rect width="20" height="10"/></svg>',
        "https://example.org/image.svg",
        103,
    )
    monkeypatch.setattr(
        update_vep_diagrams, "run_transaction", lambda client, callback: callback(None)
    )
    update_vep_diagrams.install(collection, {"103": diagram}, tmp_path / "backup.bson")
    actual = collection.find_one()
    descriptor = actual.pop("consequence_diagram")
    assert "data_base64" not in descriptor
    assert descriptor == {key: value for key, value in diagram.items() if key != "data_base64"}
    asset = collection.database.vep_diagrams.find_one({"_id": descriptor["sha256"]})
    assert isinstance(asset["data"], bytes)
    assert asset["data"] == base64.b64decode(diagram["data_base64"])
    assert actual == original


def test_all_seed_diagrams_match_their_releases_and_hashes():
    import hashlib

    with gzip.open(SEED, "rt") as stream:
        for row in map(json.loads, stream):
            diagram = row["consequence_diagram"]
            assert diagram["release"] == row["vep_id"]
            assert (
                hashlib.sha256(
                    (SEED.parent / "vep_diagrams" / diagram["sha256"]).read_bytes()
                ).hexdigest()
                == diagram["sha256"]
            )
            assert "data_base64" not in diagram


def test_binary_endpoint_is_release_scoped_and_metadata_has_no_image_bytes(monkeypatch):
    database = mongomock.MongoClient().kb
    with gzip.open(SEED, "rt") as stream:
        rows = list(map(json.loads, stream))
    database.vep_metadata.insert_many(copy.deepcopy(rows))
    assets = load_seed_diagrams(rows, SEED.parent)
    database.vep_diagrams.insert_many(assets)
    assert len(assets) < len(rows)
    repository = object.__new__(VEPMetaRepository)
    repository.get_collection = lambda: database.vep_metadata
    repository.adapter = SimpleNamespace(vep_diagrams_collection=database.vep_diagrams)
    service = object.__new__(PublicCatalogService)
    service.vep_metadata_repository = repository
    monkeypatch.setattr(routes, "get_public_catalog_service", lambda: service)
    import hashlib

    for row in rows:
        response = routes.public_vep_diagram_read(row["vep_id"])
        assert hashlib.sha256(response.body).hexdigest() == row["consequence_diagram"]["sha256"]
        assert response.headers["x-content-type-options"] == "nosniff"
        assert "data_base64" not in json.dumps(repository.get_public_reference(row["vep_id"]))
    with pytest.raises(AppError):
        routes.public_vep_diagram_read("999")
