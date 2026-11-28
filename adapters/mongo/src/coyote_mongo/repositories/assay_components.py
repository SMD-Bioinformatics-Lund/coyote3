# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Commit independent resource revisions together with all affected configuration snapshots."""

from datetime import datetime
from typing import Any, Protocol

from coyote.application.accounts.common import current_actor, utc_now
from coyote.application.resources.assay_releases import bind_resources
from coyote.config.constants import DIAGNOSIS_BASE_ID
from coyote.contracts.operations import OperationResult
from coyote.domain.common.errors import api_error
from pymongo.client_session import ClientSession
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from coyote_mongo.repositories.audit_outbox import enqueue_audit
from coyote_mongo.repositories.base import BaseRepository
from coyote_mongo.repositories.revision_rotation import rotate_in_session
from coyote_mongo.results import operation_from_insert_one, operation_from_update
from coyote_mongo.transactions import run_transaction

Document = dict[str, Any]


class AssayComponentCollections(Protocol):
    """Application collections read or updated by a resource publication."""

    asp_collection: Collection[Document]
    aspc_collection: Collection[Document]
    insilico_genelist_collection: Collection[Document]
    assay_groups_collection: Collection[Document]
    diagnoses_collection: Collection[Document]
    diagnosis_associations_collection: Collection[Document]


class AssayComponentRepository(BaseRepository):
    """Store one current revision and retain superseded documents by their original OID."""

    identity_field: str
    adapter: AssayComponentCollections

    def __init__(self, adapter: AssayComponentCollections) -> None:
        super().__init__(adapter)

    def latest_revision(self, identifier: str) -> Document | None:
        """Return the latest version for registry display, including withdrawn resources."""
        return self.get_collection().find_one(
            {self.identity_field: identifier}, sort=[("version", -1)]
        )

    def _bind(self, config: Document, panel: Document, session: ClientSession) -> Document:
        lists = list(
            self.adapter.insilico_genelist_collection.find(
                {
                    "is_active": True,
                    "adhoc": False,
                    "$or": [{"asp_ids": panel["asp_id"]}, {"asp_groups": panel["asp_group"]}],
                },
                session=session,
            )
        )
        return bind_resources(config, panel, lists)

    def _prepare_configuration(
        self, row: Document, session: ClientSession, *, expected_panel_id: object | None = None
    ) -> Document:
        """Re-read its parents and capture selectable lists inside the publishing transaction."""
        panel = self.adapter.asp_collection.find_one(
            {"asp_id": row["asp_id"], "is_active": True}, session=session
        )
        if not panel or not self._scope_available(panel, row["diagnosis_id"], session):
            raise api_error(409, "The assay, its group and the selected diagnosis must be active.")
        if expected_panel_id is not None and str(panel["_id"]) != str(expected_panel_id):
            raise api_error(
                409, "The assay definition changed. Reload the configuration before saving."
            )
        return self._bind(row, panel, session)

    def _scope_available(
        self, panel: Document, diagnosis_id: str, session: ClientSession | None
    ) -> bool:
        if not self.adapter.assay_groups_collection.find_one(
            {"group_id": panel["asp_group"], "is_active": True}, {"_id": 1}, session=session
        ):
            return False
        if diagnosis_id == DIAGNOSIS_BASE_ID:
            return True
        selector = {"diagnosis_id": diagnosis_id, "is_current": True, "is_active": True}
        return bool(
            self.adapter.diagnoses_collection.find_one(selector, {"_id": 1}, session=session)
            and self.adapter.diagnosis_associations_collection.find_one(
                {**selector, "asp_id": panel["asp_id"]}, {"_id": 1}, session=session
            )
        )

    def _lock_groups(
        self, records: list[Document], session: ClientSession, *, require_active: str | None
    ) -> None:
        """Serialize dependent publications and group status changes with the same group counter."""
        groups = {group for row in records for group in row.get("asp_groups", [])}
        groups.update(row["asp_group"] for row in records if row.get("asp_group"))
        assay_ids = {key for row in records for key in row.get("asp_ids", [])}
        if assay_ids:
            groups.update(
                row["asp_group"]
                for row in self.adapter.asp_collection.find(
                    {"asp_id": {"$in": list(assay_ids)}, "is_active": True},
                    {"asp_group": 1},
                    session=session,
                )
            )
        for group in sorted(groups):
            selector: Document = {"group_id": group}
            if group == require_active:
                selector["is_active"] = True
            result = self.adapter.assay_groups_collection.update_one(
                selector, {"$inc": {"publication_serial": 1}}, session=session
            )
            if group == require_active and not result.matched_count:
                raise api_error(409, f"Assay group {group} is inactive or unregistered")

    def _refresh_configurations(
        self, records: list[Document], actor: str, now: datetime, session: ClientSession
    ) -> None:
        if self.identity_field == "asp_id":
            selector: Document = {"asp_id": records[-1]["asp_id"]}
        elif self.identity_field == "isgl_id":
            selector = {
                "$or": [
                    {
                        "asp_id": {
                            "$in": sorted({k for row in records for k in row.get("asp_ids", [])})
                        }
                    },
                    {
                        "asp_group": {
                            "$in": sorted({k for row in records for k in row.get("asp_groups", [])})
                        }
                    },
                ]
            }
        else:
            return
        configs = self.adapter.aspc_collection
        # Fix the target IDs before inserting successors; stream the larger snapshots.
        targets = [
            row["_id"]
            for row in configs.find({**selector, "is_active": True}, {"_id": 1}, session=session)
        ]
        for old in configs.find({"_id": {"$in": targets}}, session=session):
            # A withdrawn assay is unavailable at intake. Its configuration is refreshed when reactivated.
            panel = self.adapter.asp_collection.find_one(
                {"asp_id": old["asp_id"], "is_active": True}, session=session
            )
            if panel is None:
                continue
            new = self._bind(old, panel, session)
            if all(new[k] == old.get(k) for k in ("assay_resource_release", "gene_list_release")):
                continue
            new.update(
                version=old["version"] + 1,
                supersedes_id=new.pop("_id"),
                updated_on=now,
                updated_by=actor,
            )
            rotate_in_session(
                configs,
                session=session,
                context=self.audit_context,
                selector={"_id": old["_id"]},
                expected_version=old["version"],
                new_document=new,
                retire_fields={
                    "retired_by": actor,
                    "retired_on": now,
                    "retired_reason": "dependency_updated",
                },
            )

    def publish_revision(
        self,
        document: Document,
        *,
        expected_version: int | None = None,
        retire_fields: Document | None = None,
        identifier: str | None = None,
    ) -> OperationResult:
        """Insert an active version and advance dependent configurations in the same transaction."""
        collection = self.get_collection()
        identity = {self.identity_field: document[self.identity_field]}
        if identifier is not None and identifier != document[self.identity_field]:
            raise api_error(409, "The resource identifier cannot change between revisions.")
        actor = document.get("updated_by") or document.get("created_by") or current_actor("system")
        now = document.get("updated_on") or utc_now()

        def publish(session: ClientSession) -> OperationResult:
            previous = collection.find_one(identity, sort=[("version", -1)], session=session)
            if expected_version is None and previous:
                raise api_error(
                    409, "This resource already exists. Open its current revision to edit."
                )
            if expected_version is not None and (
                not previous
                or not previous.get("is_active")
                or previous["version"] != expected_version
            ):
                raise api_error(409, "The active revision changed. Reload it before saving.")
            row = {**document, "is_active": True}
            records = [previous, row] if previous else [row]
            self._lock_groups(records, session, require_active=row.get("asp_group"))
            if self.identity_field == "aspc_id":
                prepared_panel = (row.get("assay_resource_release") or {}).get("content", {})
                row = self._prepare_configuration(
                    row, session, expected_panel_id=prepared_panel.get("_id")
                )
            if previous:
                row.update(version=previous["version"] + 1, supersedes_id=previous["_id"])
                result = rotate_in_session(
                    collection,
                    session=session,
                    context=self.audit_context,
                    selector={"_id": previous["_id"]},
                    expected_version=expected_version,
                    new_document=row,
                    retire_fields=retire_fields or {},
                )
            else:
                row["version"] = 1
                inserted = collection.insert_one(row, session=session)
                is_panel = self.identity_field == "asp_id"
                enqueue_audit(
                    collection.database,
                    session,
                    context=self.audit_context,
                    event_type="assay.created" if is_panel else "configuration.created",
                    resource_type="assay" if is_panel else collection.name,
                    resource_id=row["asp_id"] if is_panel else inserted.inserted_id,
                    actor=actor,
                    metadata={**identity, "version": row["version"]},
                )
                result = operation_from_insert_one(inserted)
            self._refresh_configurations(records, actor, now, session)
            return result

        try:
            result = run_transaction(collection.database.client, publish)
        except DuplicateKeyError as exc:
            raise api_error(
                409, "A revision already exists for this resource or configuration scope."
            ) from exc
        self.invalidate_dashboard_metrics()
        return result

    def set_availability(self, identifier: str, active: bool) -> OperationResult:
        """Change availability of the latest revision and refresh dependent releases atomically."""
        collection = self.get_collection()
        actor = current_actor("system")

        def update(session: ClientSession) -> OperationResult:
            row = collection.find_one(
                {self.identity_field: identifier}, sort=[("version", -1)], session=session
            )
            if row is None or row["is_active"] == active:
                raise api_error(409, "The resource status changed. Refresh the page.")
            self._lock_groups(
                [row], session, require_active=row.get("asp_group") if active else None
            )
            if active:
                # Capture intervening changes in a fresh version, preserving pinned snapshots.
                renewed = (
                    self._prepare_configuration(row, session)
                    if self.identity_field == "aspc_id"
                    else dict(row)
                )
                for field in ("retired_by", "retired_on", "retired_reason"):
                    renewed.pop(field, None)
                renewed.update(
                    version=row["version"] + 1,
                    supersedes_id=renewed.pop("_id"),
                    is_active=True,
                    updated_by=actor,
                    updated_on=utc_now(),
                )
                result = operation_from_insert_one(collection.insert_one(renewed, session=session))
                oid = renewed["_id"]
            else:
                result = operation_from_update(
                    collection.update_one(
                        {"_id": row["_id"]},
                        {
                            "$set": {
                                "is_active": False,
                                "retired_by": actor,
                                "retired_on": utc_now(),
                                "retired_reason": "withdrawn",
                            }
                        },
                        session=session,
                    )
                )
                oid = row["_id"]
            enqueue_audit(
                collection.database,
                session,
                context=self.audit_context,
                event_type="configuration.status_changed",
                resource_type=collection.name,
                resource_id=oid,
                actor=actor,
                metadata={self.identity_field: identifier, "is_active": active},
            )
            self._refresh_configurations([row], actor, utc_now(), session)
            return result

        result = run_transaction(collection.database.client, update)
        self.invalidate_dashboard_metrics()
        return result


def library_rows(
    collection: Collection[Document],
    key: str,
    query: Document,
    sort: dict[str, int],
    skip: int,
    limit: int,
    projection: dict[str, int] | None = None,
) -> tuple[list[Document], int]:
    """Show one row per identity, including the final revision of a withdrawn component."""
    pipeline: list[Document] = [
        *([{"$project": projection}] if projection else []),
        {"$sort": {"version": -1}},
        {"$group": {"_id": "$" + key, "row": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$row"}},
        {"$match": query},
        {
            "$facet": {
                "total": [{"$count": "count"}],
                "rows": [
                    {"$sort": sort},
                    {"$skip": skip},
                    {"$limit": limit},
                ],
            }
        },
    ]
    result = next(collection.aggregate(pipeline))
    return result["rows"], next((row["count"] for row in result["total"]), 0)
