# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Persist one blacklist record per variant with group scopes and assay measurements."""

from typing import Any

from coyote.config.constants import normalize_asp_group, normalize_clinical_identifier
from coyote.contracts.operations import OperationResult
from coyote.contracts.schemas.assay import BlacklistDoc
from coyote.domain.dna.variant_identity import build_simple_id_hash_from_simple_id
from pymongo.errors import DuplicateKeyError

from coyote_mongo.repositories.base import BaseRepository
from coyote_mongo.repository_utils import get_simple_id
from coyote_mongo.results import operation_from_update


class BlacklistRepository(BaseRepository):
    """Manage assay exclusions and informational biological-group matches."""

    def __init__(self, adapter):
        """Bind the configured application blacklist collection."""
        super().__init__(adapter)
        self.set_collection(self.adapter.blacklist_collection)

    def ensure_indexes(self) -> None:
        """Enforce one record per allele and index biological group lookups.

        Notes:
            Existing collections must be converted before deploying this schema.
        """
        col = self.get_collection()
        col.create_index([("simple_id", 1)], name="simple_id_1", unique=True)
        col.create_index([("assay_groups", 1), ("simple_id", 1)], name="assay_groups_simple_id_1")

    def add_blacklist_data(
        self, variants: list[dict[str, Any]], assay_group: str, *, asp_id: str
    ) -> list[dict[str, Any]]:
        """Attach assay exclusions or an informational group-only match.

        Args:
            variants: Findings containing canonical simple_id values; updated in place.
            assay_group: Biological group whose exclusions apply to these findings.
            asp_id: Exact sample assay used to select its measurement.

        Returns:
            ASP membership sets blacklist to its positive measurement or True for zero.
            A group-only match sets blacklist_group_match without excluding the finding.
            Derived match fields are refreshed; other assays' measurements are never used.
        """
        group = normalize_asp_group(assay_group)
        assay = normalize_clinical_identifier(asp_id, label="asp_id")
        entries = self.get_collection().find(
            {
                "simple_id": {"$in": [v["simple_id"] for v in variants]},
                "$or": [{"assay_groups": group}, {f"in_normal_perc.{assay}": {"$exists": True}}],
            },
            {"simple_id": 1, "in_normal_perc": 1, "assay_groups": 1, "_id": 0},
        )
        by_id = {entry["simple_id"]: entry for entry in entries}
        for variant in variants:
            variant.pop("blacklist", None)
            variant.pop("blacklist_group_match", None)
            entry = by_id.get(variant["simple_id"])
            if entry is None:
                continue
            measurements = entry["in_normal_perc"]
            if assay in measurements:
                variant["blacklist"] = measurements[assay] or True
            elif group in entry["assay_groups"]:
                variant["blacklist_group_match"] = True
        return variants

    def blacklist_variant(self, var: dict, assay: str) -> OperationResult:
        """Atomically add an exclusion group without overwriting measured frequencies.

        Args:
            var: Finding with a canonical simple_id or CHROM/POS/REF/ALT coordinates.
            assay: Biological group receiving the exclusion.

        Returns:
            JSON-safe upsert summary. Repeated additions are idempotent.

        Raises:
            ValueError: The finding identity or biological group is invalid.

        Notes:
            Manual exclusions do not invent a normal-sample frequency. The unique
            identity index and atomic set union preserve concurrent group additions.
        """
        identity = get_simple_id(var)
        parts = identity.split("_", 3)
        if len(parts) != 4:
            raise ValueError("Blacklist entries require chrom, pos, ref and alt")
        document = BlacklistDoc(
            simple_id=identity,
            simple_id_hash=build_simple_id_hash_from_simple_id(identity),
            chrom=parts[0],
            pos=int(parts[1]),
            ref=parts[2],
            alt=parts[3],
            assay_groups=[assay],
        )
        fields = document.model_dump(exclude={"id_", "assay_groups"})
        query = {"simple_id": identity}
        change = {
            "$setOnInsert": fields,
            "$addToSet": {"assay_groups": document.assay_groups[0]},
        }
        try:
            updated = self.write(self.get_collection(), "update_one", query, change, upsert=True)
        except DuplicateKeyError:
            updated = self.write(self.get_collection(), "update_one", query, change)
        result = operation_from_update(updated)
        if result.modified_count or result.upserted_id:
            self.invalidate_dashboard_metrics()
        return result

    def remove_assay_entry(self, var: dict, *, asp_id: str) -> OperationResult:
        """Remove one assay measurement, retaining the allele and every other assay.

        The normalized ASP identifier cannot contain MongoDB path separators.
        Mutation and audit receipt share the repository's required transaction.
        Missing entries are idempotent no-ops; this operation never deletes a record.
        """
        assay = normalize_clinical_identifier(asp_id, label="asp_id")
        updated = self.write(
            self.get_collection(),
            "update_one",
            {"simple_id": get_simple_id(var)},
            {"$unset": {f"in_normal_perc.{assay}": ""}},
        )
        result = operation_from_update(updated)
        if result.modified_count:
            self.invalidate_dashboard_metrics()
        return result

    def get_blacklisted_count(self) -> int:
        """Return the number of distinct blacklisted alleles across all groups."""
        return self.get_collection().count_documents({})

    def get_unique_blacklist_count(self) -> int:
        """Return the allele count; uniqueness is enforced by the simple_id index."""
        return self.get_blacklisted_count()
