"""Manual biomarker review preserves measured evidence, authorization and audit history."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from pydantic import ValidationError

from api.infra.mongo.repositories.biomarkers import BiomarkerRepository
from coyote3.application.biomarker.biomarker_lookup import BiomarkerService
from coyote3.application.ingest.dependent_writes import _preserve_biomarker_assessments
from coyote3.application.operations.samples import Sample
from coyote3.application.reporting.preview_consistency import preview_fingerprint
from coyote3.application.reporting.snapshot_rows import build_biomarker_snapshot_rows
from coyote3.contracts.dna import BiomarkerAssessmentRequest
from coyote3.contracts.schemas.dna import BiomarkersDoc
from coyote3.domain.exceptions import AppError
from tests.unit import test_application_sdk
from tests.unit.test_independent_biomarker_analyses import MEASUREMENTS

sdk = test_application_sdk.sdk


@pytest.fixture
def review(monkeypatch):
    """Use atomic Mongo-style updates against synthetic sample-owned measurements."""
    collection = mongomock.MongoClient().synthetic.biomarkers
    identifier = collection.insert_one(
        {**deepcopy(MEASUREMENTS), "SAMPLE_ID": "sample"}
    ).inserted_id
    repository = BiomarkerRepository(SimpleNamespace(biomarkers_collection=collection))
    analyses = ["HRD", "MSI", "TMB"]
    monkeypatch.setattr(
        "coyote3.application.biomarker.biomarker_lookup.get_formatted_assay_config",
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


def test_assessment_is_manual_revision_checked_and_clearing_retains_history(review):
    """A measured zero can be manually assessed; clearing preserves the author trail."""
    result = assign(review)
    tmb = result["biomarkers"][0]["TMB"]
    assert tmb["value"] == 0
    assert tmb["clinical_assessment"]["value"] == "HIGH"
    assert tmb["clinical_assessment"]["assessed_by"] == "synthetic-geneticist"
    assert tmb["clinical_assessment"]["revision"] == 1
    assert tmb["clinical_assessment"]["assessed_at"] is not None
    assert "assessment_history" not in tmb
    with pytest.raises(AppError) as stale:
        assign(review, value="LOW")
    assert stale.value.status_code == 409
    assign(review, value=None, revision=1)
    record = review.collection.find_one()
    assert record["TMB"]["clinical_assessment"]["value"] is None
    assert record["TMB"]["clinical_assessment"]["revision"] == 2
    assert [item["value"] for item in record["TMB"]["assessment_history"]] == ["HIGH", None]
    assert record["HRD"] == MEASUREMENTS["HRD"]
    assert record["MSIP"] == MEASUREMENTS["MSIP"]
    BiomarkersDoc.model_validate(record)


@pytest.mark.parametrize("method", ["HRD", "MSIS", "MSIP", "TMB"])
def test_measurements_have_independent_assessments_and_report_snapshots(review, method):
    before = review.service.review_payload(sample=review.sample)["biomarkers"]
    after = assign(review, method=method, value="MODERATE")["biomarkers"]
    rows = build_biomarker_snapshot_rows(after)
    assert any(
        row["result"].get(method, {}).get("clinical_assessment", {}).get("value") == "MODERATE"
        for row in rows
    )
    assert preview_fingerprint("dna_report.html", {"biomarkers": before}) != preview_fingerprint(
        "dna_report.html", {"biomarkers": after}
    )
    assert all("assessment_history" not in row["result"].get(method, {}) for row in rows)
    for other in {"HRD", "MSIS", "MSIP", "TMB"} - {method}:
        assert after[0][other] == MEASUREMENTS[other]


@pytest.mark.parametrize("case", ["sample", "record", "method", "disabled", "missing"])
def test_assessment_rejects_foreign_absent_and_disabled_measurements(review, case):
    kwargs = {}
    if case == "sample":
        kwargs["sample"] = {"_id": "other-sample", "asp_category": "dna"}
    elif case == "record":
        kwargs["record_id"] = "000000000000000000000000"
    elif case == "method":
        kwargs["method"] = "$set"
    elif case == "disabled":
        review.analyses.remove("TMB")
    else:
        review.collection.update_one({}, {"$unset": {"TMB": ""}})
    before = review.collection.find_one()
    with pytest.raises(AppError) as error:
        assign(review, **kwargs)
    assert error.value.status_code == 404
    assert review.collection.find_one() == before


@pytest.mark.parametrize(
    "payload",
    [
        {"value": "UNKNOWN", "expected_revision": 0},
        {"value": "HIGH", "expected_revision": -1},
        {"value": "HIGH", "expected_revision": 0, "assessed_by": "forged"},
    ],
)
def test_assessment_contract_rejects_invalid_values_and_actor_spoofing(payload):
    with pytest.raises(ValidationError):
        BiomarkerAssessmentRequest.model_validate(payload)


def test_sdk_requires_edit_permission_production_publication_and_editing_lease(sdk):
    service = Mock()
    sdk.services.biomarkers = lambda: service
    sample = Sample(sdk.runtime, sdk.services, "demo")
    change = BiomarkerAssessmentRequest(value="LOW", expected_revision=0)
    sdk.grants.remove("sample:edit:own")
    with pytest.raises(AppError):
        sample.assess_biomarker("record", "HRD", change)
    sdk.grants.add("sample:edit:own")
    sdk.sample["environment"] = "production"
    sdk.actor.envs = ["production"]
    sdk.grants.remove("annotation:publish")
    with pytest.raises(AppError):
        sample.assess_biomarker("record", "HRD", change)
    service.assign_assessment.assert_not_called()
    sdk.grants.add("annotation:publish")
    guard = Mock(side_effect=AppError(status_code=409, message="Lease required"))
    sdk.runtime.edit_guard = guard
    with pytest.raises(AppError):
        sample.assess_biomarker("record", "HRD", change)
    service.assign_assessment.assert_not_called()
    guard.side_effect = None
    guard.return_value = None
    sample.assess_biomarker("record", "HRD", change)
    guard.assert_called_with("sample-biomarkers", "demo", sdk.actor, True)
    assert service.assign_assessment.call_args.kwargs["actor"] == sdk.actor.username


def test_reimport_preserves_review_and_rejects_replacing_its_evidence(review):
    assign(review, method="MSIP")
    stored = review.collection.find_one()
    identical = _preserve_biomarker_assessments(stored, deepcopy(MEASUREMENTS))
    assert identical["MSIP"] == stored["MSIP"]
    changed = deepcopy(MEASUREMENTS)
    changed["MSIP"]["per"] = 9.0
    with pytest.raises(ValueError, match="reviewed MSIP"):
        _preserve_biomarker_assessments(stored, changed)
    del changed["MSIP"]
    with pytest.raises(ValueError, match="reviewed MSIP"):
        _preserve_biomarker_assessments(stored, changed)
    unrelated = {"name": MEASUREMENTS["name"], "TMB": {"value": 10.0}}
    assert _preserve_biomarker_assessments(stored, unrelated) == unrelated
