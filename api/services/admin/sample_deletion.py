"""Admin sample deletion service utilities."""

from __future__ import annotations

from api.extensions import store


def delete_all_sample_traces(sample_id: str) -> dict[str, object]:
    """Delete all persisted traces for a sample and return summary metadata."""
    sample = store.sample_handler.get_sample_by_id(sample_id) or {}
    actions = [
        store.variant_handler.delete_sample_variants,
        store.cnv_handler.delete_sample_cnvs,
        store.coverage_handler.delete_sample_coverage,
        store.coverage2_handler.delete_sample_coverage,
        store.transloc_handler.delete_sample_translocs,
        store.fusion_handler.delete_sample_fusions,
        store.biomarker_handler.delete_sample_biomarkers,
        store.sample_handler.delete_sample,
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

