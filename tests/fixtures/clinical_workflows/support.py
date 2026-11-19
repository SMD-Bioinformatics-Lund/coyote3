# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Replay synthetic manifests through real ingest and report evaluation in memory.

Requires the repository development dependencies, including mongomock. No URI,
credentials, environment file or live database is read. Mongo transactions and
audit delivery are outside this in-memory fixture replay.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import mongomock
from coyote.application.common.release_resources import (
    capture_assay_resource,
    capture_gene_lists,
)
from coyote.application.ingest.service import InternalIngestService
from coyote.application.reporting.clinical_rules.evaluator import (
    ClinicalRuleEvaluator,
)
from coyote.application.reporting.clinical_rules.preparation import (
    prepare_report_context,
)
from coyote.config.constants import ALL_SAMPLE_FILE_KEYS
from coyote.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from coyote.contracts.schemas.registry import (
    INGEST_DEPENDENT_COLLECTIONS,
    normalize_collection_document,
)
from coyote.domain.annotation_identity import primary_small_variant_identity
from coyote.domain.annotation_scope import annotation_namespace
from coyote_api.bootstrap.paths import BOOTSTRAP_ROOT
from coyote_api.infra.seed.bundle import load_reference_seed_pack
from coyote_api.infra.seed.query_rules import prepare_query_rule_seeds
from coyote_atlas.bundle import ReferenceBundle
from coyote_demo.resources import WORKFLOW_BUNDLE
from coyote_mongo.config.settings import AuditContext
from coyote_mongo.repositories.ingest_gateway import IngestCollectionGateway
from mongo_test_support.writes import fake_write

ROOT = WORKFLOW_BUNDLE
FIXTURES = Path(__file__).resolve().parent


class MemoryGateway(IngestCollectionGateway):
    """Use real ingest collection operations without a Mongo server or transactions."""

    def run_transaction(self, operation):
        """Execute once in memory; this does not test transactional rollback."""
        return operation(None)


class MemoryVault:
    """Model insert-once transcript storage in the in-memory test database."""

    def __init__(self, collection):
        """Bind the isolated annotation collection."""
        self.collection = collection

    def upsert_many(self, documents, *, session=None):
        """Preserve the first transcript document for each variant/version pair."""
        for doc in documents:
            key = {field: doc[field] for field in ("simple_id_hash", "vep_version")}
            self.collection.update_one(key, {"$setOnInsert": doc}, upsert=True)


@patch("coyote_mongo.repositories.ingest_gateway.write_with_audit", new=fake_write)
@patch("coyote_mongo.persistence.write_with_audit", new=fake_write)
def replay():
    """Validate setup records and ingest every positive manifest into isolated memory.

    Returns:
        A mongomock database holding setup and parser-produced sample documents.

    Raises:
        ValueError: A setup record or raw ingest resource violates its contract.
    """
    db = mongomock.MongoClient().synthetic_demo
    # Use the same bundled HGNC reference as deployment, without inventing MANE flags.
    genes = ReferenceBundle.packaged().load_documents()["hgnc_genes"]
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
        collection_gateway=MemoryGateway(
            collections={name: db[name] for name in names},
            context=AuditContext(environment="test", route="synthetic-demo-test"),
        ),
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
