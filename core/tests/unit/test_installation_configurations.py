"""Installation compilation captures eligible resources without inferring clinical scope."""

import pytest
from coyote.application.common.installation import compile_bundle_configurations
from coyote.application.common.release_resources import assay_resource, gene_list_resources


@pytest.fixture
def bundle():
    """Provide explicit assay/diagnosis links and a selectable synthetic gene list."""
    return {
        "assay_specific_panels": [
            {"asp_id": "synthetic-wgs", "asp_group": "hematology", "genes": ["TP53"]}
        ],
        "asp_configs": [
            {
                "asp_id": "synthetic-wgs",
                "asp_group": "hematology",
                "diagnosis_id": "mpn",
                "query_policy_release": {"content": "unrelated policy"},
                "clinical_rule_release": {"content": "unrelated report rule"},
                "clinical_rule_base": {"content": "unrelated report baseline"},
            }
        ],
        "diagnoses": [{"diagnosis_id": "mpn", "is_active": True}],
        "diagnosis_associations": [
            {"asp_id": "synthetic-wgs", "diagnosis_id": "mpn", "is_active": True}
        ],
        "insilico_genelists": [
            {
                "isgl_id": "assay-list",
                "asp_ids": ["synthetic-wgs"],
                "is_active": True,
                "genes": ["TP53"],
            }
        ],
    }


@pytest.mark.parametrize("state", ["missing", "inactive", "different_assay"])
def test_gene_list_applicability_does_not_substitute_for_a_diagnosis_association(bundle, state):
    """A scoped gene list cannot authorize a diagnosis for an unassociated assay."""
    if state == "missing":
        bundle["diagnosis_associations"] = []
    elif state == "inactive":
        bundle["diagnosis_associations"][0]["is_active"] = False
    else:
        bundle["diagnosis_associations"][0]["asp_id"] = "different-assay"
    with pytest.raises(ValueError, match="explicit shared diagnosis"):
        compile_bundle_configurations(bundle)


@pytest.mark.parametrize("state", ["missing", "inactive"])
def test_association_requires_an_active_shared_diagnosis(bundle, state):
    if state == "missing":
        bundle["diagnoses"] = []
    else:
        bundle["diagnoses"][0]["is_active"] = False
    with pytest.raises(ValueError, match="explicit shared diagnosis"):
        compile_bundle_configurations(bundle)


def test_base_configuration_does_not_require_a_named_diagnosis(bundle):
    bundle["asp_configs"][0]["diagnosis_id"] = "base"
    bundle.pop("diagnoses")
    bundle.pop("diagnosis_associations")
    compile_bundle_configurations(bundle)
    assert assay_resource(bundle["asp_configs"][0])["asp_id"] == "synthetic-wgs"


def test_captured_resources_keep_only_active_registered_lists_in_assay_or_group_scope(bundle):
    """Later source edits cannot change compiled eligibility or selected gene content."""
    original = bundle["insilico_genelists"][0]
    bundle["insilico_genelists"].extend(
        [
            {**original, "isgl_id": "group-list", "asp_ids": [], "asp_groups": ["hematology"]},
            {**original, "isgl_id": "inactive", "is_active": False},
            {**original, "isgl_id": "adhoc", "adhoc": True},
            {**original, "isgl_id": "unrelated", "asp_ids": ["different-assay"]},
            {**original, "isgl_id": "unscoped", "asp_ids": None, "asp_groups": None},
        ]
    )
    compile_bundle_configurations(bundle)
    configuration = bundle["asp_configs"][0]
    assert set(gene_list_resources(configuration)) == {"assay-list", "group-list"}
    assert not {
        "query_policy_release",
        "clinical_rule_release",
        "clinical_rule_base",
    }.intersection(configuration)

    bundle["assay_specific_panels"][0]["genes"].append("KRAS")
    original["genes"].append("BRAF")
    assert assay_resource(configuration)["genes"] == ["TP53"]
    assert gene_list_resources(configuration, ["assay-list"])["assay-list"]["genes"] == ["TP53"]


def test_configuration_cannot_capture_an_absent_assay(bundle):
    bundle["assay_specific_panels"] = []
    with pytest.raises(KeyError, match="synthetic-wgs"):
        compile_bundle_configurations(bundle)
