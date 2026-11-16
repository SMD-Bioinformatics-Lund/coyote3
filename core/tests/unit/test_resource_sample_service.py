"""ResourceSampleService behavior at persistence and API boundaries."""

from types import SimpleNamespace
from unittest.mock import Mock

from coyote.application.resources.sample import ResourceSampleService


def test_from_store_wires_all_repositories() -> None:
    repositories = {
        name: object()
        for name in (
            "sample_repository",
            "variant_repository",
            "copy_number_variant_repository",
            "d4_coverage_repository",
            "translocation_repository",
            "fusion_repository",
            "biomarker_repository",
            "pgx_repository",
            "rna_expression_repository",
            "rna_classification_repository",
            "rna_quality_repository",
            "sample_comment_repository",
            "finding_comment_repository",
            "report_repository",
            "reported_variant_repository",
            "assay_panel_repository",
        )
    }
    service = ResourceSampleService.from_store(
        SimpleNamespace(**repositories), sample_deleter=Mock()
    )

    for name in ("sample_repository", "assay_panel_repository"):
        assert getattr(service, name) is repositories[name]
