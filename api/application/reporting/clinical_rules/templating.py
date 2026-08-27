"""Restricted Jinja environment for clinical reporting rules."""

from __future__ import annotations

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from api.domain.common.reporting import (
    STANDARD_TIER_SUMMARY_PHRASES,
    TIER_SUMMARY_LABELS,
    nl_join,
    nl_num,
)


def _render_tier_summary(groups: list[dict], phrases: dict) -> str:
    """Compose prepared tier groups using one approved Swedish wording style."""
    text = ""
    first_gene_context = True
    for index, group in enumerate(groups):
        if index == 0:
            text += phrases["first_prefix"]
        elif index == len(groups) - 1 and len(groups) == 3:
            text += phrases["final_prefix"]
        else:
            text += phrases["next_prefix"]

        finding_count = int(group["finding_count"])
        text += nl_num(finding_count, phrases["number_gender"])
        text += " " + phrases["finding_singular"]
        if finding_count > 1:
            text += phrases["finding_plural_suffix"]
        text += phrases["tier_labels"][str(group["tier"])]

        genes = group["genes"]
        if len(genes) == 1:
            gene = genes[0]
            include_read_context = bool(
                phrases.get("single_gene_always_read_context", False) or first_gene_context
            )
            text += phrases["single_gene_prefix"] + gene["gene"] + phrases["value_open"]
            if include_read_context:
                text += phrases["read_context_prefix"]
            text += nl_join(gene["vaf_percentages"], phrases["respectively"])
            if include_read_context:
                text += phrases["read_context_suffix"]
            text += phrases["value_close"]
            first_gene_context = False
        elif len(genes) > 1:
            text += phrases["multiple_gene_prefix"]
            gene_texts: list[str] = []
            for gene in genes:
                gene_text = (
                    str(nl_num(len(gene["vaf_percentages"]), phrases["number_gender"]))
                    + phrases["gene_count_joiner"]
                    + gene["gene"]
                    + phrases["value_open"]
                )
                prefix_tiers = phrases.get("multiple_gene_read_prefix_tiers", [1, 2, 3])
                if first_gene_context and group["tier"] in prefix_tiers:
                    gene_text += phrases["read_context_prefix"]
                gene_text += nl_join(gene["vaf_percentages"], phrases["respectively"])
                if first_gene_context:
                    gene_text += phrases["read_context_suffix"]
                gene_text += phrases["value_close"]
                gene_texts.append(gene_text)
                first_gene_context = False
            text += nl_join(gene_texts, phrases["gene_joiner"])
        text += phrases["sentence_suffix"]
    return text


def _tier_summary(groups: list[dict]) -> str:
    """Render the standard Swedish tier-summary wording."""
    return _render_tier_summary(groups, STANDARD_TIER_SUMMARY_PHRASES)


_FUSION_TIER_LABELS = {
    tier: label.removeprefix(" av ") for tier, label in TIER_SUMMARY_LABELS.items()
}


def _fusion_summary(findings: list[dict]) -> str:
    """Render reviewed RNA fusions using the established clinical wording."""
    reportable = [
        finding
        for finding in findings
        if finding.get("kind") == "fusion"
        and finding.get("tier") in _FUSION_TIER_LABELS
        and finding.get("fusion_gene_1")
        and finding.get("fusion_gene_2")
    ]
    paragraphs: list[str] = []
    for index, finding in enumerate(reportable):
        gene_1 = str(finding["fusion_gene_1"])
        gene_2 = str(finding["fusion_gene_2"])
        lead = "Vid analysen finner man" if index == 0 else "Vidare finner man"
        finding_text = (
            f"{lead} en fusion av {_FUSION_TIER_LABELS[int(finding['tier'])]} "
            f"mellan generna {gene_1} och {gene_2}."
        )
        breakpoint_1 = finding.get("fusion_breakpoint_1")
        breakpoint_2 = finding.get("fusion_breakpoint_2")
        if breakpoint_1 and breakpoint_2:
            finding_text += (
                " De genomiska positionerna för brottspunkterna är "
                f"{breakpoint_1} och {breakpoint_2}."
            )
        paragraphs.append(finding_text)

        pairs = finding.get("fusion_spanning_pairs")
        reads = finding.get("fusion_spanning_reads")
        if pairs is not None and reads is not None:
            paragraphs.append(
                "Rearrangemanget är påvisat efter manuell eftergranskning av data där "
                f"{pairs} läspar, och {reads} läsningar direkt över brottspunkten ger stöd "
                f"för en {gene_1}::{gene_2}-genfusion."
            )
        annotation = str(finding.get("fusion_annotation") or "").strip()
        if annotation:
            paragraphs.append(annotation)
    if not paragraphs:
        return "\n\n"
    return "\n\n" + "\n\n".join(paragraphs) + "\n\n"


def _dna_report_intro(
    base_text: str,
    sample: dict,
    asp: dict,
    applied_gene_lists: list[dict],
) -> str:
    """Render a DNA introduction from the actual selected SNV gene-list scope."""
    text = str(base_text or "")
    if sample.get("paired"):
        text += "Analysen avser somatiska mutationer (hudbiopsi har använts som kontrollmaterial). "

    selected_lists = [
        gene_list
        for gene_list in applied_gene_lists
        if "snv" in (gene_list.get("selected_for") or [])
    ]
    if not selected_lists:
        return text

    selected_genes = list(
        dict.fromkeys(
            str(gene).strip()
            for gene_list in selected_lists
            for gene in (gene_list.get("genes") or [])
            if str(gene).strip()
        )
    )
    selected_list_names = [
        str(gene_list.get("isgl_id") or "").upper() for gene_list in selected_lists
    ]
    selected_list_names = [name for name in selected_list_names if name]
    if not selected_list_names:
        return text

    list_suffix = "an" if len(selected_list_names) == 1 else "orna"
    if len(selected_genes) <= 20:
        gene_label = "genen" if len(selected_genes) == 1 else "generna"
        gene_detail = f" som innefattar {gene_label}: {nl_join(selected_genes, 'samt')}"
    else:
        gene_detail = f" som innefattar {len(selected_genes)} gener"
    text += f"Analysen omfattar genlist{list_suffix}: {nl_join(selected_list_names, 'samt')}{gene_detail}. "

    if sample.get("paired"):
        germline_genes = {str(gene).strip() for gene in asp.get("germline_genes") or []}
        selected_germline = [gene for gene in selected_genes if gene in germline_genes]
        if selected_germline:
            text += f"För {nl_join(selected_germline, 'samt')} undersöks även konstitutionella mutationer."
    return text


def clinical_template_environment() -> SandboxedEnvironment:
    """Return the shared, deliberately small clinical template environment."""
    environment = SandboxedEnvironment(
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    environment.globals.clear()
    environment.filters = {
        name: environment.filters[name]
        for name in ("default", "join", "length", "lower", "round", "upper")
    }
    environment.filters["dna_report_intro"] = _dna_report_intro
    environment.filters["fusion_summary"] = _fusion_summary
    environment.filters["tier_summary"] = _tier_summary
    return environment
