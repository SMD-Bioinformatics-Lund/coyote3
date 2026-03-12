"""Canonical DNA route repository."""

from api.infra.repositories.dna_route_mongo import MongoDNARouteRepository as DnaRouteRepository

__all__ = ["DnaRouteRepository"]
