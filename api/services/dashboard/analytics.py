"""Dashboard workflow service."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from api.extensions import util
from api.runtime_state import app as runtime_app


class DashboardService:
    """Provide dashboard workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "DashboardService":
        """Build the service from the shared store."""
        return cls(
            user_handler=store.user_handler,
            roles_handler=store.roles_handler,
            assay_panel_handler=store.assay_panel_handler,
            assay_configuration_handler=store.assay_configuration_handler,
            gene_list_handler=store.gene_list_handler,
            sample_handler=store.sample_handler,
            variant_handler=store.variant_handler,
            copy_number_variant_handler=store.copy_number_variant_handler,
            translocation_handler=store.translocation_handler,
            fusion_handler=store.fusion_handler,
            blacklist_handler=store.blacklist_handler,
            reported_variant_handler=store.reported_variant_handler,
            coyote_db=store.coyote_db,
        )

    def __init__(
        self,
        *,
        user_handler: Any,
        roles_handler: Any,
        assay_panel_handler: Any,
        assay_configuration_handler: Any,
        gene_list_handler: Any,
        sample_handler: Any,
        variant_handler: Any,
        copy_number_variant_handler: Any,
        translocation_handler: Any,
        fusion_handler: Any,
        blacklist_handler: Any,
        reported_variant_handler: Any,
        coyote_db: Any | None,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.user_handler = user_handler
        self.roles_handler = roles_handler
        self.assay_panel_handler = assay_panel_handler
        self.assay_configuration_handler = assay_configuration_handler
        self.gene_list_handler = gene_list_handler
        self.sample_handler = sample_handler
        self.variant_handler = variant_handler
        self.copy_number_variant_handler = copy_number_variant_handler
        self.translocation_handler = translocation_handler
        self.fusion_handler = fusion_handler
        self.blacklist_handler = blacklist_handler
        self.reported_variant_handler = reported_variant_handler
        self.coyote_db = coyote_db

    @staticmethod
    def _cache_backend():
        """Return runtime cache backend when available."""
        return getattr(runtime_app, "cache", None)

    @staticmethod
    def _cache_version_token() -> str:
        """Resolve dashboard cache version token."""
        cache = DashboardService._cache_backend()
        if cache is None:
            return "0"
        token = cache.get("dashboard:summary:version")
        if token is None:
            return "0"
        return str(token)

    @staticmethod
    def _summary_scope_key(*, user, scope_assays: list[str] | None) -> str:
        """Build stable scope key for dashboard summary cache/snapshots."""
        payload = {
            "username": str(getattr(user, "username", "") or ""),
            "role": str(getattr(user, "role", "") or ""),
            "assays": sorted(scope_assays) if isinstance(scope_assays, list) else None,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()  # noqa: S324

    @staticmethod
    def _cache_ttl_seconds() -> int:
        """Return Redis summary TTL."""
        return int(runtime_app.config.get("DASHBOARD_SUMMARY_CACHE_TTL_SECONDS", 60) or 60)

    @staticmethod
    def _snapshot_max_age_seconds() -> int:
        """Return persisted summary staleness threshold."""
        return int(runtime_app.config.get("DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS", 300) or 300)

    def _dashboard_metrics_collection(self):
        """Return collection used for persisted dashboard snapshots."""
        if self.coyote_db is None:
            return None
        return self.coyote_db["dashboard_metrics"]

    def _read_dashboard_summary_snapshot(
        self, *, scope_key: str, max_age_seconds: int
    ) -> dict | None:
        """Read persisted summary snapshot when fresh enough."""
        collection = self._dashboard_metrics_collection()
        if collection is None:
            return None
        from datetime import datetime, timezone

        doc = collection.find_one(
            {"_id": f"dashboard_summary_v2:{scope_key}"},
            {"payload": 1, "updated_at": 1},
        )
        if not isinstance(doc, dict):
            return None
        payload = doc.get("payload")
        updated_at = doc.get("updated_at")
        if not isinstance(payload, dict) or not isinstance(updated_at, datetime):
            return None
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - updated_at).total_seconds()
        if age_seconds > int(max_age_seconds):
            return None
        return dict(payload)

    def _write_dashboard_summary_snapshot(self, *, scope_key: str, payload: dict) -> None:
        """Persist summary snapshot payload."""
        collection = self._dashboard_metrics_collection()
        if collection is None:
            return
        from datetime import datetime, timezone

        collection.update_one(
            {"_id": f"dashboard_summary_v2:{scope_key}"},
            {
                "$set": {
                    "payload": dict(payload),
                    "updated_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )

    @staticmethod
    def _set_cache_meta(payload: dict[str, Any], *, source: str, hit: bool) -> dict[str, Any]:
        """Annotate payload meta with cache source info."""
        meta = payload.setdefault("dashboard_meta", {})
        meta["cache_source"] = source
        meta["cache_hit"] = bool(hit)
        return payload

    def build_capacity_counts(self) -> dict[str, int]:
        """Return top-level admin capacity counts for the dashboard.

        Returns:
            dict[str, int]: Aggregate counts for major managed resources.
        """
        return {
            "users_total": int(self.user_handler.count_users() or 0),
            "roles_total": int(self.roles_handler.count_roles() or 0),
            "asps_total": int(self.assay_panel_handler.count_asps() or 0),
            "aspcs_total": int(self.assay_configuration_handler.count_aspcs() or 0),
            "isgl_total": int(self.gene_list_handler.count_isgls() or 0),
        }

    def build_isgl_visibility(self, isgls: list[dict] | None = None) -> dict[str, Any]:
        """Return ISGL visibility rollups for the dashboard.

        Args:
            isgls: Optional pre-fetched ISGL rows.

        Returns:
            dict[str, Any]: Visibility counts grouped by exposure mode.
        """
        if isgls is None:
            return dict(self.gene_list_handler.get_dashboard_visibility_rollup() or {})
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
        users_rollup = dict(self.user_handler.get_dashboard_user_rollup() or {})
        isgl_rollup = dict(self.gene_list_handler.get_dashboard_visibility_rollup() or {})
        return {
            "counts": {
                "users_total": int(users_rollup.get("users_total", 0) or 0),
                "users_active": int(users_rollup.get("users_active", 0) or 0),
                "roles_total": int(self.roles_handler.count_roles() or 0),
                "roles_active": int(self.roles_handler.count_roles(is_active=True) or 0),
                "asps_total": int(self.assay_panel_handler.count_asps() or 0),
                "asps_active": int(self.assay_panel_handler.count_asps(is_active=True) or 0),
                "aspcs_total": int(self.assay_configuration_handler.count_aspcs() or 0),
                "aspcs_active": int(
                    self.assay_configuration_handler.count_aspcs(is_active=True) or 0
                ),
                "isgl_total": int(self.gene_list_handler.count_isgls() or 0),
                "isgl_active": int(self.gene_list_handler.count_isgls(is_active=True) or 0),
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
            fresh_user_doc = self.user_handler.user_with_id(str(user.id)) or {}
        except Exception:
            fresh_user_doc = {}

        effective_roles = [
            str(role_id or "").strip().lower()
            for role_id in (fresh_user_doc.get("roles") or user.roles)
        ]
        if "superuser" in effective_roles:
            return None

        scoped_assays = (
            fresh_user_doc.get("assays")
            if isinstance(fresh_user_doc.get("assays"), list)
            else user.assays
        )
        scoped_groups = (
            fresh_user_doc.get("assay_groups")
            if isinstance(fresh_user_doc.get("assay_groups"), list)
            else user.assay_groups
        )

        user_assays = {str(item).strip() for item in (scoped_assays or []) if str(item).strip()}
        user_groups = {str(item).strip() for item in (scoped_groups or []) if str(item).strip()}
        if not user_assays and not user_groups:
            return []

        effective_assays = set(user_assays)
        for asp_id in (
            self.assay_panel_handler.resolve_active_asp_ids_for_scope(
                assays=sorted(user_assays),
                groups=sorted(user_groups),
            )
            or []
        ):
            if asp_id:
                effective_assays.add(str(asp_id).strip())
        return sorted(effective_assays)

    def summary_payload(self, *, user) -> dict[str, Any]:
        """Build the cached dashboard summary payload for a user.

        Args:
            user: Authenticated dashboard user.

        Returns:
            dict[str, Any]: Dashboard summary payload with cache metadata.
        """
        scope_assays = self.resolve_scope_assays(user=user)
        scope_key = self._summary_scope_key(user=user, scope_assays=scope_assays)
        cache_key = f"dashboard:summary:v2:{self._cache_version_token()}:{scope_key}"
        cache_ttl = self._cache_ttl_seconds()
        snapshot_max_age = self._snapshot_max_age_seconds()

        cache = self._cache_backend()
        if cache is not None:
            cached_payload = cache.get(cache_key)
            if isinstance(cached_payload, dict):
                return self._set_cache_meta(dict(cached_payload), source="redis", hit=True)

        snapshot_payload = self._read_dashboard_summary_snapshot(
            scope_key=scope_key, max_age_seconds=snapshot_max_age
        )
        if isinstance(snapshot_payload, dict):
            if cache is not None:
                cache.set(cache_key, snapshot_payload, timeout=cache_ttl)
            return self._set_cache_meta(dict(snapshot_payload), source="mongo_snapshot", hit=False)

        sample_rollup_global = self.sample_handler.get_dashboard_sample_rollup(assays=None)
        sample_rollup_scoped = self.sample_handler.get_dashboard_sample_rollup(assays=scope_assays)
        variant_rollup = self.variant_handler.get_dashboard_variant_counts()
        unique_quality_counts = self.variant_handler.get_unique_variant_quality_counts() or {}
        unique_total_variants = int(unique_quality_counts.get("unique_total_variants", 0) or 0)
        unique_fp_variants = int(unique_quality_counts.get("unique_fp_variants", 0) or 0)
        total_cnvs = int(self.copy_number_variant_handler.get_total_cnv_count() or 0)
        total_translocs = int(self.translocation_handler.get_total_transloc_count() or 0)
        total_fusions = int(self.fusion_handler.get_total_fusion_count() or 0)
        unique_blacklisted_variants = int(self.blacklist_handler.get_unique_blacklist_count() or 0)
        tier_stats = self.reported_variant_handler.get_dashboard_tier_stats()

        total_samples_count = int(sample_rollup_global.get("total_samples", 0) or 0)
        analysed_samples_count = int(sample_rollup_global.get("analysed_samples", 0) or 0)
        pending_samples_count = int(sample_rollup_global.get("pending_samples", 0) or 0)
        sample_stats = sample_rollup_global.get("sample_stats", {})
        user_samples_stats = sample_rollup_scoped.get("user_samples_stats", {})

        variant_stats = {
            "total_variants": int(variant_rollup.get("total_variants", 0) or 0),
            "total_snps": int(variant_rollup.get("total_snps", 0) or 0),
            "total_cnvs": int(total_cnvs or 0),
            "total_translocs": int(total_translocs or 0),
            "total_fusions": int(total_fusions or 0),
            "blacklisted": int(unique_blacklisted_variants or 0),
            "fps": int(variant_rollup.get("fps", 0) or 0),
        }

        analysed_rate = (
            round((analysed_samples_count / total_samples_count) * 100, 2)
            if total_samples_count
            else 0.0
        )
        fp_rate = (
            round((int(unique_fp_variants or 0) / int(unique_total_variants or 0)) * 100, 2)
            if unique_total_variants
            else 0.0
        )
        blacklist_rate = (
            round(
                (int(unique_blacklisted_variants or 0) / int(unique_total_variants or 0)) * 100, 2
            )
            if unique_total_variants
            else 0.0
        )
        payload = {
            "total_samples": total_samples_count,
            "analysed_samples": analysed_samples_count,
            "pending_samples": pending_samples_count,
            "user_samples_stats": user_samples_stats,
            "variant_stats": variant_stats,
            "unique_gene_count_all_panels": int(
                self.assay_panel_handler.get_all_asps_unique_gene_count() or 0
            ),
            "assay_gene_stats_grouped": util.dashboard.format_asp_gene_stats(
                self.assay_panel_handler.get_all_asp_gene_counts()
            ),
            "sample_stats": sample_stats,
            "tier_stats": tier_stats,
            "quality_stats": {
                "analysed_rate_percent": analysed_rate,
                "fp_rate_percent": fp_rate,
                "blacklist_rate_percent": blacklist_rate,
            },
            "dashboard_meta": {"scope_assays": scope_assays},
            "admin_insights": {},
            "capacity_counts": self.build_capacity_counts(),
            "isgl_visibility": self.build_isgl_visibility(),
            "isgl_association": self.gene_list_handler.get_dashboard_assay_association_rollup()
            or {},
        }
        if "superuser" in {str(role_id or "").strip().lower() for role_id in (user.roles or [])}:
            payload["admin_insights"] = self.build_admin_insights()
        self._set_cache_meta(payload, source="recomputed", hit=False)
        if cache is not None:
            cache.set(cache_key, payload, timeout=cache_ttl)
        self._write_dashboard_summary_snapshot(scope_key=scope_key, payload=payload)
        return payload
