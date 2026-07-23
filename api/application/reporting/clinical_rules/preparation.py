"""Convert already filtered report data into the stable rule fact contract."""

from __future__ import annotations

from typing import Any, Literal

from api.application.reporting.clinical_rules.facts import PreparedReportContext


def _genotype_vaf(variant: dict[str, Any], genotype_type: str) -> float | None:
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
    return (variant.get("INFO") or {}).get("selected_CSQ") or {}


def _snv_fact(variant: dict[str, Any]) -> dict[str, Any]:
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
        "hgvsc": csq.get("HGVSc") or variant.get("cdna") or variant.get("hgvsc"),
        "hgvsp": csq.get("HGVSp") or variant.get("variant") or variant.get("hgvsp"),
        "variant_type": variant.get("variant_class") or variant.get("var_type"),
    }


def _cnv_fact(cnv: dict[str, Any]) -> dict[str, Any]:
    genes = [
        str(gene.get("gene"))
        for gene in cnv.get("genes", []) or []
        if isinstance(gene, dict) and gene.get("gene")
    ]
    ratio = cnv.get("ratio")
    effect = cnv.get("effect")
    if not effect and isinstance(ratio, (int, float)):
        effect = "gain" if ratio > 0 else "loss"
    return {
        "kind": "cnv",
        "gene": genes[0] if len(genes) == 1 else None,
        "genes": genes,
        "tier": (cnv.get("classification") or {}).get("class"),
        "cnv_effect": effect,
        "variant_type": "cnv",
    }


def _structural_fact(finding: dict[str, Any], kind: str) -> dict[str, Any]:
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
    return {
        "kind": kind,
        "gene": None,
        "genes": [gene for gene in (gene_1, gene_2) if gene],
        "tier": (finding.get("classification") or {}).get("class"),
        "fusion_gene_1": gene_1,
        "fusion_gene_2": gene_2,
        "variant_type": kind,
    }


def _gene_list_fact(gene_list: dict[str, Any]) -> dict[str, Any]:
    list_type = gene_list.get("list_type") or []
    if isinstance(list_type, str):
        list_type = [list_type]
    return {
        "isgl_id": str(gene_list.get("isgl_id") or ""),
        "version": gene_list.get("version"),
        "list_type": list(list_type),
        "selected_for": list(gene_list.get("selected_for") or []),
        "genes": list(gene_list.get("genes") or []),
        "germline_genes": list(gene_list.get("germline_genes") or []),
        "adhoc": bool(gene_list.get("adhoc")),
    }


def prepare_report_context(
    *,
    sample: dict[str, Any],
    asp: dict[str, Any],
    aspc: dict[str, Any],
    analyte: Literal["dna", "rna"],
    applied_gene_lists: list[dict[str, Any]],
    report_sections_data: dict[str, Any],
) -> PreparedReportContext:
    """Build facts from the exact filtered data used by report rendering."""
    findings: list[dict[str, Any]] = []
    snvs = list(report_sections_data.get("snvs") or [])
    cnvs = list(report_sections_data.get("cnvs") or [])
    fusions = list(report_sections_data.get("fusions") or [])
    translocations = list(report_sections_data.get("translocs") or [])
    biomarkers = list(report_sections_data.get("biomarkers") or [])
    findings.extend(_snv_fact(item) for item in snvs)
    findings.extend(_cnv_fact(item) for item in cnvs)
    findings.extend(_structural_fact(item, "fusion") for item in fusions)
    findings.extend(_structural_fact(item, "translocation") for item in translocations)
    tier_counts = {
        tier: sum(1 for finding in findings if finding.get("tier") == tier) for tier in (1, 2, 3)
    }
    return PreparedReportContext(
        sample={
            "name": str(sample.get("name") or ""),
            "assay": str(sample.get("assay") or ""),
            "subpanel_id": str(sample.get("subpanel_id") or aspc.get("subpanel_id") or "base"),
            "profile": str(sample.get("profile") or aspc.get("environment") or ""),
            "omics_layer": analyte,
            "paired": bool(sample.get("paired")),
            "genome_build": sample.get("genome_build"),
        },
        asp={
            "asp_id": str(asp.get("asp_id") or sample.get("assay") or ""),
            "asp_group": asp.get("asp_group"),
            "asp_category": asp.get("asp_category"),
            "accredited": bool(asp.get("accredited")),
        },
        aspc={
            "aspc_id": str(aspc.get("aspc_id") or ""),
            "asp_id": str(aspc.get("asp_id") or sample.get("assay") or ""),
            "asp_group": aspc.get("asp_group"),
            "asp_category": aspc.get("asp_category"),
            "subpanel_id": str(aspc.get("subpanel_id") or sample.get("subpanel_id") or "base"),
            "environment": str(aspc.get("environment") or sample.get("profile") or ""),
            "reporting": {
                "analysis": list((aspc.get("reporting") or {}).get("analysis") or []),
                "report_sections": list((aspc.get("reporting") or {}).get("report_sections") or []),
            },
        },
        applied_gene_lists=[_gene_list_fact(item) for item in applied_gene_lists],
        findings=findings,
        biomarkers=biomarkers,
        aggregates={
            "finding_count": len(findings),
            "snv_count": len(snvs),
            "cnv_count": len(cnvs),
            "fusion_count": len(fusions),
            "translocation_count": len(translocations),
            "biomarker_count": len(biomarkers),
            "tier_1_count": tier_counts[1],
            "tier_2_count": tier_counts[2],
            "tier_3_count": tier_counts[3],
            "has_reportable_findings": bool(findings or biomarkers),
        },
    )
