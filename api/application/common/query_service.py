"""Common query service used by router endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.application.interpretation.report_summary import enrich_reported_variant_docs
from api.config.application_metadata import oncokb_gene_url
from api.domain.common.assay_filters import get_sample_effective_genes
from api.domain.common.errors import api_error
from api.domain.common.sample_filters import normalize_sample_filters
from api.domain.core.dna.variant_identity import (
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)
from api.infra.observability.operations import measured_operation


class CommonQueryService:
    """Provide shared gene and tiered-variant query workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "CommonQueryService":
        """Build the service from the runtime store."""
        return cls(
            hgnc_repository=store.hgnc_repository,
            oncokb_repository=store.oncokb_repository,
            variant_repository=store.variant_repository,
            reported_variant_repository=store.reported_variant_repository,
            assay_panel_repository=store.assay_panel_repository,
            annotation_repository=store.annotation_repository,
            sample_repository=store.sample_repository,
            gene_list_repository=store.gene_list_repository,
            oncokb_public_cache_repository=getattr(store, "oncokb_public_cache_repository", None),
            clinpgx_public_repository=getattr(store, "clinpgx_public_repository", None),
            civic_repository=getattr(store, "civic_repository", None),
            brca_repository=getattr(store, "brca_repository", None),
            iarc_tp53_repository=getattr(store, "iarc_tp53_repository", None),
            bam_record_repository=getattr(store, "bam_record_repository", None),
        )

    def __init__(
        self,
        *,
        hgnc_repository: Any,
        oncokb_repository: Any,
        variant_repository: Any,
        reported_variant_repository: Any,
        assay_panel_repository: Any,
        annotation_repository: Any,
        sample_repository: Any,
        gene_list_repository: Any,
        oncokb_public_cache_repository: Any | None = None,
        clinpgx_public_repository: Any | None = None,
        civic_repository: Any | None = None,
        brca_repository: Any | None = None,
        iarc_tp53_repository: Any | None = None,
        bam_record_repository: Any | None = None,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.hgnc_repository = hgnc_repository
        self.oncokb_repository = oncokb_repository
        self.variant_repository = variant_repository
        self.reported_variant_repository = reported_variant_repository
        self.assay_panel_repository = assay_panel_repository
        self.annotation_repository = annotation_repository
        self.sample_repository = sample_repository
        self.gene_list_repository = gene_list_repository
        self.oncokb_public_cache_repository = oncokb_public_cache_repository
        self.clinpgx_public_repository = clinpgx_public_repository
        self.civic_repository = civic_repository
        self.brca_repository = brca_repository
        self.iarc_tp53_repository = iarc_tp53_repository
        self.bam_record_repository = bam_record_repository

    def _resolve_gene(self, gene_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Resolve a gene identifier through HGNC id, current symbol, previous symbol, or alias."""
        normalized_gene_id = str(gene_id or "").strip()
        if normalized_gene_id.isnumeric() or normalized_gene_id.upper().startswith("HGNC:"):
            gene = self.hgnc_repository.get_metadata_by_hgnc_id(hgnc_id=normalized_gene_id)
        elif hasattr(self.hgnc_repository, "get_metadata_by_symbol_or_alias"):
            gene = self.hgnc_repository.get_metadata_by_symbol_or_alias(symbol=normalized_gene_id)
        else:
            gene = self.hgnc_repository.get_metadata_by_symbol(symbol=normalized_gene_id)
        symbol = (gene or {}).get("hgnc_symbol") or (gene or {}).get("symbol") or normalized_gene_id
        query = {
            "input": normalized_gene_id,
            "resolved_symbol": symbol,
            "symbol_changed": bool(
                normalized_gene_id
                and symbol
                and normalized_gene_id.upper() != str(symbol).upper()
                and not normalized_gene_id.upper().startswith("HGNC:")
            ),
        }
        return gene, query

    @staticmethod
    def _source_present(value: Any) -> bool:
        """Return true when a source has useful content for a response."""
        if value is None:
            return False
        if isinstance(value, dict | list | tuple | set):
            return bool(value)
        return True

    @classmethod
    def _available_sources(cls, sources: dict[str, Any]) -> list[str]:
        """Return source names that have non-empty payloads."""
        return sorted(name for name, value in sources.items() if cls._source_present(value))

    def gene_info_payload(self, gene_id: str) -> dict[str, Any]:
        """Return gene metadata by HGNC id or symbol."""
        gene, query = self._resolve_gene(gene_id)
        symbol = query["resolved_symbol"]
        oncokb_gene = self.oncokb_repository.get_oncokb_gene(str(symbol).upper())
        return {
            "gene": gene,
            "query": query,
            "knowledgebase": {
                "oncokb": oncokb_gene,
                "oncokb_url": oncokb_gene_url(symbol) if oncokb_gene else None,
            },
        }

    def knowledgebase_gene_payload(self, gene_id: str) -> dict[str, Any]:
        """Return aggregated external knowledgebase context for a gene."""
        gene, query = self._resolve_gene(gene_id)
        symbol = str(query["resolved_symbol"] or "").strip()
        upper_symbol = symbol.upper()

        public_oncokb_getter = getattr(self.oncokb_public_cache_repository, "get_gene_record", None)
        clinpgx_getter = getattr(self.clinpgx_public_repository, "get_gene_record", None)
        civic_getter = getattr(self.civic_repository, "get_civic_gene_info", None)
        sources = {
            "oncokb_public": public_oncokb_getter(symbol)
            if callable(public_oncokb_getter)
            else None,
            "oncokb_local": self.oncokb_repository.get_oncokb_gene(upper_symbol),
            "oncokb_actionable_local": self.oncokb_repository.get_oncokb_action_gene(upper_symbol),
            "clinpgx_public": clinpgx_getter(symbol) if callable(clinpgx_getter) else None,
            "civic_gene": civic_getter(symbol) if callable(civic_getter) else None,
            "brca_exchange": {
                "applies_to_gene": upper_symbol in {"BRCA1", "BRCA2"},
                "lookup": "variant-coordinate",
            },
            "iarc_tp53": {
                "applies_to_gene": upper_symbol == "TP53",
                "lookup": "variant-hgvsc",
            },
        }
        return {
            "query": query,
            "gene": gene,
            "sources": sources,
            "available_sources": self._available_sources(sources),
        }

    def knowledgebase_variant_payload(
        self,
        *,
        chrom: str,
        pos: int,
        ref: str,
        alt: str,
        gene: str,
        hgvsc: str | None = None,
        hgvsp: str | None = None,
        assay_group: str = "dna",
    ) -> dict[str, Any]:
        """Return local knowledgebase context for one variant identity."""
        selected_csq = {
            "SYMBOL": str(gene or "").strip(),
            "HGVSc": str(hgvsc or "").strip(),
            "HGVSp": str(hgvsp or "").strip(),
        }
        variant = {
            "CHROM": str(chrom or "").removeprefix("chr"),
            "POS": int(pos),
            "REF": str(ref or "").strip(),
            "ALT": str(alt or "").strip(),
            "INFO": {"selected_CSQ": selected_csq},
        }
        hgvsp_candidates = [selected_csq["HGVSp"]] if selected_csq["HGVSp"] else []
        sources = {
            "civic_variants": self.civic_repository.get_civic_data(variant, selected_csq["HGVSp"])
            if self.civic_repository is not None
            else [],
            "oncokb_local": self.oncokb_repository.get_oncokb_anno(variant, hgvsp_candidates)
            if hgvsp_candidates
            else None,
            "oncokb_actionable_local": self.oncokb_repository.get_oncokb_action(
                variant, hgvsp_candidates
            )
            if hgvsp_candidates
            else [],
            "brca_exchange": self.brca_repository.get_brca_data(variant, assay_group)
            if self.brca_repository is not None
            else None,
            "iarc_tp53": self.iarc_tp53_repository.find_iarc_tp53(variant)
            if self.iarc_tp53_repository is not None
            else None,
        }
        return {
            "query": {
                "chrom": variant["CHROM"],
                "pos": variant["POS"],
                "ref": variant["REF"],
                "alt": variant["ALT"],
                "gene": selected_csq["SYMBOL"],
                "hgvsc": selected_csq["HGVSc"] or None,
                "hgvsp": selected_csq["HGVSp"] or None,
                "assay_group": assay_group,
            },
            "variant": variant,
            "sources": sources,
            "available_sources": self._available_sources(sources),
        }

    def bam_files_payload(self, *, sample_ids: list[str]) -> dict[str, Any]:
        """Return BAM-service file paths for sample IDs."""
        normalized = [str(sample_id or "").strip() for sample_id in sample_ids]
        normalized = [sample_id for sample_id in normalized if sample_id]
        if not normalized:
            raise api_error(400, "At least one sample_id must be provided")
        if self.bam_record_repository is None:
            return {"query": {"sample_ids": normalized}, "bam_files": {}}
        lookup = {sample_id: sample_id for sample_id in normalized}
        return {
            "query": {"sample_ids": normalized},
            "bam_files": self.bam_record_repository.get_bams(lookup) or {},
        }

    def tiered_variant_context_payload(self, *, variant_id: str, tier: int) -> dict[str, Any]:
        """Return reported-variant context for a tiered variant."""
        variant = self.variant_repository.get_variant(variant_id)
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
        if simple_id_hash:
            or_conditions.append({"simple_id_hash": simple_id_hash})
        elif simple_id:
            or_conditions.append({"simple_id": simple_id})
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
        docs = list(self.reported_variant_repository.list_reported_variants(query) or [])
        docs = enrich_reported_variant_docs(
            deepcopy(docs),
            sample_repository=self.sample_repository,
            annotation_repository=self.annotation_repository,
        )
        for doc in docs:
            sample_doc = doc.get("sample") or {}
            sample_oid = doc.get("sample_oid") or sample_doc.get("_id")
            if sample_oid is not None:
                doc["sample_id"] = str(sample_oid)
                sample_doc["sample_id"] = str(sample_oid)
            if sample_doc:
                doc["sample"] = sample_doc
        return {"variant": variant, "docs": docs, "tier": tier, "error": None}

    def _sample_reference(
        self,
        *,
        sample_oid: Any,
        sample_doc: dict[str, Any] | None,
        sample_name: str | None,
    ) -> dict[str, Any]:
        """Build the sample reference carried by common search payloads."""
        sample_id = str(sample_oid) if sample_oid is not None else None
        resolved_name = sample_name or (sample_doc or {}).get("name") or "UNKNOWN_SAMPLE"
        return {
            "sample_id": sample_id,
            "sample_name": resolved_name,
            "name": resolved_name,
            "asp_id": (sample_doc or {}).get("asp_id"),
            "subpanel_id": (sample_doc or {}).get("subpanel_id"),
            "environment": (sample_doc or {}).get("environment"),
            "report_oids": {},
        }

    @measured_operation("query.tiered_variants")
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
        assay_choices = list(self.assay_panel_repository.get_all_asp_groups() or [])
        effective_assays = assays if assays else None
        docs_found = list(
            self.annotation_repository.find_variants_by_search_string(
                search_str=search_str,
                search_mode=search_mode,
                include_annotation_text=include_annotation_text,
                asp_ids=effective_assays,
                limit=limit_entries,
            )
            or []
        )
        reported_found = list(
            self.reported_variant_repository.find_reported_variants_by_search_string(
                search_str=search_str or "",
                search_mode=search_mode,
                asp_ids=effective_assays,
                limit=limit_entries,
            )
            or []
        )

        tier_stats = {"total": {}, "by_assay": {}}
        if search_str:
            tier_stats = self.annotation_repository.get_tier_stats_by_search(
                search_str=search_str,
                search_mode=search_mode,
                include_annotation_text=include_annotation_text,
                asp_ids=effective_assays,
            )

        sample_tagged_docs = []
        associated_annotation_text_oids: set[str] = set()
        reported_docs_seen: set[str] = set()

        for doc in docs_found:
            merged_doc = deepcopy(doc)
            if include_annotation_text and not merged_doc.get("text"):
                merged_doc["text"] = self.annotation_repository.get_matching_annotation_text(
                    merged_doc
                )
            sample_oids: dict[str, dict[str, Any]] = {}
            reported_docs = list(
                self.reported_variant_repository.list_reported_variants(
                    {"annotation_oid": {"$in": [doc["_id"], str(doc["_id"])]}}
                )
                or []
            )

            for reported_doc in reported_docs:
                if reported_doc.get("_id") is not None:
                    reported_docs_seen.add(str(reported_doc.get("_id")))
                sample_oid = reported_doc.get("sample_oid")
                report_oid = reported_doc.get("report_oid")
                annotation_text_oid = reported_doc.get("annotation_text_oid")
                report_id = reported_doc.get("report_id")
                sample_doc = self.sample_repository.get_sample_by_oid(sample_oid)
                sample_name = reported_doc.get("sample_name") or (sample_doc or {}).get("name")
                report_num = reported_doc.get("report_num")

                if sample_oid:
                    sample_key = str(sample_oid)
                    if sample_key not in sample_oids:
                        sample_oids[sample_key] = self._sample_reference(
                            sample_oid=sample_oid,
                            sample_doc=sample_doc,
                            sample_name=sample_name,
                        )
                    if report_oid and report_id:
                        report_oids = sample_oids.get(sample_key, {}).get("report_oids", {})
                        if report_id not in report_oids:
                            sample_oids[sample_key]["report_oids"][report_id] = report_num

                if include_annotation_text and annotation_text_oid:
                    associated_annotation_text_oids.add(annotation_text_oid)
                    merged_doc["text"] = self.annotation_repository.get_annotation_text_by_oid(
                        annotation_text_oid
                    )

            merged_doc["reported_docs"] = reported_docs
            merged_doc["samples"] = sample_oids

            if merged_doc.get("_id") not in associated_annotation_text_oids:
                sample_tagged_docs.append(merged_doc)

        for reported_doc in reported_found:
            reported_doc_id = str(reported_doc.get("_id"))
            if reported_doc_id in reported_docs_seen:
                continue

            annotation_oid = reported_doc.get("annotation_oid")
            annotation_doc = (
                self.annotation_repository.get_annotation_by_oid(annotation_oid)
                if annotation_oid
                else None
            ) or {}
            sample_oid = reported_doc.get("sample_oid")
            sample_doc = (
                self.sample_repository.get_sample_by_oid(sample_oid) if sample_oid else None
            )
            sample_name = (
                reported_doc.get("sample_name")
                or (sample_doc or {}).get("name")
                or "UNKNOWN_SAMPLE"
            )
            report_id = reported_doc.get("report_id")
            report_num = reported_doc.get("report_num")
            sample_key = str(sample_oid) if sample_oid is not None else reported_doc_id

            merged_doc = {
                **annotation_doc,
                **reported_doc,
                "class": annotation_doc.get("class") or reported_doc.get("tier"),
                "author": annotation_doc.get("author") or reported_doc.get("created_by"),
                "samples": {
                    sample_key: {
                        **self._sample_reference(
                            sample_oid=sample_oid,
                            sample_doc=sample_doc,
                            sample_name=sample_name,
                        ),
                        "report_oids": {report_id: report_num} if report_id else {},
                    }
                },
                "reported_docs": [reported_doc],
            }
            if include_annotation_text and reported_doc.get("annotation_text_oid"):
                merged_doc["text"] = self.annotation_repository.get_annotation_text_by_oid(
                    reported_doc.get("annotation_text_oid")
                )
            elif include_annotation_text and not merged_doc.get("text"):
                merged_doc["text"] = self.annotation_repository.get_matching_annotation_text(
                    merged_doc
                )
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

    @staticmethod
    def _snv_list_ids_by_intent(sample: dict[str, Any]) -> dict[str, list[str]]:
        """Return selected SNV list IDs grouped by analysis intent."""
        filters = normalize_sample_filters(
            sample.get("filters"),
            omics_layer=str(sample.get("omics_layer") or "dna"),
            analysis_intents=sample.get("analysis_intents"),
            canonical=True,
        )
        values: dict[str, list[str]] = {}
        for intent in ("somatic", "germline"):
            section = (filters.get(intent) or {}).get("snv") or {}
            values[intent] = list(
                dict.fromkeys(str(value) for value in section.get("snvlists", []) if str(value))
            )
        return values

    @measured_operation("query.gene_cohort")
    def gene_cohort_payload(
        self,
        *,
        gene_id: str,
        visible_asp_ids: list[str] | None,
        visible_environments: list[str] | None,
        include_history: bool = False,
        finding_limit: int = 10_000,
    ) -> dict[str, Any]:
        """Build prevalence and recurrent-finding statistics for one gene."""
        gene, query = self._resolve_gene(gene_id)
        symbol = str(query.get("resolved_symbol") or "").strip().upper()
        if not symbol:
            raise api_error(400, "A gene symbol or HGNC identifier is required")

        samples = self.sample_repository.get_gene_cohort_samples(
            asp_ids=visible_asp_ids,
            environments=visible_environments,
        )
        asp_map = self.assay_panel_repository.get_asps_for_gene_scope(visible_asp_ids)
        selected_ids = list(
            dict.fromkeys(
                list_id
                for sample in samples
                for list_ids in self._snv_list_ids_by_intent(sample).values()
                for list_id in list_ids
            )
        )
        isgl_map = self.gene_list_repository.get_isgl_by_ids(selected_ids)

        profiled_samples: list[dict[str, Any]] = []
        excluded_samples = 0
        for sample in samples:
            asp = asp_map.get(str(sample.get("asp_id") or ""))
            if not asp or str(sample.get("omics_layer") or "dna").lower() != "dna":
                excluded_samples += 1
                continue
            list_ids_by_intent = self._snv_list_ids_by_intent(sample)
            has_selected_lists = any(list_ids_by_intent.values())
            effective_genes: set[str] = set()
            for intent, list_ids in list_ids_by_intent.items():
                if not list_ids:
                    continue
                selected_lists = {
                    list_id: isgl_map[list_id] for list_id in list_ids if list_id in isgl_map
                }
                _scope_details, intent_genes = get_sample_effective_genes(
                    sample,
                    asp,
                    selected_lists,
                    target="snv",
                    intent=intent,
                )
                effective_genes.update(str(value).upper() for value in intent_genes)
            if not has_selected_lists:
                effective_genes.update(
                    str(value).upper() for value in (asp.get("covered_genes") or [])
                )
            if has_selected_lists and not effective_genes:
                excluded_samples += 1
                continue
            if effective_genes and symbol not in effective_genes:
                excluded_samples += 1
                continue
            profiled_samples.append(sample)

        profiled_names = {
            str(sample.get("name")) for sample in profiled_samples if sample.get("name")
        }
        latest_report_oids = [
            sample["latest_report_id"]
            for sample in profiled_samples
            if sample.get("latest_report_id") is not None
        ]
        query_scope = {
            "report_oids": None if include_history else latest_report_oids,
            "sample_oids": (
                [sample["_id"] for sample in profiled_samples if sample.get("_id") is not None]
                if include_history
                else None
            ),
            "sample_names": sorted(profiled_names) if include_history else None,
        }
        raw_findings = self.reported_variant_repository.get_gene_cohort_findings(
            gene=symbol,
            asp_ids=visible_asp_ids,
            limit=finding_limit,
            **query_scope,
        )
        sample_name_by_oid = {
            str(sample["_id"]): str(sample["name"])
            for sample in profiled_samples
            if sample.get("_id") is not None and sample.get("name")
        }
        scoped_findings = []
        for row in raw_findings:
            sample_name = str(row.get("sample_name") or "")
            if not sample_name and row.get("sample_oid") is not None:
                sample_name = sample_name_by_oid.get(str(row["sample_oid"]), "")
            if sample_name not in profiled_names:
                continue
            normalized_row = dict(row)
            normalized_row["sample_name"] = sample_name
            scoped_findings.append(normalized_row)

        duplicate_report_observations_removed = 0
        findings = scoped_findings
        if include_history:
            deduplicated = []
            seen_sample_mutations: set[tuple[str, str]] = set()
            for row in scoped_findings:
                identity = str(
                    row.get("simple_id")
                    or row.get("simple_id_hash")
                    or row.get("hgvsp")
                    or row.get("hgvsc")
                    or row.get("variant")
                    or row.get("_id")
                    or "unknown"
                )
                key = (str(row.get("sample_name")), identity)
                if key in seen_sample_mutations:
                    duplicate_report_observations_removed += 1
                    continue
                seen_sample_mutations.add(key)
                deduplicated.append(row)
            findings = deduplicated
        sample_map = {str(sample.get("name")): sample for sample in profiled_samples}
        finding_sample_names = {str(row.get("sample_name")) for row in findings}

        tier_counts = {str(tier): 0 for tier in range(1, 5)}
        variant_map: dict[str, dict[str, Any]] = {}
        sample_findings: dict[str, list[dict[str, Any]]] = {}
        for row in findings:
            tier = int(row.get("tier") or 0)
            if tier in range(1, 5):
                tier_counts[str(tier)] += 1
            sample_name = str(row.get("sample_name"))
            sample_findings.setdefault(sample_name, []).append(row)
            identity = str(
                row.get("simple_id")
                or row.get("hgvsp")
                or row.get("hgvsc")
                or row.get("variant")
                or "unknown"
            )
            entry = variant_map.setdefault(
                identity,
                {
                    "identity": identity,
                    "hgvsp": row.get("hgvsp"),
                    "hgvsc": row.get("hgvsc"),
                    "sample_names": set(),
                    "tiers": set(),
                    "observation_count": 0,
                },
            )
            entry["sample_names"].add(sample_name)
            entry["tiers"].add(tier)
            entry["observation_count"] += 1

        recurrent_variants = sorted(
            (
                {
                    "identity": entry["identity"],
                    "hgvsp": entry["hgvsp"],
                    "hgvsc": entry["hgvsc"],
                    "sample_count": len(entry["sample_names"]),
                    "observation_count": entry["observation_count"],
                    "tiers": sorted(entry["tiers"]),
                }
                for entry in variant_map.values()
            ),
            key=lambda entry: (
                -entry["sample_count"],
                -entry["observation_count"],
                entry["identity"],
            ),
        )[:25]

        def prevalence(numerator: int, denominator: int) -> float | None:
            return round((numerator / denominator) * 100, 2) if denominator else None

        assay_rows = []
        for asp_id in sorted({str(sample.get("asp_id")) for sample in profiled_samples}):
            assay_samples = [
                sample for sample in profiled_samples if sample.get("asp_id") == asp_id
            ]
            assay_names = {str(sample.get("name")) for sample in assay_samples}
            finding_count = len(assay_names & finding_sample_names)
            asp = asp_map.get(asp_id, {})
            assay_rows.append(
                {
                    "asp_id": asp_id,
                    "display_name": asp.get("display_name") or asp_id,
                    "asp_group": asp.get("asp_group"),
                    "profiled_samples": len(assay_samples),
                    "finding_samples": finding_count,
                    "prevalence_percent": prevalence(finding_count, len(assay_samples)),
                }
            )

        sex_rows = []
        for sex in ("female", "male", "unknown", "not_recorded"):
            sex_samples = [
                sample
                for sample in profiled_samples
                if (str(sample.get("sex") or "not_recorded").lower() == sex)
            ]
            if not sex_samples:
                continue
            sex_names = {str(sample.get("name")) for sample in sex_samples}
            count = len(sex_names & finding_sample_names)
            sex_rows.append(
                {
                    "sex": sex,
                    "profiled_samples": len(sex_samples),
                    "finding_samples": count,
                    "prevalence_percent": prevalence(count, len(sex_samples)),
                }
            )

        sample_rows = []
        for sample_name in sorted(finding_sample_names):
            sample = sample_map.get(sample_name, {})
            rows = sample_findings.get(sample_name, [])
            sample_rows.append(
                {
                    "sample_name": sample_name,
                    "asp_id": sample.get("asp_id"),
                    "subpanel_id": sample.get("subpanel_id"),
                    "environment": sample.get("environment"),
                    "sex": sample.get("sex"),
                    "tiers": sorted({int(row.get("tier")) for row in rows if row.get("tier")}),
                    "variants": sorted(
                        {
                            str(row.get("hgvsp") or row.get("hgvsc") or row.get("simple_id") or "-")
                            for row in rows
                        }
                    ),
                }
            )

        denominator_count = len(profiled_samples)
        finding_sample_count = len(finding_sample_names)
        return {
            "query": query,
            "gene": gene,
            "summary": {
                "profiled_samples": denominator_count,
                "finding_samples": finding_sample_count,
                "prevalence_percent": prevalence(finding_sample_count, denominator_count),
                "reported_observations": len(findings),
                "unique_variants": len(variant_map),
            },
            "denominator": {
                "method": "sample_snv_isgl_then_asp_covered_genes",
                "report_scope": "historical" if include_history else "latest",
                "ready_samples_considered": len(samples),
                "samples_excluded_outside_gene_scope": excluded_samples,
                "unrestricted_asp_scope_counts_as_profiled": True,
                "duplicate_report_observations_removed": duplicate_report_observations_removed,
            },
            "tier_counts": tier_counts,
            "assays": assay_rows,
            "sex_distribution": sex_rows,
            "recurrent_variants": recurrent_variants,
            "samples": sample_rows[:200],
            "truncated": len(raw_findings) >= finding_limit or len(sample_rows) > 200,
        }


__all__ = ["CommonQueryService"]
