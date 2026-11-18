# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Compile exact clinical grants into MongoDB predicates before pagination/aggregation."""


def restrict_assay_access(query: dict, grants: list[dict] | None) -> dict:
    """Intersect a query with paired grants; an empty grant list matches no records.

    Args:
        query: Existing repository criteria, which are never broadened or mutated.
        grants: Exact assay/environment rows; None denotes an explicitly unscoped operation.

    Returns:
        Original criteria intersected with the union of authorized pairs.
    """
    if grants is None:
        return query
    clauses = [
        {"asp_id": row["asp_id"], "environment": {"$in": list(row["environments"])}}
        for row in grants
        if row.get("asp_id") and row.get("environments")
    ]
    scope = {"$or": clauses} if clauses else {"_id": {"$in": []}}
    return {"$and": [query, scope]} if query else scope


def finding_scope_query(adapter, grants: list[dict] | None, field: str = "SAMPLE_ID") -> dict:
    """Restrict a finding inventory to samples authorized by exact pair assignments.

    Args:
        adapter: Host adapter providing the authoritative sample collection.
        grants: Exact assignments or None for a verified unscoped operation.
        field: SAMPLE_ID for serialized sample identifiers, or sample_name for snapshots.

    Returns:
        Predicate using the finding's stored identity format, or an empty predicate
        for unscoped operations.
    """
    if grants is None:
        return {}
    sample_field = "_id" if field == "SAMPLE_ID" else "name"
    identities = adapter.samples_collection.distinct(
        sample_field, restrict_assay_access({}, grants)
    )
    if field == "SAMPLE_ID":
        identities = [str(identity) for identity in identities]
    return {field: {"$in": identities}}
