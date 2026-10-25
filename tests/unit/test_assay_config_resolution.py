"""Negative-path tests for active ASPC resolution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from coyote3.application.common.assay_config import get_formatted_assay_config
from coyote3.application.common.assay_context import build_assay_context
from coyote3.application.common.release_resources import capture_assay_resource
from coyote3.domain.exceptions import AppError


def _repos(
    *,
    asp: dict | None,
    requested: dict | None,
    base: dict | None = None,
    revision: dict | None = None,
):
    if asp is not None:
        asp = {
            "asp_group": "hematology",
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "version": 1,
            **asp,
        }
    for configuration in (requested, base, revision):
        if configuration is not None:
            configuration.setdefault("asp_group", "hematology")
            configuration.setdefault("analysis_types", ["SNV"])
            configuration.setdefault("analysis_intents", ["somatic"])
            configuration.setdefault("version", 1)
            if asp is not None:
                configuration.setdefault("assay_resource_release", capture_assay_resource(asp))

    def get_aspc(asp_id: str, environment: str, diagnosis_id: str):
        if diagnosis_id == "base":
            return base
        return requested

    return (
        SimpleNamespace(get_asp=lambda _asp_id: asp),
        SimpleNamespace(
            get_aspc_no_meta=get_aspc,
            get_aspc_revision_no_meta=lambda _revision_id: revision,
        ),
    )


def _sample(**overrides: object) -> dict:
    sample = {
        "name": "clinical_sample",
        "asp_id": "hema_gmsv1",
        "diagnosis_id": "hem",
        "environment": "production",
        "asp_category": "dna",
    }
    sample.update(overrides)
    return sample


def test_assay_config_resolution_rejects_missing_assay_identity() -> None:
    """A sample without an ASP identifier cannot silently receive defaults."""
    asp_repo, aspc_repo = _repos(asp=None, requested=None)

    with pytest.raises(AppError) as exc:
        get_formatted_assay_config(
            _sample(asp_id=""),
            assay_panel_repository=asp_repo,
            assay_configuration_repository=aspc_repo,
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "Sample is missing assay metadata"


def test_assay_config_resolution_rejects_unknown_asp() -> None:
    """An unregistered assay is a setup error, never an empty configuration."""
    asp_repo, aspc_repo = _repos(asp=None, requested=None)

    with pytest.raises(AppError) as exc:
        get_formatted_assay_config(
            _sample(),
            assay_panel_repository=asp_repo,
            assay_configuration_repository=aspc_repo,
        )

    assert exc.value.status_code == 422
    assert "ASPC not registered" in exc.value.detail["error"]


def test_assay_config_resolution_falls_back_to_base_with_explicit_warning() -> None:
    """A valid base ASPC remains visible as an explicit diagnosis fallback."""
    asp_repo, aspc_repo = _repos(
        asp={"asp_id": "hema_gmsv1"},
        requested=None,
        base={
            "aspc_id": "hema_gmsv1_base_production",
            "asp_id": "hema_gmsv1",
            "diagnosis_id": "base",
            "environment": "production",
            "filters": {"somatic": {"snv": {}}},
            "reporting": {},
        },
    )

    resolved = get_formatted_assay_config(
        _sample(),
        assay_panel_repository=asp_repo,
        assay_configuration_repository=aspc_repo,
    )

    assert resolved["aspc_resolution"] == {
        "context": build_assay_context(_sample(), asp_repo.get_asp("hema_gmsv1"), resolved),
        "requested_diagnosis_id": "hem",
        "resolved_diagnosis_id": "base",
        "used_base_configuration": True,
        "resolved_from_sample_revision": False,
        "warning": "No diagnosis-specific ASPC is active; base configuration is in use.",
    }


def test_assay_config_resolution_rejects_missing_specific_and_base_aspc() -> None:
    """A sample cannot open analysis when neither exact nor base ASPC exists."""
    asp_repo, aspc_repo = _repos(asp={"asp_id": "hema_gmsv1"}, requested=None)

    with pytest.raises(AppError) as exc:
        get_formatted_assay_config(
            _sample(),
            assay_panel_repository=asp_repo,
            assay_configuration_repository=aspc_repo,
        )

    assert exc.value.status_code == 422
    assert "ASPC not registered" in exc.value.detail["error"]


def test_rna_configuration_format_comes_from_captured_assay_resource() -> None:
    """Pre-ingestion resolution uses the assay category before sample metadata is populated."""
    asp_repo, aspc_repo = _repos(
        asp={"asp_id": "rna_panel", "asp_category": "rna", "asp_family": "panel-rna"},
        requested={
            "aspc_id": "rna_panel_hem_production",
            "asp_id": "rna_panel",
            "diagnosis_id": "hem",
            "environment": "production",
            "analysis_types": ["FUSION"],
            "filters": {"somatic": {"fusion": {"min_spanning_reads": 7}}},
            "reporting": {},
        },
    )
    sample = _sample(asp_id="rna_panel")
    sample.pop("asp_category")
    resolved = get_formatted_assay_config(
        sample,
        assay_panel_repository=asp_repo,
        assay_configuration_repository=aspc_repo,
    )
    assert resolved["aspc_resolution"]["context"]["modality"] == "rna"
    assert resolved["filters"]["somatic"]["fusion"]["min_spanning_reads"] == 7


def test_assay_config_resolution_uses_the_sampled_aspc_revision_before_active_config() -> None:
    """Historical samples retain their configuration even after ASPC rotation."""
    stored_revision = {
        "_id": "historical-revision",
        "aspc_id": "hema_gmsv1_hem_production",
        "asp_id": "hema_gmsv1",
        "diagnosis_id": "hem",
        "environment": "production",
        "version": 2,
        "is_active": False,
        "filters": {"somatic": {"snv": {"min_depth": 50}}},
        "reporting": {},
    }
    asp_repo, aspc_repo = _repos(
        asp={"asp_id": "hema_gmsv1"},
        requested={"version": 3},
        revision=stored_revision,
    )

    resolved = get_formatted_assay_config(
        _sample(current_aspc_id="historical-revision"),
        assay_panel_repository=asp_repo,
        assay_configuration_repository=aspc_repo,
    )

    assert resolved["version"] == 2
    assert resolved["filters"]["somatic"]["snv"]["min_depth"] == 50
    assert resolved["aspc_resolution"]["resolved_from_sample_revision"] is True


def test_assay_config_resolution_rejects_a_missing_sampled_aspc_revision() -> None:
    """A broken revision link must not silently use the active configuration."""
    asp_repo, aspc_repo = _repos(
        asp={"asp_id": "hema_gmsv1"},
        requested={"version": 3},
    )

    with pytest.raises(AppError) as exc:
        get_formatted_assay_config(
            _sample(current_aspc_id="deleted-revision"),
            assay_panel_repository=asp_repo,
            assay_configuration_repository=aspc_repo,
        )

    assert exc.value.status_code == 422
    assert exc.value.detail["error"] == "Stored ASPC revision is unavailable"


def test_resource_receipt_preserves_family_and_group_after_definition_edit():
    """Current assay metadata cannot reinterpret an existing sample's receipt."""
    configuration = {
        "asp_id": "hema_gmsv1",
        "aspc_id": "hema_gmsv1_hem_production",
        "environment": "production",
        "diagnosis_id": "hem",
        "asp_group": "hematology",
        "analysis_types": ["SNV"],
        "analysis_intents": ["somatic"],
        "version": 1,
        "filters": {"somatic": {"snv": {}}},
        "reporting": {},
    }
    original_panel = {
        "asp_id": "hema_gmsv1",
        "asp_group": "hematology",
        "asp_family": "panel-dna",
        "asp_category": "dna",
        "version": 1,
    }
    receipt = build_assay_context(_sample(), original_panel, configuration)
    configuration["assay_resource_release"] = capture_assay_resource(original_panel)
    panel_repository, config_repository = _repos(
        asp={**original_panel, "asp_group": "solid", "asp_family": "wgs", "version": 2},
        requested=None,
        revision=configuration,
    )
    resolved = get_formatted_assay_config(
        _sample(current_aspc_id="revision_1"),
        assay_panel_repository=panel_repository,
        assay_configuration_repository=config_repository,
    )
    assert resolved["aspc_resolution"]["context"] == receipt
    assert receipt["family"] == "panel-dna"
    assert receipt["group_id"] == "hematology"


@pytest.mark.parametrize(
    "changes",
    [
        {"diagnosis_id": "base"},
        {"environment": "testing"},
        {"asp_category": "rna"},
        {"asp_family": "wts"},
    ],
)
def test_resource_receipt_rejects_another_sample_scope(changes):
    """An exact release cannot resolve a sample from another interpretation scope."""

    configuration = {
        "asp_id": "hema_gmsv1",
        "asp_group": "hematology",
        "aspc_id": "hema_gmsv1_hem_production",
        "environment": "production",
        "diagnosis_id": "hem",
        "analysis_types": ["SNV"],
        "analysis_intents": ["somatic"],
        "version": 1,
    }
    panel = {
        "asp_id": "hema_gmsv1",
        "asp_group": "hematology",
        "asp_family": "panel-dna",
        "asp_category": "dna",
        "version": 1,
    }
    with pytest.raises(AppError, match="Configuration .* does not match"):
        build_assay_context(_sample(**changes), panel, configuration)
