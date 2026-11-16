"""Finding mutations reject cross-sample identifiers before changing data."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bson import ObjectId
from bson.errors import InvalidId
from coyote_mongo.repositories.base import BaseRepository


def test_scoped_flag_write_cannot_match_another_sample():
    """The database predicate keeps sample ownership even after service validation."""
    repository = object.__new__(BaseRepository)
    repository.update_many_atomic = Mock(
        return_value=SimpleNamespace(matched_count=1, modified_count=1, acknowledged=True)
    )
    repository._invalidate_dashboard_on_change = lambda result: result
    finding_id = str(ObjectId())
    repository.set_sample_finding_flag(
        sample_id="authorized-sample", resource_ids=[finding_id], flag="fp", value=True
    )
    repository.update_many_atomic.assert_called_once_with(
        {"_id": {"$in": [ObjectId(finding_id)]}, "SAMPLE_ID": "authorized-sample"},
        {"$set": {"fp": True}},
    )


def test_malformed_bulk_identifier_prevents_every_write():
    """Invalid selections must never silently update just the valid subset."""
    repository = object.__new__(BaseRepository)
    repository.update_many_atomic = Mock()
    with pytest.raises(InvalidId):
        repository.set_sample_finding_flag(
            sample_id="sample", resource_ids=[str(ObjectId()), "invalid"], flag="fp", value=True
        )
    repository.update_many_atomic.assert_not_called()
