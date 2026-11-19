"""Explicit synthetic core composition for Relay HTTP regression tests."""

from types import SimpleNamespace
from unittest.mock import Mock

from coyote.application.operations import ApplicationRuntime
from coyote.application.operations.ingest import Ingestion
from coyote_api.app.application_factory import ingest_submission_services


def ingestion_operations(service, user):
    """Bind real ingestion operations while retaining update and scope policy checks."""
    runtime = ApplicationRuntime(
        authenticate=lambda: user,
        policy_factory=lambda actor: SimpleNamespace(
            permission_allowed=lambda actor, permission_id, **kwargs: (
                permission_id != "sample:edit:own" or permission_id in actor.permissions
            ),
            scope_allowed=lambda actor, context: (
                context.get("asp_id") in actor.asp_ids and context.get("environment") in actor.envs
            ),
        ),
        sample_loader=lambda identity: None,
        assay_loader=lambda identity: {"asp_group": "synthetic"},
        audit_access=Mock(),
    )
    return Ingestion(runtime, lambda: service, ingest_submission_services())
