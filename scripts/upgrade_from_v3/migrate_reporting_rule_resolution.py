#!/usr/bin/env python3
"""Replace ASPC rule bindings with scope-based reporting language configuration."""

from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.application.reporting.clinical_rules.resolution import (
    resolve_published_rule_set,  # noqa: E402
)
from api.application.reporting.clinical_rules.validation import content_hash  # noqa: E402
from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import (  # noqa: E402
    build_revision_snapshot,
    verify_revision_snapshot,
)
from api.infra.mongo.transactions import run_transaction  # noqa: E402


def migrate(db, *, apply: bool = False) -> dict[str, int]:
    """Migrate rule selection configuration and obsolete embedded test facts together.

    Args:
        db: Explicit application database, not the identity or knowledgebase database.
        apply: Write only when true; otherwise perform a read-only preflight.

    Returns:
        Counts of affected configurations, rule documents, revisions and changed selections.

    Raises:
        ValueError: Published scopes are ambiguous, a binding cannot supply a language,
            an in-review setup needs to return to draft, or a writer changed the plan.

    Notes:
        Pause configuration writers and back up the database before applying. Reports
        and samples are never updated. Obsolete embedded test facts and their affected
        rule/revision hashes are migrated together, unless saved reports reference them.
        ASPC revisions retain their IDs, clinical settings and version numbers.
    """
    mapping = load_collection_section("primary")
    rules = list(db[mapping["clinical_rule_sets_collection"]].find({}))
    languages: dict[str, set[str]] = {}
    active_scopes = set()
    for rule in rules:
        scope = rule["scope"]
        languages.setdefault(rule["rule_set_id"], set()).add(scope["language"])
        if rule.get("active") and rule.get("status") == "published":
            key = tuple(scope[key] for key in ("asp_id", "subpanel_id", "analyte", "language"))
            if key in active_scopes:
                raise ValueError(f"Ambiguous published scope: {key}")
            active_scopes.add(key)

    def reporting(source):
        """Preserve settings while deriving language from the previously bound rule."""
        result = deepcopy(source)
        binding = result.pop("clinical_rule_set_id", None)
        if binding:
            choices = languages.get(binding, set())
            if len(choices) != 1:
                raise ValueError(f"Cannot determine reporting language for rule {binding!r}")
            language = next(iter(choices))
            if result.get("language", language) != language:
                raise ValueError("Configured language conflicts with the previous rule binding")
            result["language"] = language
        else:
            result.setdefault("language", "sv")
        return result

    changes = []
    counts = {
        "asp_configs": 0,
        "assay_setups": 0,
        "rule_documents": 0,
        "rule_revisions": 0,
        "selection_changes": 0,
    }

    def clean_rule(source):
        """Remove obsolete bindings only from embedded prepared test-case facts."""
        result = deepcopy(source)
        for case in result.get("test_cases", []):
            facts = case.get("facts", {}).get("aspc", {}).get("reporting", {})
            if "clinical_rule_set_id" in facts:
                case["facts"]["aspc"]["reporting"] = reporting(facts)
        if result != source and result.get("content_hash"):
            result["content_hash"] = content_hash(ClinicalRuleSetDoc.model_validate(result))
        return result

    affected = set()
    cleaned_rules = []
    for rule in rules:
        updated = clean_rule(rule)
        cleaned_rules.append(updated)
        if updated != rule:
            affected.add(str(rule["_id"]))
            changes.append((db[mapping["clinical_rule_sets_collection"]], rule, updated))
            counts["rule_documents"] += 1
    previous_hashes = {}
    original_hashes = {}
    revisions = db[mapping["clinical_rule_revisions_collection"]]
    for snapshot in revisions.find({}).sort([("rule_set_oid", 1), ("revision", 1)]):
        verified = verify_revision_snapshot(snapshot)
        identity = snapshot["rule_set_oid"]
        if verified.get("previous_revision_hash") != original_hashes.get(identity):
            raise ValueError("Clinical rule revision chain is broken; migration cannot rewrite it")
        original_hashes[identity] = verified["revision_hash"]
        updated_doc = clean_rule(verified["document"])
        previous = previous_hashes.get(identity)
        updated = build_revision_snapshot(
            updated_doc,
            action=verified["action"],
            actor=verified["actor"],
            occurred_at=verified["occurred_at"],
            reason=verified.get("reason"),
            previous_revision_hash=previous,
        )
        previous_hashes[identity] = updated["revision_hash"]
        if updated["revision_hash"] != snapshot["revision_hash"]:
            affected.add(identity)
            changes.append((revisions, snapshot, dict(updated, _id=snapshot["_id"])))
            counts["rule_revisions"] += 1
    if affected and db[mapping["reports_collection"]].find_one(
        {"clinical_rule_source.source.rule_set_oid": {"$in": sorted(affected)}}
    ):
        raise ValueError(
            "Saved reports reference affected rule history; preserve those records and review migration"
        )
    rule_repository = SimpleNamespace(list_active_for_assay=lambda _asp, **_scope: cleaned_rules)

    def validate_scope(config, updated_reporting):
        """Require complete active reporting coverage and identify changed selections."""
        sections = updated_reporting.get("report_sections", [])
        if not config.get("is_active") or not sections:
            return
        rule = resolve_published_rule_set(
            rule_repository,
            asp_id=config["asp_id"],
            subpanel_id=config.get("subpanel_id") or "base",
            analyte=config["asp_category"].lower(),
            language=updated_reporting["language"],
        )
        if set(sections) - set(rule.analysis_declarations):
            raise ValueError(
                f"Undeclared reporting analyses for {config.get('aspc_id', config['asp_id'])}"
            )
        old = config.get("reporting", {}).get("clinical_rule_set_id")
        if old and old != rule.rule_set_id:
            counts["selection_changes"] += 1
            print(
                f"Rule selection changes for {config.get('aspc_id', config['asp_id'])}: {old} -> {rule.rule_set_id}"
            )

    configs = db[mapping["aspc_collection"]]
    for doc in configs.find({}):
        original = doc.get("reporting", {})
        updated = reporting(original)
        validate_scope(doc, updated)
        if updated != original:
            changes.append((configs, doc, dict(doc, reporting=updated)))
            counts["asp_configs"] += 1
    setups = db[mapping["assay_setups_collection"]]
    for doc in setups.find({"status": {"$ne": "published"}}):
        original = doc.get("content", {})
        updated = deepcopy(original)
        for config in updated.get("configurations", []):
            config["reporting"] = reporting(config.get("reporting", {}))
        if updated != original:
            if doc.get("status") != "draft":
                raise ValueError("Return in-review assay setups to draft before migrating")
            changes.append((setups, doc, dict(doc, content=updated)))
            counts["assay_setups"] += 1

    if apply:

        def write(session):
            """Apply the reviewed plan with optimistic checks inside one transaction."""
            for collection, original, updated in changes:
                result = collection.replace_one(original, updated, session=session)
                if result.matched_count != 1:
                    raise ValueError("Configuration changed during migration; rerun the plan")

        run_transaction(db.client, write)
        db[mapping["clinical_rule_sets_collection"]].create_index(
            [
                ("scope.asp_id", 1),
                ("scope.subpanel_id", 1),
                ("scope.analyte", 1),
                ("scope.language", 1),
            ],
            name="active_published_rule_scope_unique",
            unique=True,
            partialFilterExpression={"active": True, "status": "published"},
        )
    return counts


def main() -> int:
    """Run the read-only plan unless --apply explicitly enables configuration writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=os.environ.get("COYOTE3_MONGO_URI"))
    parser.add_argument("--db", default=os.environ.get("COYOTE3_DB"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.mongo_uri or not args.db:
        parser.error("COYOTE3_MONGO_URI and COYOTE3_DB or explicit overrides are required")
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000) as client:
        counts = migrate(client[args.db], apply=args.apply)
    print(f"{'Migrated' if args.apply else 'Would migrate'}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
