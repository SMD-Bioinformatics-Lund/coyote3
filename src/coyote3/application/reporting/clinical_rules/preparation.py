"""Convert already filtered report data into the stable rule fact contract."""

from __future__ import annotations

import math
from typing import Any, Literal

from coyote3.application.reporting.clinical_rules.facts import PreparedReportContext
from coyote3.domain.common.biomarkers import biomarker_counts, measurement_facts, project_biomarkers
from coyote3.domain.dna.cnv_metrics import copy_number_from_log2, supporting_read_percent


def _genotype_vaf(variant: dict[str, Any], genotype_type: str) -> float | None:
    """Read the first matching genotype's AF, with a top-level fallback for cases.

    Args:
        variant: Variant containing GT records and optional af.
        genotype_type: Exact GT type to select; only case permits the af fallback.

    Returns:
        Allele fraction as a float, or None for absent or nonnumeric values.
        A matching GT with unusable AF does not fall back to top-level af.
    """
    for genotype in variant.get("GT", []) or []:
        if genotype.get("type") == genotype_type:
            value = genotype.get("AF")
            try:
                return float(value) if value is not None else None
            except (TypeError, ValueError):
                return None
    if genotype_type != "case":
        return None
    value = variant.get("af")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _selected_csq(variant: dict[str, Any]) -> dict[str, Any]:
    """Read the selected consequence without choosing a transcript.

    Args:
        variant: Variant with optional INFO.selected_CSQ.

    Returns:
        Stored selected consequence, or an empty dictionary when falsey or absent.
    """
    return (variant.get("INFO") or {}).get("selected_CSQ") or {}


def _snv_fact(variant: dict[str, Any]) -> dict[str, Any]:
    """Project an SNV into rule facts using its already selected consequence.

    Args:
        variant: Filtered SNV with genotype, classification, and annotation fields.

    Returns:
        SNV facts with fractional VAFs left unrounded and derived percentages
        rounded to three decimals; unavailable VAFs remain None. String
        consequences split on ampersands.
    """
    csq = _selected_csq(variant)
    gene = csq.get("SYMBOL") or variant.get("symbol") or variant.get("gene")
    case_vaf = _genotype_vaf(variant, "case")
    control_vaf = _genotype_vaf(variant, "control")
    consequence = csq.get("Consequence") or variant.get("consequence") or []
    if isinstance(consequence, str):
        consequence = consequence.split("&")
    exon = csq.get("EXON") or variant.get("exon") or []
    intron = csq.get("INTRON") or variant.get("intron") or []
    if isinstance(exon, str):
        exon = [exon.split("/", 1)[0]]
    if isinstance(intron, str):
        intron = [intron.split("/", 1)[0]]
    classification = variant.get("classification") or {}
    return {
        "kind": "snv",
        "gene": gene,
        "genes": [gene] if gene else [],
        "tier": classification.get("class", variant.get("class")),
        "exon": exon,
        "intron": intron,
        "case_vaf": case_vaf,
        "case_vaf_percent": round(case_vaf * 100, 3) if case_vaf is not None else None,
        "control_vaf": control_vaf,
        "control_vaf_percent": (round(control_vaf * 100, 3) if control_vaf is not None else None),
        "consequence": consequence,
        "filter_flags": variant.get("FILTER") or [],
        "hgvsc": csq.get("HGVSc") or variant.get("cdna") or variant.get("hgvsc"),
        "hgvsp": csq.get("HGVSp") or variant.get("variant") or variant.get("hgvsp"),
        "variant_type": variant.get("variant_class") or variant.get("var_type"),
    }


def _cnv_fact(cnv: dict[str, Any]) -> dict[str, Any]:
    """Project CNV genes, tier, effect and calculated evidence into rule facts.

    Args:
        cnv: Filtered CNV with gene dictionaries and optional effect or numeric ratio.

    Returns:
        CNV facts; gene is populated only for one gene. Without an explicit
        effect, a positive ratio means gain and a nonpositive ratio means loss.
        Without a ratio, stored AMP/DUP/GAIN or DEL/LOSS types supply the effect.
        Copy number uses a diploid baseline rounded to two decimals; unusable or
        overflowing estimates remain None. Only genes with a class key enter
        cnv_report_genes, matching the established summary grouping.
    """
    genes = [
        str(gene.get("gene"))
        for gene in cnv.get("genes", []) or []
        if isinstance(gene, dict) and gene.get("gene")
    ]
    ratio = cnv.get("ratio")
    copy_number = None
    if isinstance(ratio, (int, float)) and not isinstance(ratio, bool) and math.isfinite(ratio):
        try:
            estimate = copy_number_from_log2(ratio)
            copy_number = round(estimate, 2) if math.isfinite(estimate) else None
        except OverflowError:
            pass
    else:
        ratio = None
    effect = cnv.get("effect")
    if not effect and ratio is not None:
        effect = "gain" if ratio > 0 else "loss"
    if not effect:
        effect = {"AMP": "gain", "DUP": "gain", "GAIN": "gain", "DEL": "loss", "LOSS": "loss"}.get(
            str(cnv.get("type") or "").upper()
        )
    gene_records = [gene for gene in cnv.get("genes", []) or [] if isinstance(gene, dict)]
    return {
        "kind": "cnv",
        "gene": genes[0] if len(genes) == 1 else None,
        "genes": genes,
        "tier": (cnv.get("classification") or {}).get("class"),
        "cnv_effect": effect,
        "cnv_ratio": ratio,
        "cnv_copy_number": copy_number,
        "cnv_paired_read_percent": supporting_read_percent(cnv.get("PR")),
        "cnv_split_read_percent": supporting_read_percent(cnv.get("SR")),
        "cnv_report_genes": [
            str(gene["gene"]) for gene in gene_records if "class" in gene and gene.get("gene")
        ],
        "cnv_other_gene_count": sum("class" not in gene for gene in gene_records),
        "chromosome": str(cnv["chr"]) if cnv.get("chr") is not None else None,
        "start": cnv.get("start"),
        "end": cnv.get("end"),
        "variant_type": "cnv",
    }


def _cnv_summaries(cnvs: list[dict[str, Any]], facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group reviewed CNVs using the established report evidence-selection policy.

    Args:
        cnvs: Already filtered CNVs; only explicitly interesting calls contribute.
        facts: Calculated CNV facts in the same order as cnvs.

    Returns:
        Groups in first-occurrence order, keyed by ordered classified genes and
        gain/loss. Empty gene sets and unknown effects are omitted. Each group
        keeps the largest GATK/CNVkit copy number and other-gene count, and the
        last valid Manta paired/split percentages, including observed zeroes.
        Inputs and finding eligibility are unchanged.
    """
    groups: dict[tuple[tuple[str, ...], str], dict[str, Any]] = {}
    for cnv, fact in zip(cnvs, facts, strict=True):
        genes, effect = fact["cnv_report_genes"], fact["cnv_effect"]
        if not cnv.get("interesting") or not genes or effect not in {"gain", "loss"}:
            continue
        group = groups.setdefault(
            (tuple(genes), effect),
            {
                "genes": genes,
                "effect": effect,
                "copy_number": None,
                "paired_read_percent": None,
                "split_read_percent": None,
                "other_gene_count": 0,
            },
        )
        group["other_gene_count"] = max(group["other_gene_count"], fact["cnv_other_gene_count"])
        callers = cnv.get("callers") or []
        copy_number = fact["cnv_copy_number"]
        if {"gatk", "cnvkit"}.intersection(callers) and copy_number is not None:
            group["copy_number"] = max(group["copy_number"] or 0.0, copy_number)
        if "manta" in callers:
            for key in ("paired_read_percent", "split_read_percent"):
                value = fact["cnv_" + key]
                if value is not None:
                    group[key] = value
    return list(groups.values())


def _structural_fact(finding: dict[str, Any], kind: str) -> dict[str, Any]:
    """Project structural genes, selected-call support, and visible annotation text.

    Args:
        finding: Fusion or translocation with optional calls and annotations.
        kind: Finding kind stored as both kind and variant_type.

    Returns:
        Structural facts using explicit genes before MANE/first ANN genes,
        selected call before first call, and the latest visible text by timestamp string.
    """
    gene_1 = finding.get("gene1")
    gene_2 = finding.get("gene2")
    if not gene_1 or not gene_2:
        annotation = (finding.get("INFO") or {}).get("MANE_ANN")
        if not annotation:
            annotations = (finding.get("INFO") or {}).get("ANN") or []
            annotation = annotations[0] if annotations else {}
        names = str((annotation or {}).get("Gene_Name") or "").split("&")
        gene_1 = gene_1 or (names[0] if names and names[0] else None)
        gene_2 = gene_2 or (names[1] if len(names) > 1 else None)
    calls = finding.get("calls") if isinstance(finding.get("calls"), list) else []
    selected_call = next(
        (call for call in calls if isinstance(call, dict) and call.get("selected") in (1, True)),
        calls[0] if calls and isinstance(calls[0], dict) else {},
    )
    annotations = finding.get("global_annotations") or []
    visible_annotations = [
        annotation
        for annotation in annotations
        if isinstance(annotation, dict) and annotation.get("text") and not annotation.get("hidden")
    ]
    latest_annotation = max(
        visible_annotations,
        key=lambda annotation: str(
            annotation.get("time_created") or annotation.get("created_on") or ""
        ),
        default={},
    )

    return {
        "kind": kind,
        "gene": None,
        "genes": [gene for gene in (gene_1, gene_2) if gene],
        "tier": (finding.get("classification") or {}).get("class"),
        "fusion_gene_1": gene_1,
        "fusion_gene_2": gene_2,
        "fusion_breakpoint_1": selected_call.get("breakpoint1"),
        "fusion_breakpoint_2": selected_call.get("breakpoint2"),
        "fusion_effect": selected_call.get("effect"),
        "fusion_spanning_pairs": selected_call.get("spanpairs"),
        "fusion_spanning_reads": selected_call.get("spanreads"),
        "fusion_annotation": latest_annotation.get("text"),
        "variant_type": kind,
    }


def _gene_list_fact(gene_list: dict[str, Any], assay: dict[str, Any]) -> dict[str, Any]:
    """Project an applied gene list into the report fact fields.

    Args:
        gene_list: Applied list document; list_type may be a string or sequence.
        assay: Pinned assay resource defining the germline gene subset.

    Returns:
        Identity, version, selection, and gene fields with absent sequences empty
        and adhoc converted to a boolean.
    """
    list_type = gene_list.get("list_type") or []
    if isinstance(list_type, str):
        list_type = [list_type]
    return {
        "isgl_id": str(gene_list.get("isgl_id") or ""),
        "name": gene_list.get("name"),
        "displayname": gene_list.get("displayname"),
        "gene_count": len(set(gene_list.get("genes") or [])),
        "version": gene_list.get("version"),
        "list_type": list(list_type),
        "selected_for": list(gene_list.get("selected_for") or []),
        "genes": list(gene_list.get("genes") or []),
        "germline_genes": sorted(
            set(gene_list.get("genes") or []) & set(assay.get("germline_genes") or [])
        ),
        "adhoc": bool(gene_list.get("adhoc")),
    }


def _gene_scopes(gene_lists: list[dict[str, Any]], asp: dict[str, Any]) -> dict[str, Any]:
    """Group selected lists by analysis without counting overlapping genes twice.

    Args:
        gene_lists: Resolved list documents carrying their actual selected_for domains.
        asp: Physical assay supplying the germline gene set.

    Returns:
        Per-analysis identifiers, names and unique genes, independent of findings.
    """
    scopes = {}
    for analysis in ("snv", "cnv", "translocation", "fusion", "expression", "pgx"):
        selected = [item for item in gene_lists if analysis in (item.get("selected_for") or [])]
        genes = list(dict.fromkeys(gene for item in selected for gene in item.get("genes") or []))
        scopes[analysis] = {
            "ids": [item["isgl_id"] for item in selected],
            "names": [item["name"] for item in selected]
            if all(item.get("name") for item in selected)
            else None,
            "display_names": [item["displayname"] for item in selected]
            if all(item.get("displayname") for item in selected)
            else None,
            "genes": genes,
            "gene_count": len(genes),
            "germline_genes": [gene for gene in genes if gene in (asp.get("germline_genes") or [])],
        }
    return scopes


def _tier_summaries(snvs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group reportable SNVs exactly as the established summary composer does."""
    grouped: dict[int, dict[str, list[str]]] = {}
    counts: dict[int, int] = {}
    ordered = sorted(
        snvs,
        key=lambda variant: _genotype_vaf(variant, "case") or 0.0,
        reverse=True,
    )
    for variant in ordered:
        if variant.get("irrelevant") is True:
            continue
        tier = (variant.get("classification") or {}).get("class")
        if tier not in {1, 2, 3, 4}:
            continue
        gene = _selected_csq(variant).get("SYMBOL")
        if not gene:
            continue
        case_vaf = _genotype_vaf(variant, "case")
        percentage = f"{int(round(100 * case_vaf, 0))}%" if case_vaf is not None else ""
        grouped.setdefault(tier, {}).setdefault(str(gene), []).append(percentage)
        counts[tier] = counts.get(tier, 0) + 1
    return [
        {
            "tier": tier,
            "finding_count": counts[tier],
            "genes": [
                {"gene": gene, "vaf_percentages": percentages}
                for gene, percentages in grouped[tier].items()
            ],
        }
        for tier in (1, 2, 3, 4)
        if tier in grouped
    ]


def prepare_report_context(
    *,
    sample: dict[str, Any],
    asp: dict[str, Any],
    aspc: dict[str, Any],
    analyte: Literal["dna", "rna"],
    applied_gene_lists: list[dict[str, Any]],
    report_sections_data: dict[str, Any],
    intent: Literal["somatic", "germline"] = "somatic",
) -> PreparedReportContext:
    """Build deterministic rule facts from the filtered data used by report rendering.

    Args:
        sample: Sample identity, assay scope and paired-control status.
        asp: Pinned assay metadata, covered genes and germline gene definitions.
        aspc: Resolved configuration supplying report sections, tiers and language.
        analyte: DNA or RNA reporting modality.
        applied_gene_lists: Exact selected lists with their selected_for analyses.
        report_sections_data: Already filtered findings and biomarker measurements.
        intent: Somatic or germline report intent; defaults to somatic.

    Returns:
        Query-free typed facts, including per-finding CNV metrics and reviewed CNV
        summary groups. Clinical eligibility and transcript selection remain with
        upstream preparation; this function neither queries nor mutates inputs.

    Raises:
        ValueError: Projected values do not satisfy the prepared-context contract.
    """
    findings: list[dict[str, Any]] = []
    snvs = list(report_sections_data.get("snvs") or [])
    cnvs = list(report_sections_data.get("cnvs") or [])
    fusions = list(report_sections_data.get("fusions") or [])
    translocations = list(report_sections_data.get("translocs") or [])
    biomarkers = project_biomarkers(
        report_sections_data.get("biomarkers") or [],
        (aspc.get("reporting") or {}).get("report_sections") or [],
    )
    findings.extend(_snv_fact(item) for item in snvs)
    cnv_facts = [_cnv_fact(item) for item in cnvs]
    findings.extend(cnv_facts)
    findings.extend(_structural_fact(item, "fusion") for item in fusions)
    findings.extend(_structural_fact(item, "translocation") for item in translocations)
    tier_summaries = _tier_summaries(snvs)
    cnv_summaries = _cnv_summaries(cnvs, cnv_facts)
    tier_counts = {
        tier: next(
            (
                int(summary["finding_count"])
                for summary in tier_summaries
                if summary["tier"] == tier
            ),
            0,
        )
        for tier in (1, 2, 3, 4)
    }
    return PreparedReportContext(
        sample={
            "name": str(sample.get("name") or ""),
            "asp_id": str(sample.get("asp_id") or ""),
            "diagnosis_id": str(sample.get("diagnosis_id") or "base"),
            "environment": str(sample.get("environment") or aspc.get("environment") or ""),
            "asp_category": analyte,
            "paired": bool(sample.get("paired")),
            "genome_build": sample.get("genome_build"),
            "analysis_intent": intent,
        },
        asp={
            "asp_id": str(asp.get("asp_id") or sample.get("asp_id") or ""),
            "asp_group": asp.get("asp_group"),
            "display_name": asp.get("display_name"),
            "name": asp.get("name"),
            "covered_genes_count": len(set(asp["covered_genes"]))
            if asp.get("covered_genes") is not None
            else None,
            "asp_category": asp.get("asp_category"),
            "accredited": bool(asp.get("accredited")),
            "germline_genes": list(asp.get("germline_genes") or []),
        },
        aspc={
            "aspc_id": str(aspc.get("aspc_id") or ""),
            "asp_id": str(aspc.get("asp_id") or sample.get("asp_id") or ""),
            "asp_group": aspc.get("asp_group"),
            "asp_category": aspc.get("asp_category"),
            "diagnosis_id": str(aspc.get("diagnosis_id") or sample.get("diagnosis_id") or "base"),
            "environment": str(aspc.get("environment") or sample.get("environment") or ""),
            "reporting": {
                "report_sections": list((aspc.get("reporting") or {}).get("report_sections") or []),
                "language": str((aspc.get("reporting") or {}).get("language") or "sv"),
                "reportable_tiers": (aspc.get("reporting") or {}).get("reportable_tiers", {}),
            },
        },
        applied_gene_lists=[_gene_list_fact(item, asp) for item in applied_gene_lists],
        gene_lists=_gene_scopes(applied_gene_lists, asp),
        findings=findings,
        biomarkers=biomarkers,
        **measurement_facts(biomarkers),
        aggregates={
            "finding_count": len(findings),
            "snv_count": len(snvs),
            "cnv_count": len(cnvs),
            "fusion_count": len(fusions),
            "translocation_count": len(translocations),
            **{f"{key}_count": count for key, count in biomarker_counts(biomarkers).items()},
            "tier_1_count": tier_counts[1],
            "tier_2_count": tier_counts[2],
            "tier_3_count": tier_counts[3],
            "tier_4_count": tier_counts[4],
            "tier_summaries": tier_summaries,
            "cnv_summaries": cnv_summaries,
            "cnv_summary_count": len(cnv_summaries),
            "has_tiered_snvs": bool(tier_summaries),
            "has_reportable_findings": bool(findings or biomarkers),
        },
    )
