# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Bounded metadata retrieval over fixed collections and exact access grants."""

from typing import Any

from bson import ObjectId
from coyote.application.operations.resource_reads import ResourceReadScope
from coyote.domain.common.errors import api_error
from coyote_contracts.retrieval import (
    RESOURCE_IDENTIFIERS,
    RESOURCE_MODELS,
    FieldPredicate,
    ReadResource,
    ResourceReadPage,
    ResourceReadQuery,
)

from coyote_mongo.assay_access import restrict_assay_access

_QUERY_TIMEOUT_MS = 5000
_MAX_RELATED_MATCHES = 1000


class MongoResourceReadRepository:
    """Compile validated public operations into fixed read-only Mongo pipelines.

    Every aggregate applies scope before counting or paging. Only safe metadata is
    projected, including on related records. Physical collection names, database
    operators and document identifiers cannot be supplied by the caller.
    """

    def __init__(self, store: Any) -> None:
        """Bind the host's configured collections without opening another client."""
        self._collections = {
            ReadResource.ASP: store.asp_collection,
            ReadResource.ASPC: store.aspc_collection,
            ReadResource.SAMPLES: store.samples_collection,
            ReadResource.ISGL: store.insilico_genelist_collection,
            ReadResource.ASSAY_GROUPS: store.assay_groups_collection,
            ReadResource.DIAGNOSES: store.diagnoses_collection,
        }
        self._diagnosis_links = store.diagnosis_associations_collection

    def _aggregate(self, resource: ReadResource, pipeline: list[dict]) -> list[dict]:
        """Run a bounded-time read; caller pipelines bound returned page size."""
        return list(
            self._collections[resource].aggregate(
                pipeline, maxTimeMS=_QUERY_TIMEOUT_MS, allowDiskUse=False
            )
        )

    def _scope(self, resource: ReadResource, scope: ResourceReadScope) -> dict:
        """Compile exact grants for clinical resources and their parent assays.

        Gene lists, groups and diagnoses are shared reference catalogs governed by
        their resource permission. Their nonclinical metadata is not sample scope.
        """
        if resource not in {ReadResource.SAMPLES, ReadResource.ASPC, ReadResource.ASP}:
            return {}
        if resource is ReadResource.ASP:
            query = (
                {}
                if scope.grants is None
                else {
                    "asp_id": {
                        "$in": [row["asp_id"] for row in scope.grants if row["environments"]]
                    }
                }
            )
        else:
            query = restrict_assay_access({}, scope.grants)
        if scope.groups and "*" not in scope.groups:
            allowed = self._aggregate(
                ReadResource.ASP,
                [
                    {"$match": {"is_active": True, "asp_group": {"$in": list(scope.groups)}}},
                    {"$group": {"_id": "$asp_id"}},
                ],
            )
            query = {"$and": [query, {"asp_id": {"$in": [row["_id"] for row in allowed]}}]}
        return query

    @staticmethod
    def _filter(query: ResourceReadQuery) -> dict:
        """Translate validated operators, keeping explicit null distinct from absence."""
        clauses = []
        for name, supplied in query.filters.items():
            predicate = (
                supplied if isinstance(supplied, FieldPredicate) else FieldPredicate(eq=supplied)
            )
            comparisons = predicate.model_dump(exclude_unset=True, by_alias=True)
            operators = {"$" + key: value for key, value in comparisons.items()}
            operators["$exists"] = True
            clauses.append({name: operators})
        return {"$and": clauses} if clauses else {}

    def _projection(self, resource: ReadResource, *, internal: bool = False) -> dict:
        """Project only declared metadata and private tie-breakers needed internally."""
        projection: dict[str, Any] = {key: 1 for key in RESOURCE_MODELS[resource].model_fields}
        projection["_id"] = 1 if internal else 0
        if resource is ReadResource.ASPC:
            projection["report_sections"] = {"$ifNull": ["$reporting.report_sections", []]}
        elif resource is ReadResource.ISGL:
            projection["gene_count"] = {"$size": {"$ifNull": ["$genes", []]}}
        if internal and resource is ReadResource.SAMPLES:
            projection["current_aspc_id"] = 1
        return projection

    def _base(
        self,
        resource: ReadResource,
        scope: ResourceReadScope,
        query: ResourceReadQuery | None = None,
    ) -> list[dict]:
        """Resolve derived public metadata before user filtering and sorting."""
        match = self._scope(resource, scope)
        if query is not None:
            derived = {
                ReadResource.SAMPLES: {"asp_group"},
                ReadResource.ASPC: {"report_sections"},
                ReadResource.ISGL: {"gene_count"},
                ReadResource.DIAGNOSES: {"asp_ids"},
            }.get(resource, set())
            direct = query.model_copy(
                update={
                    "filters": {
                        name: value for name, value in query.filters.items() if name not in derived
                    }
                }
            )
            match = {"$and": [match, self._filter(direct)]}
        pipeline: list[dict] = [{"$match": match}]
        needs_sample_group = query is None or (
            "asp_group" in query.filters
            or query.field == "asp_group"
            or query.sort == "asp_group"
            or query.operation == "list"
            and (query.fields is None or "asp_group" in query.fields)
        )
        if resource is ReadResource.SAMPLES and needs_sample_group:
            pipeline.extend(
                [
                    {
                        "$lookup": {
                            "from": self._collections[ReadResource.ASP].name,
                            "localField": "asp_id",
                            "foreignField": "asp_id",
                            "as": "_assays",
                        }
                    },
                    {
                        "$project": {
                            **self._projection(resource, internal=True),
                            "asp_group": {
                                "$ifNull": [
                                    "$asp_group",
                                    {
                                        "$arrayElemAt": [
                                            {
                                                "$map": {
                                                    "input": {
                                                        "$filter": {
                                                            "input": "$_assays",
                                                            "as": "assay",
                                                            "cond": {
                                                                "$eq": ["$$assay.is_active", True]
                                                            },
                                                        }
                                                    },
                                                    "as": "assay",
                                                    "in": "$$assay.asp_group",
                                                }
                                            },
                                            0,
                                        ]
                                    },
                                ]
                            },
                        }
                    },
                ]
            )
            return pipeline
        if resource is ReadResource.DIAGNOSES:
            # A definition read describes current links, including retired links.
            # Previous definition revisions remain selectable through version filters.
            pipeline.extend(
                [
                    {
                        "$lookup": {
                            "from": self._diagnosis_links.name,
                            "localField": "diagnosis_id",
                            "foreignField": "diagnosis_id",
                            "as": "_links",
                        }
                    },
                    {
                        "$project": {
                            **self._projection(resource, internal=True),
                            "asp_ids": {
                                "$map": {
                                    "input": {
                                        "$filter": {
                                            "input": "$_links",
                                            "as": "link",
                                            "cond": {"$eq": ["$$link.is_current", True]},
                                        }
                                    },
                                    "as": "link",
                                    "in": "$$link.asp_id",
                                }
                            },
                        }
                    },
                ]
            )
        else:
            pipeline.append({"$project": self._projection(resource, internal=True)})
        return pipeline

    @staticmethod
    def _metadata(resource: ReadResource, record: dict, fields: list[str] | None = None) -> dict:
        """Serialize safe fields, preserving false, zero, explicit and absent nulls."""
        names = fields or list(RESOURCE_MODELS[resource].model_fields)
        return {name: record.get(name) for name in names}

    @staticmethod
    def _revision_candidates(revision: object) -> list[object]:
        """Preserve the stored identifier and accept its existing ObjectId representation."""
        if revision is None:
            return []
        values = [revision]
        if isinstance(revision, str) and ObjectId.is_valid(revision):
            values.append(ObjectId(revision))
        return values

    def _related_page(
        self, samples: list[dict], query: ResourceReadQuery, scope: ResourceReadScope
    ) -> list[dict]:
        """Load each requested relationship once for the bounded sample page."""
        output: list[dict] = [{} for _ in samples]
        if not samples:
            return output
        for relationship in query.include:
            target = ReadResource.ASP if relationship == "assay" else ReadResource.ASPC
            if target is ReadResource.ASP:
                match = {
                    "asp_id": {"$in": list({row.get("asp_id") for row in samples})},
                    "is_active": True,
                }
            else:
                revisions = [
                    value
                    for row in samples
                    for value in self._revision_candidates(row.get("current_aspc_id"))
                ]
                match = {"_id": {"$in": revisions}}
            pipeline = self._base(target, scope)
            pipeline += [
                {"$match": match},
                {"$sort": {"version": -1, "_id": 1}},
                {"$limit": _MAX_RELATED_MATCHES + 1},
            ]
            records = self._aggregate(target, pipeline)
            if len(records) > _MAX_RELATED_MATCHES:
                raise api_error(422, "Too many related records for this page; reduce per_page")
            lookup = {}
            for record in records:
                key = record.get("asp_id") if target is ReadResource.ASP else record["_id"]
                lookup.setdefault(key, record)
            for sample, related in zip(samples, output, strict=True):
                if target is ReadResource.ASP:
                    record = lookup.get(sample.get("asp_id"))
                else:
                    record = next(
                        (
                            lookup[value]
                            for value in self._revision_candidates(sample.get("current_aspc_id"))
                            if value in lookup
                        ),
                        None,
                    )
                    if record and (
                        record.get("asp_id") != sample.get("asp_id")
                        or record.get("environment") != sample.get("environment")
                    ):
                        record = None
                related[relationship] = self._metadata(target, record) if record else None
        return output

    def _related_matches(self, query: ResourceReadQuery, scope: ResourceReadScope) -> dict:
        """Restrict samples to bounded authorized matches in fixed related catalogs.

        Configuration identity and its assay/environment must all match the sample.
        The bounded lookup also accepts persisted string forms of a revision ID,
        as supported by the existing configuration repository.
        """
        clauses = []
        for relationship, filters in query.related_filters.items():
            target = ReadResource.ASP if relationship == "assay" else ReadResource.ASPC
            related_query = ResourceReadQuery(filters=filters).validate_resource(target)
            pipeline = self._base(target, scope, related_query) + [
                {"$match": self._filter(related_query)}
            ]
            if target is ReadResource.ASP:
                pipeline.append({"$match": {"is_active": True}})
            rows = self._aggregate(target, pipeline + [{"$limit": _MAX_RELATED_MATCHES + 1}])
            if len(rows) > _MAX_RELATED_MATCHES:
                raise api_error(
                    422, "Related filters match too many records; narrow the related filters"
                )
            if target is ReadResource.ASP:
                clauses.append({"asp_id": {"$in": [row["asp_id"] for row in rows]}})
            else:
                matches = [
                    {
                        "current_aspc_id": {"$in": [row["_id"], str(row["_id"])]},
                        "asp_id": row.get("asp_id"),
                        "environment": row.get("environment"),
                    }
                    for row in rows
                ]
                clauses.append({"$or": matches} if matches else {"_id": {"$in": []}})
        return {"$and": clauses} if clauses else {}

    def query(
        self, resource: ReadResource, query: ResourceReadQuery, scope: ResourceReadScope
    ) -> ResourceReadPage:
        """Return one authorized page or aggregate with a stable value/identity order.

        Args:
            resource: Fixed public resource name.
            query: Typed request, revalidated at this adapter boundary.
            scope: Trusted current grants supplied by the application service.

        Returns:
            Metadata, distinct IDs or flattened distinct scalar values. Counts refer
            to matching records; IDs and distinct totals refer to unique values.
        """
        query = ResourceReadQuery.model_validate(
            query.model_dump(by_alias=True, exclude_unset=True, warnings="none")
        ).validate_resource(resource)
        pipeline = self._base(resource, scope, query) + [
            {"$match": self._filter(query)},
            {"$match": self._related_matches(query, scope)},
        ]
        scalar = query.operation in {"ids", "distinct"}
        if scalar:
            field = RESOURCE_IDENTIFIERS[resource] if query.operation == "ids" else query.field
            pipeline += [
                {"$match": {field: {"$exists": True}}},
                {"$unwind": {"path": "$" + str(field), "preserveNullAndEmptyArrays": True}},
                {"$match": {field: {"$exists": True}}},
            ]
            if query.operation == "ids":
                pipeline.append({"$match": {str(field): {"$type": "string", "$ne": ""}}})
            pipeline.append({"$group": {"_id": "$" + str(field)}})
        if query.operation == "exists":
            exists = bool(self._aggregate(resource, pipeline + [{"$limit": 1}]))
            return ResourceReadPage(page=query.page, per_page=query.per_page, exists=exists)
        total_rows = self._aggregate(
            resource, pipeline + [{"$group": {"_id": None, "total": {"$sum": 1}}}]
        )
        total = total_rows[0]["total"] if total_rows else 0
        if query.operation == "count":
            return ResourceReadPage(
                page=query.page, per_page=query.per_page, total=total, count=total
            )
        direction = -1 if query.descending else 1
        ordering = (
            {"_id": direction}
            if scalar
            else {
                query.sort or RESOURCE_IDENTIFIERS[resource]: direction,
                RESOURCE_IDENTIFIERS[resource]: direction,
                "version": direction,
                "_id": direction,
            }
        )
        offset = (query.page - 1) * query.per_page
        rows = self._aggregate(
            resource,
            pipeline
            + [
                {"$sort": ordering},
                {"$skip": offset},
                {"$limit": query.per_page},
            ],
        )
        if scalar:
            items = [row["_id"] for row in rows]
        else:
            items = []
            related_page = (
                self._related_page(rows, query, scope) if query.include else [{} for _ in rows]
            )
            for row, related in zip(rows, related_page, strict=True):
                item = self._metadata(resource, row, query.fields)
                if query.include:
                    item["related"] = related
                items.append(item)
        return ResourceReadPage(
            items=items,
            total=total,
            page=query.page,
            per_page=query.per_page,
            has_next=offset + len(items) < total and bool(items),
        )
