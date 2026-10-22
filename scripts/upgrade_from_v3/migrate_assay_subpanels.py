#!/usr/bin/env python3
"""Register assay subpanels, with opt-in ISGL diagnosis spelling normalization."""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.config.constants import SUBPANEL_BASE_ID, normalize_clinical_identifier  # noqa: E402
from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.infra.mongo.repositories.assay_subpanels import AssaySubpanelRepository  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402
from api.infra.seed.subpanels import plan_subpanels  # noqa: E402


def normalize_diagnosis_associations(lists: list[dict]) -> tuple[list[dict], list[dict]]:
    """Plan an explicit spelling migration for ISGL subpanel associations.

    Args:
        lists: Gene-list metadata, including the original diagnosis arrays and IDs.

    Returns:
        Copied metadata with canonical associations and the changed source documents.

    Raises:
        ValueError: Input is malformed, contains unsupported characters, or distinct
            spellings collapse onto one identifier. Semantic aliases are not inferred.
    """
    result, changes = [], []
    spellings: dict[str, set[str]] = {}
    for source in lists:
        values = source.get("diagnosis", [])
        if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
            raise ValueError("ISGL diagnosis must be a list of text identifiers")
        normalized = []
        for value in values:
            identifier = normalize_clinical_identifier(re.sub(r"\s+", "-", value.strip()))
            spellings.setdefault(identifier, set()).add(value)
            if identifier not in normalized:
                normalized.append(identifier)
        document = {**source, "diagnosis": normalized}
        result.append(document)
        if normalized != values:
            changes.append(source)
    collisions = {key: sorted(values) for key, values in spellings.items() if len(values) > 1}
    if collisions:
        raise ValueError(f"ISGL diagnosis spelling collisions require review: {collisions!r}")
    return result, changes


def validate_annotation_scopes(
    panels: list[dict], documents: list[dict], annotation_scopes: list[dict]
) -> list[dict]:
    """Verify historical annotation group/subpanel pairs without changing their identity.

    Args:
        panels: All ASP revisions, including historical group membership.
        documents: Planned and already registered subpanel definitions.
        annotation_scopes: Distinct pairs containing only assay and subpanel fields.

    Returns:
        Unmatched canonical scopes for operator review, without assigning ASP ownership.

    Raises:
        ValueError: A named annotation subpanel is not a canonical identifier.

    Notes:
        Annotation assay values represent groups, not ASP identifiers. Null or empty
        subpanels remain unscoped; they are not converted into the base scope.
        A group-level annotation alone cannot establish which ASP owns a new scope.
    """
    groups_by_assay: dict[str, set[str | None]] = {}
    for panel in panels:
        groups_by_assay.setdefault(panel["asp_id"], set()).add(panel.get("asp_group"))
    known = {
        (group, document["subpanel_id"])
        for document in documents
        for group in groups_by_assay.get(document["asp_id"], set())
    }
    unmatched = [
        scope
        for scope in annotation_scopes
        if scope.get("subpanel") not in (None, "")
        and scope.get("subpanel") != SUBPANEL_BASE_ID
        and (scope.get("assay"), scope["subpanel"]) not in known
    ]
    invalid = []
    for scope in annotation_scopes:
        value = scope.get("subpanel")
        if value in (None, ""):
            continue
        try:
            canonical = normalize_clinical_identifier(value)
        except ValueError:
            invalid.append(scope)
        else:
            if canonical != value:
                invalid.append(scope)
    if invalid:
        pairs = ", ".join(
            sorted({f"{scope.get('assay')!r}/{scope['subpanel']!r}" for scope in invalid})
        )
        raise ValueError(
            f"Noncanonical annotation group/subpanel scopes: {pairs}. "
            "Review a clinical identifier migration before retrying; annotations are not rewritten."
        )
    return unmatched


def migrate(
    db, *, actor: str, apply: bool = False, normalize_isgl_diagnosis: bool = False
) -> tuple[int, int]:
    """Validate the full plan, then optionally insert missing definitions only.

    Args:
        db: Explicit application database selected by the operator.
        actor: Named operator recorded on new registry records.
        apply: False performs reads only, including no index creation.
        normalize_isgl_diagnosis: Explicitly lowercase diagnosis associations and
            replace whitespace with hyphens. Other collections remain read-only
            except new registry definitions. Noncanonical clinical scopes still block writes.

    Returns:
        Counts of missing and already registered identities.
    """
    mapping = load_collection_section("primary")
    panels = list(
        db[mapping["asp_collection"]].find({}, {"asp_id": 1, "asp_group": 1, "version": 1})
    )
    lists = list(db[mapping["insilico_genelist_collection"]].find({}, {"genes": 0}))
    changes = []
    if normalize_isgl_diagnosis:
        lists, changes = normalize_diagnosis_associations(lists)
    documents = plan_subpanels(
        panels,
        list(db[mapping["aspc_collection"]].find({}, {"asp_id": 1, "subpanel_id": 1})),
        list(db[mapping["clinical_rule_sets_collection"]].find({}, {"scope": 1})),
        lists,
        actor=actor,
    )
    legacy = list(db["assay_subpanels"].find({"is_current": True}))
    by_identity = {(doc["asp_id"], doc["subpanel_id"]): doc for doc in documents}
    for doc in legacy:
        if doc["subpanel_id"] != SUBPANEL_BASE_ID:
            by_identity[(doc["asp_id"], doc["subpanel_id"])] = {
                key: value
                for key, value in doc.items()
                if key not in {"_id", "definition_version", "definition_is_active"}
            } | {"version": 1, "updated_by": actor, "updated_on": datetime.now(timezone.utc)}
    documents = list(by_identity.values())
    shared_metadata = {}
    for doc in documents:
        metadata = (doc["display_name"], doc.get("description", ""))
        if (
            doc["subpanel_id"] in shared_metadata
            and shared_metadata[doc["subpanel_id"]] != metadata
        ):
            raise ValueError(
                f"Conflicting shared metadata for {doc['subpanel_id']!r}; review before merging"
            )
        shared_metadata[doc["subpanel_id"]] = metadata
    existing_documents = list(
        db[mapping["subpanel_associations_collection"]].find(
            {"is_current": True}, {"asp_id": 1, "subpanel_id": 1}
        )
    )
    annotation_scopes = [
        row["_id"]
        for row in db[mapping["annotations_collection"]].aggregate(
            [{"$group": {"_id": {"assay": "$assay", "subpanel": "$subpanel"}}}]
        )
    ]
    unmatched = validate_annotation_scopes(
        panels, [*documents, *existing_documents], annotation_scopes
    )
    if unmatched:
        print(
            "[warning] Annotation scopes without a registry match are preserved, not registered. "
            "Review ownership separately; these may be historical or cross-assay scopes.",
            file=sys.stderr,
        )
        for group, subpanel in sorted(
            {(repr(scope.get("assay")), repr(scope["subpanel"])) for scope in unmatched}
        ):
            print(f"  {group}/{subpanel}", file=sys.stderr)
    repository = AssaySubpanelRepository(
        SimpleNamespace(
            subpanel_associations_collection=db[mapping["subpanel_associations_collection"]],
            subpanels_collection=db[mapping["subpanels_collection"]],
        )
    )
    missing = [
        doc
        for doc in documents
        if repository.get_current(doc["asp_id"], doc["subpanel_id"]) is None
    ]
    current_definitions = {doc["subpanel_id"]: doc for doc in repository.list_definitions()}
    for document in missing:
        definition = current_definitions.get(document["subpanel_id"])
        if definition and (
            any(
                document.get(key, "") != definition.get(key, "")
                for key in ("display_name", "description")
            )
            or document["is_active"]
            and not definition["is_active"]
        ):
            raise ValueError(
                f"Existing shared definition conflicts with {document['subpanel_id']!r}; review before applying"
            )
    if apply:
        repository.ensure_indexes()
        if normalize_isgl_diagnosis:
            normalized_by_id = {doc["_id"]: doc["diagnosis"] for doc in lists}

            def write(session):
                """Commit reviewed association changes and registry additions atomically."""
                for source in changes:
                    result = db[mapping["insilico_genelist_collection"]].update_one(
                        {"_id": source["_id"], "diagnosis": source["diagnosis"]},
                        {
                            "$set": {
                                "diagnosis": normalized_by_id[source["_id"]],
                                "updated_by": actor,
                                "updated_on": datetime.now(timezone.utc),
                            }
                        },
                        session=session,
                    )
                    if result.matched_count != 1:
                        raise ValueError("ISGL changed during migration; rerun the read-only plan")
                for document in missing:
                    repository.save(document, session=session)

            run_transaction(db.client, write)
        else:
            for document in missing:
                repository.save(document)
    if normalize_isgl_diagnosis:
        print(
            f"{'Normalized' if apply else 'Would normalize'} {len(changes)} ISGL diagnosis arrays"
        )
    return len(missing), len(documents) - len(missing)


def main() -> int:
    """Run a read-only plan unless --apply explicitly enables registry writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=os.environ.get("COYOTE3_MONGO_URI"))
    parser.add_argument("--db", default=os.environ.get("COYOTE3_DB"))
    parser.add_argument("--actor", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--normalize-isgl-diagnosis",
        action="store_true",
        help="Normalize ISGL diagnosis spelling; writes require --apply. No clinical records are renamed.",
    )
    args = parser.parse_args()
    if not args.mongo_uri or not args.db or not args.actor.strip():
        parser.error("MongoDB URI, database and a nonblank actor are required")
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000) as client:
        missing, existing = migrate(
            client[args.db],
            actor=args.actor.strip(),
            apply=args.apply,
            normalize_isgl_diagnosis=args.normalize_isgl_diagnosis,
        )
    print(f"{'Created' if args.apply else 'Would create'} {missing}; preserved {existing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
