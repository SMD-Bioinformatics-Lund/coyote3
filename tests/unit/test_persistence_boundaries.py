"""Provider-specific identifiers are converted and rejected inside repositories."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from bson import ObjectId

from api.infra.mongo.repositories.copy_number_variants import CNVsRepository
from api.infra.mongo.repositories.fusions import FusionsRepository
from api.infra.mongo.repositories.reported_variants import ReportedVariantsRepository
from api.infra.mongo.repositories.samples import SampleRepository
from api.infra.mongo.repositories.translocations import TranslocsRepository
from api.infra.mongo.repositories.variants import VariantsRepository
from coyote3.domain.exceptions import AppError


@pytest.mark.parametrize(
    ("repository_type", "method"),
    [
        (VariantsRepository, "get_variant"),
        (CNVsRepository, "get_cnv"),
        (FusionsRepository, "get_fusion"),
        (TranslocsRepository, "get_transloc"),
    ],
)
def test_finding_repositories_translate_invalid_ids_before_querying(repository_type, method):
    """Application callers receive ValueError without BSON exceptions or database reads."""
    repository = object.__new__(repository_type)
    collection = Mock()
    repository.get_collection = Mock(return_value=collection)
    with pytest.raises(ValueError) as failure:
        getattr(repository, method)("invalid-provider-id")
    assert type(failure.value) is ValueError
    collection.find_one.assert_not_called()


def test_sample_replacement_restores_nested_ids_without_mutating_application_values():
    """Persistence retains BSON IDs and the existing version precondition after conversion."""
    collection = mongomock.MongoClient().app.samples
    sample_id = ObjectId("000000000000000000000001")
    nested_id = ObjectId("000000000000000000000002")
    collection.insert_one({"_id": sample_id, "version": 3})
    repository = SampleRepository(SimpleNamespace(samples_collection=collection))
    replacement = {
        "_id": sample_id,
        "version": 3,
        "nested": [{"_id": str(nested_id), "value": None}],
    }
    original = deepcopy(replacement)

    repository.update_sample(sample_id, replacement)

    assert replacement == original
    assert collection.find_one({"_id": sample_id}) == {
        "_id": sample_id,
        "version": 4,
        "nested": [{"_id": nested_id, "value": None}],
    }
    with pytest.raises(AppError) as failure:
        repository.update_sample(sample_id, replacement)
    assert failure.value.status_code == 409


def test_saved_report_snapshot_lookup_keeps_both_provider_ids_and_order():
    """A report read cannot mix another sample's or report's immutable finding snapshots."""
    sample_id, report_id = ObjectId(), ObjectId()
    collection = mongomock.MongoClient().app.reported_variants
    collection.insert_many(
        [
            {"sample_oid": sample_id, "report_oid": report_id, "time_created": 1, "gene": "FIRST"},
            {"sample_oid": sample_id, "report_oid": report_id, "time_created": 2, "gene": "LATEST"},
            {
                "sample_oid": ObjectId(),
                "report_oid": report_id,
                "time_created": 3,
                "gene": "OTHER_SAMPLE",
            },
            {
                "sample_oid": sample_id,
                "report_oid": ObjectId(),
                "time_created": 4,
                "gene": "OTHER_REPORT",
            },
        ]
    )
    repository = ReportedVariantsRepository(
        SimpleNamespace(reported_variants_collection=collection)
    )
    rows = repository.list_for_report(sample_id=str(sample_id), report_id=str(report_id))
    assert [row["gene"] for row in rows] == ["LATEST", "FIRST"]
    assert all(row["sample_oid"] == str(sample_id) for row in rows)
    assert all(row["report_oid"] == str(report_id) for row in rows)
