# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Bind the packaged demonstration to deployment databases for initial installation."""

import os
from collections.abc import Mapping
from contextlib import closing
from types import SimpleNamespace
from typing import Any

from coyote_api.config.bootstrap import configure_center_from_environment  # noqa: E402

# Bind the host profile before importing vocabulary-dependent contracts.
configure_center_from_environment()

from coyote.application.ingest.service import InternalIngestService  # noqa: E402
from coyote_mongo.config.collections import load_collection_section  # noqa: E402
from coyote_mongo.repositories.anno_vep import AnnoVepRepository  # noqa: E402
from coyote_mongo.repositories.demo_installation import DemoInstallationRepository  # noqa: E402
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway  # noqa: E402

from coyote_demo.deployment import (  # noqa: E402
    DEMO_DATABASES,
    DEMO_MONGO_URI_KEYS,
    runtime_validator,
    validate_demo_privileges,
    validate_demo_target,
)
from coyote_demo.installation import DemoInstallationService  # noqa: E402


def validate_runtime_credentials(settings: Mapping[str, Any]) -> None:
    """Verify expanded privileges before the host initializes application persistence.

    Args:
        settings: Previously validated, explicitly projected demonstration endpoints.

    Raises:
        ValueError: The authenticated credentials exceed the four demo databases.
        PyMongoError: An endpoint cannot authenticate or inspect its current privileges.
    """
    from coyote_mongo.security_scope import authenticated_privileges

    for uri in dict.fromkeys(settings[key] for key in DEMO_MONGO_URI_KEYS):
        validate_demo_privileges(authenticated_privileges(uri))


def install_resources(
    settings: Mapping[str, Any], *, actor: str, starter: bool, apply: bool
) -> dict[str, Any]:
    """Plan or install package resources using explicitly scoped local Mongo connections.

    Args:
        settings: Reviewed demonstration targets and restricted credentials.
        actor: Existing demonstration administrator recorded in installation evidence.
        starter: Include synthetic starter samples in addition to their configuration.
        apply: Perform writes only when true; otherwise inspect the installation plan.

    Returns:
        The existing installation outcome or read-only plan.

    Raises:
        ValueError: Targets, actor or database privileges are unsafe.
        AppError: Existing configuration or sample identities conflict.
    """
    validate_demo_target(settings)
    if not actor.strip():
        raise ValueError("Actor must not be blank")
    from coyote_mongo.connections import MongoConnections

    with closing(MongoConnections(settings)) as connections:
        databases = connections.databases
        validate_database_clients(settings, **databases)
        service = build_demo_service(
            databases["primary"], databases["knowledgebase"], settings=settings
        )
        if starter:
            return service.install_starter(actor) if apply else service.plan().model_dump()
        documents = service.configuration(actor)
        service.repository.preflight(documents)
        return (
            service.install_configuration(actor)
            if apply
            else {name: len(rows) for name, rows in documents.items()}
        )


def validate_database_clients(settings: Mapping[str, Any], **databases: Any) -> None:
    """Check actual database handles and privileges before any synthetic data is written.

    Args:
        settings: Reviewed isolated demonstration configuration.
        **databases: Explicit primary, identity, knowledgebase or bam database handles.

    Raises:
        ValueError: A database handle selects ordinary data or credentials exceed demo scope.
        PyMongoError: The authenticated privilege inspection fails; installation stops.
    """
    from coyote_mongo.security_scope import authenticated_client_privileges

    validate_demo_target(settings)
    names = {
        "primary": DEMO_DATABASES["COYOTE4_DB"],
        "identity": DEMO_DATABASES["IDENTITY_DB"],
        "knowledgebase": DEMO_DATABASES["KNOWLEDGEBASE_DB"],
        "bam": DEMO_DATABASES["BAM_DB"],
    }
    checked: set[int] = set()
    for key, database in databases.items():
        if key not in names or database.name != names[key]:
            raise ValueError("Demo installation requires dedicated database handles")
        client = database.client
        if id(client) not in checked:
            validate_demo_privileges(authenticated_client_privileges(client))
            checked.add(id(client))


def build_demo_service(
    primary: Any, knowledgebase: Any, *, settings: Mapping[str, Any] | None = None
) -> DemoInstallationService:
    """Reuse normal ingestion and configured collections for packaged demonstration samples.

    Args:
        primary: Explicit application database receiving configuration and synthetic samples.
        knowledgebase: Explicit knowledgebase database used for gene lookups.
        settings: Explicit isolated deployment settings; None reads the process environment.

    Returns:
        Demo service with normal transactional parsing and no API-runtime dependency.

    Raises:
        ValueError: Configuration, actual database handles or credentials are not demo-restricted.
    """
    from coyote_api.config.backend import audit_context_from_runtime

    settings = (
        {key: os.environ.get(key) for key in runtime_validator.configuration_keys}
        if settings is None
        else dict(settings)
    )
    validate_database_clients(settings, primary=primary, knowledgebase=knowledgebase)
    mapping = load_collection_section("primary")
    references = load_collection_section("knowledgebase")
    collections = {name: primary[name] for name in mapping.values()}
    collections["hgnc_genes"] = knowledgebase[references["hgnc_collection"]]
    ingest = InternalIngestService(
        collection_gateway=IngestCollectionGateway(
            context=audit_context_from_runtime(settings), collections=collections
        ),
        anno_vep_repository=AnnoVepRepository(
            SimpleNamespace(anno_vep_collection=primary[mapping["anno_vep_collection"]])
        ),
        invalidate_dashboard_metrics=lambda: None,
    )
    return DemoInstallationService(
        DemoInstallationRepository(primary, context=audit_context_from_runtime(settings)),
        ingest,
        identifier_factory=DemoInstallationRepository.identifier,
    )


def start_background_service(service: str, options: list[str]) -> int | None:
    """Run ordinary maintenance tasks or scheduling after the demo CLI preflight.

    Args:
        service: The validated runtime selection, maintenance or beat.
        options: CLI-validated log level and optional worker concurrency arguments.

    Returns:
        Celery's process exit status.

    Raises:
        ValueError: The selection is not maintenance or beat.
        SystemExit: Celery rejects a runtime setting or cannot start.

    Notes:
        Called by coyote_demo.runtime only after target and credential validation.
        Scheduler files are stored below the isolated demo data directory.
    """
    if service not in {"maintenance", "beat"}:
        raise ValueError("Unsupported demo background service")
    from coyote_api.celery_app import celery_app
    from coyote_api.config.runtime_settings import DefaultConfig

    if service == "maintenance":
        return celery_app.start(
            ["worker", "--queues", DefaultConfig.CELERY_DEFAULT_QUEUE, *options]
        )
    from coyote_api.config.paths import COYOTE4_DATA_CONTAINER_ROOT

    COYOTE4_DATA_CONTAINER_ROOT.mkdir(parents=True, exist_ok=True)
    return celery_app.start(
        [
            "beat",
            *options,
            f"--schedule={COYOTE4_DATA_CONTAINER_ROOT / 'celerybeat-schedule'}",
            f"--pidfile={COYOTE4_DATA_CONTAINER_ROOT / 'celerybeat.pid'}",
        ]
    )
