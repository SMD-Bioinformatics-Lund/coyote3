"""Catalog HTTP serialization, request validation, and audit metadata."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from bson import ObjectId
from pydantic import ValidationError
from starlette.requests import Request

from api.contracts.public import PublicAssayCatalogUpdateRequest
from api.contracts.schemas.public_catalog import PublicAssayCatalogDoc, PublicAssayCatalogVersionDoc
from api.interfaces.http.admin import public_assay_catalog as routes
from tests.fixtures.api import mock_collections as fx


def document():
    now = datetime.now(timezone.utc)
    return PublicAssayCatalogVersionDoc(
        _id=ObjectId(),
        revision=1,
        status="draft",
        catalog=PublicAssayCatalogDoc(),
        created_at=now,
        updated_at=now,
        created_by="test.author",
        updated_by="test.author",
    ).model_dump(by_alias=True)


def test_mutation_sets_traceability_metadata_without_copying_content():
    doc = document()
    service = SimpleNamespace(create=lambda **kw: doc)
    request = Request({"type": "http", "method": "POST", "path": "/drafts", "headers": []})
    result = routes.create(request=request, user=fx.api_user(), service=service)
    assert result["_id"] == str(doc["_id"])
    assert request.state.audit_resource["retention_class"] == "traceability"
    assert request.state.audit_resource["metadata"]["revision"] == 1
    assert "catalog" not in request.state.audit_resource["metadata"]


def test_version_contract_and_expected_revision_validation():
    doc = document()
    response = routes.version(
        str(doc["_id"]), user=fx.api_user(), service=SimpleNamespace(document=lambda oid: doc)
    )
    payload = PublicAssayCatalogVersionDoc.model_validate(response).model_dump(
        mode="json", by_alias=True
    )
    assert payload["_id"] == str(doc["_id"])
    assert payload["status"] == "draft"
    with pytest.raises(ValidationError):
        PublicAssayCatalogUpdateRequest.model_validate({"catalog": {}})
