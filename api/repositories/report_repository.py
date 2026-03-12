"""Canonical report repository."""

from api.infra.repositories.dna_reporting_mongo import MongoDNAReportingRepository as ReportRepository

__all__ = ["ReportRepository"]
