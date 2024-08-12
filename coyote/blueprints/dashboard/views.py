from flask import current_app as app, render_template
from flask_login import login_required
from coyote.extensions import store, util
from coyote.blueprints.dashboard import dashboard_bp
import json


@dashboard_bp.route("/", methods=["GET", "POST"])
@dashboard_bp.route("/dashboard/", methods=["GET", "POST"])
@dashboard_bp.route("", methods=["GET", "POST"])
@login_required
def dashboard() -> str:
    """
    Dashboard
    """
    total_samples = store.sample_handler.get_all_samples()
    analysed_samples = store.sample_handler.get_all_samples(report=True)
    pending_samples = store.sample_handler.get_all_samples(report=False)
    assay_specific_stats = store.sample_handler.get_assay_specific_sample_stats()

    total_samples_count = len(total_samples)
    analysed_samples_count = len(analysed_samples)
    pending_samples_count = len(pending_samples)

    # Data for the charts based on assay
    total_samples_data = {assay: stats["total"] for assay, stats in assay_specific_stats.items()}
    analysed_samples_data = {
        assay: stats["report"] for assay, stats in assay_specific_stats.items()
    }
    pending_samples_data = {
        assay: stats["total"] - stats["report"] for assay, stats in assay_specific_stats.items()
    }

    # Get all classifications
    classified_annotations = util.dashboard.convert_annotations_to_hashable(
        store.annotation_handler.get_all_classified_variants()
    )
    class_stats, assay_class_stats = util.dashboard.get_classified_variant_stats(
        classified_annotations
    )

    # Get total variants in the db
    total_variant_counts = store.variant_handler.get_total_variant_counts()
    # Get all unique variants
    unique_variant_counts = store.variant_handler.get_unique_total_variant_counts()

    # get unique variants Snps
    unique_snps_counts = store.variant_handler.get_unique_snp_count()

    # get unique CNVs
    unique_cnv_counts: int = store.cnv_handler.get_unique_cnv_count()

    # get unique Translocations
    unique_transloc_counts: int = store.transloc_handler.get_unique_transloc_count()

    # get unique RNA fusions
    unique_fusion_counts: int = store.fusion_handler.get_unique_fusion_count()

    # Get total blacklisted variants
    unique_blacklist_counts: int = store.blacklist_handler.get_unique_blacklist_count()

    # Get total False positive variants
    unique_fp_counts: int = store.variant_handler.get_unique_fp_count()

    # Get total genes analysed from all the panels
    unique_gene_count_all_panels = store.panel_handler.get_unique_all_panel_gene_count()

    # Get gene counts in each panel
    assay_gene_counts = store.panel_handler.get_assay_gene_counts()
    genelist_gene_counts = store.panel_handler.get_genelist_gene_counts()

    # Total Assays analysed
    total_assay_count = store.group_handler.get_total_group_count()

    # Variant Caller specific stats

    return render_template(
        "dashboard.html",
        total_samples=total_samples_count,
        analysed_samples=analysed_samples_count,
        pending_samples=pending_samples_count,
        total_samples_data=total_samples_data,
        analysed_samples_data=analysed_samples_data,
        pending_samples_data=pending_samples_data,
        class_stats_data=json.dumps(class_stats),
        assay_class_stats_data=json.dumps(assay_class_stats),
        unique_variant_counts=unique_variant_counts,
        unique_snps_counts=unique_snps_counts,
        unique_cnv_counts=unique_cnv_counts,
        unique_transloc_counts=unique_transloc_counts,
        unique_fusion_counts=unique_fusion_counts,
        unique_blacklist_counts=unique_blacklist_counts,
        unique_fp_counts=unique_fp_counts,
        total_variant_counts=total_variant_counts,
        unique_gene_count_all_panels=unique_gene_count_all_panels,
        total_assay_count=total_assay_count,
        assay_gene_counts=assay_gene_counts,
        genelist_gene_counts=genelist_gene_counts,
    )
