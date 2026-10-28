"""Shared interpretation helpers for annotations and reported findings."""

from __future__ import annotations

from typing import Any

from coyote3.application.common.execution_context import current_username
from coyote3.config.knowledgebase_sources import oncokb_gene_url
from coyote3.domain.annotation_identity import (
    annotation_context_fields,
    annotation_identity_fields,
)
from coyote3.domain.common.reporting import utc_now


def create_annotation_text_from_gene(gene: str, csq: list, tumor_type: str, **kwargs) -> str:
    """Build Swedish Tier III text using terminology from the published reporting rules.

    Args:
        gene: Selected transcript's gene symbol.
        csq: Nonempty consequence list; the first value supplies the sentence description.
        tumor_type: Approved tumor-type wording from the sample's reporting-rule release.
        **kwargs: ``gene_oncokb`` selects the existing knowledgebase suffix.

    Returns:
        Established annotation text with the governed terminology inserted.
    """
    consequence = str(csq[0]).replace("_", " ")

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
            "asp_group": data.get("asp_group"),
            "asp_id": data.get("asp_id"),
            "diagnosis_id": data.get("diagnosis_id"),
            "namespace": data.get("namespace"),
            **identity,
        }
    return {
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
            "diagnosis_id": sample.get("diagnosis_id"),
        }
        annotation = annotation_map.get(str(doc.get("annotation_oid"))) or {}
        enriched_doc["annotation"] = {**annotation}
        enriched_docs.append(enriched_doc)
    return enriched_docs


def create_classified_variant_doc(
    variant: str,
    nomenclature: str,
    class_num: int,
    variant_data: dict,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build a classification or annotation dictionary without inserting it.

    Args:
        variant: Primary display identity for the finding.
        nomenclature: Identity category, normally p, c, g, cn, f, or t; passed
            to the canonical context and identity helpers without validation here.
        class_num: Classification stored as class only when text is not supplied.
        variant_data: Server-resolved asp_group, asp_id, diagnosis_id and namespace,
            plus nomenclature-specific gene, transcript and alternate identities.
        **kwargs: Only text is used. Its presence, even with None or an empty
            value, stores text instead of class; other keywords are ignored.

    Returns:
        A new dictionary with current request author (falling back to "api"),
        timezone-aware UTC creation time, and canonical context/identity fields.
        The input is not mutated and no database write is performed.
    """
    document = {
        "author": current_username(),
        "time_created": utc_now(),
        "variant": variant,
        "nomenclature": nomenclature,
        "asp_group": variant_data.get("asp_group"),
        "asp_id": variant_data.get("asp_id"),
        "diagnosis_id": variant_data.get("diagnosis_id"),
        "namespace": variant_data.get("namespace"),
    }
    for key in ("source_sample_id", "source_finding_id"):
        if variant_data.get(key):
            document[key] = variant_data[key]

    if "text" in kwargs:
        document["text"] = kwargs["text"]
    else:
        document["class"] = class_num

    document.update(annotation_context_fields(nomenclature=nomenclature, source=variant_data))

    document.update(
        annotation_identity_fields(
            variant=variant,
            nomenclature=nomenclature,
            source=variant_data,
        )
    )

    return document
