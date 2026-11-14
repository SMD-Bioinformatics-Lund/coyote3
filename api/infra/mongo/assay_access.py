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
        field: Finding field containing sample names.

    Returns:
        Indexed sample-name predicate, or an empty predicate for unscoped operations.
    """
    if grants is None:
        return {}
    names = adapter.samples_collection.distinct("name", restrict_assay_access({}, grants))
    return {field: {"$in": names}}
