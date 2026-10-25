"""Transactional installation and collision checks for packaged demonstration configuration."""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from api.config.collections import load_collection_section
from api.infra.mongo.repositories.audit_outbox import enqueue_audit
from api.infra.mongo.repositories.clinical_rule_sets import build_revision_snapshot
from api.infra.mongo.repositories.query_rule_revisions import build_query_revision
from api.infra.mongo.transactions import run_transaction
from coyote3.domain.common.errors import api_error

IDENTITIES = {
    "assay_specific_panels": ("asp_collection", "asp_id"),
    "asp_configs": ("aspc_collection", "aspc_id"),
    "clinical_rule_sets": ("clinical_rule_sets_collection", "rule_set_id"),
    "insilico_genelists": ("insilico_genelist_collection", "isgl_id"),
    "diagnoses": ("diagnoses_collection", "diagnosis_id"),
    "diagnosis_associations": ("diagnosis_associations_collection", "diagnosis_id"),
    "query_rule_sets": ("query_rule_sets_collection", "scope_key"),
    "public_assay_catalog_versions": ("public_assay_catalog_versions_collection", "_id"),
}


class DemoInstallationRepository:
    """Keep demo writes on the configured application client and database."""

    @staticmethod
    def identifier(value: str | None) -> Any:
        """Allocate a provider ID or restore the bundle's fixed public catalogue ID.

        Args:
            value: Fixed serialized ID, or None to allocate a fresh ID.

        Returns:
            MongoDB identifier owned by the repository boundary.
        """
        return ObjectId(value) if value is not None else ObjectId()

    def __init__(self, database: Any) -> None:
        """Bind the explicitly selected application database."""
        self.database = database
        self.mapping = load_collection_section("primary")

    def configuration_installed(
        self, documents: dict, session: Any = None, *, require_packaged: bool = False
    ) -> bool:
        """Check whether every bundled configuration identity is already present.

        Args:
            documents: Validated bundled configuration grouped by logical collection.
            session: Optional session on this repository's client.
            require_packaged: Require recorded package provenance before resuming a starter install.

        Returns:
            True only when all identities are present.
        """
        for name, rows in documents.items():
            collection, key = IDENTITIES[name]
            for row in rows:
                selector = {key: row[key]}
                if name == "diagnosis_associations":
                    selector["asp_id"] = row["asp_id"]
                if not self.database[self.mapping[collection]].find_one(
                    {**selector, **({"system_installed": True} if require_packaged else {})},
                    {"_id": 1},
                    session=session,
                ):
                    return False
        return True

    def sample(self, name: str) -> dict | None:
        """Return a named sample's identity and provenance, or None."""
        return self.database[self.mapping["samples_collection"]].find_one({"name": name})

    def sample_reinstallable(self, sample: dict) -> bool:
        """Allow raw-data refresh only for system-owned demos without clinical review artifacts.

        Args:
            sample: Stored starter sample after the service validates its fixed assay and scope.

        Returns:
            False for non-system provenance, completed review, reports or comments.
        """
        if (
            sample.get("ingested_by") != "system"
            or sample.get("reported")
            or sample.get("latest_report_id")
        ):
            return False
        identity = {
            "$or": [
                {"sample_oid": {"$in": [sample["_id"], str(sample["_id"])]}},
                {"SAMPLE_ID": str(sample["_id"])},
            ]
        }
        for key in (
            "reports_collection",
            "reported_variants_collection",
            "sample_comments_collection",
            "finding_comments_collection",
            "rna_classification_collection",
        ):
            if self.database[self.mapping[key]].find_one(identity) is not None:
                return False
        return True

    def repair_configuration(self, documents: dict, actor: str) -> None:
        """Restore missing packaged identities without replacing existing configuration/history.

        Args:
            documents: Validated server-owned starter configuration.
            actor: Authenticated administrator recorded in the repair audit.

        Raises:
            AppError: A packaged identity belongs to center-owned configuration.
        """
        documents = deepcopy(documents)

        def repair(session: Any) -> None:
            """Insert missing identities and capture baselines within the owning transaction."""
            self._require_baseline(documents, session)
            for name, rows in documents.items():
                attribute, key = IDENTITIES[name]
                target = self.database[self.mapping[attribute]]
                for row in rows:
                    selector = {key: row[key]}
                    if name == "diagnosis_associations":
                        selector["asp_id"] = row["asp_id"]
                    existing = target.find_one(selector, session=session)
                    if existing is not None:
                        if not existing.get("system_installed"):
                            raise api_error(409, "Demo identity belongs to center configuration")
                        continue
                    target.insert_one(row, session=session)
                    if name == "clinical_rule_sets":
                        self.database[
                            self.mapping["clinical_rule_revisions_collection"]
                        ].insert_one(
                            build_revision_snapshot(
                                row,
                                action="baseline_captured",
                                actor=actor,
                                occurred_at=datetime.now(timezone.utc),
                                reason="Missing packaged demonstration baseline restored",
                                previous_revision_hash=None,
                            ),
                            session=session,
                        )
                    elif name == "query_rule_sets":
                        self.database[self.mapping["query_rule_revisions_collection"]].insert_one(
                            build_query_revision(row, "system_installed"), session=session
                        )
                    elif name == "public_assay_catalog_versions":
                        self.database[
                            self.mapping["public_assay_catalog_revisions_collection"]
                        ].insert_one(
                            {
                                "version_id": str(row["_id"]),
                                "revision": row["revision"],
                                "document": row,
                            },
                            session=session,
                        )
            enqueue_audit(
                self.database,
                session,
                event_type="demo.configuration.repaired",
                resource_type="demo_configuration",
                resource_id="clinical_workflows",
                actor=actor,
            )

        run_transaction(self.database.client, repair)

    def install(self, documents: dict, actor: str) -> None:
        """Insert the entire configuration and report revisions, rejecting any existing identity.

        Args:
            documents: Contract-valid synthetic records grouped by logical collection.
            actor: Authenticated installer username for revision provenance.

        Raises:
            AppError: Application baseline is missing or a fixture identity already exists.
        """

        documents = deepcopy(documents)

        def write(session: Any) -> None:
            """Validate prerequisites and insert all configuration in one transaction."""
            self.preflight(documents, session)
            live = self.database[self.mapping["public_assay_catalog_collection"]]
            for row in documents.get("public_assay_catalog_versions", []):
                if live.find_one({}, session=session) is None:
                    now = datetime.now(timezone.utc)
                    row.update(
                        status="published", content_version=1, published_at=now, published_by=actor
                    )
                    row["lifecycle"] = [
                        {
                            "action": "system_installed",
                            "actor": actor,
                            "occurred_at": now,
                            "reason": "Packaged synthetic demonstration catalog baseline",
                        }
                    ]
                    live.insert_one(
                        {
                            **row["catalog"],
                            "created_by": "system",
                            "updated_by": "system",
                            "system_installed": True,
                        },
                        session=session,
                    )
            for name, rows in documents.items():
                self.database[self.mapping[IDENTITIES[name][0]]].insert_many(rows, session=session)
            now = datetime.now(timezone.utc)
            revisions = [
                build_revision_snapshot(
                    row,
                    action="baseline_captured",
                    actor=actor,
                    occurred_at=now,
                    reason="Packaged synthetic demonstration reporting baseline installed",
                    previous_revision_hash=None,
                )
                for row in documents["clinical_rule_sets"]
            ]
            self.database[self.mapping["clinical_rule_revisions_collection"]].insert_many(
                revisions, session=session
            )
            for row in documents.get("query_rule_sets", []):
                self.database[self.mapping["query_rule_revisions_collection"]].insert_one(
                    build_query_revision(row, "system_installed"), session=session
                )
            for row in documents.get("public_assay_catalog_versions", []):
                self.database[self.mapping["public_assay_catalog_revisions_collection"]].insert_one(
                    {"version_id": str(row["_id"]), "revision": row["revision"], "document": row},
                    session=session,
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
        self._require_baseline(documents, session)
        for name, rows in documents.items():
            collection, key = IDENTITIES[name]
            if self.database[self.mapping[collection]].find_one(
                {key: {"$in": [row[key] for row in rows]}}, session=session
            ):
                raise api_error(409, "Demo configuration already exists; no records replaced")

    def _require_baseline(self, documents: dict, session: Any = None) -> None:
        """Require registered active groups and query policies before adding demo identities.

        Args:
            documents: Bundled configuration containing assay group references.
            session: Owning application transaction, or None for read-only validation.

        Raises:
            AppError: An assay group or the application query baseline is missing.
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
