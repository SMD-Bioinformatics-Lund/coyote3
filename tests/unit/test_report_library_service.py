"""Tests for the read-only saved report library."""

from datetime import UTC, datetime
from types import SimpleNamespace

from bson import ObjectId

from api.application.reporting.report_library import ReportLibraryService


class ReportRepositoryStub:
    def __init__(self) -> None:
        self.arguments = None
        self.report_oid = ObjectId()

    def list_reports_page(self, **kwargs):
        self.arguments = kwargs
        return (
            [
                {
                    "_id": self.report_oid,
                    "report_id": "S1_2",
                    "report_name": "S1_2.html",
                    "sample_name": "S1",
                    "asp_id": "hema_gmsv1",
                    "subpanel_id": "hem",
                    "environment": "production",
                    "author": "reviewer",
                    "time_created": datetime(2026, 8, 25, tzinfo=UTC),
                    "pdf_filepath": "/reports/S1_2.pdf",
                }
            ],
            31,
        )


class ReportedVariantRepositoryStub:
    def __init__(self, report_oid: ObjectId) -> None:
        self.report_oid = report_oid
        self.requested_oids = None

    def summarize_reports(self, report_oids):
        self.requested_oids = report_oids
        return {
            str(self.report_oid): {
                "finding_count": 3,
                "analysis_counts": {"SNV": 2, "CNV": 1},
            }
        }


def test_report_library_scopes_non_superuser_and_attaches_snapshot_counts():
    reports = ReportRepositoryStub()
    findings = ReportedVariantRepositoryStub(reports.report_oid)
    service = ReportLibraryService(
        report_repository=reports,
        reported_variant_repository=findings,
    )
    user = SimpleNamespace(
        is_superuser=False,
        asp_ids=["hema_gmsv1"],
        envs=["production"],
    )

    payload = service.list_payload(user=user, search="S1", page=2, per_page=20)

    assert reports.arguments == {
        "asp_ids": ["hema_gmsv1"],
        "environments": ["production"],
        "search": "S1",
        "page": 2,
        "per_page": 20,
    }
    assert findings.requested_oids == [reports.report_oid]
    assert payload["reports"][0]["sample_id"] == "S1"
    assert payload["reports"][0]["finding_count"] == 3
    assert payload["reports"][0]["analysis_counts"] == {"SNV": 2, "CNV": 1}
    assert payload["reports"][0]["has_pdf"] is True
    assert payload["has_next"] is False


def test_report_library_superuser_uses_unrestricted_scope():
    reports = ReportRepositoryStub()
    findings = ReportedVariantRepositoryStub(reports.report_oid)
    service = ReportLibraryService(
        report_repository=reports,
        reported_variant_repository=findings,
    )
    user = SimpleNamespace(is_superuser=True, asp_ids=[], envs=[])

    service.list_payload(user=user, search="", page=1, per_page=30)

    assert reports.arguments["asp_ids"] is None
    assert reports.arguments["environments"] is None
