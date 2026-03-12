"""Dashboard workflow service."""

from __future__ import annotations

from copy import deepcopy
from time import perf_counter
from typing import Any

from api.extensions import util
from api.repositories.dashboard_repository import DashboardRepository as MongoDashboardRepository


class DashboardService:
    def __init__(self, repository=None) -> None:
        self.repository = repository or MongoDashboardRepository()

    def build_capacity_counts(self) -> dict[str, int]:
        return {
            "users_total": self.repository.count_users(),
            "roles_total": self.repository.count_roles(),
            "asps_total": self.repository.count_asps(),
            "aspcs_total": self.repository.count_aspcs(),
            "isgl_total": self.repository.count_isgls(),
        }

    def build_isgl_visibility(self, isgls: list[dict] | None = None) -> dict[str, Any]:
        rows = isgls if isinstance(isgls, list) else (self.repository.get_all_isgl() or [])
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
        users = self.repository.get_all_users() or []
        isgls = self.repository.get_all_isgl() or []

        role_user_counts: dict[str, int] = {}
        profession_role_matrix: dict[str, dict[str, int]] = {}
        active_users = 0

        for user_doc in users:
            role = str(user_doc.get("role") or "unknown").strip().lower() or "unknown"
            if bool(user_doc.get("is_active", True)):
                active_users += 1
            role_user_counts[role] = role_user_counts.get(role, 0) + 1

            profession = str(
                user_doc.get("job_title") or user_doc.get("profession") or user_doc.get("title") or "Unknown"
            ).strip() or "Unknown"
            profession_role_matrix.setdefault(profession, {})
            profession_role_matrix[profession][role] = profession_role_matrix[profession].get(role, 0) + 1

        isgl_total = len(isgls)
        isgl_active = sum(1 for isgl_doc in isgls if bool(isgl_doc.get("is_active", True)))
        return {
            "counts": {
                "users_total": len(users),
                "users_active": active_users,
                "roles_total": self.repository.count_roles(),
                "roles_active": self.repository.count_roles(is_active=True),
                "asps_total": self.repository.count_asps(),
                "asps_active": self.repository.count_asps(is_active=True),
                "aspcs_total": self.repository.count_aspcs(),
                "aspcs_active": self.repository.count_aspcs(is_active=True),
                "isgl_total": isgl_total,
                "isgl_active": isgl_active,
            },
            "role_user_counts": role_user_counts,
            "profession_role_matrix": profession_role_matrix,
            "isgl_venn": self.build_isgl_visibility(isgls),
        }

    def resolve_scope_assays(self, *, user) -> list[str] | None:
        try:
            fresh_user_doc = self.repository.get_user_by_id(str(user.id)) or {}
        except Exception:
            fresh_user_doc = {}

        effective_role = str(fresh_user_doc.get("role") or user.role or "").strip().lower()
        if effective_role == "admin":
            return None

        scoped_assays = fresh_user_doc.get("assays") if isinstance(fresh_user_doc.get("assays"), list) else user.assays
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
        for asp in self.repository.get_all_active_asps():
            asp_id = str(asp.get("_id") or "").strip()
            asp_group = str(asp.get("asp_group") or "").strip()
            assay_name = str(asp.get("assay_name") or "").strip()
            if (
                asp_group in user_groups
                or asp_group in user_assays
                or assay_name in user_groups
                or assay_name in user_assays
                or asp_id in user_assays
            ):
                if asp_id:
                    effective_assays.add(asp_id)
        return sorted(effective_assays)

    def summary_payload(self, *, user) -> dict[str, Any]:
        timings_ms: dict[str, float] = {}
        api_start = perf_counter()
        scope_assays = self.resolve_scope_assays(user=user)

        def _timed(name: str, fn):
            t0 = perf_counter()
            value = fn()
            timings_ms[name] = round((perf_counter() - t0) * 1000, 2)
            return value

        sample_rollup_global = _timed("sample_rollup_global", lambda: self.repository.get_dashboard_sample_rollup(assays=None))
        sample_rollup_scoped = _timed(
            "sample_rollup_scoped",
            lambda: self.repository.get_dashboard_sample_rollup(assays=scope_assays),
        )
        variant_rollup = _timed("variant_rollup", self.repository.get_dashboard_variant_counts)
        total_cnvs = _timed("cnv_total", self.repository.get_total_cnv_count)
        total_translocs = _timed("transloc_total", self.repository.get_total_transloc_count)
        total_fusions = _timed("fusion_total", self.repository.get_total_fusion_count)
        total_blacklisted = _timed("blacklist_unique", self.repository.get_unique_blacklist_count)
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
            "blacklisted": int(total_blacklisted or 0),
            "fps": int(variant_rollup.get("fps", 0) or 0),
        }

        analysed_rate = round((analysed_samples_count / total_samples_count) * 100, 2) if total_samples_count else 0.0
        fp_rate = round((variant_stats["fps"] / variant_stats["total_variants"]) * 100, 2) if variant_stats["total_variants"] else 0.0
        blacklist_rate = (
            round((variant_stats["blacklisted"] / variant_stats["total_variants"]) * 100, 2)
            if variant_stats["total_variants"]
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
                deepcopy(self.repository.get_all_asp_gene_counts())
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
        }
        if str(user.role or "").strip().lower() == "admin":
            payload["admin_insights"] = _timed("admin_insights", self.build_admin_insights)
        return payload

