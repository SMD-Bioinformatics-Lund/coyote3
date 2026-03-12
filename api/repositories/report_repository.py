"""Reporting repository facade."""

from api.infra.repositories.dna_reporting_mongo import MongoDNAReportingRepository


class ReportRepository(MongoDNAReportingRepository):
    """Concrete reporting repository facade."""


__all__ = ["ReportRepository"]
