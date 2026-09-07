"""Transactional deletion of sample-owned data, retaining shared clinical knowledge."""

from api.contracts.operations import OperationResult
from api.domain.core.exceptions import AppError
from api.infra.mongo.persistence import to_provider_id
from api.infra.mongo.transactions import run_transaction
from api.infra.samples_cache import invalidate_samples_cache


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
    pgx_repository,
    rna_expression_repository,
    rna_classification_repository,
    rna_quality_repository,
    sample_comment_repository,
    finding_comment_repository,
    report_repository,
    reported_variant_repository,
) -> dict[str, object]:
    """Delete the sample anchor and every owned collection in a single commit.

    Shared annotation, reference data, audit records, and report artifacts are retained.
    ``sample_oid`` contracts permit provider IDs and their serialized representation.
    """
    oid = to_provider_id(sample_id)
    sample_key = {"SAMPLE_ID": str(sample_id)}
    reference_key = {"sample_oid": {"$in": [oid, str(sample_id)]}}
    owned = [
        ("variants", variant_repository, sample_key),
        ("cnvs", copy_number_variant_repository, sample_key),
        ("coverage", coverage_repository, sample_key),
        ("translocs", translocation_repository, sample_key),
        ("fusions", fusion_repository, sample_key),
        ("biomarkers", biomarker_repository, sample_key),
        ("pgx", pgx_repository, sample_key),
        ("expression", rna_expression_repository, sample_key),
        ("classification", rna_classification_repository, sample_key),
        ("qc", rna_quality_repository, sample_key),
        ("comments", sample_comment_repository, reference_key),
        ("finding_comments", finding_comment_repository, reference_key),
        ("reported_variants", reported_variant_repository, reference_key),
        ("reports", report_repository, reference_key),
    ]

    def delete(session):
        sample = sample_repository.get_collection().find_one_and_delete(
            {"_id": oid}, session=session
        )
        if sample is None:
            raise AppError(404, "Sample no longer exists.")
        results = []
        for name, repository, selector in owned:
            result = repository.get_collection().delete_many(selector, session=session)
            results.append({"collection": name, **OperationResult.from_delete(result).to_dict()})
        results.append({"collection": "sample", **OperationResult(deleted_count=1).to_dict()})
        return {"sample_name": sample.get("name"), "results": results}

    result = run_transaction(sample_repository.adapter.client, delete)
    try:
        invalidate_samples_cache(sample_repository.adapter)
        for repository in [sample_repository, *(item[1] for item in owned)]:
            repository.invalidate_dashboard_metrics()
    except Exception:
        sample_repository.app.logger.exception(
            "Sample deletion committed; cache invalidation failed"
        )
    return result
