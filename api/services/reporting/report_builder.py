"""Service for sample-scoped report preview and persistence workflows."""

from __future__ import annotations

from typing import Any, Literal

from api.contracts.reports import ReportPreviewPayload, ReportSavePayload

ReportAnalyte = Literal["dna", "rna"]


class ReportService:
    """Own report preview and persistence response shaping."""

    @staticmethod
    def sample_meta(sample: dict) -> dict:
        """Build the sample metadata block for report responses.

        Args:
            sample: Sample payload linked to the report.

        Returns:
            dict: Minimal sample metadata for report payloads.
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
        """Build the preview response payload for a rendered report.

        Args:
            sample: Sample payload linked to the report.
            request_path: Request path used to build the preview.
            include_snapshot: Whether snapshot rows should be included.
            template_name: Name of the rendered report template.
            template_context: Template context used for rendering.
            snapshot_rows: Snapshot rows extracted from the report.

        Returns:
            ReportPreviewPayload: Preview response payload.
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
    def save_payload(
        *, sample: dict, report_id: str, report_oid: str, report_file: str, snapshot_rows: list
    ) -> ReportSavePayload:
        """Build the response payload for a saved report.

        Args:
            sample: Sample payload linked to the report.
            report_id: Logical report identifier.
            report_oid: Persisted report object identifier.
            report_file: Saved report filename.
            snapshot_rows: Snapshot rows extracted from the report.

        Returns:
            ReportSavePayload: Saved-report response payload.
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
