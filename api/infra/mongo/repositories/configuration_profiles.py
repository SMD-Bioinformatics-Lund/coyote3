"""Transactional immutable configuration profile revisions and publication pointers."""

from copy import deepcopy
from datetime import datetime, timezone

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from api.infra.mongo.repositories.audit_outbox import enqueue_audit
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.transactions import run_transaction
from coyote3.domain.common.errors import api_error


class ConfigurationProfileRepository(BaseRepository):
    """Retain all source versions and select one published revision per profile identity."""

    def __init__(self, adapter):
        """Bind the configured application-owned profile collection."""
        super().__init__(adapter)
        self.set_collection(adapter.configuration_profiles_collection)

    def ensure_indexes(self) -> None:
        """Enforce unique revisions and a single published selection per profile."""
        self.get_collection().create_index(
            [("profile_id", 1), ("version", 1)], unique=True, name="configuration_profile_revision"
        )
        self.get_collection().create_index(
            [("profile_id", 1)],
            unique=True,
            partialFilterExpression={"is_current": True},
            name="configuration_profile_current",
        )
        self.adapter.configuration_promotions_collection.create_index(
            [("status", 1), ("created_on", -1)], name="configuration_promotion_review"
        )

    def list_promotions(self) -> list[dict]:
        """Return up to 500 retained promotion proposals, newest first."""
        return list(
            self.adapter.configuration_promotions_collection.find()
            .sort("created_on", -1)
            .limit(500)
        )

    def get_promotion(self, identity: str) -> dict | None:
        """Read the exact promotion proposal selected by its ObjectId."""
        if not ObjectId.is_valid(identity):
            return None
        return self.adapter.configuration_promotions_collection.find_one(
            {"_id": ObjectId(identity)}
        )

    def promotion_target(self, aspc_id: str) -> dict | None:
        """Read the newest target revision, including retired history for sequence allocation."""
        return self.adapter.aspc_collection.find_one({"aspc_id": aspc_id}, sort=[("version", -1)])

    def create_promotion(self, document: dict) -> dict:
        """Persist a reviewable proposal without activating configuration or changing samples."""
        self.adapter.configuration_promotions_collection.insert_one(document)
        return document

    def approve_promotion(self, proposal: dict, *, actor: str, reason: str) -> dict:
        """Atomically activate the reviewed candidate and record approval with concurrency checks."""
        proposals = self.adapter.configuration_promotions_collection
        configurations = self.adapter.aspc_collection
        timestamp = datetime.now(timezone.utc)

        def write(session):
            """Commit approval, target rotation and audit without rebinding existing samples."""
            stored = proposals.find_one({"_id": proposal["_id"]}, session=session)
            if (
                not stored
                or stored["status"] != "pending"
                or stored["content_hash"] != proposal["content_hash"]
            ):
                raise api_error(409, "Promotion approval changed; reload before retrying")
            candidate = deepcopy(proposal["candidate"])
            latest = configurations.find_one(
                {"aspc_id": candidate["aspc_id"]}, sort=[("version", -1)], session=session
            )
            if int((latest or {}).get("version", 0)) != proposal["expected_target_version"]:
                raise api_error(409, "The target configuration changed; prepare a new promotion")
            configurations.update_many(
                {"aspc_id": candidate["aspc_id"], "is_active": True},
                {
                    "$set": {
                        "is_active": False,
                        "retired_on": timestamp,
                        "retired_by": actor,
                        "retired_reason": "approved_environment_promotion",
                    }
                },
                session=session,
            )
            candidate["promotion"].update(
                approved_by=actor, approved_on=timestamp, proposal_id=str(proposal["_id"])
            )
            result = configurations.insert_one(candidate, session=session)
            proposals.update_one(
                {"_id": proposal["_id"], "status": "pending"},
                {
                    "$set": {
                        "status": "approved",
                        "approved_by": actor,
                        "approved_on": timestamp,
                        "target_id": str(result.inserted_id),
                    }
                },
                session=session,
            )
            enqueue_audit(
                configurations.database,
                session,
                event_type="configuration.promoted",
                resource_type="aspc",
                resource_id=str(result.inserted_id),
                actor=actor,
                metadata={
                    "proposal_id": str(proposal["_id"]),
                    "reason": reason,
                    "source_hash": proposal["source_hash"],
                    "content_hash": proposal["content_hash"],
                },
            )

        try:
            run_transaction(configurations.database.client, write)
        except DuplicateKeyError as error:
            raise api_error(409, "Target configuration changed; review a new promotion") from error
        return self.get_promotion(str(proposal["_id"]))

    def list(self) -> list[dict]:
        """Return at most 500 profile revisions, newest first."""
        return list(self.get_collection().find().sort("created_on", -1).limit(500))

    def scope_resources(self, scope) -> dict:
        """Load the registered resources referenced by one proposed scope binding."""
        return {
            "group": self.adapter.assay_groups_collection.find_one({"group_id": scope.asp_group})
            if scope.asp_group
            else None,
            "assay": self.adapter.asp_collection.find_one(
                {"asp_id": scope.asp_id, "is_active": True}
            )
            if scope.asp_id
            else None,
            "diagnosis": self.adapter.diagnoses_collection.find_one(
                {"diagnosis_id": scope.diagnosis_id, "is_current": True}
            )
            if scope.diagnosis_id
            else None,
        }

    def get(self, identity: str) -> dict | None:
        """Load a single immutable revision by ObjectId."""
        if not ObjectId.is_valid(identity):
            return None
        return self.get_collection().find_one({"_id": ObjectId(identity)})

    def published(self) -> list[dict]:
        """Return the explicitly published current revision of every reusable profile."""
        return list(self.get_collection().find({"status": "published", "is_current": True}))

    def create(self, document: dict) -> dict:
        """Insert a new immutable draft; concurrent authors must retry revision conflicts."""
        previous = self.get_collection().find_one(
            {"profile_id": document["profile_id"]}, sort=[("version", -1)]
        )
        document = {**document, "version": int((previous or {}).get("version", 0)) + 1}
        if previous and previous["kind"] != document["kind"]:
            raise api_error(409, "A profile identity cannot change component kind")
        try:
            self.get_collection().insert_one(document)
        except DuplicateKeyError as error:
            raise api_error(
                409, "Another profile revision was created; reload and retry"
            ) from error
        return document

    def publish(self, document: dict, *, actor: str, reason: str) -> dict:
        """Atomically publish the reviewed revision and retain the previous publication."""
        collection = self.get_collection()
        timestamp = datetime.now(timezone.utc)

        def write(session):
            """Rotate the publication pointer and record its review in the same transaction."""
            current = collection.find_one({"_id": document["_id"]}, session=session)
            if (
                not current
                or current["status"] != "draft"
                or current["content_hash"] != document["content_hash"]
            ):
                raise api_error(409, "Profile publication changed; reload before retrying")
            collection.update_many(
                {"profile_id": document["profile_id"], "is_current": True},
                {"$set": {"is_current": False}},
                session=session,
            )
            collection.update_one(
                {"_id": document["_id"], "status": "draft"},
                {
                    "$set": {
                        "status": "published",
                        "is_current": True,
                        "published_by": actor,
                        "published_on": timestamp,
                    }
                },
                session=session,
            )
            enqueue_audit(
                collection.database,
                session,
                event_type="configuration.profile.published",
                resource_type="configuration_profile",
                resource_id=str(document["_id"]),
                actor=actor,
                metadata={"reason": reason, "content_hash": document["content_hash"]},
            )

        run_transaction(collection.database.client, write)
        return self.get(str(document["_id"]))
