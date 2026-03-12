"""Canonical sample repository."""

from api.infra.repositories.samples_mongo import MongoSamplesRepository as SampleRepository

__all__ = ["SampleRepository"]
