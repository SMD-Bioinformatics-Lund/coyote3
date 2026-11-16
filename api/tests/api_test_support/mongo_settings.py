"""Explicit synthetic audit configuration for persistence tests and their host fixtures."""

import logging
import os

from coyote_api.config.backend import audit_context_from_runtime
from coyote_mongo.config.settings import AuditContext
from coyote_mongo.runtime_adapter import MongoRuntime


def audit_context() -> AuditContext:
    """Build audit identity from the test's controlled host environment.

    Returns:
        Deployment context honoring endpoint overrides selected by the test fixture.
    """
    return audit_context_from_runtime(os.environ)


def mongo_runtime() -> MongoRuntime:
    """Return a minimal explicit persistence runtime for collection-only test adapters.

    Returns:
        Independent runtime with synthetic audit ownership and no host secrets.
    """
    return MongoRuntime(
        config={}, logger=logging.getLogger("synthetic-mongo"), audit=audit_context()
    )
