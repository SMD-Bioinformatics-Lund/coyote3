"""The portable core owns the policy used to interpret installed VEP references."""

from coyote.config.vep_reference import load_vep_metadata_policy


def test_policy_defines_one_group_and_labels_for_each_supported_consequence():
    policy = load_vep_metadata_policy()
    terms = [term for group in policy["consequence_groups"].values() for term in group]
    assert len(terms) == len(set(terms))
    assert set(terms) == set(policy["consequence_labels"])
    for term in terms:
        assert policy["consequence_labels"][term]["short"]
        assert policy["consequence_labels"][term]["display"]
    for labels in policy["variant_labels"].values():
        assert labels["short"]
        assert labels["displayname"]


def test_policy_reads_do_not_share_mutable_state():
    first = load_vep_metadata_policy()
    first["consequence_groups"].clear()
    assert load_vep_metadata_policy()["consequence_groups"]["missense"]
