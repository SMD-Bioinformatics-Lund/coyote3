"""Verify allele identity, group exclusions and per-assay blacklist measurements."""

from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from pydantic import ValidationError

from api.infra.mongo.repositories.blacklist import BlacklistRepository
from coyote3.contracts.schemas.assay import BlacklistDoc
from coyote3.domain.dna.variant_identity import build_simple_id_hash_from_simple_id


def entry(**overrides):
    """Build a synthetic single-allele record in the current blacklist contract."""
    return {
        "simple_id": "7_100_A_T",
        "simple_id_hash": "666b4e86991008843943a5e5b5118ae0",
        "chrom": "7",
        "pos": 100,
        "ref": "A",
        "alt": "T",
        "assay_groups": ["solid"],
        "in_normal_perc": {"solid_gmsv3": 0.2, "other_assay": 0.7},
        **overrides,
    }


@pytest.fixture
def repository():
    collection = mongomock.MongoClient().synthetic.blacklist
    repo = BlacklistRepository(SimpleNamespace(blacklist_collection=collection))
    repo.invalidate_dashboard_metrics = Mock()
    repo.ensure_indexes()
    return repo


def test_schema_normalizes_scopes_and_requires_consistent_coordinates():
    doc = BlacklistDoc.model_validate(
        entry(chrom="chr7", ref="a", alt="t", assay_groups=["Solid", "solid"])
    )
    assert doc.assay_groups == ["solid"]
    assert (doc.chrom, doc.ref, doc.alt) == ("7", "A", "T")
    with pytest.raises(ValidationError, match="simple_id must match"):
        BlacklistDoc.model_validate(entry(pos=101))


def test_schema_rejects_a_hash_that_does_not_match_the_variant():
    with pytest.raises(ValidationError, match="MD5 mismatch"):
        BlacklistDoc.model_validate(entry(simple_id_hash="0" * 32))


@pytest.mark.parametrize("frequency", [-0.1, 100.1, float("nan"), float("inf")])
def test_schema_rejects_invalid_assay_measurements(frequency):
    with pytest.raises(ValidationError):
        BlacklistDoc.model_validate(entry(in_normal_perc={"solid_gmsv3": frequency}))


def test_schema_preserves_numeric_measurements_without_rescaling():
    doc = BlacklistDoc.model_validate(entry(in_normal_perc={"solid_gmsv3": 20}))
    assert doc.in_normal_perc["solid_gmsv3"] == 20


def test_group_exclusion_uses_only_the_selected_assays_measurement(repository):
    repository.get_collection().insert_one(entry())
    variant = {"simple_id": "7_100_A_T"}
    assert (
        repository.add_blacklist_data([variant.copy()], "solid", asp_id="solid_gmsv3")[0][
            "blacklist"
        ]
        == 0.2
    )
    assert (
        repository.add_blacklist_data([variant.copy()], "solid", asp_id="unmeasured")[0][
            "blacklist"
        ]
        is True
    )
    assert (
        "blacklist"
        not in repository.add_blacklist_data([variant.copy()], "hematology", asp_id="solid_gmsv3")[
            0
        ]
    )
    different_allele = {"simple_id": "7_100_A_C"}
    assert (
        "blacklist"
        not in repository.add_blacklist_data([different_allele], "solid", asp_id="solid_gmsv3")[0]
    )


def test_manual_additions_merge_groups_preserve_measurements_and_are_idempotent(repository):
    repository.get_collection().insert_one(entry())
    variant = {"simple_id": "7_100_A_T"}
    result = repository.blacklist_variant(variant, "hematology")
    assert result.modified_count == 1
    assert repository.blacklist_variant(variant, "hematology").modified_count == 0
    stored = repository.get_collection().find_one()
    assert set(stored["assay_groups"]) == {"solid", "hematology"}
    assert stored["in_normal_perc"] == entry()["in_normal_perc"]
    assert repository.get_unique_blacklist_count() == 1
    assert repository.get_blacklisted_count() == 1


def test_new_manual_entry_keeps_coordinates_without_inventing_a_frequency(repository):
    result = repository.blacklist_variant(
        {"CHROM": "chr7", "POS": 101, "REF": "a", "ALT": "c"}, "solid"
    )
    assert result.upserted_id
    stored = repository.get_collection().find_one()
    assert stored["simple_id"] == "7_101_A_C"
    assert stored["simple_id_hash"] == build_simple_id_hash_from_simple_id("7_101_A_C")
    assert stored["pos"] == 101
    assert stored["in_normal_perc"] == {}
    BlacklistDoc.model_validate(stored)


def test_zero_measurement_does_not_remove_a_group_exclusion(repository):
    repository.get_collection().insert_one(entry(in_normal_perc={"solid_gmsv3": 0}))
    result = repository.add_blacklist_data(
        [{"simple_id": "7_100_A_T"}], "solid", asp_id="solid_gmsv3"
    )
    assert result[0]["blacklist"] is True
