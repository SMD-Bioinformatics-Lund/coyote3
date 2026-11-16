# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Resolve report finding eligibility, filter scopes and query policy."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from coyote.application.common.release_resources import assay_resource, gene_list_resources
from coyote.application.interpretation.annotation_enrichment import (
    add_global_annotations as shared_add_global_annotations,
)
from coyote.application.query_rules.service import effective_policy
from coyote.application.reporting.eligibility import (
    reportable_tiers,
)
from coyote.config.clinical_query_policy import CLINICAL_QUERY_POLICY, FindingQueryPolicy
from coyote.config.database_versions import sample_vep_version
from coyote.domain.common.assay_filters import (
    get_sample_effective_genes,
)
from coyote.domain.common.sample_filters import (
    merge_filter_defaults,
    merged_dna_cnv_filters,
    merged_dna_translocation_filters,
    merged_dna_variant_filters,
)
from coyote.domain.dna.cnv_selection import CnvGeneScope
from coyote.domain.dna.dna_filters import (
    cnv_organizegenes,
    cnvtype_variant,
    create_cnveffectlist,
)
from coyote.domain.dna.translocqueries import filter_translocations_by_genes
from coyote.domain.dna.varqueries import build_query
from coyote.domain.selection import Operator, Selection

from .variants import (
    filter_variants_for_report,
    hotspot_variant,
)


def _ensure_sample_filters(sample: dict, assay_config: dict) -> tuple[dict, dict]:
    """Return sample filters completed from its resolved ASPC defaults."""
    sample = deepcopy(sample)
    sample_filters = merge_filter_defaults(
        sample.get("filters"),
        assay_config.get("filters"),
        asp_category=str(sample.get("asp_category") or "dna"),
        analysis_intents=sample.get("analysis_intents"),
    )
    sample["filters"] = sample_filters
    return sample, sample_filters


def _resolve_sample_vep_version(sample: dict) -> str:
    """Return the sample VEP version used for report consequence mapping."""
    normalized = sample_vep_version(sample)
    if not normalized:
        raise ValueError("sample.database_versions.vep is required for DNA report generation")
    return normalized


def _resolve_filter_genes(
    sample: dict,
    sample_filters: dict,
    assay_panel_doc: dict,
    *,
    assay_config: dict,
    intent: str = "somatic",
) -> tuple[dict, list]:
    """Resolve gene coverage map and effective report filter genes."""
    snv_filters = merged_dna_variant_filters(sample_filters, intent=intent)
    checked_snvlists = snv_filters.get("snvlists", [])
    checked_snvlists_genes_dict = gene_list_resources(assay_config, checked_snvlists)
    return get_sample_effective_genes(
        sample, assay_panel_doc, checked_snvlists_genes_dict, intent=intent
    )


def _resolve_cnv_gene_scope(
    sample: dict,
    sample_filters: dict,
    assay_panel_doc: dict,
    *,
    assay_config: dict,
) -> CnvGeneScope:
    """Resolve the same CNV gene boundary used by analysis and query previews."""
    cnv_filters = merged_dna_cnv_filters(sample_filters)
    checked_cnvlists = cnv_filters.get("cnvlists", [])
    checked_cnvlists_genes_dict = gene_list_resources(assay_config, checked_cnvlists)
    return CnvGeneScope.resolve(
        {**sample, "filters": sample_filters},
        assay_panel_doc,
        checked_cnvlists_genes_dict,
    )


def _resolve_translocation_filter_genes(
    sample: dict,
    sample_filters: dict,
    assay_panel_doc: dict,
    *,
    assay_config: dict,
) -> list[str]:
    """Resolve DNA fusion/translocation report gene scope."""
    translocation_filters = merged_dna_translocation_filters(sample_filters)
    selected_ids = list(translocation_filters.get("fusionlists") or [])
    selected_docs = gene_list_resources(assay_config, selected_ids)
    _covered, filter_genes = get_sample_effective_genes(
        sample,
        assay_panel_doc,
        selected_docs,
        target="translocation",
    )
    return filter_genes


def _filter_translocations_for_report(
    rows: list[dict],
    *,
    filter_genes: list[str],
    restricted: bool,
    settings: dict[str, Any],
    policy: FindingQueryPolicy = CLINICAL_QUERY_POLICY.translocation,
) -> list[dict]:
    """Apply report eligibility and DNA structural gene scope to findings."""
    return filter_translocations_by_genes(
        _exclude_nonreportable_review_states(rows),
        filter_genes=filter_genes,
        restricted=restricted,
        settings=settings,
        policy=policy,
    )


def _exclude_nonreportable_review_states(rows: list[dict]) -> list[dict]:
    """Keep review-state exclusions consistent across every DNA report section."""
    return [row for row in rows if not row.get("fp") and not row.get("irrelevant")]


def _filter_cnvs_for_report(
    cnvs: list[dict],
    *,
    sample_filters: dict,
    filter_genes: list[str],
    restricted: bool,
) -> list[dict]:
    """Apply CNV effect and gene-list filters to report-included CNVs."""
    filtered_cnvs = _exclude_nonreportable_review_states(cnvs)
    cnv_filters = merged_dna_cnv_filters(sample_filters)
    filter_cnveffects = create_cnveffectlist(cnv_filters.get("cnveffects", []))
    if filter_cnveffects:
        filtered_cnvs = cnvtype_variant(filtered_cnvs, filter_cnveffects)
    if restricted:
        filter_genes_set = {str(gene).strip().upper() for gene in filter_genes if str(gene).strip()}
        filtered_cnvs = [
            cnv
            for cnv in filtered_cnvs
            if any(
                str((gene or {}).get("gene") or "").strip().upper() in filter_genes_set
                for gene in cnv.get("genes", [])
            )
        ]
    return cnv_organizegenes(filtered_cnvs)


def load_report_snv_findings(
    *,
    sample: dict,
    assay_config: dict,
    sample_filters: dict,
    intent: str,
    consequence_terms: Callable[[list], list],
    disp_pos: list,
    variant_repository,
    blacklist_repository,
    annotation_repository,
    query_rule_service=None,
    hydrate_comments: bool = False,
) -> list[dict]:
    """Load one profile through the normal SNV query and report-eligibility filters.

    Args:
        sample: Authorized sample identity and scope.
        assay_config: Pinned ASPC containing assay and gene-list releases.
        sample_filters: Merged filter profiles; not modified.
        intent: Somatic or germline SNV profile.
        consequence_terms: Resolves the sample VEP version's selected consequence groups.
        disp_pos: Reviewed verification coordinates, or an empty list.
        variant_repository: Sample-scoped finding reader.
        blacklist_repository: Scope-aware blacklist enrichment.
        annotation_repository: Exact-context classification reader.
        query_rule_service: Published selection-policy resolver, or None for software defaults.
        hydrate_comments: Include finding comments for report detail cards when True.

    Returns:
        Classified, report-eligible SNVs from only the requested filter profile.
    """
    effective_sample = {**sample, "filters": sample_filters}
    group = assay_config.get("asp_group", "unknown")
    _, genes = _resolve_filter_genes(
        effective_sample,
        sample_filters,
        assay_resource(assay_config),
        assay_config=assay_config,
        intent=intent,
    )
    filters = merged_dna_variant_filters(sample_filters, intent=intent)
    query = _build_variant_query(
        assay_group=group,
        sample=effective_sample,
        sample_filters=sample_filters,
        filter_conseq=consequence_terms(filters.get("vep_consequences", [])),
        filter_genes=genes,
        disp_pos=disp_pos,
        restrict_to_genes=True,
        intent=intent,
        query_rule_service=query_rule_service,
    )
    rows = list(variant_repository.get_case_variants(query) or [])
    if hydrate_comments:
        rows = variant_repository.hydrate_finding_comments_many(rows)
    rows = blacklist_repository.add_blacklist_data(rows, group, asp_id=sample["asp_id"])
    rows, _ = shared_add_global_annotations(
        rows,
        group,
        sample.get("diagnosis_id"),
        annotation_repository=annotation_repository,
        sample_context=assay_config["aspc_resolution"]["context"],
    )
    return filter_variants_for_report(
        hotspot_variant(rows),
        genes,
        reportable_tiers(assay_config["reporting"], "SNV"),
        restrict_to_genes=True,
    )


def _resolve_disp_positions(sample: dict, assay_config: dict) -> list:
    """Resolve optional verification display coordinates for the current sample."""
    disp_pos = []
    verification_samples = assay_config.get("verification_samples")
    if verification_samples and sample["name"] in verification_samples:
        disp_pos = verification_samples[sample["name"]]
    return disp_pos


def _build_variant_query(
    assay_group: str,
    sample: dict,
    sample_filters: dict,
    filter_conseq: list,
    filter_genes: list,
    disp_pos: list,
    restrict_to_genes: bool,
    intent: str = "somatic",
    query_rule_service=None,
) -> Selection:
    """Build a neutral variant selection for report preparation."""
    snv_filters = merged_dna_variant_filters(sample_filters, intent=intent)
    return build_query(
        assay_group,
        {
            "id": str(sample["_id"]),
            "max_freq": snv_filters["max_freq"],
            "min_freq": snv_filters["min_freq"],
            "max_control_freq": snv_filters.get("max_control_freq", 1.0),
            "min_depth": snv_filters["min_depth"],
            "min_alt_reads": snv_filters["min_alt_reads"],
            "max_popfreq": snv_filters["max_popfreq"],
            "exclude_flags": snv_filters.get("exclude_flags", []),
            "filter_conseq": filter_conseq,
            "filter_genes": filter_genes,
            "restrict_to_genes": restrict_to_genes,
            "disp_pos": disp_pos,
            "asp_id": sample.get("asp_id"),
            "diagnosis_id": sample.get("diagnosis_id"),
            "fp": {Operator.NOT_EQUAL: True},
            "irrelevant": {Operator.NOT_EQUAL: True},
        },
        intent=intent,
        policy=effective_policy(
            query_rule_service, "snv", sample, assay_group=assay_group, intent=intent
        ),
    )
