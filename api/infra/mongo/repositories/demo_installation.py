"""Transactional installation and collision checks for packaged demonstration configuration."""

from datetime import datetime, timezone
from typing import Any

from api.config.loaders.collections import load_collection_section
from api.domain.common.errors import api_error
from api.infra.mongo.repositories.audit_outbox import enqueue_audit
from api.infra.mongo.repositories.clinical_rule_sets import build_revision_snapshot
from api.infra.mongo.transactions import run_transaction

IDENTITIES = {
    "assay_specific_panels": ("asp_collection", "asp_id"),
    "asp_configs": ("aspc_collection", "aspc_id"),
    "clinical_rule_sets": ("clinical_rule_sets_collection", "rule_set_id"),
    "insilico_genelists": ("insilico_genelist_collection", "isgl_id"),
    "subpanels": ("subpanels_collection", "subpanel_id"),
    "subpanel_associations": ("subpanel_associations_collection", "subpanel_id"),
}


class DemoInstallationRepository:
    """Keep demo writes on the configured application client and database."""

    def __init__(self, database: Any) -> None:
        """Bind the explicitly selected application database."""
        self.database = database
        self.mapping = load_collection_section("primary")

    def configuration_installed(self, documents: dict, session: Any = None) -> bool:
        """Check whether every bundled configuration identity is already present.

        Args:
            documents: Validated bundled configuration grouped by logical collection.
            session: Optional session on this repository's client.

        Returns:
            True only when all identities are present.
        """
        for name, rows in documents.items():
            collection, key = IDENTITIES[name]
            for row in rows:
                if not self.database[self.mapping[collection]].find_one(
                    {key: row[key]}, {"_id": 1}, session=session
                ):
                    return False
        return True

    def sample(self, name: str) -> dict | None:
        """Return identity fields for an existing named sample, or None."""
        return self.database[self.mapping["samples_collection"]].find_one(
            {"name": name}, {"_id": 1, "name": 1, "asp_id": 1, "environment": 1}
        )

    def install(self, documents: dict, actor: str) -> None:
        """Insert the entire configuration and report revisions, rejecting any existing identity.

        Args:
            documents: Contract-valid synthetic records grouped by logical collection.
            actor: Authenticated installer username for revision provenance.

        Raises:
            AppError: Application baseline is missing or a fixture identity already exists.
        """

        def write(session: Any) -> None:
            """Validate prerequisites and insert all configuration in one transaction."""
            self.preflight(documents, session)
            for name, rows in documents.items():
                self.database[self.mapping[IDENTITIES[name][0]]].insert_many(rows, session=session)
            now = datetime.now(timezone.utc)
            revisions = [
                build_revision_snapshot(
                    row,
                    action="baseline_captured",
                    actor=actor,
                    occurred_at=now,
                    reason="Synthetic demonstration draft installed",
                    previous_revision_hash=None,
                )
                for row in documents["clinical_rule_sets"]
            ]
            self.database[self.mapping["clinical_rule_revisions_collection"]].insert_many(
                revisions, session=session
            )
            enqueue_audit(
                self.database,
                session,
                event_type="demo.configuration.installed",
                resource_type="demo_configuration",
                resource_id="clinical_workflows",
                actor=actor,
                metadata={"collections": len(documents)},
            )

        run_transaction(self.database.client, write)

    def preflight(self, documents: dict, session: Any = None) -> None:
        """Require registered groups and reject existing fixture identities without writes.

        Args:
            documents: Validated bundle grouped by logical collection.
            session: Owning write transaction, or None for a read-only plan.

        Raises:
            AppError: Required groups are absent or a fixture identity already exists.
        """
        groups = {row["asp_group"] for row in documents["assay_specific_panels"]}
        registered = {
            row["group_id"]
            for row in self.database[self.mapping["assay_groups_collection"]].find(
                {"is_active": {"$ne": False}}, session=session
            )
        }
        if groups - registered or not self.database[
            self.mapping["query_rule_sets_collection"]
        ].find_one({}, session=session):
            raise api_error(409, "Install the application group and query-rule baseline first")
        for name, rows in documents.items():
            collection, key = IDENTITIES[name]
            if self.database[self.mapping[collection]].find_one(
                {key: {"$in": [row[key] for row in rows]}}, session=session
            ):
                raise api_error(409, "Demo configuration already exists; no records replaced")
