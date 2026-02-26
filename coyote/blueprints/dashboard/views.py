#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#
from flask import render_template, request
from flask_login import login_required
from coyote.extensions import util
from coyote.blueprints.dashboard import dashboard_bp
from flask_login import current_user
from flask import current_app as app
from coyote.web_api.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@dashboard_bp.route("/", methods=["GET", "POST"])
@login_required
def dashboard() -> str:
    """
    Renders the dashboard page for the current user.

    This view aggregates and displays various statistics related to genomic samples,
    variants, and gene panels, including:
    - Total, analysed, and pending sample counts
    - User-specific sample statistics by assay
    - Variant statistics (total, unique, SNPs, CNVs, translocations, fusions, blacklist, false positives)
    - Unique gene counts across all panels
    - Gene counts per assay panel

    Results are cached for performance, and the user must be authenticated.
    """
    cache_timeout = app.config.get("CACHE_DEFAULT_TIMEOUT", 0)
    cache_key = util.dashboard.generate_dashboard_chache_key(current_user.username)

    if app.cache.get(cache_key):
        (
            total_samples_count,
            analysed_samples_count,
            pending_samples_count,
            user_samples_stats,
            variant_stats,
            unique_gene_count_all_panels,
            asp_gene_counts,
            sample_stats,
        ) = app.cache.get(cache_key)
        app.logger.info(f"Dashboard cache hit for {cache_key}")

    else:
        app.logger.info(f"Dashboard cache miss for {cache_key}")
        try:
            payload = get_web_api_client().get_dashboard_summary(
                headers=build_forward_headers(request.headers),
            )
            total_samples_count = payload.total_samples
            analysed_samples_count = payload.analysed_samples
            pending_samples_count = payload.pending_samples
            user_samples_stats = payload.user_samples_stats
            variant_stats = payload.variant_stats
            unique_gene_count_all_panels = payload.unique_gene_count_all_panels
            asp_gene_counts = payload.assay_gene_stats_grouped
            sample_stats = payload.sample_stats
        except ApiRequestError as exc:
            app.logger.error("Dashboard API fetch failed for user %s: %s", current_user.username, exc)
            total_samples_count = 0
            analysed_samples_count = 0
            pending_samples_count = 0
            user_samples_stats = []
            variant_stats = {}
            unique_gene_count_all_panels = 0
            asp_gene_counts = {}
            sample_stats = {}

    # Check if the cache exists and is still valid
    app.cache.set(
        cache_key,
        (
            total_samples_count,
            analysed_samples_count,
            pending_samples_count,
            user_samples_stats,
            variant_stats,
            unique_gene_count_all_panels,
            asp_gene_counts,
            sample_stats,
        ),
        timeout=cache_timeout,
    )

    # TODO: Add more stats here
    # Total Assays analysed
    # total_assay_count = 0

    # Variant Caller specific stats
    # class_stats = util.dashboard.format_classified_stats(
    #    store.annotation_handler.get_classified_stats()
    # )

    # assay_class_stats = util.dashboard.format_assay_classified_stats(
    #    store.annotation_handler.get_assay_classified_stats()
    # )

    return render_template(
        "dashboard.html",
        total_samples=total_samples_count,
        analysed_samples=analysed_samples_count,
        pending_samples=pending_samples_count,
        # class_stats_data=json.dumps(class_stats),
        # assay_class_stats_data=json.dumps(assay_class_stats),
        variant_stats=variant_stats,
        unique_gene_count_all_panels=unique_gene_count_all_panels,
        assay_gene_stats_grouped=asp_gene_counts,
        user_samples_stats=user_samples_stats,
        sample_stats=sample_stats,
    )
