#!/usr/bin/env python3
"""Plan or apply explicit ASPC tier policies and draft report-metadata rules.

Published rule versions, historical ASPCs, annotations and reports are retained.
Run with COYOTE3_MONGO_URI and COYOTE3_DB configured; writes require --apply.
"""

from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator  # noqa: E402
from api.application.reporting.clinical_rules.facts import PreparedReportContext  # noqa: E402
from api.application.reporting.clinical_rules.validation import validate_rule_set  # noqa: E402
from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import build_revision_snapshot  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402

MIGRATION_REASON = "Move report eligibility and metadata to governed configuration"


def predicate(fact: str, value: object, operator: str = "eq") -> dict:
    """Build a typed comparison for a migration-generated rule."""
    return {"type": "predicate", "fact": fact, "operator": operator, "value": value}


def metadata_blocks(group: str, analyte: str) -> list[dict]:
    """Translate former report-template decisions into ordinary clinical rule blocks.

    Args:
        group: Existing ASP group, used only during this one-time conversion.
        analyte: DNA or RNA rule-set scope.

    Returns:
        Whole-report blocks for the clinical question and optional header suffix.
        Base has no named clinical question for solid assays.
    """
    blocks: list[dict] = []

    def add(section: str, cases: list[tuple[dict | None, list[dict]]]) -> None:
        """Append one mutually exclusive report-metadata destination."""
        blocks.append(
            {
                "block_id": f"metadata_{section}",
                "name": section.replace("_", " ").title(),
                "analysis": None,
                "evaluation": {"mode": "once"},
                "section": section,
                "section_order": 0,
                "block_order": len(blocks),
                "show_heading": False,
                "match_strategy": "first_match",
                "rules": [
                    {
                        "rule_id": f"metadata_{section}_{index}",
                        "name": f"{section} {index}",
                        "order": index,
                        "condition": condition,
                        "output": output,
                        "rationale": MIGRATION_REASON,
                    }
                    for index, (condition, output) in enumerate(cases, start=1)
                ],
            }
        )

    def text(value: str) -> list[dict]:
        """Build literal output without introducing a second template language."""
        return [{"type": "text", "value": value}]

    if analyte == "rna":
        add("clinical_question", [(None, text("Fusionsgenanalys"))])
    elif group in {"hematology", "myeloid"}:
        add(
            "clinical_question",
            [
                (predicate("sample.paired", True), text("Hematologisk neoplasi")),
                (None, text("<DIAGNOSIS>")),
            ],
        )
    elif group == "solid":
        add(
            "clinical_question",
            [
                (predicate("sample.subpanel_id", "bp"), text("Bröst-Pilot")),
                (
                    predicate("sample.subpanel_id", ["base", ""], "not_in"),
                    [{"type": "fact", "path": "sample.subpanel_id", "missing": "omit"}],
                ),
            ],
        )
    if group == "myeloid":
        add(
            "report_header_suffix",
            [
                (
                    {
                        "type": "all",
                        "children": [
                            predicate("sample.subpanel_id", "hem-snabb"),
                            predicate("sample.paired", paired),
                        ],
                    },
                    text(value),
                )
                for paired, value in [
                    (True, ": fullständig parad analys"),
                    (False, ": preliminär oparad analys"),
                ]
            ],
        )
    return blocks


def metadata_draft(source: dict, *, group: str, version: int, actor: str) -> dict | None:
    """Copy a published version into a draft without changing existing clinical rules.

    Args:
        source: Published canonical rule document.
        group: ASP group owning the source scope.
        version: Unused content version allocated by the transaction.
        actor: Operator recorded in lifecycle and revision history.

    Returns:
        Validated draft, or None when all applicable destinations already exist.

    Raises:
        ValueError: Generated identifiers collide or existing rule semantics are invalid.
    """
    document = ClinicalRuleSetDoc.model_validate(source).model_dump(mode="python", by_alias=True)
    existing_sections = {block["section"] for block in document["blocks"]}
    additions = [
        block
        for block in metadata_blocks(group, document["scope"]["analyte"])
        if block["section"] not in existing_sections
    ]
    if not additions:
        return None
    section_order = max((block["section_order"] for block in document["blocks"]), default=0) + 1
    for block in additions:
        block["section_order"] = section_order
    now = datetime.now(timezone.utc)
    document.update(
        _id=ObjectId(),
        content_version=version,
        revision=1,
        status="draft",
        active=False,
        created_at=now,
        updated_at=now,
        created_by=actor,
        updated_by=actor,
        published_at=None,
        published_by=None,
        effective_from=None,
        retired_at=None,
        retired_by=None,
        content_hash=None,
        review={},
        change_summary=MIGRATION_REASON,
        lifecycle=[{"action": "draft_created", "actor": actor, "occurred_at": now}],
        provenance={
            "source": "template",
            "source_rule_set_id": source["rule_set_id"],
            "source_content_version": source["content_version"],
            "source_revision": source["revision"],
        },
    )
    # Extend only metadata expectations; retain every existing clinical assertion.
    metadata_only = deepcopy(document)
    metadata_only["blocks"] = additions
    metadata_only["test_cases"] = []
    candidate = ClinicalRuleSetDoc.model_validate(metadata_only)
    for case in document["test_cases"]:
        result = ClinicalRuleEvaluator().evaluate(
            PreparedReportContext.model_validate(case["facts"]), candidate, reporting_analyses=set()
        )
        case["expected_rule_ids"] += [trace.rule_id for trace in result.trace if trace.matched]
        case["expected_sections"].update(result.sections)
    document["blocks"] += additions
    parsed = ClinicalRuleSetDoc.model_validate(document)
    validation = validate_rule_set(parsed)
    if not validation.valid:
        raise ValueError(f"Rule-set migration requires review: {validation.errors}")
    return parsed.model_dump(mode="python", by_alias=True, exclude_none=True)


def migrate(db, *, actor: str, apply: bool = False) -> dict[str, int]:
    """Version active ASPCs and add metadata drafts in one retryable transaction.

    Args:
        db: Explicit target database; no identity or sample collections are accessed.
        actor: Operator attributed to new revisions.
        apply: False performs a read-only plan; True commits configuration changes.

    Returns:
        Counts of planned ASPC revisions and clinical rule drafts.

    Notes:
        Existing open drafts block duplicate generated drafts. Independent review
        and publication remain necessary. Reruns do not replace custom policies.
    """
    names = load_collection_section("primary")
    configs = db[names["aspc_collection"]]
    rules = db[names["clinical_rule_sets_collection"]]
    revisions = db[names["clinical_rule_revisions_collection"]]

    def operation(session) -> dict[str, int]:
        """Read and conditionally write the migration in the owning snapshot."""
        panels = {
            doc["asp_id"]: doc
            for doc in db[names["asp_collection"]].find({}, session=session).sort("version", 1)
        }
        counts = {"aspc_revisions": 0, "rule_drafts": 0, "open_rule_drafts": 0}
        for source in configs.find(
            {"is_active": True, "reporting.reportable_tiers": {"$exists": False}}, session=session
        ):
            group = source.get("asp_group") or panels[source["asp_id"]]["asp_group"]
            document = deepcopy(source)
            now = datetime.now(timezone.utc)
            document.update(
                _id=ObjectId(),
                supersedes_id=source["_id"],
                version=source["version"] + 1,
                created_by=actor,
                updated_by=actor,
                created_on=now,
                updated_on=now,
            )
            for field in ("retired_on", "retired_by", "retired_reason"):
                document.pop(field, None)
            document.setdefault("reporting", {})["reportable_tiers"] = {
                "SNV": [1, 2] if group == "gmsonco" else [1, 2, 3],
                "FUSION": [1, 2, 3],
            }
            if apply:
                configs.update_one(
                    {"_id": source["_id"]},
                    {
                        "$set": {
                            "is_active": False,
                            "retired_on": now,
                            "retired_by": actor,
                            "retired_reason": MIGRATION_REASON,
                        }
                    },
                    session=session,
                )
                configs.insert_one(document, session=session)
            counts["aspc_revisions"] += 1
        for source in rules.find({"status": "published", "active": True}, session=session):
            identity = source["rule_set_id"]
            if rules.find_one(
                {
                    "rule_set_id": identity,
                    "status": {"$in": ["draft", "submitted", "in_clinical_review", "approved"]},
                },
                session=session,
            ):
                counts["open_rule_drafts"] += 1
                continue
            latest = rules.find_one(
                {"rule_set_id": identity}, sort=[("content_version", -1)], session=session
            )
            draft = metadata_draft(
                source,
                group=panels[source["scope"]["asp_id"]]["asp_group"],
                version=latest["content_version"] + 1,
                actor=actor,
            )
            if draft is None:
                continue
            if apply:
                rules.insert_one(draft, session=session)
                revisions.insert_one(
                    build_revision_snapshot(
                        draft,
                        action="draft_created",
                        actor=actor,
                        occurred_at=draft["created_at"],
                        reason=MIGRATION_REASON,
                        previous_revision_hash=None,
                    ),
                    session=session,
                )
            counts["rule_drafts"] += 1
        return counts

    return run_transaction(db.client, operation) if apply else operation(None)


def main() -> int:
    """Run an explicit-target dry run or transaction; never log a connection URI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.getenv("COYOTE3_DB"))
    parser.add_argument("--actor", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    uri = os.getenv("COYOTE3_MONGO_URI")
    if not uri or not args.db or not args.actor.strip():
        parser.error("Set COYOTE3_MONGO_URI, COYOTE3_DB (or --db), and a nonempty --actor")
    with MongoClient(uri, serverSelectionTimeoutMS=7000) as client:
        result = migrate(client[args.db], actor=args.actor.strip(), apply=args.apply)
    print(f"{'Applied' if args.apply else 'Dry run'}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
