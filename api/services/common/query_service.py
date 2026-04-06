"""Shared common-query service used by router endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.core.dna.variant_identity import build_simple_id_hash_from_simple_id, normalize_simple_id
from api.http import api_error
from api.services.interpretation.report_summary import enrich_reported_variant_docs


class CommonQueryService:
    """Provide shared gene and tiered-variant query workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "CommonQueryService":
        """Build the service from the shared store."""
        return cls(
            hgnc_handler=store.hgnc_handler,
            variant_handler=store.variant_handler,
            reported_variant_handler=store.reported_variant_handler,
            assay_panel_handler=store.assay_panel_handler,
            annotation_handler=store.annotation_handler,
            sample_handler=store.sample_handler,
        )

    def __init__(
        self,
        *,
        hgnc_handler: Any,
        variant_handler: Any,
        reported_variant_handler: Any,
        assay_panel_handler: Any,
        annotation_handler: Any,
        sample_handler: Any,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.hgnc_handler = hgnc_handler
        self.variant_handler = variant_handler
        self.reported_variant_handler = reported_variant_handler
        self.assay_panel_handler = assay_panel_handler
        self.annotation_handler = annotation_handler
        self.sample_handler = sample_handler

    def gene_info_payload(self, gene_id: str) -> dict[str, Any]:
        """Return gene metadata by HGNC id or symbol."""
        if gene_id.isnumeric():
            gene = self.hgnc_handler.get_metadata_by_hgnc_id(hgnc_id=gene_id)
        else:
            gene = self.hgnc_handler.get_metadata_by_symbol(symbol=gene_id)
        return {"gene": gene}

    def tiered_variant_context_payload(self, *, variant_id: str, tier: int) -> dict[str, Any]:
        """Return reported-variant context for a tiered variant."""
        variant = self.variant_handler.get_variant(variant_id)
        if not variant:
            raise api_error(404, "Variant not found")

        csq = variant.get("INFO", {}).get("selected_CSQ", {}) or {}
        gene = csq.get("SYMBOL")
        simple_id = normalize_simple_id(variant.get("simple_id"))
        simple_id_hash = variant.get("simple_id_hash") or (
            build_simple_id_hash_from_simple_id(simple_id) if simple_id else None
        )
        hgvsc = csq.get("HGVSc")
        hgvsp = csq.get("HGVSp")

        or_conditions: list[dict[str, Any]] = []
        if simple_id and simple_id_hash:
            or_conditions.append(
                {"$and": [{"simple_id_hash": simple_id_hash}, {"simple_id": simple_id}]}
            )
        elif hgvsc:
            or_conditions.append({"hgvsc": hgvsc})
        elif hgvsp:
            or_conditions.append({"hgvsp": hgvsp})

        if not gene or not or_conditions:
            return {
                "variant": variant,
                "docs": [],
                "tier": tier,
                "error": "Variant has insufficient identity fields",
            }

        query = {"gene": gene, "$or": or_conditions}
        docs = list(self.reported_variant_handler.list_reported_variants(query) or [])
        docs = enrich_reported_variant_docs(
            deepcopy(docs),
            sample_handler=self.sample_handler,
            annotation_handler=self.annotation_handler,
        )
        return {"variant": variant, "docs": docs, "tier": tier, "error": None}

    def tiered_variant_search_payload(
        self,
        *,
        search_str: str | None,
        search_mode: str,
        include_annotation_text: bool,
        assays: list[str] | None,
        limit_entries: int,
    ) -> dict[str, Any]:
        """Search tiered variants and related annotations across reports."""
        assay_choices = list(self.assay_panel_handler.get_all_asp_groups() or [])
        docs_found = list(
            self.annotation_handler.find_variants_by_search_string(
                search_str=search_str,
                search_mode=search_mode,
                include_annotation_text=include_annotation_text,
                assays=assays,
                limit=limit_entries,
            )
            or []
        )

        tier_stats = {"total": {}, "by_assay": {}}
        if search_mode != "variant" and search_str:
            tier_stats = self.annotation_handler.get_tier_stats_by_search(
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
            reported_docs = list(
                self.reported_variant_handler.list_reported_variants({"annotation_oid": doc["_id"]})
                or []
            )

            for reported_doc in reported_docs:
                sample_oid = reported_doc.get("sample_oid")
                report_oid = reported_doc.get("report_oid")
                annotation_text_oid = reported_doc.get("annotation_text_oid")
                report_id = reported_doc.get("report_id")
                sample_doc = self.sample_handler.get_sample_by_oid(sample_oid)
                sample_name = (
                    reported_doc.get("sample_name") or sample_doc.get("name")
                    if sample_doc
                    else None
                )
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
                        if report_id not in report_oids:
                            sample_oids[sample_oid]["report_oids"][report_id] = report_num

                if include_annotation_text and annotation_text_oid:
                    associated_annotation_text_oids.add(annotation_text_oid)
                    merged_doc["text"] = self.annotation_handler.get_annotation_text_by_oid(
                        annotation_text_oid
                    )

            merged_doc["reported_docs"] = reported_docs
            merged_doc["samples"] = sample_oids

            if merged_doc.get("_id") not in associated_annotation_text_oids:
                sample_tagged_docs.append(merged_doc)

        return {
            "docs": sample_tagged_docs,
            "search_str": search_str,
            "search_mode": search_mode,
            "include_annotation_text": include_annotation_text,
            "tier_stats": tier_stats,
            "assays": assays,
            "assay_choices": assay_choices,
        }


__all__ = ["CommonQueryService"]
