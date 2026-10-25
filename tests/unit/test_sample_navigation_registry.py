"""Authenticated assay navigation is independent of public catalog publication."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from coyote3.application.sample.catalog import SampleCatalogService
from coyote3.config.constants import DEFAULT_ENVIRONMENT


def test_navigation_uses_accessible_registry_assays_even_without_samples():
    """Zero-count registered assays remain navigable without exposing unauthorized groups."""
    service = object.__new__(SampleCatalogService)
    service.sample_repository = SimpleNamespace(count_ready_samples_by_asp=lambda **kw: {})
    service.assay_panel_repository = SimpleNamespace(
        get_all_asps=lambda: [
            {
                "asp_id": "allowed",
                "asp_category": "dna",
                "asp_family": "panel-dna",
                "asp_group": "solid",
            },
            {
                "asp_id": "other",
                "asp_category": "dna",
                "asp_family": "wgs",
                "asp_group": "restricted",
            },
        ]
    )
    user = SimpleNamespace(is_superuser=False, asp_ids=["allowed"], envs=[DEFAULT_ENVIRONMENT])
    result = service.navigation_counts_payload(user=user, profile_scope=DEFAULT_ENVIRONMENT)
    assert result["counts"] == {"dna:panel:solid": 0}


@pytest.mark.parametrize("is_superuser", [True, False])
@pytest.mark.parametrize("profile_scope", [DEFAULT_ENVIRONMENT, "all"])
@pytest.mark.parametrize(
    "family,group,expected_ids",
    [("panel", "hematology", ["panel"]), ("wgs", "hematology", ["wgs"]), ("wgs", "missing", [])],
)
def test_navigation_filter_uses_registry_groups_and_preserves_access_scope(
    is_superuser, profile_scope, family, group, expected_ids
):
    """Menu selections use the same normalized registry keys as their counts."""
    service = object.__new__(SampleCatalogService)
    page = Mock(return_value={"items": [], "total": 0})
    service.sample_repository = SimpleNamespace(get_samples_page=page)
    service.biomarker_repository = SimpleNamespace()
    service.assay_panel_repository = SimpleNamespace(
        get_all_asps=lambda: [
            {
                "asp_id": "panel",
                "asp_category": "DNA",
                "asp_family": "panel-dna",
                "asp_group": "Hematology",
            },
            {
                "asp_id": "wgs",
                "asp_category": "dna",
                "asp_family": "WGS",
                "asp_group": " hematology ",
            },
            {
                "asp_id": "restricted",
                "asp_category": "dna",
                "asp_family": "wgs",
                "asp_group": "solid",
            },
        ]
    )
    user = SimpleNamespace(
        is_superuser=is_superuser,
        asp_ids=[] if is_superuser else ["panel", "wgs"],
        asp_map={},
        envs=[DEFAULT_ENVIRONMENT, "validation"],
    )
    service.samples_payload(
        user=user,
        status="live",
        search_str="",
        search_mode="live",
        live_sort="",
        reported_sort="",
        page=1,
        per_page=30,
        live_page=1,
        per_live_page=30,
        done_page=1,
        per_done_page=30,
        profile_scope=profile_scope,
        panel_type="dna",
        panel_tech=family,
        assay_group=group,
    )
    expected_envs = (
        None
        if is_superuser and profile_scope == "all"
        else user.envs
        if profile_scope == "all"
        else [DEFAULT_ENVIRONMENT]
    )
    assert page.call_count == 2
    for call in page.call_args_list:
        assert call.kwargs["user_assays"] == expected_ids
        assert call.kwargs["user_envs"] == expected_envs


def test_navigation_filter_does_not_expose_unassigned_registry_assays():
    """A regular user's group selection remains restricted to assigned assay IDs."""
    service = object.__new__(SampleCatalogService)
    page = Mock(return_value={"items": [], "total": 0})
    service.sample_repository = SimpleNamespace(get_samples_page=page)
    service.biomarker_repository = SimpleNamespace()
    service.assay_panel_repository = SimpleNamespace(
        get_all_asps=lambda: [
            {
                "asp_id": "restricted",
                "asp_category": "dna",
                "asp_family": "wgs",
                "asp_group": "solid",
            },
        ]
    )
    service.samples_payload(
        user=SimpleNamespace(
            is_superuser=False, asp_ids=["allowed"], asp_map={}, envs=[DEFAULT_ENVIRONMENT]
        ),
        status="live",
        search_str="",
        search_mode="live",
        live_sort="",
        reported_sort="",
        page=1,
        per_page=30,
        live_page=1,
        per_live_page=30,
        done_page=1,
        per_done_page=30,
        profile_scope="all",
        panel_type="dna",
        panel_tech="wgs",
        assay_group="solid",
    )
    assert all(call.kwargs["user_assays"] == [] for call in page.call_args_list)
