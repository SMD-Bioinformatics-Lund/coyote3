"""MongoDB-backed delivery ledger and fenced completion receipts for sample ingestion."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from pymongo import ReturnDocument
from pymongo.write_concern import WriteConcern

from api.contracts.schemas.ingest_jobs import IngestJobDoc
from api.infra.mongo.repositories.base import BaseRepository


class IngestJobsRepository(BaseRepository):
    """Persist ingest deliveries and claim pending or expired work with lease tokens."""

    def __init__(self, adapter):
        """Bind the ingest delivery ledger collection.

        Args:
            adapter: Mongo adapter exposing ``ingest_jobs_collection``.
        """
        super().__init__(adapter)
        self.set_collection(adapter.ingest_jobs_collection)

    def ensure_indexes(self):
        """Create the state, lease-expiration, and creation-time delivery index."""
        self.get_collection().create_index(
            [("state", 1), ("lease_until", 1), ("created_at", 1)], name="pending_delivery"
        )

    def submit(
        self,
        *,
        source_payload,
        update_existing=False,
        increment=False,
        staging_dir=None,
        submitted_by,
        job_id=None,
        kind="sample_bundle",
    ) -> str:
        """Insert a pending delivery if its job ID is not already recorded.

        Args:
            source_payload: Ingest request payload, or ``None`` when absent.
            update_existing: Store the request's update-existing flag; defaults to false.
            increment: Store the request's increment flag; defaults to false.
            staging_dir: Optional staging directory recorded for the worker.
            submitted_by: Identity submitting the delivery.
            job_id: Stable delivery ID for deduplication; falsey values generate a UUID.
            kind: Job kind: sample_bundle, insert_document, insert_documents, or
                upsert_document; defaults to sample_bundle.

        Returns:
            Delivery ID, including when an existing job is left unchanged.

        Raises:
            ValidationError: If the delivery violates the ingest job contract.

        Notes:
            Uses majority, journaled write concern and ``$setOnInsert``.
        """
        now = datetime.now(timezone.utc)
        identity = job_id or uuid4().hex
        document = IngestJobDoc(
            _id=identity,
            source_payload=source_payload,
            update_existing=update_existing,
            increment=increment,
            staging_dir=staging_dir,
            created_at=now,
            updated_at=now,
            submitted_by=submitted_by,
            kind=kind,
        ).model_dump(by_alias=True)
        self.get_collection().with_options(
            write_concern=WriteConcern("majority", j=True)
        ).update_one({"_id": identity}, {"$setOnInsert": document}, upsert=True)
        return identity

    def get(self, job_id):
        """Look up a delivery ledger entry by exact job ID.

        Args:
            job_id: Delivery identifier stored as ``_id``.

        Returns:
            Job document, or ``None`` when no entry exists.
        """
        return self.get_collection().find_one({"_id": job_id})

    def claim(self, job_id, *, lease_seconds):
        """Atomically claim pending work or replace an expired running lease.

        Args:
            job_id: Delivery identifier to claim.
            lease_seconds: Lease duration in seconds from the current UTC time.

        Returns:
            Updated running job with a new lease token and incremented attempt count,
            or ``None`` if the job is missing or not eligible.
        """
        now = datetime.now(timezone.utc)
        return self.get_collection().find_one_and_update(
            {
                "_id": job_id,
                "$or": [
                    {"state": "pending"},
                    {"state": "running", "lease_until": {"$lte": now}},
                ],
            },
            {
                "$set": {
                    "state": "running",
                    "lease_token": uuid4().hex,
                    "lease_until": now + timedelta(seconds=lease_seconds),
                    "updated_at": now,
                },
                "$inc": {"attempts": 1},
            },
            return_document=ReturnDocument.AFTER,
        )

    def complete(self, job_id, lease_token, result, session):
        """Fence stale workers and commit the receipt with the clinical writes."""
        updated = self.get_collection().update_one(
            {"_id": job_id, "state": "running", "lease_token": lease_token},
            {
                "$set": {
                    "state": "succeeded",
                    "result": result,
                    "updated_at": datetime.now(timezone.utc),
                    "source_payload": None,
                    "lease_until": None,
                    "lease_token": None,
                }
            },
            session=session,
        )
        if updated.matched_count != 1:
            raise RuntimeError("Ingest job lease changed before commit")

    def fail(self, job_id, lease_token, *, retryable):
        """Never overwrite a committed success after a lost acknowledgement."""
        self.get_collection().update_one(
            {"_id": job_id, "state": "running", "lease_token": lease_token},
            {
                "$set": {
                    "state": "pending" if retryable else "failed",
                    "error": "Temporary database failure"
                    if retryable
                    else "Ingest validation or write failed",
                    "lease_until": None,
                    "lease_token": None,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )

    def pending(self, *, limit=100, kinds=None):
        """List deliverable job IDs in oldest-created-first order.

        Args:
            limit: MongoDB result limit, defaulting to 100; zero means no limit.
            kinds: Optional allowed job kinds; ``None`` includes all kinds and an
                empty collection matches none.

        Returns:
            ID and kind projections for pending jobs and running jobs with expired leases.
        """
        now = datetime.now(timezone.utc)
        selector = {
            "$or": [{"state": "pending"}, {"state": "running", "lease_until": {"$lte": now}}]
        }
        if kinds is not None:
            selector["kind"] = {"$in": kinds}
        return list(
            self.get_collection()
            .find(
                selector,
                {"_id": 1, "kind": 1},
            )
            .sort("created_at", 1)
            .limit(limit)
        )
