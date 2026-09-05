#!/usr/bin/env python3
"""Convert legacy YAML report rules and ASPC text into canonical MongoDB rule sets."""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from bson import ObjectId
from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.application.reporting.clinical_rules.validation import (  # noqa: E402
    content_hash,
    validate_rule_set,
)
from api.contracts.schemas.assay import AspcReportingDoc  # noqa: E402
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc  # noqa: E402
from api.domain.common.reporting import STANDARD_TIER_SUMMARY_PHRASES  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import (  # noqa: E402
    build_revision_snapshot,
)

FAMILY_ORDER = {"finding_text": 100, "result_text": 500, "summary_text": 900}

DNA_TERMINOLOGY = {
    "paired_text": (
        "Analysen avser somatiska mutationer (hudbiopsi har använts som kontrollmaterial). "
    ),
    "list_singular": "Analysen omfattar genlistan: ",
    "list_plural": "Analysen omfattar genlistorna: ",
    "conjunction": "samt",
    "gene_singular": " som innefattar genen: ",
    "gene_plural": " som innefattar generna: ",
    "gene_conjunction": "samt",
    "gene_count_prefix": " som innefattar ",
    "gene_count_suffix": " gener",
    "gene_list_limit": 20,
    "list_suffix": ". ",
    "germline_prefix": "För ",
    "germline_conjunction": "samt",
    "germline_suffix": " undersöks även konstitutionella mutationer.",
}

FUSION_TERMINOLOGY = {
    "tier_labels": {
        "1": "stark klinisk signifikans (Tier I)",
        "2": "potentiell klinisk signifikans (Tier II)",
        "3": "oklar klinisk signifikans (Tier III)",
    },
    "first_lead": "Vid analysen finner man",
    "next_lead": "Vidare finner man",
    "tier_prefix": " en fusion av ",
    "genes_prefix": " mellan generna ",
    "gene_joiner": " och ",
    "sentence_suffix": ".",
    "breakpoint_prefix": " De genomiska positionerna för brottspunkterna är ",
    "breakpoint_joiner": " och ",
    "breakpoint_suffix": ".",
    "support_prefix": ("Rearrangemanget är påvisat efter manuell eftergranskning av data där "),
    "support_middle": (" läspar, och  läsningar direkt över brottspunkten ger stöd för en "),
    "support_genes_prefix": "",
    "support_gene_joiner": "::",
    "support_suffix": "-genfusion.",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", required=True, help="Application database containing ASPCs")
    parser.add_argument("--actor", required=True, help="Migration audit identity")
    parser.add_argument(
        "--clinical-reviewer",
        required=True,
        help="Independent clinical reviewer recorded for imported approved content",
    )
    parser.add_argument("--language", default="sv")
    parser.add_argument("--rules-dir", default=str(ROOT_DIR / "clinical_reporting_rules"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _condition(conditions: list[dict[str, Any]]) -> dict[str, Any] | None:
    predicates = [
        {
            "type": "predicate",
            "fact": item["fact"],
            "operator": item.get("operator", "eq"),
            "value": item.get("value"),
        }
        for item in conditions
    ]
    if not predicates:
        return None
    if len(predicates) == 1:
        return predicates[0]
    return {"type": "all", "children": predicates}


def _output(template: str) -> list[dict[str, Any]]:
    dna_token = "{{ aspc.reporting.general_report_summary | dna_report_intro(sample, asp, applied_gene_lists) }}"
    tier_token = "{{ aggregates.tier_summaries | tier_summary }}"
    fusion_token = "{{ findings | fusion_summary }}"
    if template == dna_token:
        return [{"type": "renderer", "name": "dna_report_intro"}]
    if template == tier_token:
        return [{"type": "renderer", "name": "tier_summary"}]
    if fusion_token in template:
        prefix, suffix = template.split(fusion_token, 1)
        return [
            {"type": "text", "value": prefix},
            {"type": "renderer", "name": "fusion_summary"},
            {"type": "text", "value": suffix},
        ]
    gene_token = "{{ finding.gene }}"
    if gene_token in template:
        prefix, suffix = template.split(gene_token, 1)
        return [
            {"type": "text", "value": prefix},
            {"type": "fact", "path": "finding.gene", "formatter": "gene_symbol"},
            {"type": "text", "value": suffix},
        ]
    if "{{" in template or "{%" in template:
        raise ValueError(f"Unsupported legacy template expression: {template}")
    return [{"type": "text", "value": template}]


def _summary_for_scope(
    source: dict[str, Any], aspcs: list[dict[str, Any]], exact_sources: set[tuple[str, str]]
) -> str:
    metadata = source["rule_set"]
    asp_id = metadata["asp_id"]
    subpanel_id = metadata.get("subpanel_id", "base")
    matching = []
    for aspc in aspcs:
        if aspc.get("asp_id") != asp_id:
            continue
        configured_subpanel = str(aspc.get("subpanel_id") or "base")
        selected_subpanel = (
            configured_subpanel if (asp_id, configured_subpanel) in exact_sources else "base"
        )
        if selected_subpanel == subpanel_id:
            matching.append(aspc)
    summaries = {
        str((aspc.get("reporting") or {}).get("general_report_summary") or "") for aspc in matching
    }
    if len(summaries) > 1:
        production_summaries = {
            str((aspc.get("reporting") or {}).get("general_report_summary") or "")
            for aspc in matching
            if aspc.get("is_active") is not False
            and str(aspc.get("environment") or "").lower() == "production"
        }
        if len(production_summaries) != 1:
            raise ValueError(
                f"ASPCs bound to {asp_id}/{subpanel_id} contain different general report "
                "summaries and no unique active production value is available"
            )
        selected = next(iter(production_summaries))
        affected = ", ".join(sorted(str(aspc.get("aspc_id") or aspc["_id"]) for aspc in matching))
        print(
            f"[warning] {asp_id}/{subpanel_id} has environment-specific introductory text; "
            f"using the active production value for: {affected}"
        )
        return selected
    return next(iter(summaries), "")


def _convert_source(
    source: dict[str, Any],
    *,
    base_text: str,
    language: str,
    actor: str,
    clinical_reviewer: str | None = None,
    now: datetime,
) -> ClinicalRuleSetDoc:
    metadata = source["rule_set"]
    grouped: dict[tuple[str, str, str | None, bool], list[dict[str, Any]]] = defaultdict(list)
    for rule in source.get("document_rules") or []:
        grouped[(rule["family"], rule["section"], None, bool(rule.get("heading", True)))].append(
            rule
        )
    for analysis, declaration in (source.get("analyses") or {}).items():
        for rule in declaration.get("rules") or []:
            grouped[
                (rule["family"], rule["section"], analysis, bool(rule.get("heading", True)))
            ].append(rule)

    blocks = []
    for block_index, ((family, section, analysis, heading), rules) in enumerate(
        sorted(
            grouped.items(),
            key=lambda item: (FAMILY_ORDER[item[0][0]], min(r["priority"] for r in item[1])),
        )
    ):
        mode = "each_finding" if family == "finding_text" else "once"
        strategy = "first_match" if mode == "each_finding" or len(rules) == 1 else "exactly_one"
        block_id = f"{metadata['asp_id']}_{metadata.get('subpanel_id', 'base')}_{block_index + 1}"
        blocks.append(
            {
                "block_id": block_id,
                "name": section,
                "analysis": analysis,
                "evaluation": {"mode": mode},
                "section": section,
                "section_order": FAMILY_ORDER[family] + min(r["priority"] for r in rules),
                "block_order": block_index,
                "show_heading": heading,
                "match_strategy": strategy,
                "rules": [
                    {
                        "rule_id": rule["rule_id"],
                        "name": rule["rule_id"].replace("_", " ").strip().title(),
                        "order": int(rule["priority"]),
                        "condition": _condition(rule.get("when") or []),
                        "output": _output(rule["template"]),
                    }
                    for rule in rules
                ],
            }
        )

    rule_set_id = f"{metadata['asp_id']}__{metadata.get('subpanel_id', 'base')}__{language.lower()}"
    terminology = {
        "tier_summary": STANDARD_TIER_SUMMARY_PHRASES,
        "dna_report_intro": {**DNA_TERMINOLOGY, "base_text": base_text},
        "fusion_summary": FUSION_TERMINOLOGY,
    }
    document = ClinicalRuleSetDoc.model_validate(
        {
            "_id": ObjectId(),
            "rule_set_id": rule_set_id,
            "schema_version": 1,
            "content_version": int(metadata.get("version") or 1),
            "revision": 1,
            "scope": {
                "asp_id": metadata["asp_id"],
                "subpanel_id": metadata.get("subpanel_id", "base"),
                "analyte": metadata["analyte"],
                "language": language,
            },
            "name": metadata["name"],
            "status": "published",
            "active": True,
            "minimum_engine_version": 1,
            "analysis_declarations": {
                analysis: {"narrative": "enabled" if block.get("enabled") else "none"}
                for analysis, block in (source.get("analyses") or {}).items()
            },
            "terminology": terminology,
            "blocks": blocks,
            "change_summary": "Initial canonical migration",
            "review": {
                "submitted_by": actor,
                "submitted_at": now,
                "clinical_reviewer": clinical_reviewer or actor,
                "clinical_decision_at": now,
                "clinical_decision_reason": "Approved legacy content migration",
            },
            "lifecycle": [
                {
                    "action": "published_by_migration",
                    "actor": actor,
                    "occurred_at": now,
                    "reason": "Canonical clinical rule cutover",
                }
            ],
            "created_at": now,
            "created_by": actor,
            "updated_at": now,
            "updated_by": actor,
            "published_at": now,
            "published_by": actor,
            "effective_from": now,
        }
    )
    document.content_hash = content_hash(document)
    validation = validate_rule_set(document)
    if not validation.valid:
        raise ValueError(f"{rule_set_id}: {'; '.join(validation.errors)}")
    return document


def main() -> int:
    args = parse_args()
    if args.actor.strip().lower() == args.clinical_reviewer.strip().lower():
        raise SystemExit("--clinical-reviewer must be different from --actor")
    rules_dir = Path(args.rules_dir).expanduser().resolve()
    paths = sorted(rules_dir.glob("*/*.yaml"))
    if not paths:
        raise SystemExit(f"No legacy clinical rule files found below {rules_dir}")
    all_sources = [yaml.safe_load(path.read_text(encoding="utf-8")) for path in paths]
    exact_sources = {
        (source["rule_set"]["asp_id"], source["rule_set"].get("subpanel_id", "base"))
        for source in all_sources
    }
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    inserted_ids: list[ObjectId] = []
    previous_reporting: dict[Any, dict[str, Any]] = {}
    try:
        client.admin.command("ping")
        db = client[args.db]
        installed_assays = {
            str(document.get("asp_id") or "")
            for document in db.assay_specific_panels.find({}, {"asp_id": 1})
            if str(document.get("asp_id") or "")
        }
        sources = [
            source for source in all_sources if source["rule_set"]["asp_id"] in installed_assays
        ]
        skipped = sorted(
            source["rule_set"]["asp_id"]
            for source in all_sources
            if source["rule_set"]["asp_id"] not in installed_assays
        )
        if skipped:
            print(
                f"[skip] rule sources for assays not installed in {args.db}: {', '.join(skipped)}"
            )
        source_assays = {source["rule_set"]["asp_id"] for source in sources}
        missing_sources = sorted(installed_assays - source_assays)
        if missing_sources:
            raise ValueError(
                "Installed assays without a clinical rule source: " + ", ".join(missing_sources)
            )
        aspcs = list(db.asp_configs.find({}))
        now = datetime.now(timezone.utc)
        documents = [
            _convert_source(
                source,
                base_text=_summary_for_scope(source, aspcs, exact_sources),
                language=args.language,
                actor=args.actor,
                clinical_reviewer=args.clinical_reviewer,
                now=now,
            )
            for source in sources
        ]
        bindings: list[tuple[Any, str]] = []
        for aspc in aspcs:
            asp_id = str(aspc.get("asp_id") or "")
            subpanel_id = str(aspc.get("subpanel_id") or "base")
            selected = subpanel_id if (asp_id, subpanel_id) in exact_sources else "base"
            if (asp_id, selected) not in exact_sources:
                raise ValueError(
                    f"No clinical rule source exists for active ASPC '{aspc.get('aspc_id')}'"
                )
            bindings.append((aspc["_id"], f"{asp_id}__{selected}__{args.language.lower()}"))
            migrated = dict(aspc)
            migrated["reporting"] = dict(aspc.get("reporting") or {})
            migrated["reporting"]["clinical_rule_set_id"] = bindings[-1][1]
            migrated["reporting"].pop("general_report_summary", None)
            migrated["reporting"].pop("analysis", None)
            migrated["reporting"].pop("_id", None)
            AspcReportingDoc.model_validate(migrated["reporting"])
        print(f"[plan] {len(documents)} published rule sets; {len(bindings)} ASPC bindings")
        if args.dry_run:
            return 0
        if db.clinical_rule_sets.count_documents({}):
            raise ValueError("clinical_rule_sets is not empty; migration requires an empty target")
        for document in documents:
            payload = document.model_dump(mode="python", by_alias=True, exclude_none=True)
            db.clinical_rule_sets.insert_one(payload)
            inserted_ids.append(payload["_id"])
            db.clinical_rule_revisions.insert_one(
                build_revision_snapshot(
                    payload,
                    action="migration_published",
                    actor=args.actor,
                    occurred_at=now,
                    reason="Initial governed rule set imported from approved reporting sources",
                    previous_revision_hash=None,
                )
            )
        for aspc_id, rule_set_id in bindings:
            current = next(aspc for aspc in aspcs if aspc["_id"] == aspc_id)
            previous_reporting[aspc_id] = dict(current.get("reporting") or {})
            result = db.asp_configs.update_one(
                {"_id": aspc_id},
                {
                    "$set": {"reporting.clinical_rule_set_id": rule_set_id},
                    "$unset": {
                        "reporting.general_report_summary": "",
                        "reporting.analysis": "",
                        "reporting._id": "",
                    },
                },
            )
            if result.matched_count != 1:
                raise RuntimeError(f"Failed to bind ASPC {aspc_id}")
        for aspc in db.asp_configs.find({}):
            AspcReportingDoc.model_validate(aspc.get("reporting") or {})
    except Exception:
        for aspc_id, reporting in previous_reporting.items():
            db.asp_configs.update_one({"_id": aspc_id}, {"$set": {"reporting": reporting}})
        if inserted_ids:
            db.clinical_rule_revisions.delete_many(
                {"rule_set_oid": {"$in": [str(value) for value in inserted_ids]}}
            )
            db.clinical_rule_sets.delete_many({"_id": {"$in": inserted_ids}})
        raise
    finally:
        client.close()
    print("[ok] canonical clinical rule migration completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
