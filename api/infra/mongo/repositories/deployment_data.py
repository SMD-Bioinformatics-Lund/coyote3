"""Install or explicitly repair bundled catalogs while preserving unrelated data and history."""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from api.config.loaders.collections import load_collection_section
from api.contracts.deployment_data import DeploymentDataScope
from api.domain.common.errors import api_error
from api.infra.mongo.repositories.audit_outbox import enqueue_audit
from api.infra.mongo.repositories.knowledgebase_publications import record_reference_publication
from api.infra.mongo.repositories.query_rule_revisions import build_query_revision
from api.infra.mongo.transactions import run_transaction

DEPLOYMENT_COLLECTIONS = {
    "identity": {"permissions": "permissions_collection", "roles": "roles_collection"},
    "application": {
        "assay_groups": "assay_groups_collection",
        "query_rule_sets": "query_rule_sets_collection",
    },
    "knowledgebase": {
        "vep_diagrams": "vep_diagrams_collection",
        "hgnc_genes": "hgnc_collection",
        "vep_metadata": "vep_metadata_collection",
    },
}
CATALOG_KEYS = {
    "permissions": "permission_id",
    "roles": "role_id",
    "assay_groups": "group_id",
    "query_rule_sets": "scope_key",
    "hgnc_genes": "hgnc_id",
    "vep_metadata": "vep_id",
    "vep_diagrams": "_id",
}


class DeploymentDataRepository:
    """Keep identity, application and knowledgebase operations on their configured clients."""

    def __init__(self, application: Any, knowledgebase: Any, identity: Any) -> None:
        """Bind explicit database handles; no URI or database name is inferred."""
        self.databases = {
            "application": application,
            "knowledgebase": knowledgebase,
            "identity": identity,
        }

    def _targets(self, scope: DeploymentDataScope) -> list[tuple[str, str, Any, str]]:
        """Resolve logical catalog names and physical collections for the selected scope."""
        targets = []
        for group, names in DEPLOYMENT_COLLECTIONS.items():
            if scope not in {group, "all"}:
                continue
            mapping = load_collection_section("primary" if group == "application" else group)
            targets.extend(
                (group, name, self.databases[group], mapping[key]) for name, key in names.items()
            )
        return targets

    def pending(self, scope: DeploymentDataScope) -> list[str]:
        """Return empty catalog names using read-only occupancy checks.

        Args:
            scope: Identity catalogs, application catalogs, knowledgebase references, or all.

        Returns:
            Logical names of empty selected collections; no stored records are returned.
        """
        return [
            name
            for _, name, db, collection in self._targets(scope)
            if db[collection].find_one({}, {"_id": 1}) is None
        ]

    def skipped(self, scope: DeploymentDataScope) -> dict[str, str]:
        """Return a no-op result without loading seed data.

        Args:
            scope: Selected deployment-data group.

        Returns:
            A skipped status for each selected logical collection.
        """
        return {name: "skipped" for _, name, _, _ in self._targets(scope)}

    def install(
        self, documents: dict, *, scope: DeploymentDataScope, actor: str, force: bool = False
    ) -> dict[str, str]:
        """Install empty catalogs or repair explicitly selected installation-owned records.

        Args:
            documents: Validated server-owned records, partitioned by logical collection.
            scope: Selected deployment-data group.
            actor: Authenticated administrator username recorded in audit events.
            force: Repair known installation records without deleting unrelated documents.

        Returns:
            Loaded, skipped, empty, repaired or preserved status for each selected collection.

        Notes:
            Application and identity catalog writes and their audit receipts are transactional.
            Large reference batches retain their existing ordered-insert behavior;
            the API mutation audit records their authenticated installation request.
        """
        result = {}
        for group, name, database, collection in self._targets(scope):
            rows = deepcopy(documents.get(name) or [])
            if not force and database[collection].find_one({}, {"_id": 1}) is not None:
                result[name] = "skipped"
                continue
            if not rows:
                result[name] = "empty"
                continue

            def write(session: Any) -> str:
                """Recheck occupancy before inserting this catalog and its audit receipt."""
                if force:
                    status = self._repair(database, collection, name, rows, actor, session)
                    if status == "preserved":
                        return status
                elif database[collection].find_one({}, {"_id": 1}, session=session) is not None:
                    return "skipped"
                else:
                    database[collection].insert_many(rows, ordered=True, session=session)
                    status = "loaded"
                if name == "query_rule_sets" and not force:
                    revisions = load_collection_section("primary")[
                        "query_rule_revisions_collection"
                    ]
                    database[revisions].insert_many(
                        [build_query_revision(row, "baseline_captured") for row in rows],
                        session=session,
                    )
                if group == "knowledgebase":
                    record_reference_publication(
                        database, source=name, release="bundled", session=session
                    )
                else:
                    enqueue_audit(
                        database,
                        session,
                        event_type="deployment.data.installed",
                        resource_type="deployment_data",
                        resource_id=name,
                        actor=actor,
                        metadata={"collection": name, "records": len(rows)},
                    )
                return status

            result[name] = (
                run_transaction(database.client, write) if group != "knowledgebase" else write(None)
            )
        return result

    def _repair(
        self,
        database: Any,
        collection: str,
        name: str,
        rows: list[dict],
        actor: str,
        session: Any,
    ) -> str:
        """Repair bundled identities while retaining center records and reference releases.

        Args:
            database: Database owning the selected catalog.
            collection: Configured physical collection name.
            name: Logical bundled catalog name.
            rows: Validated server-owned baseline records.
            actor: Authenticated administrator for update provenance.
            session: Owning transaction for application/identity writes, otherwise None.

        Returns:
            repaired when any bundled identity changed, otherwise preserved.
        """
        target = database[collection]
        if name in DEPLOYMENT_COLLECTIONS["knowledgebase"]:
            versions = database[
                load_collection_section("knowledgebase")["knowledgebase_versions_collection"]
            ]
            bundled = versions.find_one({"source": name, "release": "bundled"})
            external = versions.find_one(
                {"source": name, "release": {"$ne": "bundled"}, "status": "active"}
            )
            if target.find_one({}, {"_id": 1}) is not None:
                if external is not None:
                    return "preserved"
                if bundled is None:
                    # A failed initial batch may precede its publication receipt. Recover
                    # only records with system provenance or known content-addressed IDs.
                    unknown = (
                        {"_id": {"$nin": [row["_id"] for row in rows]}}
                        if name == "vep_diagrams"
                        else {"created_by": {"$ne": "system"}}
                    )
                    if target.find_one(unknown, {"_id": 1}) is not None:
                        return "preserved"
        changed = False
        key = CATALOG_KEYS[name]
        now = datetime.now(timezone.utc)
        for source in rows:
            selector = {key: source[key]}
            existing = target.find_one(selector, session=session)
            if name == "query_rule_sets":
                changed = self._repair_query(database, source, actor, session) or changed
                continue
            if existing is None:
                if key != "_id":
                    source.pop("_id", None)
                target.insert_one(source, session=session)
                changed = True
                continue
            if name == "permissions":
                # Permission policies are immutable at runtime; never overwrite local policy.
                continue
            if name == "roles":
                if not existing.get("system_managed"):
                    continue
                grants = sorted(set(existing.get("permissions", [])) | set(source["permissions"]))
                if grants != sorted(existing.get("permissions", [])):
                    target.update_one(
                        {"_id": existing["_id"]},
                        {"$set": {"permissions": grants, "updated_by": actor, "updated_on": now}},
                        session=session,
                    )
                    changed = True
                continue
            if name == "assay_groups":
                if not existing.get("system_managed"):
                    continue
                values = {field: source[field] for field in ("display_name", "description")}
                if any(existing.get(field) != value for field, value in values.items()):
                    target.update_one(
                        {"_id": existing["_id"]},
                        {
                            "$set": {**values, "updated_by": actor, "updated_on": now},
                            "$inc": {"version": 1},
                        },
                        session=session,
                    )
                    changed = True
                continue
            if name == "vep_diagrams" or existing.get("created_by") == "system":
                replacement = {
                    **source,
                    "_id": existing["_id"],
                    **(
                        {
                            field: existing[field]
                            for field in ("created_by", "created_on")
                            if field in existing
                        }
                    ),
                }
                if name != "vep_diagrams":
                    replacement.update(updated_by=actor, updated_on=now)
                target.replace_one({"_id": existing["_id"]}, replacement, session=session)
                changed = True
        return "repaired" if changed else "preserved"

    def _repair_query(self, database: Any, source: dict, actor: str, session: Any) -> bool:
        """Publish a changed bundled policy as a new version, preserving center publications.

        Args:
            database: Application database owning rules and immutable revision history.
            source: Validated published baseline with a fixed scope key.
            actor: Authenticated administrator authorizing reinstallation.
            session: Owning application transaction.

        Returns:
            True after adding a missing scope or publishing changed bundled content.

        Raises:
            AppError: Existing immutable history is missing or inconsistent.
        """
        mapping = load_collection_section("primary")
        rules = database[mapping["query_rule_sets_collection"]]
        revisions = database[mapping["query_rule_revisions_collection"]]
        versions = list(rules.find({"scope_key": source["scope_key"]}, session=session))
        if versions:
            if any(not row.get("system_installed") for row in versions):
                return False
            published = next((row for row in versions if row["status"] == "published"), None)
            if published is None or published["content"] == source["content"]:
                return False
            previous = revisions.find_one(
                {"rule_oid": str(published["_id"])}, sort=[("revision", -1)], session=session
            )
            if previous is None or previous["revision"] != published["revision"]:
                raise api_error(
                    409, "Query rule history is incomplete; repair it before reinstalling"
                )
            published.update(
                status="retired",
                revision=published["revision"] + 1,
                updated_by=actor,
                updated_on=datetime.now(timezone.utc),
                reason="Superseded by authenticated bundled-data reinstallation",
            )
            rules.replace_one({"_id": published["_id"]}, published, session=session)
            revisions.insert_one(
                build_query_revision(published, "superseded", previous["revision_hash"]),
                session=session,
            )
        document = {
            **source,
            "_id": ObjectId(),
            "version": max((row["version"] for row in versions), default=0) + 1,
            "revision": 1,
        }
        if versions:
            document.update(updated_by=actor, published_by=actor)
        rules.insert_one(document, session=session)
        revisions.insert_one(build_query_revision(document, "system_installed"), session=session)
        return True
