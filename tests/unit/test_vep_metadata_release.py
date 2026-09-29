"""Equivalent VEP release spellings must select the same consequence metadata."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.config.database_versions import vep_metadata_release
from api.infra.mongo.repositories.vep_metadata import VEPMetaRepository


@pytest.mark.parametrize("value", [113, 113.0, "113", "113.0", "v113.0", "113.0.0"])
def test_equivalent_releases(value):
    assert vep_metadata_release(value) == "113"


def test_nonzero_minor_release_is_preserved():
    assert vep_metadata_release("113.1") == "113.1"


@pytest.mark.parametrize("stored", ["113", "113.0"])
def test_metadata_lookup_uses_equivalent_release(stored):
    collection = Mock()
    document = {"vep_id": stored, "conseq_translations": {"stop_gained": "Stop gained description"}}
    collection.find_one.side_effect = lambda query, projection: (
        document if query["vep_id"] == stored else None
    )
    repository = object.__new__(VEPMetaRepository)
    repository.get_collection = lambda: collection
    repository.adapter = SimpleNamespace(app=SimpleNamespace(logger=Mock()))
    assert repository.get_conseq_translations("113.0") == document["conseq_translations"]
    assert all(
        call.args[0]["vep_id"].startswith("113") for call in collection.find_one.call_args_list
    )


@pytest.mark.parametrize(
    "versions,expected",
    [
        (["98", "99", "110", "113", "116", "invalid"], "116"),
        (["116.2", "116.10", "116"], "116.10"),
        ([], None),
        ([None, "invalid"], None),
    ],
)
def test_latest_metadata_uses_numeric_release_order(versions, expected):
    collection = Mock()
    collection.distinct.return_value = versions
    collection.find_one.side_effect = lambda query, projection: {"vep_id": query["vep_id"]}
    repository = object.__new__(VEPMetaRepository)
    repository.get_collection = lambda: collection
    repository.adapter = SimpleNamespace(app=SimpleNamespace(logger=Mock()))
    assert repository._get_latest_metadata() == ({"vep_id": expected} if expected else {})
