from flask import current_app as app
from flask import render_template
from flask_login import current_user, login_required

from coyote.blueprints.dashboard import dashboard_bp
from coyote.extensions import util
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import raise_page_load_error

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
_DEFAULT_TIER_STATS = {
    "total": {"tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0},
    "by_assay": {},
}
_DEFAULT_QUALITY_STATS = {
    "analysed_rate_percent": 0.0,
    "fp_rate_percent": 0.0,
    "blacklist_rate_percent": 0.0,
}
_DEFAULT_DASHBOARD_META = {"timings_ms": {}, "scope_assays": None}
_DEFAULT_CAPACITY_COUNTS = {
    "users_total": 0,
    "roles_total": 0,
    "asps_total": 0,
    "aspcs_total": 0,
    "isgl_total": 0,
}
_DEFAULT_ISGL_VISIBILITY = {
    "public_total": 0,
    "adhoc_total": 0,
    "private_total": 0,
    "public_only": 0,
    "private_only": 0,
    "adhoc_only": 0,
    "public_private": 0,
    "public_adhoc": 0,
    "private_adhoc": 0,
    "public_private_adhoc": 0,
    "overlap_total": 0,
    "extra_visibility_counts": {},
}
_DEFAULT_ADMIN_INSIGHTS = {
    "counts": {},
    "role_user_counts": {},
    "profession_role_matrix": {},
    "isgl_venn": {},
}


def _as_int(value: object, default: int = 0) -> int:
    """Handle  as int.

    Args:
            value: Value.
            default: Default. Optional argument.

    Returns:
            The  as int result.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_variant_stats(stats: object) -> dict[str, int]:
    """Handle  normalize variant stats.

    Args:
            stats: Stats.

    Returns:
            The  normalize variant stats result.
    """
    if not isinstance(stats, dict):
        return dict(_DEFAULT_VARIANT_STATS)
    normalized = dict(_DEFAULT_VARIANT_STATS)
    for key in normalized:
        normalized[key] = _as_int(stats.get(key), default=0)
    return normalized


def _normalize_sample_stats(stats: object) -> dict[str, dict]:
    """Handle  normalize sample stats.

    Args:
            stats: Stats.

    Returns:
            The  normalize sample stats result.
    """
    if not isinstance(stats, dict):
        return dict(_DEFAULT_SAMPLE_STATS)

    normalized = {}
    for key, default in _DEFAULT_SAMPLE_STATS.items():
        value = stats.get(key, default)
        normalized[key] = value if isinstance(value, dict) else default
    return normalized


def _normalize_tier_stats(stats: object) -> dict:
    """Handle  normalize tier stats.

    Args:
            stats: Stats.

    Returns:
            The  normalize tier stats result.
    """
    if not isinstance(stats, dict):
        return dict(_DEFAULT_TIER_STATS)
    total = stats.get("total", {}) if isinstance(stats.get("total"), dict) else {}
    by_assay = stats.get("by_assay", {}) if isinstance(stats.get("by_assay"), dict) else {}
    return {
        "total": {
            "tier1": _as_int(total.get("tier1"), 0),
            "tier2": _as_int(total.get("tier2"), 0),
            "tier3": _as_int(total.get("tier3"), 0),
            "tier4": _as_int(total.get("tier4"), 0),
        },
        "by_assay": by_assay,
    }


def _normalize_quality_stats(stats: object) -> dict:
    """Handle  normalize quality stats.

    Args:
            stats: Stats.

    Returns:
            The  normalize quality stats result.
    """
    if not isinstance(stats, dict):
        return dict(_DEFAULT_QUALITY_STATS)
    return {
        "analysed_rate_percent": float(stats.get("analysed_rate_percent", 0.0) or 0.0),
        "fp_rate_percent": float(stats.get("fp_rate_percent", 0.0) or 0.0),
        "blacklist_rate_percent": float(stats.get("blacklist_rate_percent", 0.0) or 0.0),
    }


def _normalize_dashboard_meta(meta: object) -> dict:
    """Handle  normalize dashboard meta.

    Args:
            meta: Meta.

    Returns:
            The  normalize dashboard meta result.
    """
    if not isinstance(meta, dict):
        return dict(_DEFAULT_DASHBOARD_META)
    timings = meta.get("timings_ms", {})
    if not isinstance(timings, dict):
        timings = {}
    scope_assays = meta.get("scope_assays")
    if scope_assays is not None and not isinstance(scope_assays, list):
        scope_assays = []
    return {"timings_ms": timings, "scope_assays": scope_assays}


def _normalize_admin_insights(insights: object) -> dict:
    """Handle  normalize admin insights.

    Args:
            insights: Insights.

    Returns:
            The  normalize admin insights result.
    """
    if not isinstance(insights, dict):
        return dict(_DEFAULT_ADMIN_INSIGHTS)
    normalized = dict(_DEFAULT_ADMIN_INSIGHTS)
    for key in normalized:
        value = insights.get(key, normalized[key])
        normalized[key] = value if isinstance(value, dict) else normalized[key]
    return normalized


def _normalize_capacity_counts(counts: object) -> dict:
    """Handle  normalize capacity counts.

    Args:
            counts: Counts.

    Returns:
            The  normalize capacity counts result.
    """
    if not isinstance(counts, dict):
        return dict(_DEFAULT_CAPACITY_COUNTS)
    normalized = dict(_DEFAULT_CAPACITY_COUNTS)
    for key in normalized:
        normalized[key] = _as_int(counts.get(key), default=0)
    return normalized


def _normalize_isgl_visibility(payload: object) -> dict:
    """Handle  normalize isgl visibility.

    Args:
            payload: Payload.

    Returns:
            The  normalize isgl visibility result.
    """
    if not isinstance(payload, dict):
        return dict(_DEFAULT_ISGL_VISIBILITY)
    normalized = dict(_DEFAULT_ISGL_VISIBILITY)
    for key in normalized:
        if key == "extra_visibility_counts":
            value = payload.get(key, {})
            normalized[key] = value if isinstance(value, dict) else {}
        else:
            normalized[key] = _as_int(payload.get(key), default=0)
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
    username = getattr(current_user, "username", None) or current_user.get_id() or "anonymous"
    scope_assays = sorted(list(getattr(current_user, "assays", []) or []))
    scope_groups = sorted(list(getattr(current_user, "assay_groups", []) or []))
    scope_role = str(getattr(current_user, "role", "") or "")
    scope_fingerprint = f"v3|r={scope_role}|a={scope_assays}|g={scope_groups}"
    cache_key = util.dashboard.generate_dashboard_chache_key(username, scope=scope_fingerprint)

    cache_payload = None
    fetched_from_api_ok = False
    try:
        cache_payload = app.cache.get(cache_key)
    except Exception as exc:
        app.logger.warning("Dashboard cache read failed for %s: %s", cache_key, exc)

    if isinstance(cache_payload, dict):
        app.logger.info(f"Dashboard cache hit for {cache_key}")
        total_samples_count = _as_int(cache_payload.get("total_samples"), default=0)
        analysed_samples_count = _as_int(cache_payload.get("analysed_samples"), default=0)
        pending_samples_count = _as_int(cache_payload.get("pending_samples"), default=0)
        user_samples_stats = cache_payload.get("user_samples_stats", {})
        variant_stats = cache_payload.get("variant_stats", {})
        unique_gene_count_all_panels = _as_int(
            cache_payload.get("unique_gene_count_all_panels"), default=0
        )
        asp_gene_counts = cache_payload.get("assay_gene_stats_grouped", {})
        sample_stats = cache_payload.get("sample_stats", {})
        tier_stats = cache_payload.get("tier_stats", {})
        quality_stats = cache_payload.get("quality_stats", {})
        dashboard_meta = cache_payload.get("dashboard_meta", {})
        admin_insights = cache_payload.get("admin_insights", {})
        capacity_counts = cache_payload.get("capacity_counts", {})
        isgl_visibility = cache_payload.get("isgl_visibility", {})
    else:
        app.logger.info(f"Dashboard cache miss for {cache_key}")
        payload = None
        last_error = None
        forwarded_headers = forward_headers()
        for attempt in range(2):
            try:
                payload = get_web_api_client().get_json(
                    api_endpoints.dashboard("summary"),
                    headers=forwarded_headers,
                )
                break
            except ApiRequestError as exc:
                last_error = exc
                if attempt == 0:
                    # Retries help with transient cold-start/time-to-first-auth spikes right after login.
                    app.logger.warning(
                        "Dashboard summary fetch attempt %s failed for user %s (status=%s), retrying once.",
                        attempt + 1,
                        username,
                        exc.status_code,
                    )
                    forwarded_headers = forward_headers()

        try:
            if payload is None:
                raise last_error or ApiRequestError(message="Dashboard summary unavailable")
            fetched_from_api_ok = True
            total_samples_count = _as_int(payload.get("total_samples"), default=0)
            analysed_samples_count = _as_int(payload.get("analysed_samples"), default=0)
            pending_samples_count = _as_int(payload.get("pending_samples"), default=0)
            user_samples_stats = payload.get("user_samples_stats", {})
            variant_stats = payload.get("variant_stats", {})
            unique_gene_count_all_panels = _as_int(
                payload.get("unique_gene_count_all_panels"), default=0
            )
            asp_gene_counts = payload.get("assay_gene_stats_grouped", {})
            sample_stats = payload.get("sample_stats", {})
            tier_stats = payload.get("tier_stats", {})
            quality_stats = payload.get("quality_stats", {})
            dashboard_meta = payload.get("dashboard_meta", {})
            admin_insights = payload.get("admin_insights", {})
            capacity_counts = payload.get("capacity_counts", {})
            isgl_visibility = payload.get("isgl_visibility", {})
        except ApiRequestError as exc:
            raise_page_load_error(
                exc,
                logger=app.logger,
                log_message=f"Dashboard API fetch failed for user {username}",
                summary="Unable to load the dashboard.",
            )

    variant_stats = _normalize_variant_stats(variant_stats)
    sample_stats = _normalize_sample_stats(sample_stats)
    tier_stats = _normalize_tier_stats(tier_stats)
    quality_stats = _normalize_quality_stats(quality_stats)
    dashboard_meta = _normalize_dashboard_meta(dashboard_meta)
    admin_insights = _normalize_admin_insights(admin_insights)
    capacity_counts = _normalize_capacity_counts(capacity_counts)
    isgl_visibility = _normalize_isgl_visibility(isgl_visibility)

    # Only cache successful API payloads to avoid poisoning cache with fallback zeros.
    if fetched_from_api_ok:
        try:
            app.cache.set(
                cache_key,
                {
                    "total_samples": total_samples_count,
                    "analysed_samples": analysed_samples_count,
                    "pending_samples": pending_samples_count,
                    "user_samples_stats": user_samples_stats,
                    "variant_stats": variant_stats,
                    "unique_gene_count_all_panels": unique_gene_count_all_panels,
                    "assay_gene_stats_grouped": asp_gene_counts,
                    "sample_stats": sample_stats,
                    "tier_stats": tier_stats,
                    "quality_stats": quality_stats,
                    "dashboard_meta": dashboard_meta,
                    "admin_insights": admin_insights,
                    "capacity_counts": capacity_counts,
                    "isgl_visibility": isgl_visibility,
                },
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
        tier_stats=tier_stats,
        quality_stats=quality_stats,
        dashboard_meta=dashboard_meta,
        admin_insights=admin_insights,
        capacity_counts=capacity_counts,
        isgl_visibility=isgl_visibility,
    )
