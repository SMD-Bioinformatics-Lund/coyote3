"""DNA route payload builders used by ``DnaService``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.application.common.pagination import paginate_items, request_pagination
from api.application.common.table_state import (
    parse_sort_specs,
    sort_items,
    sort_spec_to_query_value,
)
from api.application.dna.export import consequence_terms
from api.application.reporting.dna_report_payload import hotspot_variant
from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.domain.common.errors import api_error, setup_error
from api.domain.common.sample_filters import (
    merge_filter_defaults,
    merged_dna_cnv_filters,
    merged_dna_variant_filters,
)
from api.domain.core.dna.dna_variants import format_pon
from api.domain.core.dna.notation import one_letter_p
from api.domain.core.dna.translocqueries import build_transloc_query


def _variant_case_af_value(variant: dict[str, Any]) -> float:
    """Extract the case allele frequency used for table ordering."""
    for genotype in variant.get("GT", []) or []:
        if genotype.get("type") != "case":
            continue
        try:
            return float(genotype.get("AF", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def _numeric_value(value: Any) -> float | None:
    """Convert table values to sortable numbers when possible."""
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return float(int(value))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _selected_csq(variant: dict[str, Any]) -> dict[str, Any]:
    """Return the selected consequence annotation for a small variant."""
    csq = variant.get("INFO", {}).get("selected_CSQ", {})
    return csq if isinstance(csq, dict) else {}


def _sortable_text(value: Any) -> str | None:
    """Normalize strings for stable case-insensitive table sorting."""
    if value in (None, ""):
        return None
    return str(value).lower()


def _sortable_fraction(value: Any) -> tuple[int, int, int | str] | None:
    """Sort exon/intron fractions by their first numeric component when present."""
    if value in (None, "", "-"):
        return None
    text = str(value)
    try:
        first, _, second = text.partition("/")
        return (0, int(first), int(second) if second else 0)
    except ValueError:
        return (1, 0, text.lower())


def _variant_gt_af_value(variant: dict[str, Any], gt_type: str) -> float | None:
    """Extract allele frequency for a named genotype type."""
    for genotype in variant.get("GT", []) or []:
        if genotype.get("type") != gt_type:
            continue
        return _numeric_value(genotype.get("AF"))
    return None


def _chromosome_sort_value(chromosome: Any) -> tuple[int, int | str] | None:
    """Sort common human chromosomes in biological order."""
    if chromosome in (None, ""):
        return None
    text = str(chromosome).removeprefix("chr").upper()
    if text.isdigit():
        return (0, int(text))
    special = {"X": 23, "Y": 24, "M": 25, "MT": 25}
    if text in special:
        return (0, special[text])
    return (1, text)


def _chrpos_sort_value(variant: dict[str, Any]) -> tuple[Any, float] | None:
    """Sort genomic coordinates by chromosome then position."""
    chromosome = _chromosome_sort_value(variant.get("CHROM"))
    position = _numeric_value(variant.get("POS"))
    if chromosome is None and position is None:
        return None
    return (chromosome if chromosome is not None else (2, ""), position or 0)


def _variant_tier_sort_value(variant: dict[str, Any]) -> float | None:
    """Extract the active tier/classification value for table sorting."""
    for key in ("classification", "class", "tier"):
        value = variant.get(key)
        if isinstance(value, dict):
            value = value.get("class") or value.get("tier") or value.get("value")
        numeric = _numeric_value(value)
        if numeric is not None:
            return numeric
    return None


def _variant_sort_value(variant: dict[str, Any], sort_by: str) -> Any:
    """Return the backend sort key for supported small-variant table columns."""
    selected_csq = _selected_csq(variant)
    consequences = selected_csq.get("Consequence")
    if isinstance(consequences, list):
        consequence_text = ", ".join(str(value) for value in consequences)
    else:
        consequence_text = str(consequences or "").replace("&", ", ")
    filters = variant.get("FILTER", [])
    filters_text = (
        ", ".join(str(value) for value in filters)
        if isinstance(filters, list)
        else str(filters or "")
    )
    sort_map = {
        "gene": lambda: _sortable_text(
            selected_csq.get("SYMBOL")
            or selected_csq.get("VEP_SYMBOL")
            or selected_csq.get("display_symbol")
        ),
        "hgvs": lambda: _sortable_text(
            f"{selected_csq.get('HGVSc', '')} {selected_csq.get('HGVSp', '')}".strip()
        ),
        "exon": lambda: _sortable_fraction(selected_csq.get("EXON")),
        "intron": lambda: _sortable_fraction(selected_csq.get("INTRON")),
        "type": lambda: _sortable_text(variant.get("variant_class")),
        "indel_size": lambda: _numeric_value(variant.get("INFO", {}).get("SVLEN")),
        "consequence": lambda: _sortable_text(consequence_text),
        "popfreq": lambda: _numeric_value(variant.get("gnomad_frequency")),
        "tier": lambda: _variant_tier_sort_value(variant),
        "chrpos": lambda: _chrpos_sort_value(variant),
        "flags": lambda: _sortable_text(filters_text),
        "case_vaf": lambda: _variant_gt_af_value(variant, "case"),
        "control_vaf": lambda: _variant_gt_af_value(variant, "control"),
    }
    builder = sort_map.get(sort_by)
    return builder() if builder else None


def _sort_variants_for_table(
    variants: list[dict[str, Any]],
    *,
    sort_specs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    """Sort all filtered variants before pagination."""
    return sort_items(variants, specs=sort_specs, value_getter=_variant_sort_value)


def _variant_search_text(variant: dict[str, Any]) -> str:
    """Build the searchable text for one small-variant table row."""
    selected_csq = variant.get("INFO", {}).get("selected_CSQ", {}) or {}
    consequences = selected_csq.get("Consequence", "")
    if isinstance(consequences, list):
        consequences_text = " ".join(str(value) for value in consequences)
    else:
        consequences_text = str(consequences).replace("&", " ")
    filters = variant.get("FILTER", [])
    if isinstance(filters, list):
        filters_text = " ".join(str(value) for value in filters)
    else:
        filters_text = str(filters)
    genotype_text = " ".join(
        " ".join(str(genotype.get(key, "")) for key in ("sample", "type", "AF", "VD", "DP"))
        for genotype in variant.get("GT", []) or []
        if isinstance(genotype, dict)
    )
    values = [
        variant.get("_id"),
        variant.get("CHROM"),
        variant.get("POS"),
        variant.get("REF"),
        variant.get("ALT"),
        variant.get("variant_class"),
        selected_csq.get("SYMBOL"),
        selected_csq.get("VEP_SYMBOL"),
        selected_csq.get("display_symbol"),
        selected_csq.get("HGNC_ID"),
        selected_csq.get("Gene"),
        selected_csq.get("Feature"),
        selected_csq.get("HGVSc"),
        selected_csq.get("HGVSp"),
        selected_csq.get("EXON"),
        selected_csq.get("INTRON"),
        consequences_text,
        filters_text,
        genotype_text,
    ]
    return " ".join(str(value) for value in values if value not in (None, ""))


def _search_variants(variants: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Search already filtered variants before pagination."""
    terms = [term.lower() for term in str(query or "").split() if term.strip()]
    if not terms:
        return variants
    return [
        variant
        for variant in variants
        if all(term in _variant_search_text(variant).lower() for term in terms)
    ]


def _collect_oncokb_genes(service, variants: list[dict]) -> list[str]:
    """Collect unique OncoKB gene symbols present in the variant list."""
    oncokb_genes: list[str] = []
    public_cache = getattr(service, "oncokb_public_cache_repository", None)
    public_getter = getattr(public_cache, "get_gene_records", None)
    symbols = [
        symbol
        for variant in variants
        if (symbol := variant.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL"))
    ]
    if callable(public_getter):
        public_records = public_getter(symbols)
        oncokb_genes.extend(gene for gene in public_records if gene and gene not in oncokb_genes)
    return oncokb_genes


def _collect_oncokb_gene_map(service, genes: list[str]) -> dict[str, dict]:
    """Return OncoKB gene records keyed by gene symbol when locally available."""
    if not genes:
        return {}
    public_cache = getattr(service, "oncokb_public_cache_repository", None)
    public_getter = getattr(public_cache, "get_gene_records", None)
    if callable(public_getter):
        public_records = public_getter(genes)
    else:
        public_records = {}
    return dict(public_records)


def _collect_oncokb_actionable_gene_map(service, genes: list[str]) -> dict[str, dict]:
    """Return historical local OncoKB actionable gene records keyed by gene symbol."""
    if not genes:
        return {}
    getter = getattr(service.oncokb_repository, "get_oncokb_action_gene_records", None)
    if callable(getter):
        return dict(getter(genes))
    return {}


def _collect_clinpgx_gene_map(service, genes: list[str]) -> dict[str, dict]:
    """Return ClinPGx public gene records keyed by variant gene symbol."""
    if not genes:
        return {}
    repository = getattr(service, "clinpgx_public_repository", None)
    getter = getattr(repository, "get_gene_records", None)
    if callable(getter):
        return dict(getter(genes))
    return {}


def _normalize_dna_analysis_sections(sections: list[str] | None) -> list[str]:
    """Normalize DNA display/report section toggles to supported UI sections."""
    raw = [str(value).strip().upper() for value in (sections or []) if str(value).strip()]
    normalized: list[str] = []
    include_biomarker = False
    for value in raw:
        if value in {"BIOMARKER", "TMB", "PGX"}:
            include_biomarker = True
            continue
        if value not in normalized:
            normalized.append(value)
    if include_biomarker:
        normalized.append("BIOMARKER")
    return normalized


def _build_display_and_summary_sections(
    service,
    *,
    variants: list[dict],
    tiered_variants: list[dict],
    analysis_sections: list[str],
    sample: dict,
    sample_filters: dict,
    cnv_filters: dict,
    filter_genes: list[str],
    cnv_filter_genes: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build display and summary section dictionaries for report payloads."""
    display_sections_data: dict[str, Any] = {"snvs": deepcopy(variants)}
    summary_sections_data: dict[str, Any] = {"snvs": tiered_variants}

    if "CNV" in analysis_sections:
        cnvs = service.load_cnvs_for_sample(
            sample=sample,
            sample_filters=cnv_filters,
            filter_genes=cnv_filter_genes,
        )
        display_sections_data["cnvs"] = deepcopy(cnvs)
        summary_sections_data["cnvs"] = [cnv for cnv in cnvs if cnv.get("interesting")]

    if "BIOMARKER" in analysis_sections:
        biomarkers = list(
            service.biomarker_repository.get_sample_biomarkers(sample_id=str(sample["_id"]))
        )
        display_sections_data["biomarkers"] = biomarkers
        summary_sections_data["biomarkers"] = biomarkers

    if "TRANSLOCATION" in analysis_sections:
        transloc_query = build_transloc_query(
            str(sample["_id"]),
        )
        display_sections_data["translocs"] = list(
            service.translocation_repository.get_sample_translocations(transloc_query)
        )

    if "FUSION" in analysis_sections:
        display_sections_data["fusions"] = []
        summary_sections_data["translocs"] = [
            transloc
            for transloc in display_sections_data.get("translocs", [])
            if transloc.get("interesting")
        ]

    return display_sections_data, summary_sections_data


def list_variants_payload(
    *,
    service,
    request,
    sample: dict,
    util_module,
    add_global_annotations_fn,
    generate_summary_text_fn,
    build_query_fn,
    get_filter_conseq_terms_fn,
    assay_config_getter,
    paginate: bool = True,
) -> dict[str, Any]:
    """Build the list variants payload used by DNA routes."""
    assay_config = assay_config_getter(sample)
    if not assay_config:
        raise setup_error(
            "ASPC could not be resolved for the sample",
            (
                f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                "configuration during DNA findings loading."
            ),
        )

    raw_sample_filters = sample.get("filters")
    sample_filters = deepcopy(
        assay_config.get("filters", {}) if raw_sample_filters is None else raw_sample_filters
    )
    sample_filters = merge_filter_defaults(
        sample_filters,
        assay_config.get("filters"),
        omics_layer=str(sample.get("omics_layer") or "dna"),
    )
    snv_filters = merged_dna_variant_filters(sample_filters)
    cnv_filters = merged_dna_cnv_filters(sample_filters)
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel_id")
    analysis_sections = _normalize_dna_analysis_sections(assay_config.get("analysis_types", []))

    assay_panel_doc = service.assay_panel_repository.get_asp(asp_name=sample.get("assay"))
    checked_snvlists = snv_filters.get("snvlists", [])
    checked_snvlists_genes_dict = service.gene_list_repository.get_isgl_by_ids(checked_snvlists)
    genes_covered_in_panel, filter_genes = util_module.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_snvlists_genes_dict, target="snv"
    )
    checked_cnvlists = cnv_filters.get("cnvlists", [])
    checked_cnvlists_genes_dict = service.gene_list_repository.get_isgl_by_ids(checked_cnvlists)
    _cnv_genes_covered_in_panel, cnv_filter_genes = util_module.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_cnvlists_genes_dict, target="cnv"
    )
    filter_conseq = get_filter_conseq_terms_fn(snv_filters.get("vep_consequences", []))

    disp_pos = []
    verification_sample_used = None
    if assay_config.get("verification_samples"):
        for veri_key, verification_pos in assay_config.get("verification_samples", {}).items():
            if veri_key in sample.get("name", ""):
                disp_pos = verification_pos
                verification_sample_used = veri_key
                break

    query = build_query_fn(
        assay_group,
        {
            "id": str(sample["_id"]),
            "max_freq": snv_filters["max_freq"],
            "min_freq": snv_filters["min_freq"],
            "max_control_freq": snv_filters["max_control_freq"],
            "min_depth": snv_filters["min_depth"],
            "min_alt_reads": snv_filters["min_alt_reads"],
            "max_popfreq": snv_filters["max_popfreq"],
            "filter_conseq": filter_conseq,
            "filter_genes": filter_genes,
            "disp_pos": disp_pos,
        },
    )

    variants = list(service.variant_repository.get_case_variants(query))
    variants = service.blacklist_repository.add_blacklist_data(variants, assay_group)
    variants, tiered_variants = add_global_annotations_fn(variants, assay_group, subpanel)
    variants = hotspot_variant(variants)
    variants = sorted(variants, key=_variant_case_af_value, reverse=True)
    query_params = getattr(request, "query_params", {}) or {}
    search_query = str(query_params.get("q", "")).strip()
    if search_query:
        variants = _search_variants(variants, search_query)
    sort_specs = parse_sort_specs(query_params)
    variants = _sort_variants_for_table(variants, sort_specs=sort_specs)

    sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
    bam_id = service.bam_record_repository.get_bams(sample_ids)
    vep_variant_class_meta = service.vep_metadata_repository.get_variant_class_translations(
        sample.get("vep_version", "103")
    )
    vep_conseq_meta = service.vep_metadata_repository.get_conseq_translations(
        sample.get("vep_version", "103")
    )
    has_hidden_comments = service.sample_repository.hidden_sample_comments(sample.get("_id"))
    insilico_panel_genelists = service.gene_list_repository.get_isgl_by_asp(
        sample.get("assay"), is_active=True
    )
    all_panel_genelist_names = util_module.common.get_assay_genelist_names(insilico_panel_genelists)
    assay_config_schema = build_form_spec(aspc_spec_for_category("DNA"))

    oncokb_genes = _collect_oncokb_genes(service, variants)
    oncokb_gene_map = _collect_oncokb_gene_map(service, oncokb_genes)
    variant_genes = [
        symbol
        for variant in variants
        if (symbol := variant.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL"))
    ]
    oncokb_actionable_gene_map = _collect_oncokb_actionable_gene_map(
        service,
        variant_genes,
    )
    clinpgx_gene_map = _collect_clinpgx_gene_map(service, variant_genes)
    display_sections_data, summary_sections_data = _build_display_and_summary_sections(
        service,
        variants=variants,
        tiered_variants=tiered_variants,
        analysis_sections=analysis_sections,
        sample=sample,
        sample_filters=sample_filters,
        cnv_filters=cnv_filters,
        filter_genes=filter_genes,
        cnv_filter_genes=cnv_filter_genes,
    )
    pagination_meta: dict[str, Any] = {
        "total": len(variants),
        "count": len(variants),
        "page_count": len(variants),
        "page": 1,
        "per_page": len(variants) or 50,
        "has_previous": False,
        "has_next": False,
    }
    if paginate:
        page, per_page = request_pagination(request)
        variants_page, pagination_meta = paginate_items(variants, page=page, per_page=per_page)
        display_sections_data["snvs"] = variants_page

    if "cnv" in sample and str(sample["cnv"]).lower().endswith((".png", ".jpg", ".jpeg")):
        sample["cnvprofile"] = sample["cnv"]

    ai_text = generate_summary_text_fn(
        sample_ids,
        assay_config,
        assay_panel_doc,
        summary_sections_data,
        filter_genes,
        checked_snvlists,
    )

    return {
        "sample": sample,
        "meta": {
            "request_path": request.url.path,
            **pagination_meta,
            "tiered": tiered_variants,
            "search": search_query,
            "sort": sort_spec_to_query_value(sort_specs),
        },
        "filters": sample_filters,
        "assay_group": assay_group,
        "subpanel": subpanel,
        "analysis_sections": analysis_sections,
        "assay_config": assay_config,
        "assay_config_schema": assay_config_schema,
        "assay_panel_doc": assay_panel_doc,
        "assay_panels": insilico_panel_genelists,
        "all_panel_genelist_names": all_panel_genelist_names,
        "checked_snvlists": checked_snvlists,
        "checked_snvlists_dict": genes_covered_in_panel,
        "filter_genes": filter_genes,
        "sample_ids": sample_ids,
        "bam_id": bam_id,
        "hidden_comments": has_hidden_comments,
        "vep_var_class_translations": vep_variant_class_meta,
        "vep_conseq_translations": vep_conseq_meta,
        "oncokb_genes": oncokb_genes,
        "oncokb_gene_map": oncokb_gene_map,
        "oncokb_actionable_genes": list(oncokb_actionable_gene_map),
        "oncokb_actionable_gene_map": oncokb_actionable_gene_map,
        "clinpgx_genes": list(clinpgx_gene_map),
        "clinpgx_gene_map": clinpgx_gene_map,
        "verification_sample_used": verification_sample_used,
        "variants": variants,
        "display_sections_data": display_sections_data,
        "ai_text": ai_text,
    }


def plot_context_payload(*, service, sample: dict, assay_config_getter) -> dict[str, Any]:
    """Build plot context payload for DNA routes."""
    assay_config = assay_config_getter(sample)
    if not assay_config:
        raise setup_error(
            "ASPC could not be resolved for the sample",
            (
                f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                "configuration while loading DNA plot context."
            ),
        )
    assay_config_schema = build_form_spec(aspc_spec_for_category("DNA"))
    return {
        "sample": sample,
        "assay_config": assay_config,
        "assay_config_schema": assay_config_schema,
        "plots_base_dir": assay_config.get("reporting", {}).get("plots_path", None),
    }


def biomarkers_payload(*, service, sample: dict) -> dict[str, Any]:
    """Build biomarker payload for DNA routes."""
    biomarkers = list(
        service.biomarker_repository.get_sample_biomarkers(sample_id=str(sample["_id"]))
    )
    return {"sample": sample, "meta": {"count": len(biomarkers)}, "biomarkers": biomarkers}


def variant_context_payload(
    *,
    service,
    sample: dict,
    var_id: str,
    add_alt_class_fn,
    util_module,
    assay_config_getter,
) -> dict[str, Any]:
    """Build single-variant context payload for DNA routes."""
    variant = service.variant_repository.get_variant(var_id)
    if not variant:
        raise api_error(404, "Variant not found")
    if str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise api_error(404, "Variant not found for sample")

    assay_config = assay_config_getter(sample)
    if not assay_config:
        raise setup_error(
            "ASPC could not be resolved for the sample",
            (
                f"Sample '{sample.get('name', sample.get('_id'))}' could not resolve an assay "
                "configuration during DNA variant loading."
            ),
        )
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel_id")

    variant = service.blacklist_repository.add_blacklist_data([variant], assay_group)[0]
    in_other = service.variant_repository.get_variant_in_other_samples(variant)
    has_hidden_comments = service.variant_repository.hidden_var_comments(var_id)
    annotations, latest_classification, other_classifications, annotations_interesting = (
        service.annotation_repository.get_global_annotations(variant, assay_group, subpanel)
    )
    if not latest_classification or latest_classification.get("class") == 999:
        variant = add_alt_class_fn(variant, assay_group, subpanel)
    else:
        variant["additional_classifications"] = None

    expression = service.expression_repository.get_expression_data(
        list(variant.get("transcripts", []))
    )
    selected_csq = variant.get("INFO", {}).get("selected_CSQ", {})
    csq_terms = consequence_terms(selected_csq.get("Consequence"))
    variant_desc = "NOTHING_IN_HERE"
    if (
        selected_csq.get("SYMBOL") == "CALR"
        and selected_csq.get("EXON") == "9/9"
        and "frameshift_variant" in csq_terms
    ):
        variant_desc = "EXON 9 FRAMESHIFT"
    if (
        selected_csq.get("SYMBOL") == "FLT3"
        and "SVLEN" in variant.get("INFO", {})
        and variant.get("INFO", {}).get("SVLEN", 0) > 10
    ):
        variant_desc = "ITD"

    civic = service.civic_repository.get_civic_data(variant, variant_desc)
    civic_gene = service.civic_repository.get_civic_gene_info(selected_csq.get("SYMBOL"))

    oncokb_hgvsp = []
    if selected_csq.get("HGVSp"):
        hgvsp = one_letter_p(selected_csq.get("HGVSp")).replace("p.", "")
        oncokb_hgvsp.append(hgvsp)
    if csq_terms.intersection(
        {
            "frameshift_variant",
            "stop_gained",
            "frameshift_deletion",
            "frameshift_insertion",
        }
    ):
        oncokb_hgvsp.append("Truncating Mutations")

    oncokb = service.oncokb_repository.get_oncokb_anno(variant, oncokb_hgvsp)
    oncokb_action = service.oncokb_repository.get_oncokb_action(variant, oncokb_hgvsp)
    public_cache = getattr(service, "oncokb_public_cache_repository", None)
    public_gene_getter = getattr(public_cache, "get_gene_record", None)
    oncokb_gene = (
        public_gene_getter(selected_csq.get("SYMBOL")) if callable(public_gene_getter) else None
    ) or service.oncokb_repository.get_oncokb_gene(selected_csq.get("SYMBOL"))
    clinpgx_gene_getter = getattr(
        getattr(service, "clinpgx_public_repository", None),
        "get_gene_record",
        None,
    )
    clinpgx_gene = (
        clinpgx_gene_getter(selected_csq.get("SYMBOL")) if callable(clinpgx_gene_getter) else None
    )
    brca_exchange = service.brca_repository.get_brca_data(variant, assay_group)
    iarc_tp53 = service.iarc_tp53_repository.find_iarc_tp53(variant)

    sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
    return {
        "sample": sample,
        "sample_summary": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "assay_group": assay_group,
            "subpanel": subpanel,
        },
        "variant": variant,
        "annotations": annotations,
        "latest_classification": latest_classification,
        "other_classifications": other_classifications,
        "annotations_interesting": annotations_interesting,
        "in_other_samples": in_other,
        "in_other": in_other,
        "has_hidden_comments": has_hidden_comments,
        "hidden_comments": has_hidden_comments,
        "expression": expression,
        "civic": civic,
        "civic_gene": civic_gene,
        "oncokb": oncokb,
        "oncokb_action": oncokb_action,
        "oncokb_gene": oncokb_gene,
        "clinpgx_gene": clinpgx_gene,
        "brca_exchange": brca_exchange,
        "iarc_tp53": iarc_tp53,
        "assay_group": assay_group,
        "subpanel": subpanel,
        "pon": format_pon(variant),
        "sample_ids": sample_ids,
        "bam_id": service.bam_record_repository.get_bams(sample_ids),
        "vep_var_class_translations": service.vep_metadata_repository.get_variant_class_translations(
            sample.get("vep_version", "103")
        ),
        "vep_conseq_translations": service.vep_metadata_repository.get_conseq_translations(
            sample.get("vep_version", "103")
        ),
        "assay_group_mappings": service.assay_panel_repository.get_asp_group_mappings(),
    }
