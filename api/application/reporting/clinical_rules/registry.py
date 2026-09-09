"""Typed, allowlisted facts exposed to clinical reporting rules."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

FactKind = Literal["boolean", "integer", "number", "string", "string_list", "object_list"]


class ClinicalFactDefinition(BaseModel):
    """Immutable fact metadata defining rule operators, scopes, and editor hints."""

    model_config = ConfigDict(frozen=True)

    path: str
    label: str
    group: str
    kind: FactKind
    operators: tuple[str, ...]
    scopes: tuple[str, ...] = ("once", "each_finding", "each_item")
    unit: str | None = None
    description: str = ""
    value_options: tuple[str, ...] = ()
    value_format: Literal["gene", "integer", "number", "text"] = "text"


def _fact(
    path: str,
    label: str,
    group: str,
    kind: FactKind,
    operators: tuple[str, ...],
    scopes: tuple[str, ...] = ("once", "each_finding", "each_item"),
    unit: str | None = None,
    value_options: tuple[str, ...] = (),
    value_format: Literal["gene", "integer", "number", "text"] = "text",
) -> ClinicalFactDefinition:
    """Construct an allowlisted fact definition for the rule editor.

    Args:
        path: Dotted lookup path in prepared facts.
        label: Display name for the fact.
        group: Editor grouping label.
        kind: Fact value category.
        operators: Permitted predicate operator names.
        scopes: Evaluation modes in which the fact is available; defaults to all.
        unit: Display unit, or None for unitless facts.
        value_options: Suggested fixed values; empty allows no fixed suggestions.
        value_format: Editor input format, defaulting to text.

    Returns:
        Frozen fact metadata.
    """
    return ClinicalFactDefinition(
        path=path,
        label=label,
        group=group,
        kind=kind,
        operators=operators,
        scopes=scopes,
        unit=unit,
        value_options=value_options,
        value_format=value_format,
    )


_EQUALITY = ("eq", "ne", "in", "not_in", "exists", "is_unknown")
_NUMBER = (
    "eq",
    "ne",
    "in",
    "not_in",
    "gt",
    "gte",
    "lt",
    "lte",
    "between",
    "exists",
    "is_unknown",
)
_LIST = ("contains", "overlaps", "is_empty", "exists", "is_unknown")


FACT_CATALOG: tuple[ClinicalFactDefinition, ...] = (
    _fact("sample.asp_id", "Assay", "Sample", "string", _EQUALITY),
    _fact("sample.subpanel_id", "Subpanel", "Sample", "string", _EQUALITY),
    _fact("sample.environment", "Environment", "Sample", "string", _EQUALITY),
    _fact(
        "sample.omics_layer",
        "Omics layer",
        "Sample",
        "string",
        _EQUALITY,
        value_options=("dna", "rna"),
    ),
    _fact(
        "sample.analysis_intent",
        "Analysis intent",
        "Sample",
        "string",
        _EQUALITY,
        value_options=("somatic", "germline"),
    ),
    _fact("sample.paired", "Paired analysis", "Sample", "boolean", _EQUALITY),
    _fact(
        "sample.genome_build",
        "Genome build",
        "Sample",
        "string",
        _EQUALITY,
        value_options=("GRCh37", "GRCh38"),
    ),
    _fact("asp.asp_group", "Assay group", "Assay", "string", _EQUALITY),
    _fact(
        "asp.asp_category",
        "Assay category",
        "Assay",
        "string",
        _EQUALITY,
        value_options=("dna", "rna"),
    ),
    _fact("asp.accredited", "Accredited", "Assay", "boolean", _EQUALITY),
    _fact("asp.germline_genes", "Germline genes", "Assay", "string_list", _LIST),
    _fact(
        "aspc.reporting.report_sections", "Report analyses", "Configuration", "string_list", _LIST
    ),
    _fact(
        "finding.kind",
        "Finding type",
        "Finding",
        "string",
        _EQUALITY,
        ("each_finding",),
        value_options=("snv", "cnv", "fusion", "translocation", "biomarker"),
    ),
    _fact(
        "finding.gene",
        "Gene",
        "Finding",
        "string",
        _EQUALITY,
        ("each_finding",),
        value_format="gene",
    ),
    _fact(
        "finding.genes",
        "Genes",
        "Finding",
        "string_list",
        _LIST,
        ("each_finding",),
        value_format="gene",
    ),
    _fact("finding.tier", "Tier", "Finding", "integer", _NUMBER, ("each_finding",)),
    _fact("finding.exon", "Exon", "Finding", "string_list", _LIST, ("each_finding",)),
    _fact("finding.intron", "Intron", "Finding", "string_list", _LIST, ("each_finding",)),
    _fact(
        "finding.case_vaf_percent",
        "Case VAF",
        "Finding",
        "number",
        _NUMBER,
        ("each_finding",),
        "%",
    ),
    _fact(
        "finding.control_vaf_percent",
        "Control VAF",
        "Finding",
        "number",
        _NUMBER,
        ("each_finding",),
        "%",
    ),
    _fact("finding.consequence", "Consequence", "Finding", "string_list", _LIST, ("each_finding",)),
    _fact("finding.hgvsc", "HGVS.c", "Finding", "string", _EQUALITY, ("each_finding",)),
    _fact("finding.hgvsp", "HGVS.p", "Finding", "string", _EQUALITY, ("each_finding",)),
    _fact(
        "finding.cnv_effect",
        "Copy-number effect",
        "Finding",
        "string",
        _EQUALITY,
        ("each_finding",),
        value_options=("gain", "loss"),
    ),
    _fact(
        "finding.fusion_gene_1",
        "First fusion gene",
        "Finding",
        "string",
        _EQUALITY,
        ("each_finding",),
        value_format="gene",
    ),
    _fact(
        "finding.fusion_gene_2",
        "Second fusion gene",
        "Finding",
        "string",
        _EQUALITY,
        ("each_finding",),
        value_format="gene",
    ),
    _fact("aggregates.finding_count", "Finding count", "Result", "integer", _NUMBER),
    _fact("aggregates.snv_count", "SNV count", "Result", "integer", _NUMBER),
    _fact("aggregates.cnv_count", "CNV count", "Result", "integer", _NUMBER),
    _fact("aggregates.fusion_count", "Fusion count", "Result", "integer", _NUMBER),
    _fact("aggregates.translocation_count", "Translocation count", "Result", "integer", _NUMBER),
    _fact("aggregates.biomarker_count", "Biomarker count", "Result", "integer", _NUMBER),
    _fact("aggregates.has_tiered_snvs", "Has tiered SNVs", "Result", "boolean", _EQUALITY),
    _fact(
        "aggregates.has_reportable_findings",
        "Has reportable findings",
        "Result",
        "boolean",
        _EQUALITY,
    ),
    _fact("item.kind", "Item type", "Current item", "string", _EQUALITY, ("each_item",)),
    _fact(
        "item.gene",
        "Item gene",
        "Current item",
        "string",
        _EQUALITY,
        ("each_item",),
        value_format="gene",
    ),
    _fact(
        "item.genes",
        "Item genes",
        "Current item",
        "string_list",
        _LIST,
        ("each_item",),
        value_format="gene",
    ),
    _fact("item.tier", "Item tier", "Current item", "integer", _NUMBER, ("each_item",)),
)

FACTS_BY_PATH = {definition.path: definition for definition in FACT_CATALOG}


def validate_fact_path(path: str, *, scope: str | None = None) -> ClinicalFactDefinition:
    """Require a registered fact path and, optionally, a supported evaluation scope.

    Args:
        path: Exact dotted path in the fact catalog.
        scope: Evaluation mode to check; None or an empty string skips this check.

    Returns:
        The registered fact definition.

    Raises:
        ValueError: The path is unregistered or unavailable in the requested scope.
    """
    definition = FACTS_BY_PATH.get(path)
    if definition is None:
        raise ValueError(
            f"Unsupported clinical rule fact '{path}'. Add a typed prepared-context fact "
            "and tests before using it in a rule."
        )
    if scope and scope not in definition.scopes:
        raise ValueError(f"Fact '{path}' is unavailable in {scope} evaluation")
    return definition


def fact_catalog_payload() -> list[dict[str, object]]:
    """Serialize the allowlisted facts for the rule editor.

    Returns:
        JSON-compatible fact definitions in catalog order.
    """
    return [definition.model_dump(mode="json") for definition in FACT_CATALOG]
