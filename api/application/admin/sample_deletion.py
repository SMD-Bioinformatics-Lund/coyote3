"""Admin sample deletion service utilities."""

from __future__ import annotations

from api.contracts.operations import OperationResult


class SampleDeletionService:
    """Provide sample deletion workflows."""


def delete_all_sample_traces(
    sample_id: str,
    *,
    sample_repository,
    variant_repository,
    copy_number_variant_repository,
    coverage_repository,
    translocation_repository,
    fusion_repository,
    biomarker_repository,
) -> dict[str, object]:
    """Delete all persisted traces for a sample and return summary metadata."""
    sample = sample_repository.get_sample_by_id(sample_id) or {}
    actions = [
        variant_repository.delete_sample_variants,
        copy_number_variant_repository.delete_sample_cnvs,
        coverage_repository.delete_sample_coverage,
        translocation_repository.delete_sample_translocs,
        fusion_repository.delete_sample_fusions,
        biomarker_repository.delete_sample_biomarkers,
        sample_repository.delete_sample,
    ]
    results: list[dict[str, object]] = []
    for delete_action in actions:
        result = delete_action(sample_id)
        collection_name = delete_action.__name__.replace("delete_sample_", "")
        if collection_name == "delete_sample":
            collection_name = "sample"
        if isinstance(result, OperationResult):
            result_payload = result.to_dict()
        else:
            result_payload = {"ok": bool(result)}
        results.append(
            {
                "collection": collection_name,
                **result_payload,
            }
        )
    return {
        "sample_name": sample.get("name"),
        "results": results,
    }
