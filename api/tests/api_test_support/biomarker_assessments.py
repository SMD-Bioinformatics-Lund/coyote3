"""Synthetic reusable fixtures for package-owned behavior tests."""

from copy import deepcopy
from types import SimpleNamespace

import mongomock
import pytest
from coyote.application.biomarker.biomarker_lookup import BiomarkerService
from coyote.contracts.dna import BiomarkerAssessmentRequest
from coyote_mongo.repositories.biomarkers import BiomarkerRepository

from api_test_support.measurements import MEASUREMENTS
from api_test_support.mongo_settings import mongo_runtime


@pytest.fixture
def review(monkeypatch):
    """Use atomic Mongo-style updates against synthetic sample-owned measurements."""
    collection = mongomock.MongoClient().synthetic.biomarkers
    identifier = collection.insert_one(
        {**deepcopy(MEASUREMENTS), "SAMPLE_ID": "sample"}
    ).inserted_id
    repository = BiomarkerRepository(
        SimpleNamespace(app=mongo_runtime(), biomarkers_collection=collection)
    )
    analyses = ["HRD", "MSI", "TMB"]
    monkeypatch.setattr(
        "coyote.application.biomarker.biomarker_lookup.get_formatted_assay_config",
        lambda *args, **kwargs: {"analysis_types": analyses},
    )
    service = BiomarkerService(
        biomarker_repository=repository,
        assay_panel_repository=object(),
        assay_configuration_repository=object(),
    )
    return SimpleNamespace(
        service=service,
        repository=repository,
        collection=collection,
        identifier=str(identifier),
        sample={"_id": "sample", "asp_category": "dna"},
        analyses=analyses,
    )


def assign(review, method="TMB", value="HIGH", revision=0, record_id=None, sample=None):
    """Assign through the application service with explicit optimistic concurrency."""
    return review.service.assign_assessment(
        sample=sample or review.sample,
        record_id=record_id or review.identifier,
        method=method,
        change=BiomarkerAssessmentRequest(value=value, expected_revision=revision),
        actor="synthetic-geneticist",
    )
