"""Read-only extraction of latest Mongo documents for test fixture seeding.

Outputs:
- tests/api/fixtures/db_snapshots/prod_latest.json
- tests/api/fixtures/db_snapshots/dev_rna_wgs_latest.json
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
from typing import Any

import pymongo
from bson import ObjectId

import config

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / "tests" / "api" / "fixtures" / "db_snapshots"

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


def _json_safe(value: Any) -> Any:
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


def _latest_doc(coll, query: dict | None = None) -> dict | None:
    query = query or {}
    for key in SORT_CANDIDATES:
        try:
            doc = coll.find(query).sort([(key, pymongo.DESCENDING)]).limit(1).next()
            if doc is not None:
                return doc
        except StopIteration:
            return None
        except Exception:
            continue
    try:
        return coll.find(query).limit(1).next()
    except Exception:
        return None


def _extract(config_obj, scoped_query: dict | None = None) -> dict[str, Any]:
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
        },
        "collections": {},
    }

    for alias, coll_name in mapping.items():
        coll = db[coll_name]
        count_total = 0
        count_scoped = None
        try:
            count_total = coll.count_documents({})
            if scoped_query:
                count_scoped = coll.count_documents(scoped_query)
        except Exception:
            pass

        doc = _latest_doc(coll, query=scoped_query)
        if doc is None and scoped_query:
            doc = _latest_doc(coll, query={})

        result["collections"][alias] = {
            "collection": coll_name,
            "count_total": count_total,
            "count_scoped": count_scoped,
            "latest": _json_safe(doc) if doc is not None else None,
        }

    client.close()
    return result


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    prod = config.ProductionConfig()
    dev = config.DevelopmentConfig()

    prod_snapshot = _extract(prod)
    dev_snapshot = _extract(dev, scoped_query=RNA_WGS_PATTERN)

    (OUT_DIR / "prod_latest.json").write_text(json.dumps(prod_snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "dev_rna_wgs_latest.json").write_text(
        json.dumps(dev_snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("wrote:", OUT_DIR / "prod_latest.json")
    print("wrote:", OUT_DIR / "dev_rna_wgs_latest.json")


if __name__ == "__main__":
    main()
