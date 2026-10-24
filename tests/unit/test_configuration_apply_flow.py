"""Configuration previews preserve context and apply only the reviewed sample version."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.application.common.assay_context import build_assay_context
from api.application.common.release_resources import capture_assay_resource, capture_gene_lists
from api.application.sample.catalog import SampleCatalogService
from api.domain.core.exceptions import AppError


@pytest.fixture
def flow():
    sample = {
        "_id": "sample-1",
        "asp_id": "demo-solid_gmsv3",
        "diagnosis_id": "breast",
        "environment": "validation",
        "asp_category": "dna",
        "version": 7,
        "analysis_intents": ["somatic"],
        "filters": {"somatic": {"snv": {"min_depth": 100, "snvlists": ["breast"]}}},
    }
    panel = {
        "asp_id": "demo-solid_gmsv3",
        "asp_group": "solid",
        "asp_category": "dna",
        "asp_family": "panel-dna",
        "version": 1,
        "covered_genes": ["TP53"],
    }
    lists = [{"isgl_id": "breast", "version": 1, "list_type": ["snv"], "genes": ["TP53"]}]

    def configuration(version, depth):
        result = {
            "_id": f"configuration-{version}",
            "aspc_id": "solid_breast_validation",
            "version": version,
            "asp_id": "demo-solid_gmsv3",
            "asp_group": "solid",
            "asp_category": "dna",
            "diagnosis_id": "breast",
            "environment": "validation",
            "analysis_types": ["SNV"],
            "analysis_intents": ["somatic"],
            "filters": {"somatic": {"snv": {"min_depth": depth, "snvlists": ["breast"]}}},
            "assay_resource_release": capture_assay_resource(panel),
            "gene_list_release": capture_gene_lists(lists),
        }
        result["aspc_resolution"] = {
            "context": build_assay_context(sample, panel, result),
            "resolved_diagnosis_id": "breast",
            "used_base_configuration": False,
            "warning": None,
        }
        return result

    old, candidate = configuration(1, 30), configuration(2, 50)
    service = object.__new__(SampleCatalogService)
    service._get_formatted_assay_config = lambda sample, use_sample_revision=True: (
        old if use_sample_revision else candidate
    )
    service.sample_repository = SimpleNamespace(update_sample_filters=Mock())
    return service, sample, candidate


@pytest.mark.parametrize("retain,depth", [(False, 50), (True, 100)])
def test_preview_is_read_only_and_explicitly_resets_or_retains_overrides(flow, retain, depth):
    service, sample, _ = flow
    original = deepcopy(sample)
    preview = service.preview_latest_aspc(sample=sample, retain_overrides=retain)
    assert preview["filters_after"]["somatic"]["snv"]["min_depth"] == depth
    assert preview["expected_version"] == 7
    assert preview["configuration_id"] == "configuration-2"
    assert sample == original
    service.sample_repository.update_sample_filters.assert_not_called()


def test_preview_rejects_list_that_loses_snv_support(flow):
    service, sample, candidate = flow
    candidate["gene_list_release"] = capture_gene_lists(
        [{"isgl_id": "breast", "version": 2, "list_type": ["cnv"], "genes": ["TP53"]}]
    )
    with pytest.raises(AppError, match="do not support SNV"):
        service.preview_latest_aspc(sample=sample, retain_overrides=True)
    service.sample_repository.update_sample_filters.assert_not_called()


@pytest.mark.parametrize(
    "version,identifier,reason",
    [
        (6, "configuration-2", "Reviewed"),
        (7, "configuration-1", "Reviewed"),
        (7, "configuration-2", " "),
    ],
)
def test_apply_rejects_stale_sample_release_or_missing_reason(flow, version, identifier, reason):
    service, sample, _ = flow
    with pytest.raises(AppError):
        service.apply_latest_aspc(
            sample=sample, expected_version=version, configuration_id=identifier, reason=reason
        )
    service.sample_repository.update_sample_filters.assert_not_called()


def test_apply_passes_exact_release_and_version_to_atomic_write(flow):
    service, sample, candidate = flow
    service.apply_latest_aspc(
        sample=sample,
        expected_version=7,
        configuration_id="configuration-2",
        reason="Validated thresholds",
        retain_overrides=False,
    )
    args, kwargs = service.sample_repository.update_sample_filters.call_args
    assert args[0] == "sample-1"
    assert args[1]["somatic"]["snv"]["min_depth"] == 50
    assert kwargs["expected_version"] == 7
    assert kwargs["aspc"]["_id"] == "configuration-2"
    assert "aspc_resolution" not in kwargs
    assert kwargs["settings_reason"] == "Validated thresholds"
