#!/usr/bin/env python3
"""Plan or install synthetic workflow configuration in a local demo database.

Requires an initialized local replica set and application baseline. This command
never installs samples, findings, accounts or published report rules. Existing
fixture scopes are rejected rather than overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from bson import ObjectId
from pymongo import MongoClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from api.application.reporting.clinical_rules.validation import content_hash  # noqa: E402
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc  # noqa: E402
from api.contracts.schemas.registry import normalize_collection_document  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import (  # noqa: E402
    build_revision_snapshot,
)


def validate_target(uri: str, database: str) -> None:
    """Require a loopback Mongo endpoint and an explicitly named demonstration database.

    Args:
        uri: A single-host MongoDB URI for the local test installation.
        database: Target name beginning with ``coyote3_demo``.

    Raises:
        ValueError: The target could be a remote or ordinary application database.
    """
    parsed = urlsplit(uri)
    if parsed.scheme != "mongodb" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only a loopback MongoDB endpoint is supported")
    if "," in parsed.netloc or parsed.path not in {"", "/"}:
        raise ValueError("Use one local endpoint with the database supplied through --db")
    if database != "coyote3_demo" and not database.startswith("coyote3_demo_"):
        raise ValueError("Database must be coyote3_demo or start with coyote3_demo_")


def main() -> None:
    """Validate the entire configuration, then optionally insert it in one transaction."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--actor", required=True, help="Existing demonstration administrator")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    validate_target(args.mongo_uri, args.db)
    if not args.actor.strip():
        raise ValueError("Actor must not be blank")
    now = datetime.now(timezone.utc)
    documents = {}
    for path in sorted((REPO / "demo_data/clinical_workflows/setup").glob("*.json")):
        rows = []
        for source in json.loads(path.read_text()):
            row = normalize_collection_document(path.stem, source)
            row["_id"] = ObjectId()
            for field in ("created_by", "updated_by"):
                if field in row:
                    row[field] = args.actor
            for field in ("created_on", "updated_on", "created_at", "updated_at"):
                if field in row:
                    row[field] = now
            if path.stem == "clinical_rule_sets":
                row["content_hash"] = content_hash(ClinicalRuleSetDoc.model_validate(row))
            rows.append(normalize_collection_document(path.stem, row))
        documents[path.stem] = rows
    with MongoClient(
        args.mongo_uri, directConnection=True, serverSelectionTimeoutMS=5000
    ) as client:
        db = client[args.db]

        def preflight(session=None):
            """Reject uninitialized targets and any conflicting demonstration identity."""
            groups = {row["asp_group"] for row in documents["assay_specific_panels"]}
            registered = {
                row["group_id"]
                for row in db.assay_groups.find({"is_active": True}, session=session)
            }
            if groups - registered or not db.query_rule_sets.count_documents({}, session=session):
                raise ValueError("Install the application groups and query-rule baseline first")
            identities = {
                "assay_specific_panels": "asp_id",
                "asp_configs": "aspc_id",
                "clinical_rule_sets": "rule_set_id",
                "insilico_genelists": "isgl_id",
                "subpanels": "subpanel_id",
                "subpanel_associations": "subpanel_id",
            }
            for name, rows in documents.items():
                key = identities[name]
                if db[name].count_documents(
                    {key: {"$in": [r[key] for r in rows]}}, session=session
                ):
                    raise ValueError(f"Existing demo configuration in {name}; nothing replaced")

        preflight()
        print(json.dumps({name: len(rows) for name, rows in documents.items()}, indent=2))
        if not args.apply:
            print("Plan only; repeat with --apply to install this configuration")
            return
        with client.start_session() as session, session.start_transaction():
            preflight(session)
            for name, rows in documents.items():
                db[name].insert_many(rows, session=session)
            revisions = [
                build_revision_snapshot(
                    row,
                    action="baseline_captured",
                    actor=args.actor,
                    occurred_at=now,
                    reason="Synthetic demonstration draft installed",
                    previous_revision_hash=None,
                )
                for row in documents["clinical_rule_sets"]
            ]
            db.clinical_rule_revisions.insert_many(revisions, session=session)
        print("Installed synthetic configuration; report rules remain unpublished drafts")


if __name__ == "__main__":
    main()
