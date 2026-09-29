"""Transactional assay setup drafts and all-or-nothing operational publication."""

from copy import deepcopy
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from api.domain.common.errors import api_error
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.transactions import run_transaction


class AssaySetupRepository(BaseRepository):
    """Reserve one setup workspace per assay and preserve every saved revision."""

    def __init__(self, adapter: Any) -> None:
        """Bind setup workspaces to the application database."""
        super().__init__(adapter)
        self.set_collection(adapter.assay_setups_collection)

    def ensure_indexes(self) -> None:
        """Enforce assay reservations and efficient workspace listing."""
        self.get_collection().create_index([("asp_id", 1)], unique=True, name="setup_assay_unique")
        self.get_collection().create_index(
            [("status", 1), ("updated_at", -1)], name="setup_status_updated"
        )

    def list(self) -> list[dict]:
        """Return setup summaries without embedded clinical configuration content."""
        return list(self.get_collection().find({}, {"content": 0}).sort("updated_at", -1))

    def get(self, identifier: str) -> dict | None:
        """Return a workspace, or None for an invalid or missing ObjectId."""
        try:
            return self.get_collection().find_one({"_id": ObjectId(identifier)})
        except (InvalidId, TypeError):
            return None

    def authoring_scopes(self) -> list[dict]:
        """Expose unpublished assay definitions only to clinical rule authoring."""
        return list(
            self.get_collection().find(
                {"status": {"$in": ["draft", "submitted"]}},
                {"content.panel": 1, "content.scopes": 1},
            )
        )

    def revisions(self, identifier: str) -> list[dict]:
        """Return immutable setup snapshots in newest-first order."""
        return list(
            self.adapter.assay_setup_revisions_collection.find({"setup_id": identifier}).sort(
                "revision", -1
            )
        )

    def save(
        self,
        candidate: dict,
        *,
        previous: dict | None = None,
        action: str,
        bundle: dict | None = None,
    ) -> dict:
        """Save a revision, optionally publishing all staged resources atomically.

        Args:
            candidate: New workspace state, copied before persistence.
            previous: Expected revision/status, or None for a new reservation.
            action: Audit snapshot action.
            bundle: Validated operational documents and dependency versions for publication.

        Returns:
            Saved workspace including its ObjectId.

        Raises:
            AppError: A concurrent edit, duplicate resource or changed dependency prevents saving.
        """
        payload = deepcopy(candidate)
        payload["_id"] = previous["_id"] if previous else ObjectId()

        def transaction(session: Any) -> dict:
            """Commit a workspace revision and its associated writes in one session."""
            if bundle:
                # A real write serializes publication against concurrent group status changes.
                guard = self.adapter.assay_groups_collection.update_one(
                    {"group_id": bundle["panel"]["asp_group"], "is_active": True},
                    {"$inc": {"publication_serial": 1}},
                    session=session,
                )
                if guard.matched_count != 1:
                    raise api_error(
                        409, "Assay group is inactive or unregistered; publication refused"
                    )
            if previous:
                result = self.get_collection().replace_one(
                    {
                        "_id": previous["_id"],
                        "revision": previous["revision"],
                        "status": previous["status"],
                    },
                    payload,
                    session=session,
                )
                if not result.matched_count:
                    raise api_error(409, "Setup changed; reload before continuing")
            else:
                if self.adapter.asp_collection.find_one(
                    {"asp_id": payload["asp_id"]}, session=session
                ):
                    raise api_error(409, "An ASP already exists for this identifier")
                self.get_collection().insert_one(payload, session=session)
            if bundle:
                if self.adapter.asp_collection.find_one(
                    {"asp_id": payload["asp_id"]}, session=session
                ):
                    raise api_error(409, "An ASP already exists for this identifier")
                for dependency in bundle["definitions"]:
                    if not self.adapter.subpanels_collection.find_one(
                        {
                            "subpanel_id": dependency["subpanel_id"],
                            "version": dependency["version"],
                            "is_current": True,
                            "is_active": True,
                        },
                        session=session,
                    ):
                        raise api_error(409, "A selected subpanel changed; review the setup again")
                for rule in bundle["rules"]:
                    if not self.adapter.clinical_rule_sets_collection.find_one(
                        {
                            "_id": rule["_id"],
                            "revision": rule["revision"],
                            "active": True,
                            "status": "published",
                        },
                        session=session,
                    ):
                        raise api_error(409, "A reporting rule changed; review the setup again")
                for gene_list in bundle["existing_lists"]:
                    if not self.adapter.insilico_genelist_collection.find_one(
                        {
                            "_id": gene_list["_id"],
                            "version": gene_list.get("version", 1),
                            "is_active": True,
                        },
                        session=session,
                    ):
                        raise api_error(409, "A shared gene list changed; review the setup again")
                for collection, documents, key in [
                    (self.adapter.asp_collection, [bundle["panel"]], "asp_id"),
                    (self.adapter.insilico_genelist_collection, bundle["gene_lists"], "isgl_id"),
                    (self.adapter.aspc_collection, bundle["configurations"], "aspc_id"),
                ]:
                    for document in documents:
                        if collection.find_one({key: document[key]}, session=session):
                            raise api_error(409, f"Resource already exists: {document[key]}")
                        collection.insert_one(deepcopy(document), session=session)
                for association in bundle["associations"]:
                    self.adapter.subpanel_associations_collection.insert_one(
                        deepcopy(association), session=session
                    )
            self.adapter.assay_setup_revisions_collection.insert_one(
                {
                    "setup_id": str(payload["_id"]),
                    "revision": payload["revision"],
                    "action": action,
                    "document": deepcopy(payload),
                },
                session=session,
            )
            return payload

        try:
            return run_transaction(self.adapter.client, transaction)
        except DuplicateKeyError as exc:
            raise api_error(409, "An assay setup or staged resource already exists") from exc


class AssaySetupRevisionRepository(BaseRepository):
    """Register setup snapshot indexes with the index-management contract."""

    def __init__(self, adapter: Any) -> None:
        """Bind immutable setup revision snapshots."""
        super().__init__(adapter)
        self.set_collection(adapter.assay_setup_revisions_collection)

    def ensure_indexes(self) -> None:
        """Require one snapshot for every setup revision."""
        self.get_collection().create_index(
            [("setup_id", 1), ("revision", 1)], unique=True, name="setup_revision_unique"
        )
