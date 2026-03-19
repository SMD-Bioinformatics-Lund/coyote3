"""Dashboard workflow service."""

from __future__ import annotations

from time import perf_counter
from typing import Any

from api.extensions import util
from api.repositories.dashboard_repository import DashboardRepository as MongoDashboardRepository


class DashboardService:
    """Provide dashboard workflows."""

    def __init__(self, repository=None) -> None:
        """__init__.

        Args:
                repository: Repository. Optional argument.
        """
        self.repository = repository or MongoDashboardRepository()

    def build_capacity_counts(self) -> dict[str, int]:
        """Build capacity counts.

        Returns:
            dict[str, int]: The function result.
        """
        return {
            "users_total": self.repository.count_users(),
            "roles_total": self.repository.count_roles(),
            "asps_total": self.repository.count_asps(),
            "aspcs_total": self.repository.count_aspcs(),
            "isgl_total": self.repository.count_isgls(),
        }

    def build_isgl_visibility(self, isgls: list[dict] | None = None) -> dict[str, Any]:
        """Build isgl visibility.

        Args:
            isgls (list[dict] | None): Value for ``isgls``.

        Returns:
            dict[str, Any]: The function result.
        """
        if isgls is None:
            return self.repository.get_dashboard_isgl_visibility()
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
        """Build admin insights.

        Returns:
            dict[str, Any]: The function result.
        """
        users_rollup = self.repository.get_dashboard_user_rollup() or {}
        isgl_rollup = self.repository.get_dashboard_isgl_visibility() or {}
        return {
            "counts": {
                "users_total": int(users_rollup.get("users_total", 0) or 0),
                "users_active": int(users_rollup.get("users_active", 0) or 0),
                "roles_total": self.repository.count_roles(),
                "roles_active": self.repository.count_roles(is_active=True),
                "asps_total": self.repository.count_asps(),
                "asps_active": self.repository.count_asps(is_active=True),
                "aspcs_total": self.repository.count_aspcs(),
                "aspcs_active": self.repository.count_aspcs(is_active=True),
                "isgl_total": self.repository.count_isgls(),
                "isgl_active": self.repository.count_isgls(is_active=True),
            },
            "role_user_counts": users_rollup.get("role_user_counts", {}),
            "profession_role_matrix": users_rollup.get("profession_role_matrix", {}),
            "isgl_venn": isgl_rollup,
        }

    def resolve_scope_assays(self, *, user) -> list[str] | None:
        """Resolve scope assays.

        Args:
            user: Value for ``user``.

        Returns:
            list[str] | None: The function result.
        """
        try:
            fresh_user_doc = self.repository.get_user_by_id(str(user.id)) or {}
        except Exception:
            fresh_user_doc = {}

        effective_role = str(fresh_user_doc.get("role") or user.role or "").strip().lower()
        if effective_role == "admin":
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
        for asp_id in self.repository.resolve_active_asp_ids_for_scope(
            assays=sorted(user_assays), groups=sorted(user_groups)
        ):
            if asp_id:
                effective_assays.add(str(asp_id).strip())
        return sorted(effective_assays)

    def summary_payload(self, *, user) -> dict[str, Any]:
        """Summary payload.

        Args:
            user: Value for ``user``.

        Returns:
            dict[str, Any]: The function result.
        """
        timings_ms: dict[str, float] = {}
        api_start = perf_counter()
        scope_assays = self.resolve_scope_assays(user=user)

        def _timed(name: str, fn):
            """Timed.

            Args:
                    name: Name.
                    fn: Fn.

            Returns:
                    The  timed result.
            """
            t0 = perf_counter()
            value = fn()
            timings_ms[name] = round((perf_counter() - t0) * 1000, 2)
            return value

        sample_rollup_global = _timed(
            "sample_rollup_global", lambda: self.repository.get_dashboard_sample_rollup(assays=None)
        )
        sample_rollup_scoped = _timed(
            "sample_rollup_scoped",
            lambda: self.repository.get_dashboard_sample_rollup(assays=scope_assays),
        )
        variant_rollup = _timed("variant_rollup", self.repository.get_dashboard_variant_counts)
        unique_quality_counts = _timed(
            "variant_unique_quality", self.repository.get_unique_variant_quality_counts
        )
        unique_total_variants = int(unique_quality_counts.get("unique_total_variants", 0) or 0)
        unique_fp_variants = int(unique_quality_counts.get("unique_fp_variants", 0) or 0)
        total_cnvs = _timed("cnv_total", self.repository.get_total_cnv_count)
        total_translocs = _timed("transloc_total", self.repository.get_total_transloc_count)
        total_fusions = _timed("fusion_total", self.repository.get_total_fusion_count)
        unique_blacklisted_variants = _timed(
            "blacklist_unique", self.repository.get_unique_blacklist_count
        )
        tier_stats = _timed("reported_tier_stats", self.repository.get_dashboard_tier_stats)

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

        timings_ms["total"] = round((perf_counter() - api_start) * 1000, 2)
        payload = {
            "total_samples": total_samples_count,
            "analysed_samples": analysed_samples_count,
            "pending_samples": pending_samples_count,
            "user_samples_stats": user_samples_stats,
            "variant_stats": variant_stats,
            "unique_gene_count_all_panels": self.repository.get_all_asps_unique_gene_count(),
            "assay_gene_stats_grouped": util.dashboard.format_asp_gene_stats(
                self.repository.get_all_asp_gene_counts()
            ),
            "sample_stats": sample_stats,
            "tier_stats": tier_stats,
            "quality_stats": {
                "analysed_rate_percent": analysed_rate,
                "fp_rate_percent": fp_rate,
                "blacklist_rate_percent": blacklist_rate,
            },
            "dashboard_meta": {"timings_ms": timings_ms, "scope_assays": scope_assays},
            "admin_insights": {},
            "capacity_counts": _timed("capacity_counts", self.build_capacity_counts),
            "isgl_visibility": _timed("isgl_visibility", self.build_isgl_visibility),
            "isgl_association": _timed(
                "isgl_association", self.repository.get_dashboard_isgl_association
            ),
        }
        if str(user.role or "").strip().lower() == "admin":
            payload["admin_insights"] = _timed("admin_insights", self.build_admin_insights)
        return payload
