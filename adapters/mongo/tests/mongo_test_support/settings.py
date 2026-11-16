"""Explicit synthetic adapter settings without application environment discovery."""

import logging

from coyote_mongo.config.settings import AuditContext
from coyote_mongo.runtime_adapter import MongoRuntime


def audit_context():
    """Return the fixed audit namespace of this synthetic adapter fixture."""
    return AuditContext(environment="test", route="synthetic-identity-route")


def mongo_runtime():
    """Return a collection-only runtime with synthetic audit ownership."""
    return MongoRuntime(
        config={},
        logger=logging.getLogger("synthetic-mongo"),
        audit=audit_context(),
    )
