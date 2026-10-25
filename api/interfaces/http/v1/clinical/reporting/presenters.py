"""HTTP response adaptation for completed application report operations."""

from __future__ import annotations

from typing import Any


class ReportPresenter:
    """Adapt report SDK values to the established HTTP response envelopes."""

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
            "asp_id": sample.get("asp_id"),
            "environment": sample.get("environment"),
        }

    @staticmethod
    def preview_payload(
        *,
        sample: dict,
        request_path: str,
        include_snapshot: bool,
        template_name: str,
        template_context: dict[str, Any],
        html: str,
        snapshot_rows: list,
        fingerprint: str,
        snapshot_count: int,
    ) -> dict[str, Any]:
        """Build the preview response payload for a rendered report.

        Args:
            sample: Sample payload linked to the report.
            request_path: Request path used to build the preview.
            include_snapshot: Whether snapshot rows should be included.
            template_name: Name of the rendered report template.
            template_context: Template context used for rendering.
            html: Rendered report HTML.
            snapshot_rows: Snapshot rows extracted from the report.
            fingerprint: Concurrency fingerprint computed by the application operation.
            snapshot_count: Total prepared snapshot count, including rows omitted from this response.

        Returns:
            The existing preview response envelope.
        """
        has_html = bool(str(html or "").strip())
        return {
            "sample": ReportPresenter.sample_meta(sample),
            "meta": {
                "request_path": request_path,
                "include_snapshot": include_snapshot,
                "snapshot_count": snapshot_count,
                "preview_fingerprint": fingerprint,
                "template_status": {
                    "status": "ready" if has_html else "unavailable",
                    "template": template_name,
                    "has_html": has_html,
                    "message": (
                        "Report preview is ready."
                        if has_html
                        else "No rendered report HTML was returned for this sample and report type."
                    ),
                },
            },
            "report": {
                "template": template_name,
                "context": template_context,
                "html": html,
                "snapshot_rows": snapshot_rows if include_snapshot else [],
            },
        }

    @staticmethod
    def save_payload(
        *,
        sample: dict,
        report_id: str,
        report_oid: str,
        report_file: str,
        pdf_file: str | None = None,
        snapshot_count: int,
    ) -> dict[str, Any]:
        """Build the response payload for a saved report.

        Args:
            sample: Sample payload linked to the report.
            report_id: Logical report identifier.
            report_oid: Persisted report object identifier.
            report_file: Saved report filename.
            pdf_file: Saved PDF report filename.
            snapshot_count: Number of findings retained in the saved report snapshot.

        Returns:
            The existing saved-report response envelope.
        """
        return {
            "sample": ReportPresenter.sample_meta(sample),
            "report": {
                "id": report_id,
                "oid": str(report_oid),
                "file": report_file,
                "pdf_file": pdf_file,
                "snapshot_count": snapshot_count,
            },
            "meta": {"status": "saved"},
        }


__all__ = ["ReportPresenter"]
