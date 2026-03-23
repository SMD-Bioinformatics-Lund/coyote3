"""Mongo repository adapter for coverage read endpoints."""

from __future__ import annotations

from api.extensions import store


class MongoCoverageRouteRepository:
    """Provide mongo coverage route persistence operations."""

    def get_aspc_no_meta(self, assay: str, profile: str) -> dict | None:
        """Return aspc no meta.

        Args:
            assay (str): Value for ``assay``.
            profile (str): Value for ``profile``.

        Returns:
            dict | None: The function result.
        """
        return store.aspc_handler.get_aspc_no_meta(assay, profile)

    def get_asp(self, asp_name: str) -> dict | None:
        """Return asp.

        Args:
            asp_name (str): Value for ``asp_name``.

        Returns:
            dict | None: The function result.
        """
        return store.asp_handler.get_asp(asp_name=asp_name)

    def get_isgl_by_ids(self, ids: list[str]) -> dict:
        """Return isgl by ids.

        Args:
            ids (list[str]): Value for ``ids``.

        Returns:
            dict: The function result.
        """
        return store.isgl_handler.get_isgl_by_ids(ids)

    def get_sample_coverage(self, sample_id: str) -> dict | None:
        """Return sample coverage.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict | None: The function result.
        """
        return store.coverage_handler.get_sample_coverage(sample_id)

    def get_regions_per_group(self, group: str) -> list[dict]:
        """Return regions per group.

        Args:
            group (str): Value for ``group``.

        Returns:
            list[dict]: The function result.
        """
        return list(store.groupcov_handler.get_regions_per_group(group) or [])
