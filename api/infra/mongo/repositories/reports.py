"""Repository for saved clinical report metadata."""

from __future__ import annotations

import re
from typing import Any

from bson.objectid import ObjectId

from api.contracts.operations import OperationResult
from api.infra.dashboard_cache import invalidate_dashboard_summary_cache
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repository_utils import utc_now
from api.infra.request_context import current_username
from api.infra.samples_cache import invalidate_samples_cache


class ReportRepository(BaseRepository):
    """Persist report metadata outside the sample document."""

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.reports_collection)

    def ensure_indexes(self) -> None:
        col = self.get_collection()
        col.create_index([("report_id", 1)], name="report_id_1", background=True)
        col.create_index(
            [("sample_oid", 1), ("report_num", -1)], name="sample_oid_report_num", background=True
        )
        col.create_index(
            [("sample_name", 1), ("time_created", -1)], name="sample_name_time", background=True
        )
        col.create_index(
            [("asp_id", 1), ("environment", 1), ("time_created", -1)],
            name="asp_environment_time",
            background=True,
        )

    @staticmethod
    def _object_id(value: Any) -> ObjectId:
        return value if isinstance(value, ObjectId) else ObjectId(str(value))

    def next_report_num(self, sample_oid: str) -> int:
        latest = self.get_collection().find_one(
            {"sample_oid": self._object_id(sample_oid)},
            {"report_num": 1},
            sort=[("report_num", -1)],
        )
        return int((latest or {}).get("report_num") or 0) + 1

    def save_report(
        self,
        *,
        sample: dict,
        report_num: int,
        report_id: str,
        filepath: str,
        pdf_filepath: str | None = None,
        filters_snapshot: dict | None = None,
        aspc_snapshot: dict | None = None,
        rule_provenance: dict | None = None,
    ) -> ObjectId:
        report_oid = ObjectId()
        now = utc_now()
        doc = {
            "_id": report_oid,
            "sample_oid": self._object_id(sample.get("_id")),
            "sample_name": sample.get("name"),
            "asp_id": sample.get("asp_id"),
            "subpanel_id": sample.get("subpanel_id"),
            "environment": sample.get("environment"),
            "report_num": int(report_num),
            "report_id": str(report_id),
            "report_type": "html",
            "report_name": f"{report_id}.html",
            "filepath": filepath,
            "pdf_report_name": f"{report_id}.pdf" if pdf_filepath else None,
            "pdf_filepath": pdf_filepath,
            "author": current_username(),
            "time_created": now,
            "filters_snapshot": filters_snapshot or sample.get("filters") or {},
            "aspc": aspc_snapshot
            or {
                "_id": sample.get("current_aspc_id"),
                "aspc_id": sample.get("current_aspc_key"),
                "version": sample.get("current_aspc_version"),
            },
            "clinical_rule_source": rule_provenance,
        }
        self.get_collection().insert_one(doc)
        self.adapter.samples_collection.update_one(
            {"_id": self._object_id(sample.get("_id"))},
            {
                "$set": {
                    "reported": True,
                    "latest_report_id": report_oid,
                    "latest_report_on": now,
                }
            },
        )
        invalidate_samples_cache(self.adapter)
        invalidate_dashboard_summary_cache(self.adapter)
        return report_oid

    def get_report(self, sample_id: str, report_id: str) -> dict | None:
        sample = self.adapter.sample_repository.get_sample(sample_id)
        if not sample:
            return None
        return self.get_collection().find_one(
            {"sample_oid": self._object_id(sample.get("_id")), "report_id": report_id}
        )

    def list_reports_page(
        self,
        *,
        asp_ids: list[str] | None,
        environments: list[str] | None,
        search: str = "",
        page: int = 1,
        per_page: int = 30,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return a newest-first page of report metadata within an access scope."""
        query_parts: list[dict[str, Any]] = []
        if asp_ids is not None:
            query_parts.append({"asp_id": {"$in": asp_ids}})
        if environments is not None:
            query_parts.append({"environment": {"$in": environments}})
        normalized_search = str(search or "").strip()
        if normalized_search:
            expression = {"$regex": re.escape(normalized_search), "$options": "i"}
            query_parts.append(
                {
                    "$or": [
                        {"report_id": expression},
                        {"report_name": expression},
                        {"sample_name": expression},
                        {"author": expression},
                        {"asp_id": expression},
                        {"subpanel_id": expression},
                    ]
                }
            )
        query: dict[str, Any] = {"$and": query_parts} if query_parts else {}
        safe_page = max(1, int(page))
        safe_per_page = max(1, min(200, int(per_page)))
        collection = self.get_collection()
        total = int(collection.count_documents(query))
        rows = list(
            collection.find(query)
            .sort([("time_created", -1), ("_id", -1)])
            .skip((safe_page - 1) * safe_per_page)
            .limit(safe_per_page)
        )
        return rows, total

    def delete_sample_reports(self, sample_oid: str) -> OperationResult:
        """Delete report metadata owned by a sample."""
        return OperationResult.from_delete(
            self.get_collection().delete_many({"sample_oid": self._object_id(sample_oid)})
        )
