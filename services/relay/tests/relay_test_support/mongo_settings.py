"""Explicit synthetic persistence identity for ingestion worker tests."""

import logging

from coyote_mongo.config.settings import AuditContext
from coyote_mongo.runtime_adapter import MongoRuntime


def mongo_runtime() -> MongoRuntime:
    """Build an isolated runtime with no environment-derived secrets or connections."""
    return MongoRuntime(
        config={},
        logger=logging.getLogger("synthetic-ingest"),
        audit=AuditContext(environment="development", route="synthetic-ingest"),
    )
