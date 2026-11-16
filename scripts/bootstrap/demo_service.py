# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Bind the packaged demonstration to deployment databases for initial installation."""

import os
from types import SimpleNamespace
from typing import Any

from coyote_api.config.bootstrap import configure_center_from_environment  # noqa: E402

# Bind the host profile before importing vocabulary-dependent contracts.
configure_center_from_environment()

from coyote.application.ingest.service import InternalIngestService  # noqa: E402
from coyote_api.services.provisioning.demo_installation import DemoInstallationService  # noqa: E402
from coyote_mongo.config.collections import load_collection_section  # noqa: E402
from coyote_mongo.repositories.anno_vep import AnnoVepRepository  # noqa: E402
from coyote_mongo.repositories.demo_installation import DemoInstallationRepository  # noqa: E402
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway  # noqa: E402


def build_demo_service(primary: Any, knowledgebase: Any) -> DemoInstallationService:
    """Reuse normal ingestion and configured collections for packaged demonstration samples.

    Args:
        primary: Explicit application database receiving configuration and synthetic samples.
        knowledgebase: Explicit knowledgebase database used for gene lookups.

    Returns:
        Demo service with normal transactional parsing and no API-runtime dependency.
    """
    from coyote_api.config.backend import audit_context_from_runtime

    mapping = load_collection_section("primary")
    references = load_collection_section("knowledgebase")
    collections = {name: primary[name] for name in mapping.values()}
    collections["hgnc_genes"] = knowledgebase[references["hgnc_collection"]]
    ingest = InternalIngestService(
        collection_gateway=IngestCollectionGateway(
            context=audit_context_from_runtime(os.environ), collections=collections
        ),
        anno_vep_repository=AnnoVepRepository(
            SimpleNamespace(anno_vep_collection=primary[mapping["anno_vep_collection"]])
        ),
        invalidate_dashboard_metrics=lambda: None,
    )
    return DemoInstallationService(
        DemoInstallationRepository(primary, context=audit_context_from_runtime(os.environ)),
        ingest,
        identifier_factory=DemoInstallationRepository.identifier,
    )
