"""Assay/filter configuration helpers shared across API workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.runtime_state import app


def assay_config(assay_name: str | None = None) -> dict:
    conf = app.config.get("ASSAYS")
    if conf is None:
        return {}
    if assay_name is not None:
        conf = conf.get(assay_name)
    return deepcopy(conf)


def get_group_parameters(group: str) -> dict:
    conf = app.config.get("GROUP_CONFIGS")
    if conf is not None:
        return deepcopy(conf.get(group))
    return {}


def table_config() -> dict:
    return deepcopy(app.config.get("TABLE"))


def cutoff_config(assay_name: str, sample_type: str | None = None) -> dict:
    conf = app.config.get("CUTOFFS")
    if conf is None:
        return {}
    try:
        conf = conf[assay_name]
        if sample_type is not None:
            conf = conf.get(sample_type)
    except KeyError:
        return {}
    return deepcopy(conf)


def assay_info_vars(assay_name: str) -> list:
    return assay_config(assay_name).get("sample_info")


def assay_qc_vars(assay_name: str) -> list:
    return assay_config(assay_name).get("sample_qc")


def assays_in_assay_group(assay_name: str) -> list:
    return assay_config(assay_name).get("include_assays")


def has_subtypes(assay_name: str) -> bool:
    return "subtypes" in assay_config(assay_name)


def get_sample_subtypes(assay_name: str) -> list:
    subtypes = assay_config(assay_name).get("subtypes", {})
    return subtypes.get("subtype_names", None)


def subtype_id_var(assay_name: str) -> list | None:
    if not has_subtypes(assay_name):
        return None
    assay_conf = assay_config(assay_name)
    if "subtype_id_col" not in assay_conf:
        config_path = app.config.get("PATH_ASSAY_CONFIG")
        raise AttributeError(
            f"Error in assay config: {config_path}. "
            "subtypes enabled but no subtype_id_col "
            f"defined for {assay_name}."
        )
    return assay_conf["subtype_id_col"]


def assay_exists(assay_name: str) -> bool:
    return assay_name in assay_config()


def assay_names_for_db_query(assay_category_name: str) -> list:
    assay_names = assay_config(assay_category_name.removesuffix("_restored")).get("include_assays")
    if assay_category_name.endswith("_restored"):
        assay_names = [f"{assay_name}_restored" for assay_name in assay_names]
    return assay_names


def merge_sample_settings_with_assay_config(sample_doc: dict, assay_config_doc: dict) -> dict:
    filters_config = assay_config_doc.get("filters", {})
    sample_filters = sample_doc.get("filters", {})
    if not sample_filters:
        sample_doc["filters"] = deepcopy(filters_config)
    else:
        sample_doc["filters"] = deepcopy(sample_filters)
    sample_doc.pop("use_diagnosis_genelist", None)
    return sample_doc


def get_fusions_settings(sample: dict, settings: dict) -> dict:
    return {
        "min_spanreads": int(
            sample.get("filter_min_spanreads", settings.get("default_spanreads", 0))
        ),
        "min_spanpairs": int(
            sample.get("filter_min_spanpairs", settings.get("default_spanpairs", 0))
        ),
    }


def create_filter_genelist(genelist_dict: dict) -> list:
    filter_genes = []
    for _genelist_id, genelist_values in genelist_dict.items():
        if genelist_values.get("is_active", False):
            filter_genes.extend(genelist_values["covered"])
    return list(set(filter_genes))


def get_genes_covered_in_panel(genelists: dict, assay_panel_doc: dict) -> dict:
    covered_genes_set = set(assay_panel_doc.get("covered_genes", []))
    updated_genelists = {}
    asp_family = assay_panel_doc.get("asp_family", "").lower()

    for genelist_id, genelist_values in genelists.items():
        genelist_genes = set(genelist_values.get("genes", []))
        if asp_family in ["wgs", "wts"]:
            genelist_values["covered"] = sorted(genelist_genes)
            genelist_values["uncovered"] = []
        else:
            genelist_values["covered"] = sorted(
                list(genelist_genes.intersection(covered_genes_set))
            )
            genelist_values["uncovered"] = sorted(
                list(genelist_genes.difference(covered_genes_set))
            )
        updated_genelists[genelist_id] = genelist_values
    return updated_genelists


def get_assay_genelist_names(genelists: list[dict]) -> list[str]:
    return [genelist["_id"] for genelist in genelists]


def format_assay_config(config: dict, schema: dict) -> dict:
    if config is None:
        config = {}
    if schema is None:
        schema = {}
    sections = schema.get("sections", {})
    filter_section = sections.get("filters", {})
    report_section = sections.get("reporting", {})

    def section_keys_and_defaults(section_obj):
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


def format_filters_from_form(form_data: Any, assay_config_schema: dict) -> dict:
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
    vep_consequences, genelists, fusionlists, fusion_callers, fusion_effects, cnveffects = (
        [],
        [],
        [],
        [],
        [],
        [],
    )

    prefix_map = {
        "vep_": vep_consequences,
        "genelist_": genelists,
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
        elif field == "genelists":
            filters["genelists"] = genelists
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


def create_assay_group_map(assay_groups_panels: list) -> dict:
    assay_group_map = {}
    for assay in assay_groups_panels:
        group = assay.get("asp_group")
        if group not in assay_group_map:
            assay_group_map[group] = []
        assay_group_map[group].append(
            {
                "assay_name": assay.get("assay_name"),
                "display_name": assay.get("display_name"),
                "asp_category": assay.get("asp_category"),
            }
        )
    return assay_group_map


def get_case_and_control_sample_ids(sample_doc: dict) -> dict:
    sample_ids = {}
    case = sample_doc.get("case_id")
    control = sample_doc.get("control_id")
    if case:
        sample_ids["case"] = case
    if control:
        sample_ids["control"] = control
    return sample_ids


def get_sample_effective_genes(
    sample: dict, asp_doc: dict, checked_gl_dict: dict, target: str = "snv"
) -> tuple:
    sample_filters = sample.get("filters", {})
    adhoc_genes_doc = sample_filters.get("adhoc_genes", {}) or {}
    scoped_adhoc_entries = {}
    if {"snv", "cnv", "fusion", "all"} & set(adhoc_genes_doc.keys()):
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
            scoped_adhoc_entries[target if target in {"snv", "cnv", "fusion"} else "all"] = {
                "label": sample_filters.get("adhoc_genes", {}).get("label", "AdHoc genes"),
                "genes": adhoc_genes_doc.get("genes", {}),
            }

    for scope, entry in scoped_adhoc_entries.items():
        adhoc_key = entry.get("label", "AdHoc genes")
        if scope != "all":
            adhoc_key = f"{adhoc_key} ({scope.upper()})"
        checked_gl_dict[adhoc_key] = {
            "displayname": adhoc_key,
            "is_active": True,
            "genes": entry.get("genes", {}),
            "adhoc": True,
        }

    genes_covered_in_panel = get_genes_covered_in_panel(checked_gl_dict, asp_doc)
    effective_filter_genes = create_filter_genelist(genes_covered_in_panel)
    if target == "cnv" and not effective_filter_genes:
        effective_filter_genes = sorted(asp_doc.get("covered_genes", []))
    return genes_covered_in_panel, effective_filter_genes
