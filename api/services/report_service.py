"""Service for sample-scoped report preview and persistence workflows."""

from __future__ import annotations

from typing import Any, Literal

from api.contracts.reports import ReportPreviewPayload, ReportSavePayload

ReportAnalyte = Literal["dna", "rna"]


class ReportService:
    """Own report preview and persistence response shaping."""

    @staticmethod
    def sample_meta(sample: dict) -> dict:
        """Handle sample meta.

        Args:
            sample (dict): Value for ``sample``.

        Returns:
            dict: The function result.
        """
        return {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        }

    @staticmethod
    def preview_payload(
        *,
        sample: dict,
        request_path: str,
        include_snapshot: bool,
        template_name: str,
        template_context: dict[str, Any],
        snapshot_rows: list,
    ) -> ReportPreviewPayload:
        """Handle preview payload.

        Args:
            sample (dict): Value for ``sample``.
            request_path (str): Value for ``request_path``.
            include_snapshot (bool): Value for ``include_snapshot``.
            template_name (str): Value for ``template_name``.
            template_context (dict[str, Any]): Value for ``template_context``.
            snapshot_rows (list): Value for ``snapshot_rows``.

        Returns:
            ReportPreviewPayload: The function result.
        """
        return {
            "sample": ReportService.sample_meta(sample),
            "meta": {
                "request_path": request_path,
                "include_snapshot": include_snapshot,
                "snapshot_count": len(snapshot_rows),
            },
            "report": {
                "template": template_name,
                "context": template_context,
                "snapshot_rows": snapshot_rows if include_snapshot else [],
            },
        }

    @staticmethod
    def save_payload(*, sample: dict, report_id: str, report_oid: str, report_file: str, snapshot_rows: list) -> ReportSavePayload:
        """Handle save payload.

        Args:
            sample (dict): Value for ``sample``.
            report_id (str): Value for ``report_id``.
            report_oid (str): Value for ``report_oid``.
            report_file (str): Value for ``report_file``.
            snapshot_rows (list): Value for ``snapshot_rows``.

        Returns:
            ReportSavePayload: The function result.
        """
        return {
            "sample": ReportService.sample_meta(sample),
            "report": {
                "id": report_id,
                "oid": str(report_oid),
                "file": report_file,
                "snapshot_count": len(snapshot_rows),
            },
            "meta": {"status": "saved"},
        }


__all__ = ["ReportAnalyte", "ReportService"]
