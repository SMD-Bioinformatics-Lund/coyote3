"""Assay/filter configuration helpers used by API workflows."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.app.runtime_state import app
from api.domain.common import assay_filters as domain_assay_filters


def assay_config(assay_name: str | None = None) -> dict:
    """Copy runtime assay configuration without sharing mutable settings.

    Args:
        assay_name: Assay key to select, or None for the entire ASSAYS mapping.

    Returns:
        A deep copy of the selected value, including an explicit None. Missing
        or null ASSAYS and unknown assay keys return an empty dictionary.
    """
    conf = app.config.get("ASSAYS")
    if conf is None:
        return {}
    if assay_name is not None:
        conf = conf.get(assay_name, {})
    return deepcopy(conf)


def get_group_parameters(group: str) -> dict:
    """Copy the configured parameters for an assay group.

    Args:
        group: Key in the runtime GROUP_CONFIGS mapping.

    Returns:
        A deep copy of the group value, or None for an absent or null group.
        Missing or null GROUP_CONFIGS instead returns an empty dictionary.
    """
    conf = app.config.get("GROUP_CONFIGS")
    if conf is not None:
        return deepcopy(conf.get(group))
    return {}


def table_config() -> dict:
    """Copy the runtime table settings.

    Returns:
        A deep copy of TABLE, or None when it is absent or null.
    """
    return deepcopy(app.config.get("TABLE"))


def cutoff_config(assay_name: str, sample_type: str | None = None) -> dict:
    """Copy assay cutoffs, optionally selecting a sample-type subsection.

    Args:
        assay_name: Key in the runtime CUTOFFS mapping.
        sample_type: Subsection key, or None to return all assay cutoffs.

    Returns:
        A deep copy of the selected cutoffs. Missing or null CUTOFFS and missing
        assays return an empty dictionary; missing sample types return None.
        Explicit null assay values are preserved when no sample type is selected.

    Raises:
        AttributeError: A sample type is requested from a null assay value.
    """
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
    """Read the assay's sample-information fields from a configuration copy.

    Args:
        assay_name: Assay key in ASSAYS.

    Returns:
        The copied sample_info value, or None if the assay or field is missing.
    """
    return assay_config(assay_name).get("sample_info")


def assay_qc_vars(assay_name: str) -> list:
    """Read the assay's quality-control fields from a configuration copy.

    Args:
        assay_name: Assay key in ASSAYS.

    Returns:
        The copied sample_qc value, or None if the assay or field is missing.
    """
    return assay_config(assay_name).get("sample_qc")


def assays_in_assay_group(assay_name: str) -> list:
    """Read the member assays configured for a group.

    Args:
        assay_name: Group key in ASSAYS.

    Returns:
        The copied include_assays value, or None if the group or field is missing.
    """
    return assay_config(assay_name).get("include_assays")


def has_subtypes(assay_name: str) -> bool:
    """Check for a subtypes key, regardless of its value.

    Args:
        assay_name: Assay key in ASSAYS.

    Returns:
        True when subtypes is present, even if empty or null; otherwise False.
    """
    return "subtypes" in assay_config(assay_name)


def get_sample_subtypes(assay_name: str) -> list:
    """Read subtype names from the assay's copied subtypes section.

    Args:
        assay_name: Assay key in ASSAYS.

    Returns:
        The subtype_names value, or None if the assay, section, or names are absent.

    Raises:
        AttributeError: The subtypes section is explicitly null instead of a mapping.
    """
    subtypes = assay_config(assay_name).get("subtypes", {})
    return subtypes.get("subtype_names", None)


def subtype_id_var(assay_name: str) -> list | None:
    """Read the identifier-column setting for an assay with subtypes.

    Args:
        assay_name: Assay key in ASSAYS.

    Returns:
        The copied subtype_id_col value, commonly a column-name string, without
        type coercion. Returns None when subtypes is absent or the column is null.

    Raises:
        AttributeError: A subtypes key exists but subtype_id_col is missing.
    """
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
    """Check whether an assay key is registered in runtime configuration.

    Args:
        assay_name: Key to look up in ASSAYS.

    Returns:
        True if the key exists, including when its value is null.
    """
    return assay_name in assay_config()


def assay_names_for_db_query(assay_category_name: str) -> list:
    """Expand a category into its configured assay names for querying.

    Args:
        assay_category_name: Group key, optionally ending in _restored. That suffix
            is removed for lookup and appended to each resulting assay name.

    Returns:
        Copied member names in configuration order. A non-restored category with
        missing or null include_assays returns None.

    Raises:
        TypeError: A restored category has missing or null include_assays.
    """
    assay_names = assay_config(assay_category_name.removesuffix("_restored")).get("include_assays")
    if assay_category_name.endswith("_restored"):
        assay_names = [f"{assay_name}_restored" for assay_name in assay_names]
    return assay_names


def merge_sample_settings_with_assay_config(sample_doc: dict, assay_config_doc: dict) -> dict:
    """Replace sample filters with a copy of sample settings or assay defaults.

    Args:
        sample_doc: Sample document to mutate. Truthy filters take precedence;
            missing, null, or empty filters select assay defaults.
        assay_config_doc: Assay defaults; missing filters means an empty mapping,
            while an explicit null filters value is preserved.

    Returns:
        The same sample dictionary with deeply copied filters and without
        use_diagnosis_genelist. Individual filter fields are not merged.
    """
    filters_config = assay_config_doc.get("filters", {})
    sample_filters = sample_doc.get("filters", {})
    if not sample_filters:
        sample_doc["filters"] = deepcopy(filters_config)
    else:
        sample_doc["filters"] = deepcopy(sample_filters)
    sample_doc.pop("use_diagnosis_genelist", None)
    return sample_doc


def get_fusions_settings(sample: dict, settings: dict) -> dict:
    """Resolve integer thresholds for fusion-supporting reads and pairs.

    Args:
        sample: Optional filter_min_spanreads and filter_min_spanpairs overrides.
        settings: default_spanreads and default_spanpairs used for absent sample
            keys; absent defaults become zero. Explicit nulls do not fall back.

    Returns:
        A new dictionary containing min_spanreads and min_spanpairs as integers.

    Raises:
        TypeError: A selected threshold is None or cannot be passed to int.
        ValueError: A selected threshold string is not an integer.
    """
    return {
        "min_spanreads": int(
            sample.get("filter_min_spanreads", settings.get("default_spanreads", 0))
        ),
        "min_spanpairs": int(
            sample.get("filter_min_spanpairs", settings.get("default_spanpairs", 0))
        ),
    }


def create_filter_genelist(genelist_dict: dict) -> list:
    """Collect unique covered genes from active gene lists.

    Args:
        genelist_dict: Documents keyed by list ID, with truthy is_active values
            selecting their covered gene sequences.

    Returns:
        Deduplicated genes with no guaranteed ordering; inputs are not mutated.

    Raises:
        KeyError: An active document lacks covered.
        TypeError: Covered genes are not iterable or contain unhashable values.
    """
    filter_genes = []
    for _genelist_id, genelist_values in genelist_dict.items():
        if genelist_values.get("is_active", False):
            filter_genes.extend(genelist_values["covered"])
    return list(set(filter_genes))


def get_genes_covered_in_panel(genelists: dict, assay_panel_doc: dict) -> dict:
    """Annotate gene-list records with their overlap with an assay panel.

    Args:
        genelists: Records keyed by list ID; missing genes means an empty sequence.
        assay_panel_doc: Panel with covered_genes and asp_family. WGS and WTS,
            compared case-insensitively, treat every listed gene as covered.

    Returns:
        A new outer dictionary sharing the input records. Each record is mutated
        to hold sorted, deduplicated covered and uncovered lists.

    Raises:
        TypeError: A genes or covered_genes value is null or not iterable.
    """
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
    """Extract gene-list identifiers without sorting or deduplication.

    Args:
        genelists: Iterable of gene-list documents, each containing _id.

    Returns:
        A new list of _id values in input order, preserving explicit nulls.

    Raises:
        KeyError: A document has no _id key.
    """
    return [genelist["_id"] for genelist in genelists]


def format_assay_config(config: dict, schema: dict) -> dict:
    """Move flat assay settings into filter and reporting sections in place.

    Args:
        config: Dictionary to mutate, or None to create a new dictionary.
        schema: Form schema with sections.filters and sections.reporting as
            mappings or lists of field names/descriptors; None means no fields.

    Returns:
        The same config dictionary, or a new one for None, with filters and
        reporting dictionaries. Flat values win over nested values, then schema
        defaults; explicit None values are retained. Non-dictionary existing
        sections become empty sections. Unspecified nested extension keys survive,
        except section metadata keys (_id, id, id_ and the section's own name).

    Notes:
        Consumed flat keys are removed. Values and schema defaults are not deep
        copied; nested mutable values can remain shared with either input.
    """
    if config is None:
        config = {}
    if schema is None:
        schema = {}
    sections = schema.get("sections", {})
    filter_section = sections.get("filters", {})
    report_section = sections.get("reporting", {})

    def section_keys_and_defaults(section_obj):
        """Collect supported schema keys and defaults, excluding section metadata.

        Args:
            section_obj: Mapping of field definitions or list of names/descriptors.
                Descriptors choose the first truthy key, id, name, or field value.
                Other section types, including None, produce no keys.

        Returns:
            A pair of ordered keys and defaults by key. Missing defaults are None;
            nameless descriptors and id_, id, _id, filters, reporting are skipped.
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
    """Build schema-selected filters from submitted values and checkbox groups.

    Args:
        form_data: Dictionary or iterable of fields exposing name and data.
        assay_config_schema: Schema whose sections.filters is a mapping or list
            of field names/descriptors. Missing sections select no fields.

    Returns:
        A new dictionary containing only schema fields. Truthy vep_, snvlist_,
        fusionlist_, fusioncaller_, fusioneffect_, and cnveffect_ keys populate
        their list fields in submission order, with prefix text removed. Other
        absent fields become None; schema defaults are not applied.

    Notes:
        Inputs are not mutated. Ordinary field values are shared, not deep copied.
    """
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
    vep_consequences, snvlists, fusionlists, fusion_callers, fusion_effects, cnveffects = (
        [],
        [],
        [],
        [],
        [],
        [],
    )

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


def create_assay_group_map(assay_groups_panels: list) -> dict:
    """Group selected panel metadata by assay group.

    Args:
        assay_groups_panels: Panel documents containing asp_group and optional
            asp_id, display_name, and asp_category values.

    Returns:
        New lists of three-field metadata dictionaries keyed by asp_group, in
        input order. Missing groups use the None key; missing fields remain None.
    """
    assay_group_map = {}
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


def get_case_and_control_sample_ids(sample_doc: dict) -> dict:
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


def get_sample_effective_genes(
    sample: dict,
    asp_doc: dict,
    checked_gl_dict: dict,
    target: str = "snv",
    intent: str = "somatic",
) -> tuple:
    """Resolve target-specific gene-list coverage through the domain helper.

    Args:
        sample: Sample filters, omics_layer, and analysis_intents used to select
            the applicable profile and ad-hoc genes; missing filters are normalized.
        asp_doc: Panel covered_genes and asp_family used to determine coverage.
        checked_gl_dict: Gene-list records keyed by IDs selected for this target;
            None is treated as empty. Records are copied before coverage updates.
        target: Analysis scope, normally snv (default), cnv, fusion, or translocation.
            Other values do not restrict gene lists by list_type.
        intent: Profile to resolve, defaulting to somatic.

    Returns:
        A pair of coverage-annotated gene-list records and deduplicated active
        covered genes. Without applicable lists or ad-hoc genes, the gene list is
        the sorted panel coverage. Empty genes alone do not distinguish unrestricted
        panels from selected lists without overlap. Caller documents are not mutated.
    """
    return domain_assay_filters.get_sample_effective_genes(
        sample,
        asp_doc,
        checked_gl_dict,
        target=target,
        intent=intent,
    )
