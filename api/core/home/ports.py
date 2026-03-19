"""Repository port for home/read and sample settings flows."""

from __future__ import annotations

from typing import Protocol


class HomeRepository(Protocol):
    """Define the persistence operations required by sample catalog flows."""

    def get_samples(
        self,
        *,
        user_assays: list,
        user_envs: list,
        status: str,
        report: bool,
        search_str: str,
        limit: int | None,
        offset: int,
        use_cache: bool,
        reload: bool,
    ) -> list[dict]:
        """Return samples.

        Args:
            user_assays (list): Value for ``user_assays``.
            user_envs (list): Value for ``user_envs``.
            status (str): Value for ``status``.
            report (bool): Value for ``report``.
            search_str (str): Value for ``search_str``.
            limit (int | None): Value for ``limit``.
            offset (int): Value for ``offset``.
            use_cache (bool): Value for ``use_cache``.
            reload (bool): Value for ``reload``.

        Returns:
            list[dict]: The function result.
        """
        ...

    def get_isgl_by_asp(self, **query) -> list[dict]:
        """Return isgl by asp.

        Args:
            **query: Additional keyword values for ``query``.

        Returns:
            list[dict]: The function result.
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

    def get_asp(self, assay: str) -> dict:
        """Return asp.

        Args:
            assay (str): Value for ``assay``.

        Returns:
            dict: The function result.
        """
        ...

    def get_asp_genes(self, assay: str) -> tuple[list, list]:
        """Return asp genes.

        Args:
            assay (str): Value for ``assay``.

        Returns:
            tuple[list, list]: The function result.
        """
        ...

    def reset_sample_settings(self, sample_id: str, filters: dict) -> None:
        """Reset sample settings.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict): Value for ``filters``.

        Returns:
            None.
        """
        ...

    def get_sample(self, sample_id: str) -> dict | None:
        """Return sample.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict | None: The function result.
        """
        ...

    def get_variant_stats(self, sample_id: str, genes: list[str] | None = None) -> dict:
        """Return variant stats.

        Args:
            sample_id (str): Value for ``sample_id``.
            genes (list[str] | None): Value for ``genes``.

        Returns:
            dict: The function result.
        """
        ...

    def update_sample_filters(self, sample_id: str, filters: dict) -> None:
        """Update sample filters.

        Args:
            sample_id (str): Value for ``sample_id``.
            filters (dict): Value for ``filters``.

        Returns:
            None.
        """
        ...

    def get_report(self, sample_id: str, report_id: str) -> dict:
        """Return report.

        Args:
            sample_id (str): Value for ``sample_id``.
            report_id (str): Value for ``report_id``.

        Returns:
            dict: The function result.
        """
        ...
