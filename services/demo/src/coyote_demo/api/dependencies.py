# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Bind demo routes to current authorization and restricted demonstration databases."""

import os

from coyote.application.common.execution_context import current_request_id
from coyote_api.app.application_factory import open_authenticated_runtime
from coyote_api.app.deps.repositories import get_store
from coyote_api.app.deps.services import get_internal_ingest_service
from coyote_api.app.runtime_state import app as runtime_app
from coyote_api.config.backend import audit_context_from_runtime
from coyote_api.security.access import get_request_api_session
from coyote_mongo.repositories.demo_installation import DemoInstallationRepository
from fastapi import Request

from coyote_demo.deployment import runtime_validator, validate_demo_target
from coyote_demo.host import validate_database_clients
from coyote_demo.installation import DemoInstallationService
from coyote_demo.operations import DemoInstallation


def get_demo_service() -> DemoInstallationService:
    """Validate active settings and database privileges before composing any demo writes.

    Returns:
        Installer using the normal transactional ingestion and repository implementations.

    Raises:
        ValueError: Settings, actual database names or expanded Mongo privileges are unsafe.
    """
    settings = {
        key: runtime_app.config.get(key, os.environ.get(key))
        for key in runtime_validator.configuration_keys
    }
    validate_demo_target(settings)
    store = get_store()
    validate_database_clients(
        settings,
        primary=store.coyote_db,
        identity=store.identity_db,
        knowledgebase=store.knowledgebase_db,
        bam=store.bam_db,
    )
    repository = DemoInstallationRepository(
        store.coyote_db, context=audit_context_from_runtime(settings)
    )
    return DemoInstallationService(
        repository, get_internal_ingest_service(), identifier_factory=repository.identifier
    )


def get_demo_installation(request: Request) -> DemoInstallation:
    """Resolve session permissions before the guarded installer performs database operations.

    Args:
        request: Incoming request whose session was authenticated by the host.

    Returns:
        Package-owned operations retaining host access auditing and demo:install permission.
    """
    session = get_request_api_session(request)
    return DemoInstallation(
        open_authenticated_runtime(session.token, correlation_id=current_request_id()),
        get_demo_service,
    )
