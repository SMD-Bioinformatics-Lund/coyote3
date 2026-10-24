"""Aggregate sample workload and observed provenance without loading sample cohorts."""

from api.config.constants import DEFAULT_ENVIRONMENT


class SampleStatisticsMixin:
    """Read sample statistics through MongoDB aggregation pipelines."""

    def user_sample_counts_by_assay(self, report: bool | None = None, assays: list = None) -> dict:
        """
        Retrieve the count of samples for each assay group.
        This method aggregates sample counts by assay groups, returning a dictionary
        where each key is an assay group and the value is the count of samples in that group.
        Args:
            assays (list, optional): A list of assay groups to filter the samples. If None, counts all samples.
        Returns:
            dict: A dictionary where each key is an assay group and the value is the count of samples in that group.
        """
        pipeline = [
            {"$match": {"asp_id": {"$in": assays}}} if assays else {},
            {"$group": {"_id": "$asp_id", "count": {"$sum": 1}}},
            {"$project": {"_id": 0, "asp_id": "$_id", "count": 1}},
        ]
        if assays is None:
            pipeline = [
                {"$group": {"_id": "$asp_id", "count": {"$sum": 1}}},
                {"$project": {"_id": 0, "asp_id": "$_id", "count": 1}},
            ]
        result = list(self.get_collection().aggregate(pipeline))
        return {item["asp_id"]: item["count"] for item in result}

    def get_dashboard_sample_rollup(self, asp_ids: list[str] | None = None) -> dict:
        """
        Aggregate all dashboard sample counters in a single query.
        """
        # asp_ids=None => unscoped (admin/all), asp_ids=[] => explicit no access (match nothing)
        base_match = {"asp_id": {"$in": asp_ids}} if asp_ids is not None else {}
        collection = self.get_collection()

        pipeline: list[dict] = []
        if base_match:
            pipeline.append({"$match": base_match})
        pipeline.append(
            {
                "$facet": {
                    "totals": [
                        {
                            "$group": {
                                "_id": None,
                                "total_samples": {"$sum": 1},
                                "analysed_samples": {"$sum": {"$cond": ["$reported", 1, 0]}},
                            }
                        },
                        {"$project": {"_id": 0, "total_samples": 1, "analysed_samples": 1}},
                    ],
                    "by_assay": [
                        {
                            "$group": {
                                "_id": "$asp_id",
                                "total": {"$sum": 1},
                                "analysed": {"$sum": {"$cond": ["$reported", 1, 0]}},
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "asp_id": "$_id",
                                "total": 1,
                                "analysed": 1,
                                "pending": {"$subtract": ["$total", "$analysed"]},
                            }
                        },
                    ],
                    "profiles": [
                        {"$group": {"_id": "$environment", "count": {"$sum": 1}}},
                        {"$project": {"_id": 0, "key": "$_id", "count": 1}},
                    ],
                    "omics_layers": [
                        {"$group": {"_id": "$asp_category", "count": {"$sum": 1}}},
                        {"$project": {"_id": 0, "key": "$_id", "count": 1}},
                    ],
                    "sequencing_scopes": [
                        {"$group": {"_id": "$asp_family", "count": {"$sum": 1}}},
                        {"$project": {"_id": 0, "key": "$_id", "count": 1}},
                    ],
                    "pair_counts": [
                        {"$group": {"_id": "$paired", "count": {"$sum": 1}}},
                        {"$project": {"_id": 0, "key": "$_id", "count": 1}},
                    ],
                    "ingest_statuses": [
                        {"$group": {"_id": "$ingest_status", "count": {"$sum": 1}}},
                        {"$project": {"_id": 0, "key": "$_id", "count": 1}},
                    ],
                    "pipelines": [
                        {
                            "$group": {
                                "_id": {
                                    "name": "$pipeline",
                                    "version": "$pipeline_version",
                                },
                                "count": {"$sum": 1},
                                "analysed": {"$sum": {"$cond": ["$reported", 1, 0]}},
                                "ready": {
                                    "$sum": {
                                        "$cond": [
                                            {"$eq": ["$ingest_status", "ready"]},
                                            1,
                                            0,
                                        ]
                                    }
                                },
                            }
                        },
                        {
                            "$project": {
                                "_id": 0,
                                "name": {"$ifNull": ["$_id.name", "unknown"]},
                                "version": {"$ifNull": ["$_id.version", None]},
                                "count": 1,
                                "analysed": 1,
                                "ready": 1,
                            }
                        },
                        {"$sort": {"count": -1, "name": 1, "version": 1}},
                    ],
                    "recent_samples": [
                        {"$sort": {"time_added": -1, "_id": -1}},
                        {"$limit": 5},
                        {
                            "$project": {
                                "_id": 0,
                                "id": {"$toString": "$_id"},
                                "name": 1,
                                "asp_id": 1,
                                "diagnosis_id": 1,
                                "environment": 1,
                                "reported": 1,
                                "ingest_status": 1,
                                "asp_category": 1,
                                "time_added": 1,
                            }
                        },
                    ],
                }
            }
        )

        facet_result = list(collection.aggregate(pipeline, allowDiskUse=True))
        facet_doc = facet_result[0] if facet_result else {}
        totals = (facet_doc.get("totals") or [{}])[0]

        total_samples = int(totals.get("total_samples", 0) or 0)
        analysed_samples = int(totals.get("analysed_samples", 0) or 0)

        user_samples_stats: dict[str, dict[str, int]] = {}
        for row in facet_doc.get("by_assay", []) or []:
            asp_id = row.get("asp_id")
            if not asp_id:
                continue
            assay_total = int(row.get("total", 0) or 0)
            assay_analysed = int(row.get("analysed", 0) or 0)
            user_samples_stats[str(asp_id)] = {
                "total": assay_total,
                "analysed": assay_analysed,
                "pending": max(int(row.get("pending", 0) or 0), 0),
            }

        def _kv_to_dict(items: list[dict]) -> dict:
            """Kv to dict.

            Args:
                    items: Items.

            Returns:
                    The  kv to dict result.
            """
            out = {}
            for row in items or []:
                key = row.get("key")
                if key is None:
                    key = "unknown"
                out[str(key)] = int(row.get("count", 0) or 0)
            return out

        pair_counts = {"paired": 0, "unpaired": 0, "unknown": 0}
        for row in facet_doc.get("pair_counts", []) or []:
            key = row.get("key")
            count = int(row.get("count", 0) or 0)
            if key is True:
                pair_counts["paired"] = count
            elif key is False:
                pair_counts["unpaired"] = count
            else:
                pair_counts["unknown"] = count

        return {
            "total_samples": total_samples,
            "analysed_samples": analysed_samples,
            "pending_samples": max(total_samples - analysed_samples, 0),
            "user_samples_stats": user_samples_stats,
            "sample_stats": {
                "profiles": _kv_to_dict(facet_doc.get("profiles", []) or []),
                "omics_layers": _kv_to_dict(facet_doc.get("omics_layers", []) or []),
                "sequencing_scopes": _kv_to_dict(facet_doc.get("sequencing_scopes", []) or []),
                "pair_count": pair_counts,
                "ingest_statuses": _kv_to_dict(facet_doc.get("ingest_statuses", []) or []),
                "pipelines": list(facet_doc.get("pipelines", []) or []),
            },
            "recent_samples": list(facet_doc.get("recent_samples", []) or []),
        }

    def get_assay_specific_sample_stats(
        self, assays: list = None, environment: str = DEFAULT_ENVIRONMENT
    ) -> dict:
        """
        Retrieve assay-specific statistics.

        This method calculates statistics for each assay group, including:
        - Total number of samples.
        - Number of samples with reports.
        - Number of samples pending reports.

        Returns:
            dict: A dictionary where each key is an assay group, and the value is another dictionary containing:
                - 'total': Total number of samples in the group.
                - 'report': Number of samples with reports.
                - 'pending': Number of samples without reports.
        """
        pipeline = []

        if assays:
            pipeline.append({"$match": {"asp_id": {"$in": assays}, "environment": environment}})

        pipeline.append(
            {
                "$group": {
                    "_id": {"asp_id": "$asp_id"},
                    "total": {"$sum": 1},
                    "analysed": {"$sum": {"$cond": ["$reported", 1, 0]}},
                    "pending": {"$sum": {"$cond": ["$reported", 0, 1]}},
                }
            }
        )

        result = list(self.get_collection().aggregate(pipeline))

        assay_group_stats = {}
        for doc in result:
            asp_id = doc["_id"]["asp_id"]
            assay_group_stats[asp_id] = {
                "total": doc.get("total", 0),
                "analysed": doc.get("analysed", 0),
                "pending": doc.get("pending", 0),
            }

        return assay_group_stats

    def get_observed_software_versions(self, *, limit: int = 1000) -> dict[str, object]:
        """Return bounded, de-duplicated pipeline and VEP versions for public metadata."""
        pipelines: dict[str, set[str]] = {}
        vep_versions: set[str] = set()
        cursor = (
            self.get_collection()
            .find(
                {},
                {"pipeline": 1, "pipeline_version": 1, "database_versions.vep": 1},
            )
            .limit(limit)
        )
        for sample in cursor:
            pipeline = str(sample.get("pipeline") or "").strip()
            pipeline_version = str(sample.get("pipeline_version") or "").strip()
            if pipeline:
                pipelines.setdefault(pipeline, set())
                if pipeline_version:
                    pipelines[pipeline].add(pipeline_version)
            vep_version = str((sample.get("database_versions") or {}).get("vep") or "").strip()
            if vep_version:
                vep_versions.add(vep_version)
        return {
            "pipelines": {key: sorted(values) for key, values in sorted(pipelines.items())},
            "vep": sorted(vep_versions),
        }

    def get_observed_database_versions(self, *, limit: int = 1000) -> dict[str, list[str]]:
        """Return bounded, de-duplicated sample database versions for public metadata."""
        database_versions: dict[str, set[str]] = {}
        cursor = (
            self.get_collection()
            .find(
                {"database_versions": {"$type": "object"}},
                {"database_versions": 1},
            )
            .limit(limit)
        )
        for sample in cursor:
            for name, version in dict(sample.get("database_versions") or {}).items():
                key = str(name).strip()
                value = str(version).strip()
                if key and value:
                    database_versions.setdefault(key, set()).add(value)
        return {key: sorted(values) for key, values in sorted(database_versions.items())}
