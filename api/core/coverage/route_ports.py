"""Repository port for coverage read endpoints."""

from __future__ import annotations

from typing import Protocol


class CoverageRouteRepository(Protocol):
    """Define the persistence operations required by coverage read routes."""

    def get_aspc_no_meta(self, assay: str, profile: str) -> dict | None:
        """Return aspc no meta.

        Args:
            assay (str): Value for ``assay``.
            profile (str): Value for ``profile``.

        Returns:
            dict | None: The function result.
        """
        ...

    def get_asp(self, asp_name: str) -> dict | None:
        """Return asp.

        Args:
            asp_name (str): Value for ``asp_name``.

        Returns:
            dict | None: The function result.
        """
        ...

    def get_isgl_by_ids(self, ids: list[str]) -> dict:
        """Return isgl by ids.

        Args:
            ids (list[str]): Value for ``ids``.

        Returns:
            dict: The function result.
        """
        ...

    def get_sample_coverage(self, sample_id: str) -> dict | None:
        """Return sample coverage.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict | None: The function result.
        """
        ...

    def get_regions_per_group(self, group: str) -> list[dict]:
        """Return regions per group.

        Args:
            group (str): Value for ``group``.

        Returns:
            list[dict]: The function result.
        """
        ...
