"""Dashboard API routes."""

from copy import deepcopy

from fastapi import Depends

from coyote.extensions import store, util
from api.app import ApiUser, app, require_access


@app.get("/api/v1/dashboard/summary")
def dashboard_summary(user: ApiUser = Depends(require_access(min_level=1))):
    total_samples_count = store.sample_handler.get_all_sample_counts()
    analysed_samples_count = store.sample_handler.get_all_sample_counts(report=True)
    pending_samples_count = total_samples_count - analysed_samples_count

    user_samples_stats = store.sample_handler.get_assay_specific_sample_stats(assays=user.assays)

    variant_stats = {
        "total_variants": store.variant_handler.get_total_variant_counts(),
        "total_snps": store.variant_handler.get_total_snp_counts(),
        "total_cnvs": store.cnv_handler.get_total_cnv_count(),
        "total_translocs": store.transloc_handler.get_total_transloc_count(),
        "total_fusions": store.fusion_handler.get_total_fusion_count(),
        "blacklisted": store.blacklist_handler.get_unique_blacklist_count(),
        "fps": store.variant_handler.get_fp_counts(),
    }

    unique_gene_count_all_panels = store.asp_handler.get_all_asps_unique_gene_count()
    asp_gene_counts = store.asp_handler.get_all_asp_gene_counts()
    asp_gene_counts = util.dashboard.format_asp_gene_stats(deepcopy(asp_gene_counts))

    sample_stats = {
        "profiles": store.sample_handler.get_profile_counts(),
        "omics_layers": store.sample_handler.get_omics_counts(),
        "sequencing_scopes": store.sample_handler.get_sequencing_scope_counts(),
        "pair_count": store.sample_handler.get_paired_sample_counts(),
    }

    return util.common.convert_to_serializable(
        {
            "total_samples": total_samples_count,
            "analysed_samples": analysed_samples_count,
            "pending_samples": pending_samples_count,
            "user_samples_stats": user_samples_stats,
            "variant_stats": variant_stats,
            "unique_gene_count_all_panels": unique_gene_count_all_panels,
            "assay_gene_stats_grouped": asp_gene_counts,
            "sample_stats": sample_stats,
        }
    )

