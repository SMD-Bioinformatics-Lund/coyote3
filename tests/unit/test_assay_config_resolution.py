"""Negative-path tests for active ASPC resolution."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.application.common.assay_config import get_formatted_assay_config
from api.domain.core.exceptions import AppError


def _repos(
    *,
    asp: dict | None,
    requested: dict | None,
    base: dict | None = None,
    revision: dict | None = None,
):
    def get_aspc(asp_id: str, environment: str, subpanel_id: str):
        if subpanel_id == "base":
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
        "subpanel_id": "hem",
        "environment": "production",
        "omics_layer": "dna",
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
    assert "ASP not registered" in exc.value.detail["error"]


def test_assay_config_resolution_falls_back_to_base_with_explicit_warning() -> None:
    """A valid base ASPC remains visible as an explicit subpanel fallback."""
    asp_repo, aspc_repo = _repos(
        asp={"asp_id": "hema_gmsv1"},
        requested=None,
        base={
            "aspc_id": "hema_gmsv1_base_production",
            "asp_id": "hema_gmsv1",
            "subpanel_id": "base",
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
        "requested_subpanel_id": "hem",
        "resolved_subpanel_id": "base",
        "used_base_configuration": True,
        "resolved_from_sample_revision": False,
        "warning": "No subpanel-specific ASPC is active; base configuration is in use.",
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


def test_assay_config_resolution_uses_the_sampled_aspc_revision_before_active_config() -> None:
    """Historical samples retain their configuration even after ASPC rotation."""
    stored_revision = {
        "_id": "historical-revision",
        "aspc_id": "hema_gmsv1_hem_production",
        "asp_id": "hema_gmsv1",
        "subpanel_id": "hem",
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
