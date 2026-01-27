#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
ReportedVariantsHandler module for Coyote3
=========================================

This module defines the `ReportedVariantsHandler` class used for accessing and managing
**reported variant tier snapshots** in MongoDB.

A "reported variant" record represents a single variant that was included in a specific
generated report for a specific sample, along with the tier/class **as it was at the
time of report generation** (i.e., an immutable snapshot).

Collection purpose
------------------
- Persist per-report, per-sample, per-variant tier snapshots (audit-safe)
- Enable fast lookups for:
  - "Which variants were reported in report X for sample Y?"
  - "How many times was variant/simple_id reported, and at which tiers?"
  - "Which samples/reports included a given gene / HGVSp / HGVSc?"

Compatibility
-------------
Designed for MongoDB 3.4 compatibility (and forward compatible with newer versions).

"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
from typing import Any, Optional, List, Dict
from pymongo import ASCENDING, DESCENDING, UpdateOne

from coyote.db.base import BaseHandler


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class ReportedVariantsHandler(BaseHandler):
    """
    MongoDB handler for reported variant snapshots.

    The `ReportedVariantsHandler` provides a focused interface for interacting with the
    `reported_variants` collection. Each document in the collection corresponds to a
    single variant reported in a specific report for a specific sample.

    Notes
    -----
    - Documents are written once at report creation time.
    - Snapshot fields (e.g. `tier`) should NOT be retroactively updated when global
      tier annotations change.
    - Sample metadata remains in `samples` and full variant payload remains in `variants`.
      This collection stores identifiers + snapshot tier + small query helper fields.
    """

    def __init__(self, adapter: Any):
        """
        Initialize the handler with a given adapter and bind the collection.
        """
        super().__init__(adapter)

        # Bind the Mongo collection holding per-report reported variant snapshots.
        # Prefer an explicit adapter attribute (e.g., adapter.reported_variants_collection).
        # If your adapter uses a different naming convention, update this accordingly.
        self.set_collection(self.adapter.reported_variants_collection)

    def bulk_upsert_from_snapshot_rows(
        self,
        sample_name,
        sample_oid,
        report_oid,
        report_id: str,
        snapshot_rows: List[Dict[str, Any]],
        created_by: str,
    ) -> int:
        """
        Upsert reported variant snapshot rows for a single report.

        snapshot_rows should contain (at minimum):
          - var_oid
          - simple_id
          - tier
          - gene/transcript/hgvsp/hgvsc (optional but recommended)
          - created_on
          - annotation_oid (optional)

        This method writes only after the report is saved successfully.
        """
        if not snapshot_rows:
            return 0

        col = self.get_collection()
        ops = []

        for r in snapshot_rows:
            simple_id = r.get("simple_id")
            if not simple_id:
                continue

            # Ensure core fields are always set (don’t rely on snapshot_rows to be perfect)
            doc = {
                "sample_name": sample_name,
                "sample_oid": sample_oid,
                "report_oid": report_oid,
                "report_id": report_id,
                "created_by": created_by,
                **r,  # r can include var_oid, tier, gene, etc.
            }

            # IMPORTANT: do NOT allow snapshot_rows to override report_oid/report_id/sample_oid
            doc["sample_name"] = sample_name
            doc["sample_oid"] = sample_oid
            doc["report_oid"] = report_oid
            doc["report_id"] = report_id
            doc["created_by"] = created_by

            ops.append(
                UpdateOne(
                    {
                        "sample_oid": sample_oid,
                        "report_oid": report_oid,
                        "simple_id": simple_id,
                    },
                    {"$setOnInsert": doc},
                    upsert=True,
                )
            )

        if not ops:
            return 0

        res = self.get_collection().bulk_write(ops, ordered=False)
        return int(res.upserted_count or 0)

    def list_reported_variants(self, query: dict) -> list:
        """
        List reported variant snapshot documents matching the given Mongo query.
        """
        return list(self.get_collection().find(query))

    def get_reported_docs(self, query: dict, limit: int | None = None) -> list:
        """
        Retrieve reported variant documents based on the provided query.

        Args:
            query (dict): MongoDB query to filter reported variant documents.
            limit (Optional[int]): Maximum number of documents to retrieve. If None, retrieves all matching documents.
            include_annotation_text (bool): Whether to include documents with annotation text.

        Returns:
            list: List of reported variant documents matching the query.
        """
        if not query:
            return []

        cursor = (
            self.get_collection().find(query, {"_id": 1, "sample_oid": 1}).sort("time_created", -1)
        )

        if limit is not None:
            cursor = cursor.limit(limit)

        return list(cursor)

    def ensure_indexes(self) -> None:
        """
        Create required indexes for the reported_variants collection.

        Safe to call multiple times; MongoDB will keep existing indexes.
        Compatible with MongoDB 3.4.
        """
        col = self.get_collection()

        # Prevent duplicates: same variant cannot be recorded twice in the same report
        col.create_index(
            [
                ("sample_oid", ASCENDING),
                ("report_oid", ASCENDING),
                ("simple_id", ASCENDING),
            ],
            unique=True,
            name="uq_sample_report_simple_id",
            background=True,
        )

        # Fast "open report": fetch all reported variants for a given sample+report
        col.create_index(
            [("sample_oid", ASCENDING), ("report_oid", ASCENDING)],
            name="ix_sample_report",
            background=True,
        )

        # Cross-sample variant queries by genomic identity + tier
        col.create_index(
            [("simple_id", ASCENDING), ("tier", ASCENDING)],
            name="ix_simple_id_tier",
            background=True,
        )

        # Protein / transcript queries (tier distribution, most common, etc.)
        col.create_index(
            [("gene", ASCENDING), ("hgvsp", ASCENDING), ("tier", ASCENDING)],
            name="ix_gene_hgvsp_tier",
            background=True,
        )
        col.create_index(
            [("gene", ASCENDING), ("hgvsc", ASCENDING), ("tier", ASCENDING)],
            name="ix_gene_hgvsc_tier",
            background=True,
        )

        # Optional: time-based queries (recent reports, time-window stats)
        col.create_index(
            [("created_on", DESCENDING)],
            name="ix_created_on_desc",
            background=True,
        )
