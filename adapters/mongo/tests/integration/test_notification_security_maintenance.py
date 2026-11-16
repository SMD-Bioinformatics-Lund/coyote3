"""Focused tests for notification transport, security indexes, and maintenance tasks."""

from __future__ import annotations

import logging

import mongomock
from coyote_mongo.config.operational_collections import (
    get_api_sessions_collection_name,
    get_audit_events_collection_name,
)
from coyote_mongo.security_indexes import _create_index, ensure_security_indexes
from pymongo.errors import OperationFailure


def test_identity_collection_names_follow_the_identity_mapping() -> None:
    config = {
        "IDENTITY_DB": "identity",
        "DB_COLLECTIONS_CONFIG": {
            "identity": {
                "api_sessions_collection": "sessions",
                "audit_events_collection": "audit",
            }
        },
    }

    assert get_api_sessions_collection_name(config) == "sessions"
    assert get_audit_events_collection_name(config) == "audit"


def test_security_indexes_are_created_and_failures_are_nonfatal() -> None:
    """Security collections receive required indexes while one conflict is logged."""
    client = mongomock.MongoClient()
    primary_database = client["coyote4_test"]
    identity_database = client["coyote4_identity_test"]
    logger = logging.getLogger("test.security.indexes")
    ensure_security_indexes(
        primary_db=primary_database,
        identity_db=identity_database,
        config={},
        logger=logger,
    )
    assert "ttl_api_session_expiry" in identity_database.api_sessions.index_information()
    assert (
        identity_database.api_sessions.index_information()["ttl_api_session_expiry"][
            "expireAfterSeconds"
        ]
        == 0
    )
    assert "idx_audit_actor_time" in identity_database.audit_events.index_information()
    assert primary_database.app_controls.index_information()["uniq_app_controls_control_id"][
        "unique"
    ]
    assert "api_sessions" not in primary_database.list_collection_names()
    assert "app_controls" not in identity_database.list_collection_names()

    class BrokenCollection:
        name = "broken"

        def create_index(self, *_args, **_kwargs):
            raise OperationFailure("conflict")

    _create_index(BrokenCollection(), [("field", 1)], name="broken_index", logger=logger)
