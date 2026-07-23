"""Restricted Jinja environment for clinical reporting rules."""

from __future__ import annotations

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment

from api.domain.common.reporting import nl_join, nl_num

_STANDARD_TIER_SUMMARY_PHRASES = {
    "first_prefix": "Vid analysen finner man ",
    "next_prefix": "Vidare ses ",
    "final_prefix": "Slutligen ses ",
    "number_gender": "n",
    "finding_singular": "variant",
    "finding_plural_suffix": "er",
    "tier_labels": {
        "1": " av stark klinisk signifikans (Tier I)",
        "2": " av potentiell klinisk signifikans (Tier II)",
        "3": " av oklar klinisk signifikans (Tier III)",
    },
    "single_gene_prefix": " i ",
    "multiple_gene_prefix": ": ",
    "gene_count_joiner": " i ",
    "value_open": " (",
    "value_close": ")",
    "read_context_prefix": "i ",
    "read_context_suffix": " av läsningarna",
    "multiple_gene_read_prefix_tiers": [1],
    "respectively": "respektive",
    "gene_joiner": "och",
    "sentence_suffix": ". ",
    "single_gene_always_read_context": False,
}

_HEMA_TIER_SUMMARY_PHRASES = {
    **_STANDARD_TIER_SUMMARY_PHRASES,
    "finding_singular": "mutation",
    "multiple_gene_read_prefix_tiers": [1, 2, 3],
    "single_gene_always_read_context": True,
}


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
    return _render_tier_summary(groups, _STANDARD_TIER_SUMMARY_PHRASES)


def _hema_tier_summary(groups: list[dict]) -> str:
    """Render the established GMS-HEM tier-summary wording."""
    return _render_tier_summary(groups, _HEMA_TIER_SUMMARY_PHRASES)


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
    environment.filters["tier_summary"] = _tier_summary
    environment.filters["hema_tier_summary"] = _hema_tier_summary
    return environment
