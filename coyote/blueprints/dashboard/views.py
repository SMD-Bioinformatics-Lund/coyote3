from flask import current_app as app, render_template
from flask_login import login_required
from coyote.extensions import store, util
from coyote.blueprints.dashboard import dashboard_bp
import json
from collections import OrderedDict


@dashboard_bp.route("/", methods=["GET", "POST"])
@dashboard_bp.route("/dashboard/", methods=["GET", "POST"])
@dashboard_bp.route("", methods=["GET", "POST"])
@login_required
def dashboard() -> str:
    """
    Dashboard
    """
    total_samples_count = store.sample_handler.get_all_sample_counts()
    analysed_samples_count = store.sample_handler.get_all_sample_counts(report=True)
    pending_samples_count = store.sample_handler.get_all_sample_counts(report=False)

    assay_specific_stats = store.sample_handler.get_assay_specific_sample_stats()  # Change it back
    print(total_samples_count, analysed_samples_count, pending_samples_count)

    # Data for the charts based on assay
    total_samples_data = {
        assay: stats.get("total") for assay, stats in assay_specific_stats.items()
    }
    analysed_samples_data = {
        assay: stats.get("report") for assay, stats in assay_specific_stats.items()
    }
    pending_samples_data = {
        assay: stats.get("total") - stats.get("report")
        for assay, stats in assay_specific_stats.items()
    }

    class_stats = util.dashboard.format_classified_stats(
        store.annotation_handler.get_classified_stats()
    )
    assay_class_stats = util.dashboard.format_assay_classified_stats(
        store.annotation_handler.get_assay_classified_stats()
    )

    # Get total variants in the db
    total_variant_counts = store.variant_handler.get_total_variant_counts()  # Change it back
    # Get all unique variants
    # unique_variant_counts = (
    #     store.variant_handler.get_unique_total_variant_counts()
    # )  # Change it back
    unique_variant_counts = 12

    # get unique variants Snps
    # unique_snps_counts = store.variant_handler.get_unique_snp_count() # Change it back
    unique_snps_counts = 10

    # get unique CNVs
    unique_cnv_counts: int = store.cnv_handler.get_unique_cnv_count()
    # get unique Translocations
    unique_transloc_counts: int = store.transloc_handler.get_unique_transloc_count()

    # get unique RNA fusions
    unique_fusion_counts: int = store.fusion_handler.get_unique_fusion_count()

    # Get total blacklisted variants
    unique_blacklist_counts: int = store.blacklist_handler.get_unique_blacklist_count()

    # Get total False positive variants
    # unique_fp_counts: int = store.variant_handler.get_unique_fp_count()  # Change it back
    unique_fp_counts: int = 10

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
