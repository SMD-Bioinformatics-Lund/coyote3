# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""
ASPConfigRepository module for Coyote4
======================================

This module defines the `ASPConfigRepository` class used for accessing and managing
assay configuration data in MongoDB.

It is part of the MongoDB infrastructure layer.
"""

# -------------------------------------------------------------------------
# Imports
# -------------------------------------------------------------------------
import re
from typing import Any

from bson import ObjectId
from coyote.config.constants import (
    DEFAULT_ENVIRONMENT,
    DIAGNOSIS_BASE_ID,
    normalize_clinical_identifier,
    normalize_environment,
    validate_identifier,
)
from coyote.contracts.operations import OperationResult
from coyote.domain.repository_protocols import AnalysisTypeRollup
from pymongo import cursor
from pymongo.client_session import ClientSession

from coyote_mongo.repositories.assay_components import (
    AssayComponentCollections,
    AssayComponentRepository,
    library_rows,
)


# -------------------------------------------------------------------------
# Class Definition
# -------------------------------------------------------------------------
class ASPConfigRepository(AssayComponentRepository):
    """
    ASPConfigRepository is a class responsible for managing assay configuration data
    stored in a MongoDB collection. It provides methods to perform CRUD operations
    on assay configurations, retrieve specific data, toggle the active status of an
    assay configuration, and manage assay groups and mappings. This class serves as
    a key component for handling assay-related data efficiently in the database.
    """

    identity_field = "aspc_id"

    def __init__(self, adapter: AssayComponentCollections) -> None:
        """Retain the adapter context and bind its assay configuration collection.

        Args:
            adapter: Persistence host exposing the ASPC collection and any audit or
                cache context required by write operations.
        """
        super().__init__(adapter)
        self.set_collection(adapter.aspc_collection)

    def ensure_indexes(self) -> None:
        """
        Create minimal indexes for ASPC filter/distinct paths.
        """
        col = self.get_collection()
        col.create_index(
            [("aspc_id", 1), ("is_active", 1)],
            name="aspc_id_active_1",
            unique=True,
            background=True,
            partialFilterExpression={
                "aspc_id": {"$exists": True, "$type": "string"},
                "is_active": True,
            },
        )
        col.create_index(
            [("is_active", 1), ("asp_id", 1), ("diagnosis_id", 1), ("environment", 1)],
            name="is_active_asp_diagnosis_environment",
            background=True,
        )
        col.create_index(
            [("asp_id", 1), ("diagnosis_id", 1), ("environment", 1), ("is_active", 1)],
            name="asp_diagnosis_environment_active_1",
            unique=True,
            background=True,
            partialFilterExpression={
                "asp_id": {"$exists": True, "$type": "string"},
                "diagnosis_id": {"$exists": True, "$type": "string"},
                "environment": {"$exists": True, "$type": "string"},
                "is_active": True,
            },
        )
        col.create_index(
            [("aspc_id", 1), ("version", 1)],
            name="aspc_id_version_1",
            unique=True,
            background=True,
        )

    @staticmethod
    def build_aspc_id(asp_id: str, environment: str, diagnosis_id: str | None = None) -> str:
        """Build the ASPC business key from the unique runtime configuration tuple."""
        asp = validate_identifier(asp_id, label="asp_id")
        diagnosis = validate_identifier(diagnosis_id or DIAGNOSIS_BASE_ID, label="diagnosis_id")
        env = normalize_environment(environment)
        return normalize_clinical_identifier(f"{asp}::{diagnosis}::{env}", label="aspc_id")

    @staticmethod
    def _normalize_aspc_id(aspc_id: str | None) -> str | None:
        """Normalize aspc id.

        Args:
                aspc_id: Aspc id.

        Returns:
                The  normalize aspc id result.
        """
        if aspc_id is None:
            return None
        return normalize_clinical_identifier(aspc_id, label="aspc_id")

    def _aspc_lookup_query(self, aspc_id: str) -> dict[str, Any]:
        """Select the normalized stable business identifier without restricting its revision.

        Args:
            aspc_id: Configuration business identifier to validate and normalize.

        Returns:
            MongoDB equality predicate for the aspc_id field.
        """
        normalized = self._normalize_aspc_id(aspc_id)
        return {"aspc_id": normalized}

    def ensure_aspc_id(self, data: dict[str, Any]) -> dict[str, Any]:
        """Populate and normalize a configuration's business key in the supplied document.

        Args:
            data: Mutable document with aspc_id, or assay/environment fields from which
                to derive it; a missing diagnosis selects the base diagnosis.

        Returns:
            The same document with normalized configuration, assay and diagnosis IDs.

        Raises:
            ValueError: Required identifiers are absent or have invalid syntax.
        """
        if not isinstance(data, dict):
            return data
        normalized = self._normalize_aspc_id(data.get("aspc_id"))
        if not normalized and data.get("asp_id") and data.get("environment"):
            normalized = self.build_aspc_id(
                str(data.get("asp_id")),
                str(data.get("environment")),
                str(data.get("diagnosis_id") or DIAGNOSIS_BASE_ID),
            )
        if normalized:
            data["aspc_id"] = normalized
            data["asp_id"] = normalize_clinical_identifier(data.get("asp_id"), label="asp_id")
            data["diagnosis_id"] = normalize_clinical_identifier(
                data.get("diagnosis_id") or DIAGNOSIS_BASE_ID,
                label="diagnosis_id",
            )
            return data
        raise ValueError("asp_configs.aspc_id is required in strict business-key mode")

    def count_aspcs(self, is_active: bool | None = None) -> int:
        """Count assay configurations, optionally selecting an active state.

        Args:
            is_active: True selects active configurations; False selects inactive ones.
                None, the default, counts all stored configurations.

        Returns:
            The number of stored configurations matching the selected state.
        """
        query = {}
        if is_active is not None:
            query["is_active"] = is_active
        return int(self.get_collection().count_documents(query))

    def get_dashboard_analysis_type_rollup(self, *, asp_ids: list[str]) -> list[AnalysisTypeRollup]:
        """Count analysis capabilities of active configurations for selected assays.

        Args:
            asp_ids: Required assay IDs; an empty list selects none. Blank IDs are
                ignored, and duplicates select an assay only once.

        Returns:
            Rows sorted by uppercase analysis_type, each containing integer enabled
            and reportable counts, including zero for an absent category.

        Raises:
            ValueError: A nonblank assay identifier has invalid syntax.
        """
        normalized_ids = sorted(
            {
                normalize_clinical_identifier(value, label="asp_id")
                for value in asp_ids
                if str(value or "").strip()
            }
        )
        if not normalized_ids:
            return []

        rows = list(
            self.get_collection().aggregate(
                [
                    {"$match": {"is_active": True, "asp_id": {"$in": normalized_ids}}},
                    {
                        "$facet": {
                            "enabled": [
                                {"$unwind": "$analysis_types"},
                                {"$group": {"_id": "$analysis_types", "count": {"$sum": 1}}},
                            ],
                            "reportable": [
                                {"$unwind": "$reporting.report_sections"},
                                {
                                    "$group": {
                                        "_id": "$reporting.report_sections",
                                        "count": {"$sum": 1},
                                    }
                                },
                            ],
                        }
                    },
                ],
                allowDiskUse=True,
            )
        )
        result = rows[0] if rows else {}
        counts: dict[str, AnalysisTypeRollup] = {}
        for field in ("enabled", "reportable"):
            for row in result.get(field, []) or []:
                analysis_type = str(row.get("_id") or "").strip().upper()
                if not analysis_type:
                    continue
                entry = counts.setdefault(
                    analysis_type,
                    {"analysis_type": analysis_type, "enabled": 0, "reportable": 0},
                )
                count = int(row.get("count", 0) or 0)
                if field == "enabled":
                    entry["enabled"] = count
                else:
                    entry["reportable"] = count
        return [counts[key] for key in sorted(counts)]

    def get_all_aspc(self) -> cursor.Cursor[dict[str, Any]]:
        """
        Retrieves all assay configuration documents from the collection.

        Returns:
            pymongo.cursor.Cursor: A cursor to iterate over all assay configuration documents.
        """
        return self.get_collection().find({})

    def search_aspcs(
        self,
        *,
        q: str = "",
        page: int = 1,
        per_page: int = 30,
        latest_only: bool = False,
        is_active: bool | None = True,
    ) -> tuple[list[dict[str, Any]], int]:
        """Search configuration identities and metadata using a literal case-insensitive query.

        Args:
            q: Search text across identifiers, environment, assay type and category.
            page: One-based page; values below one select the first page.
            per_page: Page size, constrained to 1–200; zero selects the default of 30.
            is_active: Active-state filter; None includes all revisions.

        Returns:
            Documents ordered by assay, diagnosis and environment, plus the total match count.
        """
        query: dict[str, Any] = {}
        if is_active is not None and not latest_only:
            query["is_active"] = is_active
        normalized_q = str(q or "").strip()
        if normalized_q:
            pattern = re.escape(normalized_q)
            query["$or"] = [
                {"aspc_id": {"$regex": pattern, "$options": "i"}},
                {"asp_id": {"$regex": pattern, "$options": "i"}},
                {"diagnosis_id": {"$regex": pattern, "$options": "i"}},
                {"environment": {"$regex": pattern, "$options": "i"}},
                {"assay_type": {"$regex": pattern, "$options": "i"}},
                {"category": {"$regex": pattern, "$options": "i"}},
            ]
        page = max(1, int(page or 1))
        per_page = max(1, min(int(per_page or 30), 200))
        skip = (page - 1) * per_page
        col = self.get_collection()
        if latest_only:
            rows, total = library_rows(
                col,
                self.identity_field,
                query,
                {"aspc_id": 1},
                skip,
                per_page,
                {"gene_list_release": 0, "assay_resource_release": 0},
            )
            return rows, total
        total = int(col.count_documents(query))
        docs = list(
            col.find(query)
            .sort([("asp_id", 1), ("diagnosis_id", 1), ("environment", 1)])
            .skip(skip)
            .limit(per_page)
        )
        return docs, total

    def list_versions(self, identifier: str) -> list[dict[str, Any]]:
        """Read all retained revisions of one exact resource without changing activation.

        Args:
            identifier: Stable aspc_id business identifier, including retired-only resources.

        Returns:
            Current and retired documents in descending version order; empty if unknown.
        """
        return list(self.get_collection().find({"aspc_id": identifier}).sort("version", -1))

    def get_aspc(
        self, assay: str, profile: str = DEFAULT_ENVIRONMENT, diagnosis_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Retrieve the active configuration for an assay, environment, and diagnosis.

        Args:
            assay (str): ASP identifier, independent of the configuration's chosen ID.
            profile (str): The environment profile associated with the assay configuration (default is "production").
            diagnosis_id: Diagnosis identifier; omitted selects the base diagnosis.

        Returns:
            dict | None: The assay configuration document if found, otherwise None.
        """
        return self.get_collection().find_one(
            self._scope_lookup_query(assay, profile, diagnosis_id)
        )

    @staticmethod
    def _scope_lookup_query(assay: str, profile: str, diagnosis_id: str | None) -> dict[str, Any]:
        """Resolve the unique active runtime scope without inferring a business ID."""
        return {
            "asp_id": normalize_clinical_identifier(assay, label="asp_id"),
            "diagnosis_id": normalize_clinical_identifier(
                diagnosis_id or DIAGNOSIS_BASE_ID, label="diagnosis_id"
            ),
            "environment": normalize_environment(profile),
            "is_active": True,
        }

    def get_aspc_with_id(self, aspc_id: str) -> dict[str, Any] | None:
        """
        Retrieves a specific assay configuration document by its ID.

        Args:
            aspc_id: Stable configuration business identifier, including a full
                assay::diagnosis::environment identifier when generated from its scope.

        Returns:
            dict | None: The assay configuration document if found, otherwise None.
        """
        return self.get_collection().find_one(
            {**self._aspc_lookup_query(aspc_id), "is_active": True}
        )

    def registered_scope(self, assay: str, profile: str, diagnosis_id: str) -> bool:
        """Check whether a configuration already owns this scope in the component library."""
        selector = self._scope_lookup_query(assay, profile, diagnosis_id)
        selector.pop("is_active")
        return self.get_collection().find_one(selector, {"_id": 1}) is not None

    def intake_scope_available(
        self, asp_id: str, diagnosis_id: str, *, session: ClientSession | None = None
    ) -> bool:
        """Check current assay, group and named diagnosis availability before applying a release."""
        panel = self.adapter.asp_collection.find_one(
            {"asp_id": asp_id, "is_active": True}, {"asp_group": 1}, session=session
        )
        return bool(
            panel and self._scope_available({**panel, "asp_id": asp_id}, diagnosis_id, session)
        )

    def active_revision_for_sample(
        self, sample: dict[str, Any], *, session: ClientSession
    ) -> object | None:
        """Resolve the eligible named or Base release again inside the sample update transaction."""
        diagnosis = sample.get("diagnosis_id") or DIAGNOSIS_BASE_ID
        if not self.intake_scope_available(sample["asp_id"], diagnosis, session=session):
            return None
        for scope in dict.fromkeys((diagnosis, DIAGNOSIS_BASE_ID)):
            selector = self._scope_lookup_query(sample["asp_id"], sample["environment"], scope)
            row = self.get_collection().find_one(selector, {"_id": 1}, session=session)
            if row:
                identifier: object = row["_id"]
                return identifier
        return None

    def get_aspc_no_meta(
        self, assay_id: str, profile: str = DEFAULT_ENVIRONMENT, diagnosis_id: str | None = None
    ) -> dict[str, Any] | None:
        """
        Retrieve an active scope configuration without creation/update metadata.

        Args:
            assay_id (str): ASP identifier.
            profile (str): The profile name to filter the assay configuration.
            diagnosis_id: Diagnosis identifier; omitted selects the base diagnosis.

        Returns:
            dict: The filtered assay configuration document if found, otherwise `None`.
        """
        projection = {
            "updated_on": 0,
            "updated_by": 0,
            "created_on": 0,
            "created_by": 0,
        }
        return self.get_collection().find_one(
            self._scope_lookup_query(assay_id, profile, diagnosis_id),
            projection,
        )

    def get_aspc_revision_no_meta(self, revision_id: object) -> dict[str, Any] | None:
        """Return one stored ASPC revision, including an inactive historical revision.

        Samples store this MongoDB identity when they are ingested or deliberately
        moved to a newer configuration.  It is therefore the authoritative source
        for that sample's filters and reporting context.
        """
        if revision_id is None:
            return None
        candidate_ids: list[object] = [revision_id]
        if not isinstance(revision_id, ObjectId):
            try:
                candidate_ids.append(ObjectId(str(revision_id)))
            except Exception:
                pass
        projection = {
            "updated_on": 0,
            "updated_by": 0,
            "created_on": 0,
            "created_by": 0,
        }
        return self.get_collection().find_one({"_id": {"$in": candidate_ids}}, projection)

    def get_active_aspcs_for_asp(
        self, asp_id: str, environment: str = DEFAULT_ENVIRONMENT
    ) -> list[dict[str, Any]]:
        """Return active assay configurations for one ASP and environment."""
        assay_id = normalize_clinical_identifier(asp_id, label="asp_id") if asp_id else ""
        env = normalize_environment(environment)
        if not assay_id:
            return []
        return list(
            self.get_collection()
            .find({"asp_id": assay_id, "environment": env, "is_active": True})
            .sort([("diagnosis_id", 1), ("aspc_id", 1)])
        )

    def rotate_aspc(
        self,
        aspc_id: str,
        data: dict[str, Any],
        *,
        expected_version: int,
        retire_fields: dict[str, Any],
    ) -> OperationResult:
        """Publish a successor and retire the expected active revision."""
        return self.publish_revision(
            self.ensure_aspc_id(dict(data)),
            expected_version=expected_version,
            retire_fields=retire_fields,
            identifier=aspc_id,
        )

    def create_assay_config(self, data: dict[str, Any]) -> OperationResult:
        """Create the first active revision."""
        return self.publish_revision(self.ensure_aspc_id(dict(data)))

    def delete_assay_config(self, assay_id: str) -> OperationResult:
        """Withdraw the current revision while retaining its history."""
        return self.set_availability(assay_id, False)

    def toggle_aspc_active(self, aspc_id: str, active_status: bool) -> OperationResult:
        """Change availability of the current library revision."""
        return self.set_availability(aspc_id, active_status)

    def get_all_assay_names(self, is_active: bool | None = None) -> list[str]:
        """List distinct assay identifiers, optionally selecting an activation state.

        Args:
            is_active: True selects active configurations; False selects inactive ones.
                None, the default, includes both states.

        Returns:
            Distinct stored asp_id values with no guaranteed order; empty if none match.
        """
        if is_active is None:
            return self.get_collection().distinct("asp_id")
        else:
            return self.get_collection().find({"is_active": is_active}).distinct("asp_id")

    def get_available_assay_envs(
        self,
        assay_name: str,
        all_envs: list[str],
        diagnosis_id: str | None = None,
    ) -> list[str]:
        """
        Retrieves a list of available environments for a specific assay configuration.

        Args:
            assay_name (str): The base assay name (e.g., "Demo").
            all_envs (list): All supported environments (e.g., ["production", "development", "validation"]).
            diagnosis_id: Diagnosis scope to exclude; None selects the base diagnosis.

        Returns:
            list: A list of environments not yet used for this assay.
        """
        query = {
            "asp_id": assay_name,
            "diagnosis_id": str(diagnosis_id or DIAGNOSIS_BASE_ID).strip(),
        }
        assay_configs = self.get_collection().find(query, {"environment": 1})

        used_envs = set()
        for config in assay_configs:
            env = config.get("environment")
            if env:
                used_envs.add(env)

        return [env for env in all_envs if env not in used_envs]
