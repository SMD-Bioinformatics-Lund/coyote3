"""Admin sample deletion service utilities."""

from __future__ import annotations


class SampleDeletionService:
    """Provide sample deletion workflows."""


def delete_all_sample_traces(
    sample_id: str,
    *,
    sample_handler,
    variant_handler,
    copy_number_variant_handler,
    coverage_handler,
    translocation_handler,
    fusion_handler,
    biomarker_handler,
) -> dict[str, object]:
    """Delete all persisted traces for a sample and return summary metadata."""
    sample = sample_handler.get_sample_by_id(sample_id) or {}
    actions = [
        variant_handler.delete_sample_variants,
        copy_number_variant_handler.delete_sample_cnvs,
        coverage_handler.delete_sample_coverage,
        translocation_handler.delete_sample_translocs,
        fusion_handler.delete_sample_fusions,
        biomarker_handler.delete_sample_biomarkers,
        sample_handler.delete_sample,
    ]
    results: list[dict[str, object]] = []
    for handler in actions:
        result = handler(sample_id)
        collection_name = handler.__name__.replace("delete_sample_", "").replace("_handler", "")
        if collection_name == "delete_sample":
            collection_name = "sample"
        results.append(
            {
                "collection": collection_name,
                "ok": bool(result),
            }
        )
    return {
        "sample_name": sample.get("name"),
        "results": results,
    }
