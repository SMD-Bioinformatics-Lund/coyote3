"""Deterministic renderers for structured clinical rule output."""

from __future__ import annotations

from typing import Any

from api.domain.common.reporting import nl_join, nl_num


def _required(mapping: dict[str, Any], key: str) -> Any:
    if key not in mapping:
        raise ValueError(f"Clinical rule terminology is missing '{key}'")
    return mapping[key]


def render_tier_summary(groups: list[dict[str, Any]], terminology: dict[str, Any]) -> str:
    """Compose prepared tier groups using rule-set-owned language."""
    phrases = _required(terminology, "tier_summary")
    text = ""
    first_gene_context = True
    for index, group in enumerate(groups):
        if index == 0:
            text += _required(phrases, "first_prefix")
        elif index == len(groups) - 1 and len(groups) == 3:
            text += _required(phrases, "final_prefix")
        else:
            text += _required(phrases, "next_prefix")

        finding_count = int(group["finding_count"])
        text += str(nl_num(finding_count, _required(phrases, "number_gender")))
        text += " " + _required(phrases, "finding_singular")
        if finding_count > 1:
            text += _required(phrases, "finding_plural_suffix")
        text += _required(phrases, "tier_labels")[str(group["tier"])]

        genes = group["genes"]
        if len(genes) == 1:
            gene = genes[0]
            include_context = bool(
                phrases.get("single_gene_always_read_context", False) or first_gene_context
            )
            text += _required(phrases, "single_gene_prefix") + gene["gene"]
            text += _required(phrases, "value_open")
            if include_context:
                text += _required(phrases, "read_context_prefix")
            text += nl_join(gene["vaf_percentages"], _required(phrases, "respectively"))
            if include_context:
                text += _required(phrases, "read_context_suffix")
            text += _required(phrases, "value_close")
            first_gene_context = False
        elif len(genes) > 1:
            text += _required(phrases, "multiple_gene_prefix")
            gene_texts: list[str] = []
            for gene in genes:
                gene_text = (
                    str(nl_num(len(gene["vaf_percentages"]), _required(phrases, "number_gender")))
                    + _required(phrases, "gene_count_joiner")
                    + gene["gene"]
                    + _required(phrases, "value_open")
                )
                prefix_tiers = phrases.get("multiple_gene_read_prefix_tiers", [1, 2, 3])
                if first_gene_context and group["tier"] in prefix_tiers:
                    gene_text += _required(phrases, "read_context_prefix")
                gene_text += nl_join(gene["vaf_percentages"], _required(phrases, "respectively"))
                if first_gene_context:
                    gene_text += _required(phrases, "read_context_suffix")
                gene_text += _required(phrases, "value_close")
                gene_texts.append(gene_text)
                first_gene_context = False
            text += nl_join(gene_texts, _required(phrases, "gene_joiner"))
        text += _required(phrases, "sentence_suffix")
    return text


def render_dna_report_intro(scope: dict[str, Any], terminology: dict[str, Any]) -> str:
    """Render the selected DNA gene-list scope using rule-set terminology."""
    terms = _required(terminology, "dna_report_intro")
    sample = scope["sample"]
    asp = scope["asp"]
    selected_lists = [
        item for item in scope["applied_gene_lists"] if "snv" in (item.get("selected_for") or [])
    ]
    text = str(_required(terms, "base_text"))
    if sample.get("paired"):
        text += str(_required(terms, "paired_text"))
    if not selected_lists:
        return text

    genes = list(
        dict.fromkeys(
            str(gene).strip()
            for item in selected_lists
            for gene in (item.get("genes") or [])
            if str(gene).strip()
        )
    )
    names = [str(item.get("isgl_id") or "").upper() for item in selected_lists]
    names = [name for name in names if name]
    if not names:
        return text
    list_label = (
        _required(terms, "list_singular") if len(names) == 1 else _required(terms, "list_plural")
    )
    text += str(list_label) + nl_join(names, _required(terms, "conjunction"))
    if len(genes) <= int(terms.get("gene_list_limit", 20)):
        gene_label = (
            _required(terms, "gene_singular")
            if len(genes) == 1
            else _required(terms, "gene_plural")
        )
        text += str(gene_label) + nl_join(genes, _required(terms, "gene_conjunction"))
    else:
        text += str(_required(terms, "gene_count_prefix")) + str(len(genes))
        text += str(_required(terms, "gene_count_suffix"))
    text += str(_required(terms, "list_suffix"))

    if sample.get("paired"):
        germline = {str(gene).strip() for gene in asp.get("germline_genes") or []}
        selected_germline = [gene for gene in genes if gene in germline]
        if selected_germline:
            text += str(_required(terms, "germline_prefix"))
            text += nl_join(selected_germline, _required(terms, "germline_conjunction"))
            text += str(_required(terms, "germline_suffix"))
    return text


def render_fusion_summary(findings: list[dict[str, Any]], terminology: dict[str, Any]) -> str:
    """Render reviewed fusions using rule-set-owned sentence fragments."""
    terms = _required(terminology, "fusion_summary")
    tier_labels = _required(terms, "tier_labels")
    reportable = [
        finding
        for finding in findings
        if finding.get("kind") == "fusion"
        and str(finding.get("tier")) in tier_labels
        and finding.get("fusion_gene_1")
        and finding.get("fusion_gene_2")
    ]
    paragraphs: list[str] = []
    for index, finding in enumerate(reportable):
        gene_1 = str(finding["fusion_gene_1"])
        gene_2 = str(finding["fusion_gene_2"])
        lead = _required(terms, "first_lead") if index == 0 else _required(terms, "next_lead")
        text = (
            str(lead)
            + str(_required(terms, "tier_prefix"))
            + str(tier_labels[str(finding["tier"])])
            + str(_required(terms, "genes_prefix"))
            + gene_1
            + str(_required(terms, "gene_joiner"))
            + gene_2
            + str(_required(terms, "sentence_suffix"))
        )
        breakpoint_1 = finding.get("fusion_breakpoint_1")
        breakpoint_2 = finding.get("fusion_breakpoint_2")
        if breakpoint_1 and breakpoint_2:
            text += (
                str(_required(terms, "breakpoint_prefix"))
                + str(breakpoint_1)
                + str(_required(terms, "breakpoint_joiner"))
                + str(breakpoint_2)
                + str(_required(terms, "breakpoint_suffix"))
            )
        paragraphs.append(text)
        pairs = finding.get("fusion_spanning_pairs")
        reads = finding.get("fusion_spanning_reads")
        if pairs is not None and reads is not None:
            paragraphs.append(
                str(_required(terms, "support_prefix"))
                + str(pairs)
                + str(_required(terms, "support_middle"))
                + str(reads)
                + str(_required(terms, "support_genes_prefix"))
                + gene_1
                + str(_required(terms, "support_gene_joiner"))
                + gene_2
                + str(_required(terms, "support_suffix"))
            )
        annotation = str(finding.get("fusion_annotation") or "").strip()
        if annotation:
            paragraphs.append(annotation)
    return "\n\n" + "\n\n".join(paragraphs) + "\n\n" if paragraphs else "\n\n"


def render_named(
    name: str, *, source: Any, scope: dict[str, Any], terminology: dict[str, Any]
) -> str:
    if name == "dna_report_intro":
        return render_dna_report_intro(scope, terminology)
    if name == "tier_summary":
        return render_tier_summary(list(source or []), terminology)
    if name == "fusion_summary":
        return render_fusion_summary(list(source or []), terminology)
    raise ValueError(f"Unsupported clinical renderer '{name}'")
