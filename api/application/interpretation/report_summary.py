"""Shared interpretation helpers for annotations and reported findings."""

from __future__ import annotations

from collections import defaultdict

from api.config.application_metadata import oncokb_gene_url
from api.config.clinical_vocabulary import CLINICAL_VOCABULARY
from api.domain.common.reporting import utc_now
from api.domain.core.annotation_identity import (
    annotation_context_fields,
    annotation_identity_fields,
)
from api.infra.mongo.persistence import new_object_id
from api.infra.request_context import current_username


def process_gene_annotations(annotations: dict) -> dict:
    """Group annotation documents by assay/subpanel and variant."""
    annotations_dict = defaultdict(lambda: defaultdict(dict))
    for anno in annotations:
        assub = f"{anno['assay']}:{anno['subpanel']}"
        if "class" in anno:
            annotations_dict[assub][anno["variant"]]["latest_class"] = anno
        if "text" in anno:
            annotations_dict[assub][anno["variant"]]["latest_text"] = anno
    return annotations_dict


def create_annotation_text_from_gene(gene: str, csq: list, assay_group: str, **kwargs) -> str:
    """Build the established automatic Tier III small-variant annotation."""
    consequence = str(csq[0]).replace("_", " ")
    tumor_type = CLINICAL_VOCABULARY.annotation_tumor_types.get(assay_group, "")

    text = (
        f"Analysen påvisar en {consequence}. Mutationen är klassad som Tier III då "
        f"mutationer i {gene} är sällsynta men förekommer i {tumor_type} maligniteter."
    )
    if kwargs.get("gene_oncokb"):
        return f"{text} För ytterligare information om {gene} se {oncokb_gene_url(gene)}."
    return f"{text} {gene} finns ej beskriven i https://www.oncokb.org."


def create_comment_doc(
    data: dict, nomenclature: str = "", variant: str = "", key: str = "text"
) -> dict:
    """Build a comment document for variant or global annotations."""
    author = current_username()
    identity = {
        key: value
        for key, value in {
            "variant": variant,
            "nomenclature": nomenclature,
        }.items()
        if value not in (None, "")
    }
    identity.update(annotation_context_fields(nomenclature=nomenclature, source=data))
    identity.update(
        annotation_identity_fields(
            variant=variant,
            nomenclature=nomenclature,
            source=data,
        )
    )
    if data.get("global", None) == "global":
        return {
            "text": data.get(key),
            "author": author,
            "time_created": utc_now(),
            "assay": data.get("assay_group", None),
            "subpanel": data.get("subpanel", None),
            **identity,
        }
    return {
        "_id": new_object_id(),
        "hidden": 0,
        "text": data.get(key),
        "author": author,
        "time_created": utc_now(),
        **identity,
    }


def get_tier_classification(data: dict) -> int:
    """Return the selected tier classification, or zero when none is selected."""
    tiers = {"tier1": 1, "tier2": 2, "tier3": 3, "tier4": 4}
    class_num = 0
    for key, value in tiers.items():
        if data.get(key, None) is not None:
            class_num = value
    return class_num


def enrich_reported_variant_docs(
    tier_docs: list, *, sample_repository, annotation_repository
) -> list:
    """Attach sample and annotation context to reported-variant documents."""
    if not tier_docs:
        return []

    sample_ids: list[object] = []
    annotation_ids: list[object] = []
    for doc in tier_docs:
        sample_oid = doc.get("sample_oid")
        if sample_oid is not None:
            sample_ids.append(sample_oid)
        annotation_oid = doc.get("annotation_oid")
        if annotation_oid is not None:
            annotation_ids.append(annotation_oid)

    sample_map: dict[str, dict] = {}
    if sample_ids:
        for sample in sample_repository.get_samples_by_oids(list(set(sample_ids))) or []:
            if isinstance(sample, dict):
                sample_map[str(sample.get("_id"))] = sample

    annotation_map: dict[str, dict] = {}
    if annotation_ids:
        annotations = annotation_repository.get_annotations_by_oids(list(set(annotation_ids))) or []
        for annotation in annotations:
            if isinstance(annotation, dict):
                annotation_map[str(annotation.get("_id"))] = annotation

    enriched_docs = []
    for doc in tier_docs:
        enriched_doc = doc.copy()
        sample = sample_map.get(str(doc.get("sample_oid")), {})
        enriched_doc["sample"] = {
            "sample_name": sample.get("name"),
            "case_id": sample.get("case_id"),
            "control_id": sample.get("control_id"),
            "environment": sample.get("environment"),
            "paired": sample.get("paired"),
            "asp_id": sample.get("asp_id"),
            "subpanel_id": sample.get("subpanel_id"),
        }
        annotation = annotation_map.get(str(doc.get("annotation_oid"))) or {}
        enriched_doc["annotation"] = {**annotation}
        enriched_docs.append(enriched_doc)
    return enriched_docs
