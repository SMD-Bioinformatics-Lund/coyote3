"""Pure assay/filter configuration helpers for domain workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.domain.common.sample_filters import (
    normalize_sample_filters,
    sample_filters_from_aspc_filters,
)


def merge_sample_settings_with_assay_config(
    sample_doc: dict[str, Any], assay_config_doc: dict[str, Any]
) -> dict[str, Any]:
    """Merge assay filter defaults into a sample document when no sample filters exist."""
    sample_doc = deepcopy(sample_doc)
    filters_config = assay_config_doc.get("filters", {})
    sample_filters = sample_doc.get("filters", {})
    asp_category = str(sample_doc.get("asp_category") or "dna")
    sample_doc["filters"] = (
        normalize_sample_filters(
            deepcopy(sample_filters),
            asp_category=asp_category,
            analysis_intents=sample_doc.get("analysis_intents"),
            canonical=True,
        )
        if sample_filters
        else sample_filters_from_aspc_filters(
            filters_config,
            asp_category,
            analysis_intents=sample_doc.get("analysis_intents"),
        )
    )
    sample_doc.pop("use_diagnosis_genelist", None)
    return sample_doc


def create_filter_genelist(genelist_dict: dict[str, Any]) -> list[str]:
    """Return active genes from selected genelist documents."""
    filter_genes: list[str] = []
    for _genelist_id, genelist_values in genelist_dict.items():
        if genelist_values.get("is_active", False):
            filter_genes.extend(genelist_values["covered"])
    return list(set(filter_genes))


def get_genes_covered_in_panel(
    genelists: dict[str, Any], assay_panel_doc: dict[str, Any]
) -> dict[str, Any]:
    """Annotate each genelist with covered and uncovered genes for the assay panel."""
    covered_genes_set = set(assay_panel_doc.get("covered_genes", []))
    updated_genelists = {}

    for genelist_id, genelist_values in genelists.items():
        genelist_genes = set(genelist_values.get("genes", []))
        genelist_values = deepcopy(genelist_values)
        genelist_values["covered"] = sorted(genelist_genes.intersection(covered_genes_set))
        genelist_values["uncovered"] = sorted(genelist_genes.difference(covered_genes_set))
        updated_genelists[genelist_id] = genelist_values
    return updated_genelists


def get_assay_genelist_names(genelists: list[dict[str, Any]]) -> list[str]:
    """Return genelist identifiers from configured genelist docs."""
    return [genelist["_id"] for genelist in genelists]


def format_assay_config(
    config: dict[str, Any] | None, schema: dict[str, Any] | None
) -> dict[str, Any]:
    """Format flat ASPC values into filters/reporting sections using a form schema."""
    if config is None:
        config = {}
    if schema is None:
        schema = {}
    config = dict(config)
    sections = schema.get("sections", {})
    filter_section = sections.get("filters", {})
    report_section = sections.get("reporting", {})

    def section_keys_and_defaults(section_obj: Any) -> tuple[list[str], dict[str, Any]]:
        """Extract configurable field names and defaults from a section definition.

        Args:
            section_obj: Mapping or list of field names/definitions; other values yield no fields.

        Returns:
            A pair of ordered keys and defaults, excluding identity keys and the
            filters/reporting containers. Fields without a declared default use None.
        """
        keys = []
        defaults = {}
        skip_keys = {"id_", "id", "_id", "filters", "reporting"}
        if isinstance(section_obj, dict):
            keys = [key for key in section_obj.keys() if key not in skip_keys]
            for key, value in section_obj.items():
                if key in skip_keys:
                    continue
                defaults[key] = value.get("default") if isinstance(value, dict) else None
        elif isinstance(section_obj, list):
            for item in section_obj:
                if isinstance(item, str):
                    if item in skip_keys:
                        continue
                    keys.append(item)
                    defaults[item] = None
                    continue
                if isinstance(item, dict):
                    key = item.get("key") or item.get("id") or item.get("name") or item.get("field")
                    if not key:
                        continue
                    key = str(key)
                    if key in skip_keys:
                        continue
                    keys.append(key)
                    defaults[key] = item.get("default")
        return keys, defaults

    filter_keys, filter_defaults = section_keys_and_defaults(filter_section)
    report_keys, report_defaults = section_keys_and_defaults(report_section)

    existing_filters = config.pop("filters", {})
    existing_report = config.pop("reporting", {})
    if not isinstance(existing_filters, dict):
        existing_filters = {}
    if not isinstance(existing_report, dict):
        existing_report = {}

    # Intent-aware profiles are already canonical. Form schemas may describe
    # individual fields for presentation, but must never flatten or discard
    # the persisted somatic/germline grouping.
    if any(intent in existing_filters for intent in ("somatic", "germline")):
        config["filters"] = existing_filters
        config["reporting"] = existing_report
        return config

    config_filters = {}
    config_report = {}
    for key in filter_keys:
        if key in config:
            config_filters[key] = config.pop(key)
        elif key in existing_filters:
            config_filters[key] = existing_filters.get(key)
        else:
            config_filters[key] = filter_defaults.get(key)

    for key in report_keys:
        if key in config:
            config_report[key] = config.pop(key)
        elif key in existing_report:
            config_report[key] = existing_report.get(key)
        else:
            config_report[key] = report_defaults.get(key)

    for key, value in existing_filters.items():
        config_filters.setdefault(key, value)
    for key, value in existing_report.items():
        config_report.setdefault(key, value)

    for meta_key in ("_id", "id", "id_", "filters"):
        config_filters.pop(meta_key, None)
    for meta_key in ("_id", "id", "id_", "reporting"):
        config_report.pop(meta_key, None)

    config["filters"] = config_filters
    config["reporting"] = config_report
    return config


def format_filters_from_form(form_data: Any, assay_config_schema: dict[str, Any]) -> dict[str, Any]:
    """Normalize submitted assay-filter form data using the ASPC schema sections."""
    if hasattr(form_data, "__iter__") and not isinstance(form_data, dict):
        form_data = {field.name: field.data for field in form_data}

    fields_raw = assay_config_schema.get("sections", {}).get("filters", [])
    fields = []
    if isinstance(fields_raw, dict):
        fields = list(fields_raw.keys())
    elif isinstance(fields_raw, list):
        for item in fields_raw:
            if isinstance(item, str):
                fields.append(item)
            elif isinstance(item, dict):
                key = item.get("key") or item.get("id") or item.get("name") or item.get("field")
                if key:
                    fields.append(str(key))

    filters = {}
    vep_consequences: list[str] = []
    snvlists: list[str] = []
    fusionlists: list[str] = []
    fusion_callers: list[str] = []
    fusion_effects: list[str] = []
    cnveffects: list[str] = []
    prefix_map = {
        "vep_": vep_consequences,
        "snvlist_": snvlists,
        "fusionlist_": fusionlists,
        "fusioncaller_": fusion_callers,
        "fusioneffect_": fusion_effects,
        "cnveffect_": cnveffects,
    }

    for key, value in form_data.items():
        for prefix, target_list in prefix_map.items():
            if isinstance(key, str) and key.startswith(prefix) and value:
                target_list.append(key.replace(prefix, ""))
                break

    for field in fields:
        if field == "vep_consequences":
            filters["vep_consequences"] = vep_consequences
        elif field == "snvlists":
            filters["snvlists"] = snvlists
        elif field == "fusionlists":
            filters["fusionlists"] = fusionlists
        elif field == "fusion_callers":
            filters["fusion_callers"] = fusion_callers
        elif field == "fusion_effects":
            filters["fusion_effects"] = fusion_effects
        elif field == "cnveffects":
            filters["cnveffects"] = cnveffects
        else:
            filters[field] = form_data.get(field)

    return filters


def create_assay_group_map(
    assay_groups_panels: list[dict[str, Any]],
) -> dict[str | None, list[dict[str, Any]]]:
    """Build the admin UI assay-group map from assay panel docs."""
    assay_group_map: dict[str | None, list[dict[str, Any]]] = {}
    for assay in assay_groups_panels:
        group = assay.get("asp_group")
        if group not in assay_group_map:
            assay_group_map[group] = []
        assay_group_map[group].append(
            {
                "asp_id": assay.get("asp_id"),
                "display_name": assay.get("display_name"),
                "asp_category": assay.get("asp_category"),
            }
        )
    return assay_group_map


def get_sample_effective_genes(
    sample: dict[str, Any],
    asp_doc: dict[str, Any],
    checked_gl_dict: dict[str, Any],
    target: str = "snv",
    intent: str = "somatic",
) -> tuple[dict[str, Any], list[str]]:
    """Return selected-list details and the effective genes for one analysis target.

    ``checked_gl_dict`` must contain only IDs selected in the target-specific
    filter section. An ISGL's ``list_type`` controls whether it is valid for
    that target; it does not make a selection in one analysis apply to another.

    Without a target-specific selection, use the assay's validated eligible genes.
    Sequencing family does not grant eligibility. Empty selections and empty
    eligibility remain restrictive; an empty scope selects no findings.
    """
    sample_filters = normalize_sample_filters(
        sample.get("filters"),
        asp_category=str(sample.get("asp_category") or "dna"),
        analysis_intents=sample.get("analysis_intents"),
        intent=intent,
    )
    section = "translocation" if target == "translocation" else target
    target_filters = sample_filters.get(section) or {}
    list_key = {
        "snv": "snvlists",
        "cnv": "cnvlists",
        "fusion": "fusionlists",
        "translocation": "fusionlists",
    }.get(target)
    selected_ids = target_filters.get(list_key, []) if list_key else []
    target_adhoc_genes = target_filters.get("adhoc_genes") or {}
    adhoc_genes_doc = target_adhoc_genes or sample_filters.get("adhoc_genes", {}) or {}
    scoped_adhoc_entries = {}
    if isinstance(target_adhoc_genes, dict) and target_adhoc_genes.get("genes"):
        scoped_adhoc_entries[target] = target_adhoc_genes
    elif {"snv", "cnv", "fusion", "translocation", "all"} & set(adhoc_genes_doc.keys()):
        for scope in ("all", target):
            entry = adhoc_genes_doc.get(scope)
            if isinstance(entry, dict) and entry.get("genes"):
                scoped_adhoc_entries[scope] = entry
    elif adhoc_genes_doc.get("genes"):
        adhoc_list_types = adhoc_genes_doc.get("list_types", ["snv"])
        if isinstance(adhoc_list_types, str):
            adhoc_list_types = [adhoc_list_types]
        adhoc_list_types = {
            str(value).strip().lower() for value in adhoc_list_types if str(value).strip()
        }
        if not adhoc_list_types:
            adhoc_list_types = {"snv"}
        if target == "all" or "all" in adhoc_list_types or target in adhoc_list_types:
            scoped_adhoc_entries[
                target if target in {"snv", "cnv", "fusion", "translocation"} else "all"
            ] = {
                "label": sample_filters.get("adhoc_genes", {}).get("label", "AdHoc genes"),
                "genes": adhoc_genes_doc.get("genes", {}),
            }

    allowed_list_types = {
        "snv": {"snv", "adhoc_snv"},
        "cnv": {"cnv", "adhoc_cnv"},
        "fusion": {"fusion", "adhoc_fusion"},
        "translocation": {"fusion", "adhoc_fusion", "adhoc_translocation"},
    }.get(target)
    target_gl_dict = {}
    for list_id, list_doc in (checked_gl_dict or {}).items():
        raw_types = list_doc.get("list_type") or []
        if isinstance(raw_types, str):
            list_types = {raw_types.strip().lower()}
        else:
            list_types = {str(value).strip().lower() for value in raw_types if str(value).strip()}
        if allowed_list_types is None or list_types & allowed_list_types:
            target_gl_dict[list_id] = dict(list_doc)

    for scope, entry in scoped_adhoc_entries.items():
        adhoc_key = entry.get("label", "AdHoc genes")
        if scope != "all":
            adhoc_key = f"{adhoc_key} ({scope.upper()})"
        target_gl_dict[adhoc_key] = {
            "displayname": adhoc_key,
            "is_active": True,
            "list_type": [f"adhoc_{target}"],
            "genes": entry.get("genes", {}),
            "adhoc": True,
        }

    genes_covered_in_panel = get_genes_covered_in_panel(target_gl_dict, asp_doc)
    effective_filter_genes = create_filter_genelist(genes_covered_in_panel)
    if not target_gl_dict and not selected_ids:
        effective_filter_genes = sorted(
            {
                str(gene).strip()
                for gene in (asp_doc.get("covered_genes") or [])
                if str(gene).strip()
            }
        )
    return genes_covered_in_panel, effective_filter_genes


def get_case_and_control_sample_ids(sample_doc: dict[str, Any]) -> dict[str, str]:
    """Extract populated case and control identifiers from a sample.

    Args:
        sample_doc: Document with optional case_id and control_id values.

    Returns:
        A new dictionary with case and/or control keys for truthy identifiers.
        Missing, null, and other falsy identifiers are omitted.
    """
    sample_ids = {}
    case = sample_doc.get("case_id")
    control = sample_doc.get("control_id")
    if case:
        sample_ids["case"] = case
    if control:
        sample_ids["control"] = control
    return sample_ids
