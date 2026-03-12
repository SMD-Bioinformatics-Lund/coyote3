"""Read-only extraction of Mongo documents for test fixture seeding.

Outputs:
- tests/fixtures/api/db_snapshots/prod_latest.json
- tests/fixtures/api/db_snapshots/dev_rna_wgs_latest.json

Extraction rules:
- collections are read from the active config's DB collection mapping
- `samples` snapshots include the latest 10 documents per assay
- collections containing `SAMPLE_ID` are filtered to sampled `samples._id`
- all other configured collections are snapshotted in full
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import sys
from typing import Any

import pymongo
from bson import ObjectId

ROOT = Path(__file__).resolve().parents[3]
root_str = str(ROOT)
if root_str not in sys.path:
    sys.path.insert(0, root_str)

import config

OUT_DIR = ROOT / "tests" / "fixtures" / "api" / "db_snapshots"

SORT_CANDIDATES = [
    "updated_on",
    "updated_at",
    "time_updated",
    "time_created",
    "created_on",
    "created_at",
    "timestamp",
    "_id",
]

RNA_WGS_PATTERN = {
    "$or": [
        {"assay": {"$regex": "rna|wgs|wts|tumwgs", "$options": "i"}},
        {"asp_group": {"$regex": "rna|wgs|wts|tumwgs", "$options": "i"}},
        {"analysis_types": {"$elemMatch": {"$regex": "rna|wgs|wts|fusion", "$options": "i"}}},
        {"schema_name": {"$regex": "rna|wgs|wts|tumwgs", "$options": "i"}},
    ]
}

SAMPLES_ALIAS = "samples_collection"
SAMPLES_PER_ASSAY = 10


def _json_safe(value: Any) -> Any:
    """Handle  json safe.

    Args:
            value: Value.

    Returns:
            The  json safe result.
    """
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _sorted_cursor(coll, query: dict | None = None):
    """Handle  sorted cursor.

    Args:
            coll: Coll.
            query: Query. Optional argument.

    Returns:
            The  sorted cursor result.
    """
    query = query or {}
    for key in SORT_CANDIDATES:
        try:
            return coll.find(query).sort([(key, pymongo.DESCENDING)])
        except Exception:
            continue
    return coll.find(query)


def _latest_doc(coll, query: dict | None = None) -> dict | None:
    """Handle  latest doc.

    Args:
            coll: Coll.
            query: Query. Optional argument.

    Returns:
            The  latest doc result.
    """
    try:
        return _sorted_cursor(coll, query=query).limit(1).next()
    except StopIteration:
        return None
    except Exception:
        try:
            return coll.find(query or {}).limit(1).next()
        except Exception:
            return None


def _collection_counts(coll, scoped_query: dict | None = None) -> tuple[int, int | None]:
    """Handle  collection counts.

    Args:
            coll: Coll.
            scoped_query: Scoped query. Optional argument.

    Returns:
            The  collection counts result.
    """
    count_total = 0
    count_scoped = None
    try:
        count_total = coll.count_documents({})
        if scoped_query:
            count_scoped = coll.count_documents(scoped_query)
    except Exception:
        pass
    return count_total, count_scoped


def _sample_assay_values(coll, scoped_query: dict | None = None) -> list[Any]:
    """Handle  sample assay values.

    Args:
            coll: Coll.
            scoped_query: Scoped query. Optional argument.

    Returns:
            The  sample assay values result.
    """
    query = scoped_query or {}
    try:
        values = list(coll.distinct("assay", query))
    except Exception:
        values = []
    normalized = [value for value in values if value not in (None, "")]
    return sorted(normalized, key=lambda value: str(value).lower())


def _merge_query(base: dict | None, extra: dict | None) -> dict:
    """Handle  merge query.

    Args:
            base: Base.
            extra: Extra.

    Returns:
            The  merge query result.
    """
    if base and extra:
        return {"$and": [base, extra]}
    return dict(base or extra or {})


def _sample_documents(coll, scoped_query: dict | None = None) -> list[dict[str, Any]]:
    """Handle  sample documents.

    Args:
            coll: Coll.
            scoped_query: Scoped query. Optional argument.

    Returns:
            The  sample documents result.
    """
    docs: list[dict[str, Any]] = []
    assay_values = _sample_assay_values(coll, scoped_query=scoped_query)
    if not assay_values:
        query = scoped_query or {}
        return list(_sorted_cursor(coll, query=query).limit(SAMPLES_PER_ASSAY))

    for assay in assay_values:
        assay_query = _merge_query(scoped_query, {"assay": assay})
        docs.extend(list(_sorted_cursor(coll, query=assay_query).limit(SAMPLES_PER_ASSAY)))
    return docs


def _collection_has_sample_id(coll) -> bool:
    """Handle  collection has sample id.

    Args:
            coll: Coll.

    Returns:
            The  collection has sample id result.
    """
    try:
        return coll.find_one({"SAMPLE_ID": {"$exists": True}}, {"_id": 1}) is not None
    except Exception:
        return False


def _documents_for_collection(
    *,
    alias: str,
    coll,
    scoped_query: dict | None,
    sampled_sample_ids: list[Any],
) -> tuple[list[dict[str, Any]], str]:
    """Handle  documents for collection.

    Args:
            alias: Alias. Keyword-only argument.
            coll: Coll. Keyword-only argument.
            scoped_query: Scoped query. Keyword-only argument.
            sampled_sample_ids: Sampled sample ids. Keyword-only argument.

    Returns:
            The  documents for collection result.
    """
    if alias == SAMPLES_ALIAS:
        return _sample_documents(coll, scoped_query=scoped_query), "latest_10_per_assay"

    if _collection_has_sample_id(coll):
        if not sampled_sample_ids:
            return [], "sample_id_dependency"
        query = {"SAMPLE_ID": {"$in": sampled_sample_ids}}
        return list(_sorted_cursor(coll, query=query)), "sample_id_dependency"

    return list(coll.find({})), "full_collection"


def _extract(config_obj, scoped_query: dict | None = None) -> dict[str, Any]:
    """Handle  extract.

    Args:
            config_obj: Config obj.
            scoped_query: Scoped query. Optional argument.

    Returns:
            The  extract result.
    """
    mongo_uri = config_obj.MONGO_URI
    db_name = config_obj.MONGO_DB_NAME
    mapping = config_obj.DB_COLLECTIONS_CONFIG.get(db_name, {})

    client = pymongo.MongoClient(mongo_uri)
    db = client[db_name]

    result: dict[str, Any] = {
        "meta": {
            "mongo_uri": mongo_uri,
            "db_name": db_name,
            "extracted_at": datetime.now(timezone.utc).isoformat(),
            "scoped_query": scoped_query or {},
            "samples_per_assay": SAMPLES_PER_ASSAY,
        },
        "collections": {},
    }

    samples_coll = db[mapping[SAMPLES_ALIAS]]
    sample_docs = _sample_documents(samples_coll, scoped_query=scoped_query)
    sampled_sample_ids = [doc.get("_id") for doc in sample_docs if doc.get("_id") is not None]

    for alias, coll_name in mapping.items():
        coll = db[coll_name]
        count_total, count_scoped = _collection_counts(coll, scoped_query=scoped_query)
        docs, strategy = _documents_for_collection(
            alias=alias,
            coll=coll,
            scoped_query=scoped_query,
            sampled_sample_ids=sampled_sample_ids,
        )

        latest = docs[0] if docs else None
        if latest is None and strategy != "full_collection":
            latest = _latest_doc(coll)

        result["collections"][alias] = {
            "collection": coll_name,
            "count_total": count_total,
            "count_scoped": count_scoped,
            "strategy": strategy,
            "document_count": len(docs),
            "sampled_sample_ids": _json_safe(sampled_sample_ids) if alias != SAMPLES_ALIAS else None,
            "latest": _json_safe(latest) if latest is not None else None,
            "docs": _json_safe(docs),
        }

    client.close()
    return result


def main() -> None:
    """Handle main.

    Returns:
        None.
    """
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prod = config.ProductionConfig()
    dev = config.DevelopmentConfig()

    prod_snapshot = _extract(prod)
    dev_snapshot = _extract(dev, scoped_query=RNA_WGS_PATTERN)

    (OUT_DIR / "prod_latest.json").write_text(
        json.dumps(prod_snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUT_DIR / "dev_rna_wgs_latest.json").write_text(
        json.dumps(dev_snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("wrote:", OUT_DIR / "prod_latest.json")
    print("wrote:", OUT_DIR / "dev_rna_wgs_latest.json")


if __name__ == "__main__":
    main()
