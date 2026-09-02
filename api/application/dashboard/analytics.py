"""Dashboard workflow service."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
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
from api.infra.observability.operations import measured_operation


class DashboardSnapshotUnavailable(RuntimeError):
    """Raised when no background-generated dashboard snapshot exists yet."""


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
            dashboard_metrics_repository=store.dashboard_metrics_repository,
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
        dashboard_metrics_repository: Any | None,
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
        self.dashboard_metrics_repository = dashboard_metrics_repository
        self.config = config or {}

    @staticmethod
    def _summary_scope_key(*, user, scope_assays: list[str] | None) -> str:
        """Build a stable key for a user's materialized dashboard summary."""
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
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()  # noqa: S324

    def _snapshot_max_age_seconds(self) -> int:
        """Return persisted summary staleness threshold."""
        return int(self.config.get("DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS", 300) or 300)

    def _read_dashboard_summary_snapshot(self, *, scope_key: str) -> dict | None:
        """Read the latest persisted summary snapshot, including stale snapshots."""
        if self.dashboard_metrics_repository is None:
            return None

        doc = self.dashboard_metrics_repository.get_summary_snapshot(scope_key=scope_key)
        if not isinstance(doc, dict):
            return None
        payload = doc.get("payload")
        updated_at = doc.get("updated_at")
        if not isinstance(payload, dict) or not isinstance(updated_at, datetime):
            return None
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_seconds = max(0.0, (datetime.now(timezone.utc) - updated_at).total_seconds())
        dirty_since = doc.get("dirty_since")
        result = deepcopy(payload)
        meta = result.setdefault("dashboard_meta", {})
        meta.update(
            {
                "snapshot_updated_at": updated_at.isoformat(),
                "snapshot_age_seconds": round(age_seconds, 1),
                "snapshot_stale": bool(
                    dirty_since is not None or age_seconds > self._snapshot_max_age_seconds()
                ),
                "snapshot_dirty": dirty_since is not None,
            }
        )
        return result

    def _write_dashboard_summary_snapshot(self, *, scope_key: str, payload: dict) -> None:
        """Persist summary snapshot payload."""
        if self.dashboard_metrics_repository is None:
            return
        self.dashboard_metrics_repository.upsert_summary_snapshot(
            scope_key=scope_key, payload=payload
        )

    def summary_scope_key(self, *, user) -> str:
        """Return the persisted snapshot key for an authenticated user."""
        scope_assays = self.resolve_scope_assays(user=user)
        return self._summary_scope_key(user=user, scope_assays=scope_assays)

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

    def summary_payload(self, *, user) -> dict[str, Any]:
        """Return a background-generated dashboard summary without aggregating data.

        Args:
            user: Authenticated dashboard user.

        Returns:
            dict[str, Any]: Persisted dashboard summary with freshness metadata.

        Raises:
            DashboardSnapshotUnavailable: No background snapshot exists for the user scope.
        """
        scope_assays = self.resolve_scope_assays(user=user)
        scope_key = self._summary_scope_key(user=user, scope_assays=scope_assays)
        snapshot_payload = self._read_dashboard_summary_snapshot(scope_key=scope_key)
        if isinstance(snapshot_payload, dict):
            return snapshot_payload

        raise DashboardSnapshotUnavailable(
            "Dashboard metrics are being prepared. Refresh the metrics now or try again shortly."
        )

    def build_shared_summary_payload(self) -> dict[str, Any]:
        """Build metrics that are identical for every dashboard authorization scope."""
        sample_rollup_global = self.sample_repository.get_dashboard_sample_rollup(asp_ids=None)
        variant_rollup = self.variant_repository.get_dashboard_variant_counts()
        total_cnvs = int(self.copy_number_variant_repository.get_total_cnv_count() or 0)
        total_translocs = int(self.translocation_repository.get_total_transloc_count() or 0)
        total_fusions = int(self.fusion_repository.get_total_fusion_count() or 0)
        unique_blacklisted_variants = int(
            self.blacklist_repository.get_unique_blacklist_count() or 0
        )
        tier_stats = self.annotation_repository.get_dashboard_classification_stats()
        top_tiered_genes = self.annotation_repository.get_dashboard_top_tiered_genes(limit=15)
        reported_tier_stats = self.reported_variant_repository.get_dashboard_tier_stats()

        total_samples_count = int(sample_rollup_global.get("total_samples", 0) or 0)
        analysed_samples_count = int(sample_rollup_global.get("analysed_samples", 0) or 0)
        pending_samples_count = int(sample_rollup_global.get("pending_samples", 0) or 0)
        sample_stats = sample_rollup_global.get("sample_stats", {})
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

        analysed_rate = (
            round((analysed_samples_count / total_samples_count) * 100, 2)
            if total_samples_count
            else 0.0
        )
        fp_rate = round((total_fp / total_small_variants) * 100, 2) if total_small_variants else 0.0
        asp_gene_stats = self.assay_panel_repository.get_all_asp_gene_counts()
        targeted_panel_ids = panel_asp_ids(asp_gene_stats)
        return {
            "total_samples": total_samples_count,
            "analysed_samples": analysed_samples_count,
            "pending_samples": pending_samples_count,
            "variant_stats": variant_stats,
            "unique_gene_count_all_panels": int(
                self.assay_panel_repository.get_all_asps_unique_gene_count() or 0
            ),
            "assay_gene_stats_grouped": format_asp_gene_stats(asp_gene_stats),
            "panel_gene_stats_grouped": format_panel_gene_stats(asp_gene_stats),
            "panel_portfolio": summarize_panel_gene_stats(asp_gene_stats),
            "panel_analysis_capabilities": self.assay_configuration_repository.get_dashboard_analysis_type_rollup(
                asp_ids=targeted_panel_ids
            ),
            "sample_stats": sample_stats,
            "tier_stats": tier_stats,
            "top_tiered_genes": top_tiered_genes,
            "reported_tier_stats": reported_tier_stats,
            "quality_stats": {
                "analysed_rate_percent": analysed_rate,
                "fp_rate_percent": fp_rate,
            },
            "capacity_counts": self.build_capacity_counts(),
            "isgl_visibility": self.build_isgl_visibility(),
            "isgl_association": self.gene_list_repository.get_dashboard_assay_association_rollup()
            or {},
        }

    @measured_operation("query.dashboard_summary_refresh")
    def refresh_summary_payload(
        self,
        *,
        user,
        shared_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist one scoped snapshot using a refresh-cycle shared metrics payload."""
        common_metrics = (
            shared_payload if shared_payload is not None else self.build_shared_summary_payload()
        )
        scope_assays = self.resolve_scope_assays(user=user)
        scope_key = self._summary_scope_key(user=user, scope_assays=scope_assays)
        sample_rollup_scoped = self.sample_repository.get_dashboard_sample_rollup(
            asp_ids=scope_assays
        )
        user_total_samples = int(sample_rollup_scoped.get("total_samples", 0) or 0)
        user_analysed_samples = int(sample_rollup_scoped.get("analysed_samples", 0) or 0)
        user_pending_samples = int(sample_rollup_scoped.get("pending_samples", 0) or 0)

        payload = deepcopy(common_metrics)
        payload.update(
            {
                "user_samples_stats": sample_rollup_scoped.get("user_samples_stats", {}) or {},
                "user_scope_summary": {
                    "total_samples": user_total_samples,
                    "analysed_samples": user_analysed_samples,
                    "pending_samples": user_pending_samples,
                    "analysed_rate_percent": (
                        round((user_analysed_samples / user_total_samples) * 100, 2)
                        if user_total_samples
                        else 0.0
                    ),
                    "recent_samples": sample_rollup_scoped.get("recent_samples", []) or [],
                    "sample_stats": sample_rollup_scoped.get("sample_stats", {}) or {},
                },
                "dashboard_meta": {"scope_assays": scope_assays},
                "admin_insights": {},
            }
        )
        if "superuser" in {str(role_id or "").strip().lower() for role_id in (user.roles or [])}:
            payload["admin_insights"] = self.build_admin_insights()
        generated_at = datetime.now(timezone.utc)
        payload["dashboard_meta"].update(
            {
                "snapshot_updated_at": generated_at.isoformat(),
                "snapshot_age_seconds": 0.0,
                "snapshot_stale": False,
                "snapshot_dirty": False,
            }
        )
        self._write_dashboard_summary_snapshot(scope_key=scope_key, payload=payload)
        return payload
