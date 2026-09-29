"""Opt-in atomic activation checks using a disposable Mongo replica-set database."""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pymongo import MongoClient

from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories.assay_setup import (
    AssaySetupRepository,
    AssaySetupRevisionRepository,
)


@pytest.fixture
def repository():
    """Create and remove only a uniquely named synthetic test database."""
    uri = os.getenv("ASSAY_SETUP_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set ASSAY_SETUP_TEST_MONGO_URI for disposable replica-set tests")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    db = client[f"coyote3_setup_test_{uuid4().hex}"]
    adapter = SimpleNamespace(
        client=client,
        assay_groups_collection=db.groups,
        assay_setups_collection=db.setups,
        assay_setup_revisions_collection=db.revisions,
        asp_collection=db.asp,
        aspc_collection=db.aspc,
        insilico_genelist_collection=db.isgl,
        subpanels_collection=db.subpanels,
        subpanel_associations_collection=db.associations,
        clinical_rule_sets_collection=db.rules,
    )
    try:
        repo = AssaySetupRepository(adapter)
        repo.ensure_indexes()
        AssaySetupRevisionRepository(adapter).ensure_indexes()
        db.groups.insert_one({"group_id": "demo", "is_active": True, "version": 1})
        yield repo
    finally:
        client.drop_database(db.name)
        client.close()


def test_duplicate_resource_rolls_back_all_operational_writes(repository):
    """A late conflict must not leave an active ASP or advance the submitted draft."""
    draft = repository.save(
        {"asp_id": "synthetic", "revision": 1, "status": "submitted"}, action="test"
    )
    repository.adapter.aspc_collection.insert_one({"aspc_id": "conflict"})
    bundle = {
        "panel": {"asp_id": "synthetic", "asp_group": "demo"},
        "configurations": [{"aspc_id": "conflict"}],
        "gene_lists": [],
        "associations": [],
        "rules": [],
        "definitions": [],
        "existing_lists": [],
    }
    with pytest.raises(AppError, match="already exists"):
        repository.save(
            {**draft, "revision": 2, "status": "published"},
            previous=draft,
            action="publish",
            bundle=bundle,
        )
    assert repository.adapter.asp_collection.count_documents({}) == 0
    assert repository.get(str(draft["_id"]))["status"] == "submitted"
    assert len(repository.revisions(str(draft["_id"]))) == 1
    assert repository.adapter.assay_groups_collection.find_one().get("publication_serial", 0) == 0


def test_publication_commits_all_documents_and_revision(repository):
    """A successful activation commits its draft state and all related records."""
    draft = repository.save(
        {"asp_id": "synthetic", "revision": 1, "status": "submitted"}, action="test"
    )
    bundle = {
        "panel": {"asp_id": "synthetic", "asp_group": "demo"},
        "configurations": [{"aspc_id": "synthetic_base_development"}],
        "gene_lists": [{"isgl_id": "synthetic-list"}],
        "associations": [],
        "rules": [],
        "definitions": [],
        "existing_lists": [],
    }
    repository.save(
        {**draft, "revision": 2, "status": "published"},
        previous=draft,
        action="publish",
        bundle=bundle,
    )
    assert repository.adapter.asp_collection.count_documents({}) == 1
    assert repository.adapter.aspc_collection.count_documents({}) == 1
    assert repository.adapter.insilico_genelist_collection.count_documents({}) == 1
    assert len(repository.revisions(str(draft["_id"]))) == 2
    group = repository.adapter.assay_groups_collection.find_one()
    assert group["publication_serial"] == 1
    assert group["version"] == 1


def test_concurrent_group_deactivation_prevents_publication(repository, monkeypatch):
    """A publication blocked on a group write must recheck availability when retried."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    draft = repository.save(
        {"asp_id": "synthetic", "revision": 1, "status": "submitted"},
        action="test",
    )
    bundle = {
        "panel": {"asp_id": "synthetic", "asp_group": "demo"},
        "configurations": [],
        "gene_lists": [],
        "associations": [],
        "rules": [],
        "definitions": [],
        "existing_lists": [],
    }
    groups = repository.adapter.assay_groups_collection
    attempted = Event()
    original_update = groups.update_one

    def signal_update(*args, **kwargs):
        attempted.set()
        return original_update(*args, **kwargs)

    with repository.adapter.client.start_session() as session:
        session.start_transaction()
        groups.update_one({"group_id": "demo"}, {"$set": {"is_active": False}}, session=session)
        monkeypatch.setattr(groups, "update_one", signal_update)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                repository.save,
                {**draft, "revision": 2, "status": "published"},
                previous=draft,
                action="publish",
                bundle=bundle,
            )
            try:
                assert attempted.wait(5)
                session.commit_transaction()
                with pytest.raises(AppError, match="group is inactive"):
                    future.result(timeout=10)
            finally:
                if session.in_transaction:
                    session.abort_transaction()
    assert repository.get(str(draft["_id"]))["status"] == "submitted"
    assert repository.adapter.asp_collection.count_documents({}) == 0
