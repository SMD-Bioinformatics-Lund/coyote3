"""Transactional storage of assay-owned subpanel revisions."""

from typing import Any

from pymongo.errors import DuplicateKeyError

from api.contracts.schemas.registry import normalize_collection_document
from api.domain.common.errors import api_error
from api.infra.mongo.repositories.audit_outbox import enqueue_audit
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.transactions import run_transaction


class AssaySubpanelRepository(BaseRepository):
    """Keep stable identities and immutable previous metadata revisions."""

    def __init__(self, adapter: Any) -> None:
        """Bind the application-owned subpanel collection."""
        super().__init__(adapter)
        self.set_collection(adapter.subpanel_associations_collection)
        self.definitions = adapter.subpanels_collection

    def ensure_indexes(self) -> None:
        """Enforce one current record and unique revision numbers per assay/scope."""
        collection = self.get_collection()
        collection.create_index(
            [("asp_id", 1), ("subpanel_id", 1)],
            unique=True,
            partialFilterExpression={"is_current": True},
            name="subpanel_current_unique",
        )
        collection.create_index(
            [("asp_id", 1), ("subpanel_id", 1), ("version", 1)],
            unique=True,
            name="subpanel_revision_unique",
        )
        self.adapter.subpanels_collection.create_index(
            [("subpanel_id", 1)],
            unique=True,
            partialFilterExpression={"is_current": True},
            name="subpanel_definition_current",
        )
        self.adapter.subpanels_collection.create_index(
            [("subpanel_id", 1), ("version", 1)],
            unique=True,
            name="subpanel_definition_revision",
        )

    def list_definitions(self) -> list[dict]:
        """Return shared current definitions, including globally retired definitions."""
        return list(self.definitions.find({"is_current": True}).sort("display_name", 1))

    def create_definition(self, document: dict, asp_ids: list[str]) -> None:
        """Create a shared definition and selected associations in one transaction.

        Args:
            document: Complete shared metadata with actor and timestamp.
            asp_ids: Validated distinct parent assay identifiers.

        Raises:
            AppError: The shared identifier already exists.
        """
        definition = normalize_collection_document("subpanels", document)
        associations = [
            normalize_collection_document(
                "subpanel_associations",
                {
                    "asp_id": asp_id,
                    "subpanel_id": definition["subpanel_id"],
                    "is_active": definition["is_active"],
                    "updated_by": definition["updated_by"],
                    "updated_on": definition["updated_on"],
                },
            )
            for asp_id in asp_ids
        ]

        def write(session):
            """Insert all requested records, rolling back on any conflict."""
            self.definitions.insert_one(dict(definition), session=session)
            if associations:
                self.get_collection().insert_many(
                    [dict(row) for row in associations], session=session
                )
            enqueue_audit(
                self.definitions.database,
                session,
                event_type="subpanel.created",
                resource_type="subpanel",
                resource_id=definition["subpanel_id"],
                actor=definition.get("updated_by"),
                metadata={"asp_ids": asp_ids},
            )

        try:
            run_transaction(self.definitions.database.client, write)
        except DuplicateKeyError as exc:
            raise api_error(409, "Subpanel identifier already exists") from exc

    def _join(self, association: dict, definition: dict) -> dict:
        """Present shared display metadata with the association's independent status."""
        return {
            **association,
            "display_name": definition["display_name"],
            "description": definition.get("description", ""),
            "definition_is_active": definition["is_active"],
            "definition_version": definition["version"],
        }

    def list_for_assay(self, asp_id: str, *, active_only: bool = False) -> list[dict]:
        """Return current definitions ordered by display name, optionally excluding retired ones."""
        query = {"asp_id": asp_id, "is_current": True}
        if active_only:
            query["is_active"] = True
        definitions = {doc["subpanel_id"]: doc for doc in self.list_definitions()}
        rows = []
        for association in self.get_collection().find(query):
            definition = definitions.get(association["subpanel_id"])
            if definition is None:
                raise api_error(409, "Subpanel association has no definition; complete migration")
            if not active_only or definition["is_active"]:
                rows.append(self._join(association, definition))
        return sorted(rows, key=lambda row: (row["display_name"], row["subpanel_id"]))

    def get_current(self, asp_id: str, subpanel_id: str) -> dict | None:
        """Return the current revision, including a retired definition, or None."""
        association = self.get_collection().find_one(
            {"asp_id": asp_id, "subpanel_id": subpanel_id, "is_current": True}
        )
        if association is None:
            return None
        definition = self.definitions.find_one({"subpanel_id": subpanel_id, "is_current": True})
        if definition is None:
            raise api_error(409, "Subpanel association has no definition; complete migration")
        return self._join(association, definition)

    def save(self, document: dict, *, expected_version: int | None = None, session=None) -> None:
        """Insert a definition or atomically replace its expected current revision.

        Args:
            document: Complete successor record, including actor and timestamp.
            expected_version: Current version for edits; None creates a new identity.
            session: Existing transaction on this database's client, or None to start one.

        Raises:
            AppError: A concurrent edit or duplicate identity prevents the write.
        """
        payload = normalize_collection_document(
            "subpanel_associations",
            {
                key: value
                for key, value in document.items()
                if key
                not in {
                    "display_name",
                    "description",
                    "_id",
                    "definition_version",
                    "definition_is_active",
                }
            },
        )
        collection = self.get_collection()

        def write(session):
            """Retire the expected revision and insert its successor in the same transaction."""
            definition = self.definitions.find_one(
                {"subpanel_id": payload["subpanel_id"], "is_current": True}, session=session
            )
            if definition is None:
                if expected_version is not None:
                    raise api_error(409, "Subpanel definition is missing")
                definition = normalize_collection_document(
                    "subpanels",
                    {key: value for key, value in document.items() if key != "asp_id"}
                    | {"is_active": True, "version": 1},
                )
                self.definitions.insert_one(dict(definition), session=session)
            elif any(
                document.get(key, "") != definition.get(key, "")
                for key in ("display_name", "description")
            ):
                raise api_error(
                    409, "Shared metadata differs; edit the shared definition explicitly"
                )
            if payload["is_active"] and not definition["is_active"]:
                raise api_error(409, "Globally retired subpanel cannot be enabled for an assay")
            if expected_version is not None:
                result = collection.update_one(
                    {
                        "asp_id": payload["asp_id"],
                        "subpanel_id": payload["subpanel_id"],
                        "is_current": True,
                        "version": expected_version,
                    },
                    {"$set": {"is_current": False}},
                    session=session,
                )
                if result.matched_count != 1:
                    raise api_error(409, "Subpanel changed; reload before saving")
            collection.insert_one(dict(payload), session=session)
            enqueue_audit(
                collection.database,
                session,
                event_type="subpanel.association_saved",
                resource_type="subpanel_association",
                resource_id=payload["subpanel_id"],
                actor=payload.get("updated_by"),
                metadata={
                    "asp_id": payload["asp_id"],
                    "version": payload.get("version"),
                    "is_active": payload.get("is_active"),
                },
            )

        try:
            if session is not None:
                write(session)
            else:
                run_transaction(collection.database.client, write)
        except DuplicateKeyError as exc:
            raise api_error(
                409, "Subpanel already exists or changed; reload before saving"
            ) from exc

    def assays_by_subpanel(self) -> dict[str, list[str]]:
        """Return current assay links grouped by shared key, including inactive links."""
        result: dict[str, list[str]] = {}
        for row in self.get_collection().find(
            {"is_current": True}, {"subpanel_id": 1, "asp_id": 1}
        ):
            result.setdefault(row["subpanel_id"], []).append(row["asp_id"])
        return result

    def revise_definition(
        self,
        subpanel_id: str,
        values: dict,
        *,
        expected_version: int,
        add_asp_ids: list[str] | tuple[str, ...] = (),
    ) -> None:
        """Revise shared metadata atomically; association status remains unchanged.

        Args:
            subpanel_id: Global business key.
            values: Full replacement metadata including actor and timestamp.
            expected_version: Current revision observed by the editor.
            add_asp_ids: Links to insert if absent; existing status and history are preserved.

        Raises:
            AppError: Another editor changed the definition or it does not exist.
        """
        document = normalize_collection_document(
            "subpanels",
            {
                **values,
                "subpanel_id": subpanel_id,
                "version": expected_version + 1,
                "is_current": True,
            },
        )

        def write(session):
            """Replace only the expected shared revision in one transaction."""
            result = self.definitions.update_one(
                {"subpanel_id": subpanel_id, "version": expected_version, "is_current": True},
                {"$set": {"is_current": False}},
                session=session,
            )
            if result.matched_count != 1:
                raise api_error(409, "Shared definition changed; reload before saving")
            self.definitions.insert_one(dict(document), session=session)
            for asp_id in add_asp_ids:
                if self.get_collection().find_one(
                    {"asp_id": asp_id, "subpanel_id": subpanel_id, "is_current": True},
                    session=session,
                ):
                    continue
                association = normalize_collection_document(
                    "subpanel_associations",
                    {
                        "asp_id": asp_id,
                        "subpanel_id": subpanel_id,
                        "is_active": document["is_active"],
                        "updated_by": document["updated_by"],
                        "updated_on": document["updated_on"],
                    },
                )
                self.get_collection().insert_one(association, session=session)
            enqueue_audit(
                self.definitions.database,
                session,
                event_type="subpanel.revised",
                resource_type="subpanel",
                resource_id=subpanel_id,
                actor=document.get("updated_by"),
                metadata={"version": document.get("version"), "added_asp_ids": add_asp_ids},
            )

        run_transaction(self.definitions.database.client, write)
