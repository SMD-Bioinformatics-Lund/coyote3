"""Mongo repository adapter for dashboard read models."""

from __future__ import annotations

from api.extensions import store


class MongoDashboardRepository:
    """Provide mongo dashboard persistence operations."""

    def count_users(self) -> int:
        """Handle count users.

        Returns:
            int: The function result.
        """
        return int(store.user_handler.count_users())

    def count_roles(self, is_active: bool | None = None) -> int:
        """Handle count roles.

        Args:
            is_active (bool | None): Value for ``is_active``.

        Returns:
            int: The function result.
        """
        return int(store.roles_handler.count_roles(is_active=is_active))

    def count_asps(self, is_active: bool | None = None) -> int:
        """Handle count asps.

        Args:
            is_active (bool | None): Value for ``is_active``.

        Returns:
            int: The function result.
        """
        return int(store.asp_handler.count_asps(is_active=is_active))

    def count_aspcs(self, is_active: bool | None = None) -> int:
        """Handle count aspcs.

        Args:
            is_active (bool | None): Value for ``is_active``.

        Returns:
            int: The function result.
        """
        return int(store.aspc_handler.count_aspcs(is_active=is_active))

    def count_isgls(self, is_active: bool | None = None) -> int:
        """Handle count isgls.

        Returns:
            int: The function result.
        """
        return int(store.isgl_handler.count_isgls(is_active=is_active))

    def get_all_isgl(self) -> list[dict]:
        """Return all isgl.

        Returns:
            list[dict]: The function result.
        """
        return list(store.isgl_handler.get_all_isgl() or [])

    def get_all_users(self) -> list[dict]:
        """Return all users.

        Returns:
            list[dict]: The function result.
        """
        return list(store.user_handler.get_all_users() or [])

    def get_dashboard_user_rollup(self) -> dict:
        """Return dashboard user role/profession rollup."""
        return dict(store.user_handler.get_dashboard_user_rollup() or {})

    def get_dashboard_isgl_visibility(self) -> dict:
        """Return dashboard ISGL visibility rollup."""
        return dict(store.isgl_handler.get_dashboard_visibility_rollup() or {})

    def get_dashboard_isgl_association(self) -> dict:
        """Return dashboard ISGL association rollup by ASP."""
        return dict(store.isgl_handler.get_dashboard_assay_association_rollup() or {})

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Return user by id.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            dict | None: The function result.
        """
        return store.user_handler.user_with_id(str(user_id))

    def get_all_active_asps(self) -> list[dict]:
        """Return all active asps.

        Returns:
            list[dict]: The function result.
        """
        return list(store.asp_handler.get_all_asps(is_active=True) or [])

    def resolve_active_asp_ids_for_scope(self, assays: list[str], groups: list[str]) -> list[str]:
        """Resolve active ASP ids for assay/group scope values."""
        return list(store.asp_handler.resolve_active_asp_ids_for_scope(assays=assays, groups=groups) or [])

    def get_dashboard_sample_rollup(self, assays: list[str] | None) -> dict:
        """Return dashboard sample rollup.

        Args:
            assays (list[str] | None): Value for ``assays``.

        Returns:
            dict: The function result.
        """
        return store.sample_handler.get_dashboard_sample_rollup(assays=assays)

    def get_dashboard_variant_counts(self) -> dict:
        """Return dashboard variant counts.

        Returns:
            dict: The function result.
        """
        return store.variant_handler.get_dashboard_variant_counts()

    def get_unique_total_variant_count(self) -> int:
        """Return unique total variant count."""
        return int(store.variant_handler.get_unique_total_variant_counts())

    def get_unique_fp_count(self) -> int:
        """Return unique false-positive variant count."""
        return int(store.variant_handler.get_unique_fp_count())

    def get_unique_variant_quality_counts(self) -> dict:
        """Return unique variant quality counts in a single query."""
        return dict(store.variant_handler.get_unique_variant_quality_counts() or {})

    def get_total_cnv_count(self) -> int:
        """Return total cnv count.

        Returns:
            int: The function result.
        """
        return int(store.cnv_handler.get_total_cnv_count())

    def get_total_transloc_count(self) -> int:
        """Return total transloc count.

        Returns:
            int: The function result.
        """
        return int(store.transloc_handler.get_total_transloc_count())

    def get_total_fusion_count(self) -> int:
        """Return total fusion count.

        Returns:
            int: The function result.
        """
        return int(store.fusion_handler.get_total_fusion_count())

    def get_unique_blacklist_count(self) -> int:
        """Return unique blacklist count.

        Returns:
            int: The function result.
        """
        return int(store.blacklist_handler.get_unique_blacklist_count())

    def get_dashboard_tier_stats(self) -> dict:
        """Return dashboard tier stats.

        Returns:
            dict: The function result.
        """
        return store.reported_variants_handler.get_dashboard_tier_stats()

    def get_all_asps_unique_gene_count(self) -> int:
        """Return all asps unique gene count.

        Returns:
            int: The function result.
        """
        return int(store.asp_handler.get_all_asps_unique_gene_count())

    def get_all_asp_gene_counts(self) -> dict:
        """Return all asp gene counts.

        Returns:
            dict: The function result.
        """
        return store.asp_handler.get_all_asp_gene_counts()
