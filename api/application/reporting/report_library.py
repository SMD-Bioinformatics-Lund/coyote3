"""Read-only saved report library service."""

from __future__ import annotations

from typing import Any


class ReportLibraryService:
    """List saved reports and their immutable finding snapshot summaries."""

    def __init__(self, *, report_repository: Any, reported_variant_repository: Any) -> None:
        self.report_repository = report_repository
        self.reported_variant_repository = reported_variant_repository

    @classmethod
    def from_store(cls, store: Any) -> "ReportLibraryService":
        """Build the service from the runtime repository store."""
        return cls(
            report_repository=store.report_repository,
            reported_variant_repository=store.reported_variant_repository,
        )

    def list_payload(
        self,
        *,
        user: Any,
        search: str,
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        """Return reports visible through the user's assay and environment scope."""
        asp_ids = None if user.is_superuser else list(user.asp_ids)
        environments = None if user.is_superuser else list(user.envs)
        rows, total = self.report_repository.list_reports_page(
            asp_ids=asp_ids,
            environments=environments,
            search=search,
            page=page,
            per_page=per_page,
        )
        summaries = self.reported_variant_repository.summarize_reports(
            [row.get("_id") for row in rows if row.get("_id") is not None]
        )
        reports = []
        for row in rows:
            summary = summaries.get(
                str(row.get("_id")), {"finding_count": 0, "analysis_counts": {}}
            )
            reports.append(
                {
                    "oid": str(row.get("_id")),
                    "report_id": str(row.get("report_id") or row.get("_id")),
                    "report_name": row.get("report_name"),
                    "sample_id": str(row.get("sample_name") or row.get("sample_oid") or ""),
                    "asp_id": row.get("asp_id"),
                    "subpanel_id": row.get("subpanel_id"),
                    "environment": row.get("environment"),
                    "author": row.get("author"),
                    "time_created": row.get("time_created"),
                    "finding_count": summary["finding_count"],
                    "analysis_counts": summary["analysis_counts"],
                    "has_pdf": bool(row.get("pdf_filepath")),
                }
            )
        safe_page = max(1, int(page))
        safe_per_page = max(1, min(200, int(per_page)))
        return {
            "reports": reports,
            "total": total,
            "page": safe_page,
            "per_page": safe_per_page,
            "has_next": safe_page * safe_per_page < total,
        }
