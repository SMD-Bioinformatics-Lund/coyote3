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
from coyote.integrations.api.api_client import ApiRequestError, build_forward_headers, get_web_api_client


_DEFAULT_VARIANT_STATS = {
    "total_variants": 0,
    "total_snps": 0,
    "total_cnvs": 0,
    "total_translocs": 0,
    "total_fusions": 0,
    "blacklisted": 0,
    "fps": 0,
}

_DEFAULT_SAMPLE_STATS = {
    "profiles": {},
    "omics_layers": {},
    "sequencing_scopes": {},
    "pair_count": {},
}


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_variant_stats(stats: object) -> dict[str, int]:
    if not isinstance(stats, dict):
        return dict(_DEFAULT_VARIANT_STATS)
    normalized = dict(_DEFAULT_VARIANT_STATS)
    for key in normalized:
        normalized[key] = _as_int(stats.get(key), default=0)
    return normalized


def _normalize_sample_stats(stats: object) -> dict[str, dict]:
    if not isinstance(stats, dict):
        return dict(_DEFAULT_SAMPLE_STATS)

    normalized = {}
    for key, default in _DEFAULT_SAMPLE_STATS.items():
        value = stats.get(key, default)
        normalized[key] = value if isinstance(value, dict) else default
    return normalized


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

    cache_payload = None
    try:
        cache_payload = app.cache.get(cache_key)
    except Exception as exc:
        app.logger.warning("Dashboard cache read failed for %s: %s", cache_key, exc)

    if cache_payload:
        (
            total_samples_count,
            analysed_samples_count,
            pending_samples_count,
            user_samples_stats,
            variant_stats,
            unique_gene_count_all_panels,
            asp_gene_counts,
            sample_stats,
        ) = cache_payload
        app.logger.info(f"Dashboard cache hit for {cache_key}")
        if not isinstance(user_samples_stats, dict):
            app.logger.warning(
                "Dashboard cache payload has invalid user_samples_stats type (%s); resetting.",
                type(user_samples_stats).__name__,
            )
            user_samples_stats = {}
        variant_stats = _normalize_variant_stats(variant_stats)
        sample_stats = _normalize_sample_stats(sample_stats)

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
            user_samples_stats = {}
            variant_stats = dict(_DEFAULT_VARIANT_STATS)
            unique_gene_count_all_panels = 0
            asp_gene_counts = {}
            sample_stats = dict(_DEFAULT_SAMPLE_STATS)

    variant_stats = _normalize_variant_stats(variant_stats)
    sample_stats = _normalize_sample_stats(sample_stats)

    # Check if the cache exists and is still valid
    try:
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
    except Exception as exc:
        app.logger.warning("Dashboard cache write failed for %s: %s", cache_key, exc)

    return render_template(
        "dashboard.html",
        total_samples=total_samples_count,
        analysed_samples=analysed_samples_count,
        pending_samples=pending_samples_count,
        variant_stats=variant_stats,
        unique_gene_count_all_panels=unique_gene_count_all_panels,
        assay_gene_stats_grouped=asp_gene_counts,
        user_samples_stats=user_samples_stats,
        sample_stats=sample_stats,
    )
