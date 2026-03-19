"""Repository port for dashboard read models."""

from __future__ import annotations

from typing import Protocol


class DashboardRepository(Protocol):
    """Define the persistence operations required by dashboard read models."""

    def count_users(self) -> int:
        """Count users.

        Returns:
            int: The function result.
        """
        ...

    def count_roles(self, is_active: bool | None = None) -> int:
        """Count roles.

        Args:
            is_active (bool | None): Value for ``is_active``.

        Returns:
            int: The function result.
        """
        ...

    def count_asps(self, is_active: bool | None = None) -> int:
        """Count asps.

        Args:
            is_active (bool | None): Value for ``is_active``.

        Returns:
            int: The function result.
        """
        ...

    def count_aspcs(self, is_active: bool | None = None) -> int:
        """Count aspcs.

        Args:
            is_active (bool | None): Value for ``is_active``.

        Returns:
            int: The function result.
        """
        ...

    def count_isgls(self, is_active: bool | None = None) -> int:
        """Count isgls.

        Returns:
            int: The function result.
        """
        ...

    def get_dashboard_user_rollup(self) -> dict:
        """Return dashboard user rollup."""
        ...

    def get_dashboard_isgl_visibility(self) -> dict:
        """Return dashboard ISGL visibility rollup."""
        ...

    def get_dashboard_isgl_association(self) -> dict:
        """Return dashboard ISGL association rollup."""
        ...

    def get_all_isgl(self) -> list[dict]:
        """Return all isgl.

        Returns:
            list[dict]: The function result.
        """
        ...

    def get_all_users(self) -> list[dict]:
        """Return all users.

        Returns:
            list[dict]: The function result.
        """
        ...

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Return user by id.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            dict | None: The function result.
        """
        ...

    def get_all_active_asps(self) -> list[dict]:
        """Return all active asps.

        Returns:
            list[dict]: The function result.
        """
        ...

    def resolve_active_asp_ids_for_scope(self, assays: list[str], groups: list[str]) -> list[str]:
        """Resolve active ASP ids for assay/group scope values."""
        ...

    def get_dashboard_sample_rollup(self, assays: list[str] | None) -> dict:
        """Return dashboard sample rollup.

        Args:
            assays (list[str] | None): Value for ``assays``.

        Returns:
            dict: The function result.
        """
        ...

    def get_dashboard_variant_counts(self) -> dict:
        """Return dashboard variant counts.

        Returns:
            dict: The function result.
        """
        ...

    def get_unique_variant_quality_counts(self) -> dict:
        """Return unique variant quality counts."""
        ...

    def get_total_cnv_count(self) -> int:
        """Return total cnv count.

        Returns:
            int: The function result.
        """
        ...

    def get_total_transloc_count(self) -> int:
        """Return total transloc count.

        Returns:
            int: The function result.
        """
        ...

    def get_total_fusion_count(self) -> int:
        """Return total fusion count.

        Returns:
            int: The function result.
        """
        ...

    def get_unique_blacklist_count(self) -> int:
        """Return unique blacklist count.

        Returns:
            int: The function result.
        """
        ...

    def get_dashboard_tier_stats(self) -> dict:
        """Return dashboard tier stats.

        Returns:
            dict: The function result.
        """
        ...

    def get_all_asps_unique_gene_count(self) -> int:
        """Return all asps unique gene count.

        Returns:
            int: The function result.
        """
        ...

    def get_all_asp_gene_counts(self) -> dict:
        """Return all asp gene counts.

        Returns:
            dict: The function result.
        """
        ...
