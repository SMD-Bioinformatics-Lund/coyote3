"""Ports for reporting persistence workflows."""

from __future__ import annotations

from typing import Protocol


class ReportingPersistenceRepository(Protocol):
    """Define the persistence operations required by report save flows."""

    def save_report(
        self,
        *,
        sample_id: str,
        report_num: int,
        report_id: str,
        filepath: str,
    ) -> str:
        """Persist report metadata and return the created report identifier."""
        ...

    def bulk_upsert_snapshot_rows(
        self,
        *,
        sample_name: str | None,
        sample_oid: str | None,
        report_oid: str,
        report_id: str,
        snapshot_rows: list,
        created_by: str,
    ) -> None:
        """Persist reported-variants snapshot rows for the saved report."""
        ...
