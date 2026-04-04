"""Mongo-backed repository for core-layer data access."""

from __future__ import annotations

from bson.objectid import ObjectId

from api.extensions import store


class MongoCoreStoreRepository:
    """Provide mongo core store persistence operations."""

    def __init__(self) -> None:
        """__init__."""
        self.sample_handler = store.sample_handler
        self.reported_variants_handler = store.reported_variants_handler
        self.annotation_handler = store.annotation_handler

    def save_report(
        self,
        *,
        sample_id: str,
        report_num: int,
        report_id: str,
        filepath: str,
    ) -> str:
        """Persist report metadata and return the created report identifier."""
        return self.sample_handler.save_report(
            sample_id=sample_id,
            report_num=report_num,
            report_id=report_id,
            filepath=filepath,
        )

    def bulk_upsert_snapshot_rows(
        self,
        *,
        sample_name: str | None,
        sample_oid: str | None,
        report_oid: str,
        report_id: str,
        snapshot_rows: list,
        created_by: str,
    ) -> None:
        """Persist reported-variant snapshot rows for the saved report."""
        self.reported_variants_handler.bulk_upsert_from_snapshot_rows(
            sample_name=sample_name,
            sample_oid=sample_oid,
            report_oid=report_oid,
            report_id=report_id,
            snapshot_rows=snapshot_rows,
            created_by=created_by,
        )

    def new_comment_id(self) -> ObjectId:
        """Return a new identifier for embedded comment documents."""
        return ObjectId()

    def get_additional_classifications(
        self, variant: dict, assay: str, subpanel: str
    ) -> list[dict]:
        """Return additional classifications for a variant or fusion."""
        return list(
            self.annotation_handler.get_additional_classifications(variant, assay, subpanel) or []
        )

    def get_global_annotations(
        self, variant: dict, assay: str, subpanel: str
    ) -> tuple[list, dict | None, list, list]:
        """Return annotations and classifications for a variant or fusion."""
        return self.annotation_handler.get_global_annotations(variant, assay, subpanel)

    def get_samples_by_oids(self, sample_oids: list[object]) -> list[dict]:
        """Return samples matching the given identifiers."""
        return list(self.sample_handler.get_samples_by_oids(sample_oids) or [])

    def list_annotations_by_ids(self, annotation_ids: list[object]) -> list[dict]:
        """Return annotation documents matching the given identifiers."""
        return list(
            self.annotation_handler.get_collection().find({"_id": {"$in": list(annotation_ids)}})
            or []
        )

    def new_object_id(self) -> ObjectId:
        """New object id.

        Returns:
            ObjectId: The function result.
        """
        return self.new_comment_id()
