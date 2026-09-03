"""Dashboard workflow service."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from api.domain.common.dashboard import (
    format_asp_gene_stats,
    format_panel_gene_stats,
    panel_asp_ids,
    summarize_panel_gene_stats,
)
from api.domain.core.repository_protocols import (
    AssayConfigurationRepositoryProtocol,
    SampleRepositoryProtocol,
    VariantsRepositoryProtocol,
)
from api.infra.dashboard_metric_cache import DASHBOARD_METRICS, DashboardMetricCache
from api.infra.observability.operations import measured_operation


class DashboardService:
    """Provide dashboard workflows."""

    @classmethod
    def from_store(cls, store: Any, *, config: dict | None = None) -> "DashboardService":
        """Build the service from the runtime store."""
        return cls(
            user_repository=store.user_repository,
            roles_repository=store.roles_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            gene_list_repository=store.gene_list_repository,
            sample_repository=store.sample_repository,
            variant_repository=store.variant_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            translocation_repository=store.translocation_repository,
            fusion_repository=store.fusion_repository,
            blacklist_repository=store.blacklist_repository,
            annotation_repository=store.annotation_repository,
            reported_variant_repository=store.reported_variant_repository,
            cache=getattr(getattr(store, "app", None), "cache", None),
            config=config,
        )

    def __init__(
        self,
        *,
        user_repository: Any,
        roles_repository: Any,
        assay_panel_repository: Any,
        assay_configuration_repository: AssayConfigurationRepositoryProtocol,
        gene_list_repository: Any,
        sample_repository: SampleRepositoryProtocol,
        variant_repository: VariantsRepositoryProtocol,
        copy_number_variant_repository: Any,
        translocation_repository: Any,
        fusion_repository: Any,
        blacklist_repository: Any,
        annotation_repository: Any,
        reported_variant_repository: Any,
        cache: Any | None,
        config: dict | None = None,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.user_repository = user_repository
        self.roles_repository = roles_repository
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.gene_list_repository = gene_list_repository
        self.sample_repository = sample_repository
        self.variant_repository = variant_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.translocation_repository = translocation_repository
        self.fusion_repository = fusion_repository
        self.blacklist_repository = blacklist_repository
        self.annotation_repository = annotation_repository
        self.reported_variant_repository = reported_variant_repository
        self.config = config or {}
        self.metric_cache = (
            DashboardMetricCache(
                cache,
                fresh_seconds=int(
                    self.config.get("DASHBOARD_METRIC_CACHE_TTL_SECONDS", 300) or 300
                ),
                retention_seconds=int(
                    self.config.get("DASHBOARD_METRIC_CACHE_RETENTION_SECONDS", 3600) or 3600
                ),
            )
            if cache is not None
            else None
        )

    @staticmethod
    def _scope_key(*, user, scope_assays: list[str] | None) -> str:
        """Build a stable cache key for metrics affected by authorization scope."""
        payload = {
            "roles": sorted(
                {
                    str(value or "").strip().lower()
                    for value in [getattr(user, "role", ""), *(getattr(user, "roles", []) or [])]
                    if str(value or "").strip()
                }
            ),
            "assays": sorted(scope_assays) if isinstance(scope_assays, list) else None,
        }
        import json

        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()  # noqa: S324

    def build_capacity_counts(self) -> dict[str, int]:
        """Return top-level admin capacity counts for the dashboard.

        Returns:
            dict[str, int]: Aggregate counts for major managed resources.
        """
        return {
            "users_total": int(self.user_repository.count_users() or 0),
            "roles_total": int(self.roles_repository.count_roles() or 0),
            "asps_total": int(self.assay_panel_repository.count_asps() or 0),
            "aspcs_total": int(self.assay_configuration_repository.count_aspcs() or 0),
            "isgl_total": int(self.gene_list_repository.count_isgls() or 0),
        }

    def build_isgl_visibility(self, isgls: list[dict] | None = None) -> dict[str, Any]:
        """Return ISGL visibility rollups for the dashboard.

        Args:
            isgls: Optional pre-fetched ISGL rows.

        Returns:
            dict[str, Any]: Visibility counts grouped by exposure mode.
        """
        if isgls is None:
            return dict(self.gene_list_repository.get_dashboard_visibility_rollup() or {})
        rows = isgls
        public_total = private_total = adhoc_total = 0
        public_only = private_only = adhoc_only = 0
        public_private = public_adhoc = private_adhoc = public_private_adhoc = 0
        extra_visibility_counts: dict[str, int] = {}

        for isgl_doc in rows:
            is_public = bool(isgl_doc.get("is_public", False))
            is_private = bool(isgl_doc.get("is_private", not is_public))
            is_adhoc = bool(isgl_doc.get("adhoc", False))
            if is_public:
                public_total += 1
            if is_private:
                private_total += 1
            if is_adhoc:
                adhoc_total += 1

            if is_public and not is_private and not is_adhoc:
                public_only += 1
            elif is_private and not is_public and not is_adhoc:
                private_only += 1
            elif is_adhoc and not is_public and not is_private:
                adhoc_only += 1
            elif is_public and is_private and not is_adhoc:
                public_private += 1
            elif is_public and is_adhoc and not is_private:
                public_adhoc += 1
            elif is_private and is_adhoc and not is_public:
                private_adhoc += 1
            elif is_public and is_private and is_adhoc:
                public_private_adhoc += 1
            else:
                if is_public:
                    public_only += 1
                elif is_private:
                    private_only += 1
                elif is_adhoc:
                    adhoc_only += 1

            for key, value in isgl_doc.items():
                key_str = str(key or "").strip().lower()
                if key_str in {"is_public", "is_private", "is_active", "adhoc"}:
                    continue
                if key_str.startswith("is_") and isinstance(value, bool) and value:
                    extra_visibility_counts[key_str] = extra_visibility_counts.get(key_str, 0) + 1

        return {
            "public_total": public_total,
            "adhoc_total": adhoc_total,
            "private_total": private_total,
            "public_only": public_only,
            "private_only": private_only,
            "adhoc_only": adhoc_only,
            "public_private": public_private,
            "public_adhoc": public_adhoc,
            "private_adhoc": private_adhoc,
            "public_private_adhoc": public_private_adhoc,
            "overlap_total": public_private + public_adhoc + private_adhoc + public_private_adhoc,
            "extra_visibility_counts": extra_visibility_counts,
        }

    def build_admin_insights(self) -> dict[str, Any]:
        """Return administrative dashboard insights and counts.

        Returns:
            dict[str, Any]: Aggregate user, role, assay, and visibility insights.
        """
        users_rollup = dict(self.user_repository.get_dashboard_user_rollup() or {})
        isgl_rollup = dict(self.gene_list_repository.get_dashboard_visibility_rollup() or {})
        return {
            "counts": {
                "users_total": int(users_rollup.get("users_total", 0) or 0),
                "users_active": int(users_rollup.get("users_active", 0) or 0),
                "roles_total": int(self.roles_repository.count_roles() or 0),
                "roles_active": int(self.roles_repository.count_roles(is_active=True) or 0),
                "asps_total": int(self.assay_panel_repository.count_asps() or 0),
                "asps_active": int(self.assay_panel_repository.count_asps(is_active=True) or 0),
                "aspcs_total": int(self.assay_configuration_repository.count_aspcs() or 0),
                "aspcs_active": int(
                    self.assay_configuration_repository.count_aspcs(is_active=True) or 0
                ),
                "isgl_total": int(self.gene_list_repository.count_isgls() or 0),
                "isgl_active": int(self.gene_list_repository.count_isgls(is_active=True) or 0),
            },
            "role_user_counts": users_rollup.get("role_user_counts", {}),
            "profession_role_matrix": users_rollup.get("profession_role_matrix", {}),
            "isgl_venn": isgl_rollup,
        }

    def resolve_scope_assays(self, *, user) -> list[str] | None:
        """Resolve the assays visible to a dashboard user.

        Args:
            user: Authenticated dashboard user.

        Returns:
            list[str] | None: Scoped assay identifiers, or ``None`` for global access.
        """
        try:
            fresh_user_doc = self.user_repository.user_with_id(str(user.id)) or {}
        except Exception:
            fresh_user_doc = {}

        effective_roles = [
            str(role_id or "").strip().lower()
            for role_id in (fresh_user_doc.get("roles") or user.roles)
        ]
        if "superuser" in effective_roles:
            return None

        scoped_assays = (
            fresh_user_doc.get("asp_ids")
            if isinstance(fresh_user_doc.get("asp_ids"), list)
            else user.asp_ids
        )
        scoped_groups = (
            fresh_user_doc.get("asp_groups")
            if isinstance(fresh_user_doc.get("asp_groups"), list)
            else user.asp_groups
        )

        user_assays = {str(item).strip() for item in (scoped_assays or []) if str(item).strip()}
        user_groups = {str(item).strip() for item in (scoped_groups or []) if str(item).strip()}
        if not user_assays and not user_groups:
            return []

        effective_assays = set(user_assays)
        for asp_id in (
            self.assay_panel_repository.resolve_active_asp_ids_for_scope(
                asp_ids=sorted(user_assays),
                groups=sorted(user_groups),
            )
            or []
        ):
            if asp_id:
                effective_assays.add(str(asp_id).strip())
        return sorted(effective_assays)

    def metric_scope_key(self, metric: str, *, user) -> str:
        """Return the cache scope for a metric."""
        if metric not in {"samples", "resources"}:
            return "global"
        scope_assays = self.resolve_scope_assays(user=user)
        return self._scope_key(user=user, scope_assays=scope_assays)

    def build_samples_metric(self, *, user) -> dict[str, Any]:
        """Build sample workload and composition metrics for the user's assay scope."""
        sample_rollup_global = self.sample_repository.get_dashboard_sample_rollup(asp_ids=None)
        scope_assays = self.resolve_scope_assays(user=user)
        sample_rollup_scoped = self.sample_repository.get_dashboard_sample_rollup(
            asp_ids=scope_assays
        )
        total = int(sample_rollup_global.get("total_samples", 0) or 0)
        analysed = int(sample_rollup_global.get("analysed_samples", 0) or 0)
        scoped_total = int(sample_rollup_scoped.get("total_samples", 0) or 0)
        scoped_analysed = int(sample_rollup_scoped.get("analysed_samples", 0) or 0)
        return {
            "total_samples": total,
            "analysed_samples": analysed,
            "pending_samples": int(sample_rollup_global.get("pending_samples", 0) or 0),
            "sample_stats": sample_rollup_global.get("sample_stats", {}) or {},
            "user_samples_stats": sample_rollup_scoped.get("user_samples_stats", {}) or {},
            "user_scope_summary": {
                "total_samples": scoped_total,
                "analysed_samples": scoped_analysed,
                "pending_samples": int(sample_rollup_scoped.get("pending_samples", 0) or 0),
                "analysed_rate_percent": (
                    round((scoped_analysed / scoped_total) * 100, 2) if scoped_total else 0.0
                ),
                "recent_samples": sample_rollup_scoped.get("recent_samples", []) or [],
                "sample_stats": sample_rollup_scoped.get("sample_stats", {}) or {},
            },
            "quality_stats": {
                "analysed_rate_percent": round((analysed / total) * 100, 2) if total else 0.0
            },
            "dashboard_meta": {"scope_assays": scope_assays},
        }

    def build_findings_metric(self) -> dict[str, Any]:
        """Build finding inventory, classification, and quality metrics."""
        variant_rollup = self.variant_repository.get_dashboard_variant_counts()
        total_cnvs = int(self.copy_number_variant_repository.get_total_cnv_count() or 0)
        total_translocs = int(self.translocation_repository.get_total_transloc_count() or 0)
        total_fusions = int(self.fusion_repository.get_total_fusion_count() or 0)
        unique_blacklisted_variants = int(
            self.blacklist_repository.get_unique_blacklist_count() or 0
        )
        tier_stats = self.annotation_repository.get_dashboard_classification_stats()
        reported_tier_stats = self.reported_variant_repository.get_dashboard_tier_stats()
        tier_total = tier_stats.get("total", {}) if isinstance(tier_stats, dict) else {}
        tier1 = int(tier_total.get("tier1", tier_total.get("tier_1", 0)) or 0)
        tier2 = int(tier_total.get("tier2", tier_total.get("tier_2", 0)) or 0)
        tier3 = int(tier_total.get("tier3", tier_total.get("tier_3", 0)) or 0)
        tier4 = int(tier_total.get("tier4", tier_total.get("tier_4", 0)) or 0)
        reported_tier_total = (
            reported_tier_stats.get("total", {}) if isinstance(reported_tier_stats, dict) else {}
        )
        reported_findings = sum(
            int(
                reported_tier_total.get(
                    key, reported_tier_total.get(key.replace("tier", "tier_"), 0)
                )
                or 0
            )
            for key in ("tier1", "tier2", "tier3", "tier4")
        )

        total_small_variants = int(variant_rollup.get("total_variants", 0) or 0)
        total_snv_like = int(
            variant_rollup.get("snv")
            or variant_rollup.get("small_variants")
            or total_small_variants
            or 0
        )
        total_fp = int(variant_rollup.get("fps", 0) or 0)
        variant_stats = {
            "total_variants": total_small_variants,
            "snv": total_snv_like,
            "small_variants": total_snv_like,
            "snps": int(variant_rollup.get("total_snps", 0) or 0),
            "cnv": int(total_cnvs or 0),
            "cnvs": int(total_cnvs or 0),
            "fusion": int(total_fusions or 0),
            "fusions": int(total_fusions or 0),
            "translocation": int(total_translocs or 0),
            "translocations": int(total_translocs or 0),
            "blacklisted": int(unique_blacklisted_variants or 0),
            "fps": total_fp,
            "false_positives": total_fp,
            "reported_findings": reported_findings,
            "tier1_or_2": tier1 + tier2,
            "vus": tier3,
            "pathogenic": tier1 + tier2,
            "tier4": tier4,
            "by_variant_class": variant_rollup.get("by_variant_class", {}) or {},
        }

        fp_rate = round((total_fp / total_small_variants) * 100, 2) if total_small_variants else 0.0
        return {
            "variant_stats": variant_stats,
            "tier_stats": tier_stats,
            "reported_tier_stats": reported_tier_stats,
            "quality_stats": {"fp_rate_percent": fp_rate},
        }

    def build_top_tiered_genes_metric(self) -> dict[str, Any]:
        """Build the independently refreshable top-tiered-gene ranking."""
        return {
            "top_tiered_genes": self.annotation_repository.get_dashboard_top_tiered_genes(limit=15)
            or []
        }

    def build_panels_metric(self) -> dict[str, Any]:
        """Build targeted-panel coverage and analysis-capability metrics."""
        asp_gene_stats = self.assay_panel_repository.get_all_asp_gene_counts()
        targeted_panel_ids = panel_asp_ids(asp_gene_stats)
        return {
            "unique_gene_count_all_panels": int(
                self.assay_panel_repository.get_all_asps_unique_gene_count() or 0
            ),
            "assay_gene_stats_grouped": format_asp_gene_stats(asp_gene_stats),
            "panel_gene_stats_grouped": format_panel_gene_stats(asp_gene_stats),
            "panel_portfolio": summarize_panel_gene_stats(asp_gene_stats),
            "panel_analysis_capabilities": self.assay_configuration_repository.get_dashboard_analysis_type_rollup(
                asp_ids=targeted_panel_ids
            ),
        }

    def build_clinical_configuration_metric(self) -> dict[str, Any]:
        """Build gene-list visibility and assay-association metrics."""
        return {
            "isgl_visibility": self.build_isgl_visibility(),
            "isgl_association": self.gene_list_repository.get_dashboard_assay_association_rollup()
            or {},
        }

    def build_resources_metric(self, *, user) -> dict[str, Any]:
        """Build managed-resource totals and authorized administrative insights."""
        payload: dict[str, Any] = {
            "capacity_counts": self.build_capacity_counts(),
            "admin_insights": {},
        }
        if "superuser" in {str(role_id or "").strip().lower() for role_id in (user.roles or [])}:
            payload["admin_insights"] = self.build_admin_insights()
        return payload

    def _build_metric(self, metric: str, *, user) -> dict[str, Any]:
        builders = {
            "samples": lambda: self.build_samples_metric(user=user),
            "findings": self.build_findings_metric,
            "top_tiered_genes": self.build_top_tiered_genes_metric,
            "panels": self.build_panels_metric,
            "clinical_configuration": self.build_clinical_configuration_metric,
            "resources": lambda: self.build_resources_metric(user=user),
        }
        if metric not in builders:
            raise ValueError(f"Unknown dashboard metric: {metric}")
        return builders[metric]()

    @measured_operation("query.dashboard_metric")
    def metric_payload(self, metric: str, *, user, force: bool = False) -> dict[str, Any]:
        """Return one metric with cache metadata, computing it when no cache exists."""
        if metric not in DASHBOARD_METRICS:
            raise ValueError(f"Unknown dashboard metric: {metric}")
        scope_key = self.metric_scope_key(metric, user=user)
        cached = self.metric_cache.read(metric, scope_key=scope_key) if self.metric_cache else None
        if cached is not None and not force:
            payload = dict(cached.payload)
            payload["metric_meta"] = {
                "metric": metric,
                "generated_at": cached.generated_at.isoformat(),
                "stale": cached.stale,
                "cache_hit": True,
            }
            return payload

        payload = self._build_metric(metric, user=user)
        generated_at = datetime.now(timezone.utc)
        if self.metric_cache:
            generated_at = self.metric_cache.write(metric, payload, scope_key=scope_key)
        payload["metric_meta"] = {
            "metric": metric,
            "generated_at": generated_at.isoformat(),
            "stale": False,
            "cache_hit": False,
        }
        return payload

    def acquire_metric_refresh(self, metric: str, *, user) -> bool:
        """Acquire a short distributed lock before queueing stale metric refresh."""
        if not self.metric_cache:
            return False
        return self.metric_cache.acquire_refresh(
            metric, scope_key=self.metric_scope_key(metric, user=user)
        )

    def release_metric_refresh(self, metric: str, *, user) -> None:
        if self.metric_cache:
            self.metric_cache.release_refresh(
                metric, scope_key=self.metric_scope_key(metric, user=user)
            )
