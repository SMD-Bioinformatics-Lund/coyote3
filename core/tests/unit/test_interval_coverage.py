"""Legacy interval coverage retains measured zeros and rejects unsafe input."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.ingest.dependent_writes import data_counts, write_dependents
from coyote.application.operations.ingest_permissions import enforce_collection_permission
from coyote.contracts.schemas.registry import normalize_collection_document
from coyote.domain.exceptions import AppError
from pydantic import ValidationError


def interval(**overrides):
    return {"SAMPLE_ID": "sample", "chr": 7, "start": 0, "end": 0, "avg_cov": 0, **overrides}


@pytest.mark.parametrize("depth", [0, 0.5, None])
def test_interval_preserves_endpoints_depth_null_and_original_identity(depth):
    source = interval(_id="preserved", avg_cov=depth, created_by="original-author")
    before = deepcopy(source)
    result = normalize_collection_document("coverage", source)
    assert result["_id"] == "preserved"
    assert result["chr"] == "7"
    assert result["start"] == result["end"] == 0
    assert result["avg_cov"] == depth
    assert result["created_by"] == "original-author"
    assert "system_installed" not in result
    assert source == before


@pytest.mark.parametrize(
    "changes",
    [
        {"start": -1},
        {"start": 2, "end": 1},
        {"start": True},
        {"end": 1.5},
        {"avg_cov": -0.1},
        {"avg_cov": float("nan")},
        {"avg_cov": float("inf")},
        {"avg_cov": False},
        {"avg_cov": "0.5"},
        {"chr": True},
        {"chr": " "},
        {"SAMPLE_ID": " "},
        {"cosmic": []},
        {"sample": "name"},
    ],
)
def test_invalid_measurements_and_undeclared_legacy_fields_are_rejected(changes):
    with pytest.raises(ValidationError):
        normalize_collection_document("coverage", interval(**changes))


def test_missing_depth_is_not_assumed_to_mean_zero_or_null():
    source = interval()
    del source["avg_cov"]
    with pytest.raises(ValidationError):
        normalize_collection_document("coverage", source)


def test_interval_ingestion_uses_parent_session_and_independent_d4_counts():
    gateway = Mock()
    service = SimpleNamespace(
        collection_gateway=gateway,
        _normalize_collection_docs=lambda collection, rows: [
            normalize_collection_document(collection, row) for row in rows
        ],
    )
    transaction = object()
    preload = {"coverage": [interval()], "cov": {"genes": {}}}
    written = write_dependents(
        service,
        preload=preload,
        sample_id="owner",
        sample_name="SYNTHETIC",
        actor="submitter",
        session=transaction,
    )
    assert written == {"cov": 1, "coverage": 1}
    args, kwargs = gateway.insert_dependents.call_args
    assert args[0] == "coverage"
    assert args[1][0]["SAMPLE_ID"] == "owner"
    assert args[1][0]["created_by"] == "submitter"
    assert args[1][0]["avg_cov"] == 0
    assert kwargs["session"] is transaction
    assert gateway.insert_dependent.call_args.args[0] == "d4_coverage"
    assert gateway.insert_dependent.call_args.kwargs["session"] is transaction
    assert data_counts({"coverage": [interval(), interval()], "cov": {"genes": {}}}) == {
        "coverage": 2,
        "cov": True,
    }


def test_direct_interval_collection_ingest_cannot_bypass_sample_permissions():
    with pytest.raises(AppError):
        enforce_collection_permission(
            SimpleNamespace(),
            user=SimpleNamespace(is_superuser=False),
            collection="coverage",
            action="create",
        )
