"""Authenticated assay navigation is independent of public catalog publication."""

from types import SimpleNamespace

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
