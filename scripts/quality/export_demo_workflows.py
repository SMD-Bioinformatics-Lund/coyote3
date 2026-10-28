"""Replay synthetic manifests through ingest and export portable collection examples.

Requires the repository development dependencies, including mongomock. No URI,
credentials, environment file or live database is read. Mongo transactions and
audit delivery are outside this in-memory reference export.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import mongomock
from bson import ObjectId
from bson.json_util import dumps, loads

from api.bootstrap.paths import BOOTSTRAP_ROOT  # noqa: E402
from coyote3.domain.annotation_identity import primary_small_variant_identity
from coyote3.domain.annotation_scope import annotation_namespace

ROOT = Path(__file__).resolve().parents[2] / "demo_data/clinical_workflows"
FIXTURES = Path(__file__).resolve().parents[2] / "tests/fixtures/clinical_workflows"
sys.path.insert(0, str(ROOT.parents[1]))

from api.infra.mongo.repositories.ingest_gateway import IngestCollectionGateway  # noqa: E402
from api.infra.seed.bundle import load_reference_seed_pack  # noqa: E402
from api.infra.seed.query_rules import prepare_query_rule_seeds  # noqa: E402
from coyote3.application.common.release_resources import (  # noqa: E402
    capture_assay_resource,
    capture_gene_lists,
)
from coyote3.application.ingest.service import InternalIngestService  # noqa: E402
from coyote3.application.reporting.clinical_rules.evaluator import (  # noqa: E402
    ClinicalRuleEvaluator,
)
from coyote3.application.reporting.clinical_rules.preparation import (  # noqa: E402
    prepare_report_context,
)
from coyote3.config.constants import ALL_SAMPLE_FILE_KEYS  # noqa: E402
from coyote3.contracts.schemas.clinical_rules import ClinicalRuleSetDoc  # noqa: E402
from coyote3.contracts.schemas.registry import (  # noqa: E402
    INGEST_DEPENDENT_COLLECTIONS,
    normalize_collection_document,
)


class MemoryGateway(IngestCollectionGateway):
    """Use real ingest collection operations without a Mongo server or transactions."""

    def run_transaction(self, operation):
        """Execute once in memory; this does not test transactional rollback."""
        return operation(None)


class MemoryVault:
    """Model insert-once transcript storage in the in-memory export database."""

    def __init__(self, collection):
        """Bind the isolated annotation collection."""
        self.collection = collection

    def upsert_many(self, documents, *, session=None):
        """Preserve the first transcript document for each variant/version pair."""
        for doc in documents:
            key = {field: doc[field] for field in ("simple_id_hash", "vep_version")}
            self.collection.update_one(key, {"$setOnInsert": doc}, upsert=True)


def replay():
    """Validate setup records and ingest every positive manifest into isolated memory.

    Returns:
        A mongomock database holding setup and parser-produced sample documents.

    Raises:
        ValueError: A setup record or raw ingest resource violates its contract.
    """
    db = mongomock.MongoClient().synthetic_demo
    # Use the same bundled HGNC reference as deployment, without inventing MANE flags.
    reference = BOOTSTRAP_ROOT / "reference/hgnc_genes.seed.ndjson.gz"
    with gzip.open(reference, "rt") as source:
        genes = [json.loads(line) for line in source]
    db.hgnc_genes.insert_many(
        [row for row in genes if row.get("hgnc_symbol") in {"BCR", "ABL1", "TP53", "CEBPA"}]
    )
    catalog = load_reference_seed_pack(BOOTSTRAP_ROOT / "reference", include_knowledgebase=False)
    db.assay_groups.insert_many(
        [normalize_collection_document("assay_groups", row) for row in catalog["assay_groups"]]
    )
    db.query_rule_sets.insert_many(
        prepare_query_rule_seeds(
            catalog["query_rule_sets"], catalog["assay_groups"], actor="demo.installer"
        )
    )
    for path in sorted((ROOT / "setup").glob("*.json")):
        documents = [
            normalize_collection_document(path.stem, row) for row in json.loads(path.read_text())
        ]
        if documents:
            db[path.stem].insert_many(documents)
    for configuration in db.asp_configs.find():
        panel = db.assay_specific_panels.find_one({"asp_id": configuration["asp_id"]})
        db.asp_configs.update_one(
            {"_id": configuration["_id"]},
            {
                "$set": {
                    "assay_resource_release": capture_assay_resource(panel),
                    "gene_list_release": capture_gene_lists(
                        list(
                            db.insilico_genelists.find(
                                {
                                    "is_active": True,
                                    "$or": [
                                        {"asp_ids": configuration["asp_id"]},
                                        {"asp_groups": configuration["asp_group"]},
                                    ],
                                }
                            )
                        )
                    ),
                }
            },
        )
    names = set(INGEST_DEPENDENT_COLLECTIONS.values()) | {
        "samples",
        "anno_vep",
        "hgnc_genes",
        "asp_configs",
        "assay_specific_panels",
        "diagnoses",
        "diagnosis_associations",
        "assay_groups",
        "insilico_genelists",
    }
    service = InternalIngestService(
        collection_gateway=MemoryGateway(collections={name: db[name] for name in names}),
        anno_vep_repository=MemoryVault(db.anno_vep),
        invalidate_dashboard_metrics=lambda: None,
    )
    for path in sorted((ROOT / "manifests").glob("*.yaml")):
        payload = service.parse_yaml_payload(path.read_text())
        for key in ALL_SAMPLE_FILE_KEYS:
            if payload.get(key):
                payload[key] = str((path.parent / payload[key]).resolve())
        service.ingest_sample_bundle(payload, ingested_by="demo.ingester", ingest_source="api")
    return db


def portable_documents(db):
    """Replace runtime IDs, timestamps and absolute fixture paths consistently.

    Args:
        db: Isolated replay database.

    Returns:
        Collection arrays with stable example IDs and a fixed demonstration time.
        Shapes and parsed evidence remain those produced by application ingestion.
        HGNC reference input is excluded; it remains in the bootstrap seed.
    """
    raw = {
        name: list(db[name].find())
        for name in sorted(db.list_collection_names())
        if name != "hgnc_genes"
    }
    identities = {
        str(row["_id"]): hashlib.sha256(f"{name}/{index}".encode()).hexdigest()[:24]
        for name, rows in raw.items()
        for index, row in enumerate(rows)
    }

    def normalize(value):
        """Normalize export-only volatile values without changing evidence."""
        if isinstance(value, ObjectId):
            return identities[str(value)]
        if isinstance(value, datetime):
            return {"$date": "2026-01-01T00:00:00Z"}
        if isinstance(value, dict):
            normalized = {key: normalize(item) for key, item in value.items()}
            if set(normalized) == {"content", "content_hash"}:
                # Exported resource content has portable IDs and dates. Its digest
                # must describe that content, not the volatile in-memory original.
                content = loads(json.dumps(normalized["content"]))
                release = (
                    capture_assay_resource(content)
                    if "asp_id" in content
                    else capture_gene_lists(list(content.values()))
                )
                normalized["content_hash"] = release["content_hash"]
            return normalized
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, str):
            return identities.get(value, value.replace(str(ROOT) + "/", ""))
        return value

    return normalize(raw)


def review_examples(db):
    """Build contract-validated illustrative review records from ingested identities.

    Args:
        db: Isolated replay database, extended with synthetic annotations/comments.

    Returns:
        Report-engine evaluations after assigning four example SNV tiers. These
        are previews, not persisted reports or evidence of user/API review.
    """
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    scenario = {
        row["id"]: row for row in json.loads((FIXTURES / "scenarios/variants.json").read_text())
    }
    previews = {}
    for name in (
        "DEMO_MYELOID",
        "DEMO_MYELOID_MISSING",
        "DEMO_FUSION",
        "DEMO_WTS",
        "DEMO_GROUP_DNA",
        "DEMO_GROUP_RNA",
    ):
        sample = db.samples.find_one({"name": name})
        sid = str(sample["_id"])
        asp = db.assay_specific_panels.find_one({"asp_id": sample["asp_id"]})
        aspc = db.asp_configs.find_one({"_id": sample["current_aspc_id"]})
        snvs = []
        if sample["asp_category"] == "dna":
            for tier, label in enumerate(
                ["baseline_pass", "tier2_candidate", "tier3_candidate", "tier4_candidate"], 1
            ):
                variant = db.variants.find_one(
                    {"SAMPLE_ID": sid, "simple_id": scenario[label]["simple_id"]}
                )
                csq = variant["INFO"]["selected_CSQ"]
                identity = dict(
                    variant=variant["simple_id"],
                    genomic=variant["simple_id"],
                    genomic_hash=variant["simple_id_hash"],
                    gene=csq["SYMBOL"],
                    transcript=variant["selected_csq_feature"],
                    hgvsp=csq.get("HGVSp"),
                    hgvsc=csq.get("HGVSc"),
                )
                nomenclature, identity["variant"] = primary_small_variant_identity(identity)
                annotation = dict(
                    identity,
                    asp_group=asp["asp_group"],
                    asp_id=sample["asp_id"],
                    diagnosis_id=sample["diagnosis_id"],
                    namespace=annotation_namespace(sample["environment"]),
                    author="demo.reviewer",
                    nomenclature=nomenclature,
                    time_created=now,
                )
                if not db.annotation.find_one(
                    {
                        "asp_group": asp["asp_group"],
                        "asp_id": sample["asp_id"],
                        "diagnosis_id": sample["diagnosis_id"],
                        "namespace": annotation["namespace"],
                        "nomenclature": nomenclature,
                        "variant": identity["variant"],
                        "gene": identity["gene"],
                    }
                ):
                    db.annotation.insert_one(
                        normalize_collection_document("annotation", {**annotation, "class": tier})
                    )
                db.finding_comments.insert_one(
                    normalize_collection_document(
                        "finding_comments",
                        dict(
                            identity,
                            sample_oid=sid,
                            sample_name=name,
                            finding_oid=str(variant["_id"]),
                            finding_type="small_variant",
                            nomenclature=nomenclature,
                            author="demo.reviewer",
                            text=f"Synthetic tier {tier} review exercise; not a clinical assessment.",
                            time_created=now,
                        ),
                    )
                )
                variant["classification"] = {"class": tier}
                snvs.append(variant)
        for hidden in (False, True):
            db.sample_comments.insert_one(
                normalize_collection_document(
                    "sample_comments",
                    dict(
                        sample_oid=sid,
                        sample_name=name,
                        author="demo.reviewer",
                        text="Synthetic sample comment" + (" - hidden example" if hidden else ""),
                        hidden=hidden,
                        hidden_by="demo.reviewer" if hidden else None,
                        time_created=now,
                        time_hidden=now if hidden else None,
                    ),
                )
            )
        rule = ClinicalRuleSetDoc.model_validate(
            db.clinical_rule_sets.find_one({"scope.asp_id": sample["asp_id"]})
        )
        context = prepare_report_context(
            sample=sample,
            asp=asp,
            aspc=aspc,
            analyte=sample["asp_category"],
            applied_gene_lists=[],
            report_sections_data={
                "snvs": snvs,
                "cnvs": list(db.cnvs.find({"SAMPLE_ID": sid}))[:2],
                "fusions": list(db.fusions.find({"SAMPLE_ID": sid})),
                "translocs": list(db.translocations.find({"SAMPLE_ID": sid})),
                "biomarkers": list(db.biomarkers.find({"SAMPLE_ID": sid})),
            },
        )
        result = ClinicalRuleEvaluator().evaluate(
            context, rule, reporting_analyses=set(aspc["reporting"]["report_sections"])
        )
        previews[name] = {"sections": result.sections}
    return previews


def main():
    """Write snapshots, or compare committed examples without modifying them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail on snapshot drift")
    args = parser.parse_args()
    db = replay()
    ingest = portable_documents(db)
    previews = review_examples(db)
    reviewed = portable_documents(db)
    artifacts = {
        **{f"after_ingest/{name}": rows for name, rows in ingest.items()},
        **{
            f"after_review/{name}": reviewed[name]
            for name in ("annotation", "finding_comments", "sample_comments")
        },
        "report_previews": previews,
    }
    output = FIXTURES / "expected"
    if not args.check:
        output.mkdir(parents=True, exist_ok=True)
    for name, rows in artifacts.items():
        text = json.dumps(json.loads(dumps(rows)), indent=2, ensure_ascii=False) + "\n"
        path = output / f"{name}.json"
        if args.check:
            if not path.exists() or path.read_text() != text:
                raise SystemExit(f"Snapshot differs: {path.relative_to(FIXTURES)}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    if args.check and {
        str(p.relative_to(output).with_suffix("")) for p in output.rglob("*.json")
    } != set(artifacts):
        raise SystemExit("Unexpected or missing collection snapshot")
    print(f"Verified {len(ingest)} collections and illustrative review/report artifacts")


if __name__ == "__main__":
    main()
