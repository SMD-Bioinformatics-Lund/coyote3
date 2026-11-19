# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""MongoDB persistence and owning-client retention transactions for runtime controls."""

from datetime import datetime
from typing import Any

from pymongo import ReturnDocument

from coyote_mongo.config.operational_collections import OPERATIONAL_COLLECTIONS
from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.mutations import write_with_audit
from coyote_mongo.transactions import run_transaction


class MongoAppControlsRepository:
    """Keep control persistence and audit retention on their configured database clients."""

    def __init__(
        self, db: Any, *, identity_db: Any, config: dict[str, Any], context: AuditContext
    ) -> None:
        """Bind controls and audit collections to independently configured databases.

        Args:
            db: Application database owning operational controls.
            identity_db: Identity database owning audit records.
            config: Deployment collection-name configuration.
            context: Owning deployment's transactional audit identity.
        """
        self.controls = db[OPERATIONAL_COLLECTIONS.app_controls]
        self.audit_context = context
        self.audit = identity_db[OPERATIONAL_COLLECTIONS.operational_audit_events]

    def read(self) -> dict[str, Any] | None:
        """Return persisted controls without exposing a MongoDB collection."""
        return self.controls.find_one(
            {"control_id": OPERATIONAL_COLLECTIONS.app_controls_document_id}
        )

    def retention_override(self) -> dict[str, Any] | None:
        """Read the persisted operational audit-retention interval."""
        return self.controls.find_one(
            {"control_id": OPERATIONAL_COLLECTIONS.app_controls_document_id},
            {"retention.audit_events_days": 1},
        )

    def save(self, document: dict[str, Any], *, now: datetime) -> dict[str, Any]:
        """Upsert validated controls and retain their original creation timestamp.

        Args:
            document: Validated control fields excluding creation metadata.
            now: Current UTC time used only when inserting the initial document.

        Returns:
            Persisted replacement state after the update.
        """
        return write_with_audit(
            self.controls,
            "find_one_and_update",
            {"control_id": OPERATIONAL_COLLECTIONS.app_controls_document_id},
            {"$set": document, "$setOnInsert": {"created_on": now}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
            context=self.audit_context,
        )

    def delete_operational_audit_before(self, cutoff: datetime) -> int:
        """Remove expired operational events in a transaction on the audit client's session.

        Args:
            cutoff: Exclusive UTC occurrence-time bound; traceability events are retained.

        Returns:
            Number of deleted operational events after commit.
        """
        result = run_transaction(
            self.audit.database.client,
            lambda session: write_with_audit(
                self.audit,
                "delete_many",
                {"retention_class": "operational", "occurred_at": {"$lt": cutoff}},
                session=session,
                context=self.audit_context,
            ),
        )
        return int(result.deleted_count)
