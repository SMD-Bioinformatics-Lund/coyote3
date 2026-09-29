"""Persistence for registered assay groups; no rename or deletion operations."""

from typing import Any

from pymongo.errors import DuplicateKeyError

from api.domain.common.errors import api_error
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.transactions import run_transaction


class AssayGroupRepository(BaseRepository):
    """Store immutable scope definitions in the operational database."""

    def __init__(self, adapter: Any) -> None:
        """Bind the configured assay-group collection."""
        super().__init__(adapter)
        self.set_collection(adapter.assay_groups_collection)

    def ensure_indexes(self) -> None:
        """Require a unique stable identifier for every group."""
        self.get_collection().create_index(
            [("group_id", 1)], unique=True, name="assay_group_id_unique"
        )

    def list(self) -> list[dict]:
        """Return all registered groups ordered by display name."""
        return list(self.get_collection().find().sort("display_name", 1))

    def get(self, group_id: str) -> dict | None:
        """Read a definition regardless of its operational availability."""
        return self.get_collection().find_one({"group_id": group_id})

    def affected_assays(self, group_id: str) -> list[str]:
        """List distinct assay identities whose records reference this group."""
        return sorted(self.adapter.asp_collection.distinct("asp_id", {"asp_group": group_id}))

    def change_status(self, group_id: str, *, expected_version: int, values: dict) -> dict:
        """Change only availability metadata atomically, including for system groups.

        Args:
            group_id: Immutable registry key.
            expected_version: Revision inspected by the operator before confirmation.
            values: Server-built status, reason and actor/time fields.

        Returns:
            Previous record for audit attribution.

        Raises:
            AppError: The record is missing or was changed since inspection.
        """
        collection = self.get_collection()

        def write(session):
            """Update the expected revision without cascading to any child records."""
            previous = collection.find_one_and_update(
                {"group_id": group_id, "version": expected_version},
                {"$set": values, "$inc": {"version": 1}},
                session=session,
            )
            if previous is None:
                raise api_error(
                    409, "Assay group changed or is unavailable; reload before retrying"
                )
            return previous

        return run_transaction(collection.database.client, write)

    def create(self, document: dict) -> None:
        """Insert one definition transactionally; reject existing scope keys.

        Args:
            document: Validated group metadata stamped by the application service.

        Raises:
            AppError: The group identifier is already registered.
        """
        collection = self.get_collection()
        try:
            run_transaction(
                collection.database.client,
                lambda session: collection.insert_one(dict(document), session=session),
            )
        except DuplicateKeyError as exc:
            raise api_error(409, "Assay group already exists") from exc
