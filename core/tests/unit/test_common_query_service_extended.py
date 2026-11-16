"""Extended behavior tests for shared query workflows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from coyote.application.common.query_service import CommonQueryService


def test_from_store_copies_required_and_optional_repositories() -> None:
    store = SimpleNamespace(
        hgnc_repository=object(),
        oncokb_repository=object(),
        variant_repository=object(),
        reported_variant_repository=object(),
        assay_panel_repository=object(),
        assay_configuration_repository=object(),
        annotation_repository=object(),
        sample_repository=object(),
        gene_list_repository=object(),
        bam_record_repository=object(),
    )
    service = CommonQueryService.from_store(store)
    assert service.hgnc_repository is store.hgnc_repository
    assert service.bam_record_repository is store.bam_record_repository
    assert service.civic_repository is None


@pytest.mark.parametrize(
    ("value", "present"),
    [(None, False), ({}, False), ([], False), ("", True), (0, True), ("value", True)],
)
def test_source_presence_and_available_source_sorting(value, present) -> None:
    assert CommonQueryService._source_present(value) is present
    sources = {"zeta": None, "beta": {"value": 1}, "alpha": [1]}
    assert CommonQueryService._available_sources(sources) == ["alpha", "beta"]
