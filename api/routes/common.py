"""Common read routes used by Flask presentation endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import Depends, Query

from api.app import ApiUser, _api_error, app, flask_app, require_access
from coyote.extensions import store, util
from coyote.services.interpretation.report_summary import enrich_reported_variant_docs


@app.get("/api/v1/common/gene/{gene_id}/info")
def common_gene_info_read(gene_id: str):
    if gene_id.isnumeric():
        gene = store.hgnc_handler.get_metadata_by_hgnc_id(hgnc_id=gene_id)
    else:
        gene = store.hgnc_handler.get_metadata_by_symbol(symbol=gene_id)
    return util.common.convert_to_serializable({"gene": gene})


@app.get("/api/v1/common/reported_variants/variant/{variant_id}/{tier}")
def common_tiered_variant_context_read(
    variant_id: str,
    tier: int,
    user: ApiUser = Depends(require_access(permission="view_gene_annotations", min_role="user", min_level=9)),
):
    _ = user
    variant = store.variant_handler.get_variant(variant_id)
    if not variant:
        raise _api_error(404, "Variant not found")

    csq = variant.get("INFO", {}).get("selected_CSQ", {}) or {}
    gene = csq.get("SYMBOL")
    simple_id = variant.get("simple_id")
    simple_id_hash = variant.get("simple_id_hash")
    hgvsc = csq.get("HGVSc")
    hgvsp = csq.get("HGVSp")

    or_conditions: list[dict[str, Any]] = []
    if simple_id or simple_id_hash:
        if simple_id_hash:
            or_conditions.append({"simple_id_hash": simple_id_hash})
        elif simple_id:
            or_conditions.append({"simple_id": simple_id})
    else:
        if hgvsc:
            or_conditions.append({"hgvsc": hgvsc})
        elif hgvsp:
            or_conditions.append({"hgvsp": hgvsp})

    if not gene or not or_conditions:
        return util.common.convert_to_serializable(
            {
                "variant": variant,
                "docs": [],
                "tier": tier,
                "error": "Variant has insufficient identity fields",
            }
        )

    query = {"gene": gene, "$or": or_conditions}
    docs = store.reported_variants_handler.list_reported_variants(query)
    docs = enrich_reported_variant_docs(deepcopy(docs))
    return util.common.convert_to_serializable({"variant": variant, "docs": docs, "tier": tier, "error": None})


@app.get("/api/v1/common/search/tiered_variants")
def common_tiered_variant_search_read(
    search_str: str | None = None,
    search_mode: str = "gene",
    include_annotation_text: bool = False,
    assays: list[str] | None = Query(default=None),
    limit_entries: int | None = None,
    user: ApiUser = Depends(require_access(permission="view_gene_annotations", min_role="user", min_level=9)),
):
    _ = user
    if limit_entries is None:
        limit_entries = flask_app.config.get("TIERED_VARIANT_SEARCH_LIMIT", 1000)

    assay_choices = store.asp_handler.get_all_asp_groups()
    docs_found = store.annotation_handler.find_variants_by_search_string(
        search_str=search_str,
        search_mode=search_mode,
        include_annotation_text=include_annotation_text,
        assays=assays,
        limit=limit_entries,
    )

    tier_stats = {"total": {}, "by_assay": {}}
    if search_mode != "variant" and search_str:
        tier_stats = store.annotation_handler.get_tier_stats_by_search(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            assays=assays,
        )

    sample_tagged_docs = []
    associated_annotation_text_oids: set[str] = set()

    for doc in docs_found:
        merged_doc = deepcopy(doc)
        sample_oids: dict[str, dict[str, Any]] = {}
        reported_docs = store.reported_variants_handler.list_reported_variants({"annotation_oid": doc["_id"]})

        for reported_doc in reported_docs:
            sample_oid = reported_doc.get("sample_oid")
            report_oid = reported_doc.get("report_oid")
            annotation_text_oid = reported_doc.get("annotation_text_oid")
            report_id = reported_doc.get("report_id")
            sample_doc = store.sample_handler.get_sample_by_oid(sample_oid)
            sample_name = reported_doc.get("sample_name") or sample_doc.get("name") if sample_doc else None
            report_num = next(
                (
                    rpt.get("report_num")
                    for rpt in ((sample_doc.get("reports") if sample_doc else None) or [])
                    if rpt.get("_id") == report_oid
                ),
                None,
            )

            if sample_oid:
                if sample_oid not in sample_oids:
                    sample_oids[sample_oid] = {
                        "sample_name": sample_name if sample_name else "UNKNOWN_SAMPLE",
                        "report_oids": {},
                    }
                if report_oid and report_id:
                    report_oids = sample_oids.get(sample_oid, {}).get("report_oids", {})
                    if report_oid not in report_oids:
                        sample_oids[sample_oid]["report_oids"][report_id] = report_num

            if include_annotation_text and annotation_text_oid:
                associated_annotation_text_oids.add(annotation_text_oid)
                merged_doc["text"] = store.annotation_handler.get_annotation_text_by_oid(annotation_text_oid)

        merged_doc["reported_docs"] = reported_docs
        merged_doc["samples"] = sample_oids

        if merged_doc.get("_id") not in associated_annotation_text_oids:
            sample_tagged_docs.append(merged_doc)

    return util.common.convert_to_serializable(
        {
            "docs": sample_tagged_docs,
            "search_str": search_str,
            "search_mode": search_mode,
            "include_annotation_text": include_annotation_text,
            "tier_stats": tier_stats,
            "assays": assays,
            "assay_choices": assay_choices,
        }
    )
