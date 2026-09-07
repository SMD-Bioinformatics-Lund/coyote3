"""Report atomicity checks against an explicitly selected disposable replica-set database."""

import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import pytest
from bson import ObjectId
from pymongo import MongoClient

from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories.reported_variants import ReportedVariantsRepository
from api.infra.mongo.repositories.reports import ReportRepository


@pytest.fixture
def reports():
    uri = os.getenv("REPORT_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set REPORT_TEST_MONGO_URI for disposable report transaction tests")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    database = client[f"coyote3_report_test_{uuid4().hex}"]
    adapter = SimpleNamespace(
        client=client,
        reports_collection=database.reports,
        samples_collection=database.samples,
        reported_variants_collection=database.reported_variants,
    )
    adapter.reported_variant_repository = ReportedVariantsRepository(adapter)
    repository = ReportRepository(adapter)
    sample = {"_id": ObjectId(), "name": "SYNTHETIC", "asp_id": "synthetic", "reported": False}
    database.samples.insert_one(sample)
    try:
        yield repository, sample
    finally:
        client.drop_database(database.name)
        client.close()


def save(repository, sample, report_id):
    return repository.save_report(
        sample=sample,
        report_num=1,
        report_id=report_id,
        filepath=f"/synthetic/{report_id}.html",
        snapshot_rows=[],
    )


def test_snapshot_failure_rolls_back_metadata_and_sample_status(reports, monkeypatch):
    repository, sample = reports

    def fail(**kwargs):
        repository.adapter.reported_variants_collection.insert_one(
            {"report_id": kwargs["report_id"]}, session=kwargs["session"]
        )
        raise RuntimeError("Synthetic snapshot failure")

    monkeypatch.setattr(
        repository.adapter.reported_variant_repository, "bulk_upsert_from_snapshot_rows", fail
    )
    with pytest.raises(RuntimeError, match="Synthetic snapshot failure"):
        save(repository, sample, "r1")
    assert repository.get_collection().count_documents({}) == 0
    assert repository.adapter.reported_variants_collection.count_documents({}) == 0
    assert repository.adapter.samples_collection.find_one({})["reported"] is False


def test_concurrent_report_numbers_cannot_both_commit(reports):
    repository, sample = reports

    def attempt(index):
        try:
            save(repository, sample, f"report-{index}")
            return 200
        except AppError as error:
            return error.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(attempt, range(2)))
    assert sorted(results) == [200, 409]
    document = repository.get_collection().find_one({})
    assert repository.get_collection().count_documents({}) == 1
    assert repository.adapter.samples_collection.find_one({})["latest_report_id"] == document["_id"]
