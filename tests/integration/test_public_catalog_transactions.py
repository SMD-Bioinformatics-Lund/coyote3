"""Opt-in catalog transaction tests against a disposable replica-set database."""

import os
from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pymongo import MongoClient

from api.contracts.schemas.public_catalog import PublicAssayCatalogDoc, PublicAssayCatalogVersionDoc
from api.infra.mongo.repositories.public_assay_catalog import PublicAssayCatalogRepository
from api.infra.mongo.repositories.public_assay_catalog_versions import (
    PublicAssayCatalogRevisionRepository,
    PublicAssayCatalogVersionRepository,
)


@pytest.fixture
def repository():
    uri = os.getenv("CATALOG_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set CATALOG_TEST_MONGO_URI to run disposable replica-set tests")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    name = f"coyote3_catalog_test_{uuid4().hex}"
    db = client[name]
    adapter = SimpleNamespace(
        client=client,
        public_assay_catalog_collection=db.public_assay_catalog,
        public_assay_catalog_versions_collection=db.public_assay_catalog_versions,
        public_assay_catalog_revisions_collection=db.public_assay_catalog_revisions,
    )
    repository = PublicAssayCatalogVersionRepository(adapter)
    try:
        PublicAssayCatalogRepository(adapter).ensure_indexes()
        PublicAssayCatalogRevisionRepository(adapter).ensure_indexes()
        repository.ensure_indexes()
        yield repository
    finally:
        client.drop_database(name)
        client.close()


def approved(repository, base=0):
    now = datetime.now(timezone.utc)
    return repository.insert(
        PublicAssayCatalogVersionDoc(
            revision=1,
            status="approved",
            base_version=base,
            created_at=now,
            updated_at=now,
            created_by="test.author",
            updated_by="test.reviewer",
            catalog=PublicAssayCatalogDoc(header="Synthetic catalog"),
        ).model_dump(by_alias=True)
    )


def publish(repository, doc):
    candidate = deepcopy(doc)
    candidate.update(
        status="published",
        revision=doc["revision"] + 1,
        published_by="test.publisher",
        published_at=datetime.now(timezone.utc),
    )
    return repository.replace(doc, candidate, publish=True)


def test_publication_and_revision_are_committed_together(repository):
    doc = approved(repository)
    result = publish(repository, doc)
    assert result["content_version"] == 1
    assert repository.adapter.public_assay_catalog_collection.find_one({})["version"] == 1
    assert len(repository.revisions(str(doc["_id"]))) == 2
    assert publish(repository, doc) is None


def test_failed_snapshot_rolls_back_publication(repository, monkeypatch):
    doc = approved(repository)

    def fail(*args):
        raise RuntimeError("Synthetic storage failure")

    monkeypatch.setattr(repository, "_snapshot", fail)
    with pytest.raises(RuntimeError, match="Synthetic storage failure"):
        publish(repository, doc)
    assert repository.get(str(doc["_id"]))["status"] == "approved"
    assert repository.adapter.public_assay_catalog_collection.count_documents({}) == 0


def test_baseline_keeps_original_provenance_and_stale_draft_is_rejected(repository):
    baseline = PublicAssayCatalogDoc(created_by="original.owner", updated_by="original.owner")
    repository.adapter.public_assay_catalog_collection.insert_one(
        baseline.model_dump(by_alias=True)
    )
    doc = approved(repository, base=1)
    stale = approved(repository, base=1)
    assert publish(repository, doc)["content_version"] == 2
    preserved = repository.get_collection().find_one({"content_version": 1})
    assert preserved["created_by"] == "original.owner"
    assert preserved["review"]["reviewer"] is None
    assert preserved["published_by"] is None
    assert preserved["lifecycle"][0]["action"] == "baseline_archived"
    assert publish(repository, stale) is None
    assert repository.adapter.public_assay_catalog_collection.find_one({})["version"] == 2
