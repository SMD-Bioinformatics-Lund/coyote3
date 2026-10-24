"""Bind the packaged demonstration to deployment databases for initial installation."""

from types import SimpleNamespace
from typing import Any

from api.application.ingest.service import InternalIngestService
from api.application.provisioning.demo_installation import DemoInstallationService
from api.application.query_rules.service import QueryRuleService
from api.config.loaders.collections import load_collection_section
from api.infra.mongo.repositories.anno_vep import AnnoVepRepository
from api.infra.mongo.repositories.demo_installation import DemoInstallationRepository
from api.infra.mongo.repositories.ingest_gateway import IngestCollectionGateway
from api.infra.mongo.repositories.query_rules import QueryRuleRepository


def build_demo_service(primary: Any, knowledgebase: Any) -> DemoInstallationService:
    """Reuse normal ingestion and configured collections for packaged demonstration samples.

    Args:
        primary: Explicit application database receiving configuration and synthetic samples.
        knowledgebase: Explicit knowledgebase database used for gene lookups.

    Returns:
        Demo service with normal transactional parsing and no API-runtime dependency.
    """
    mapping = load_collection_section("primary")
    references = load_collection_section("knowledgebase")
    collections = {name: primary[name] for name in mapping.values()}
    collections["hgnc_genes"] = knowledgebase[references["hgnc_collection"]]
    ingest = InternalIngestService(
        collection_gateway=IngestCollectionGateway(collections=collections),
        anno_vep_repository=AnnoVepRepository(
            SimpleNamespace(anno_vep_collection=primary[mapping["anno_vep_collection"]])
        ),
        invalidate_dashboard_metrics=lambda: None,
    )
    rules = QueryRuleService(
        QueryRuleRepository(
            SimpleNamespace(
                query_rule_sets_collection=primary[mapping["query_rule_sets_collection"]],
                query_rule_revisions_collection=primary[mapping["query_rule_revisions_collection"]],
            )
        )
    )
    return DemoInstallationService(
        DemoInstallationRepository(primary), ingest, query_rule_service=rules
    )
