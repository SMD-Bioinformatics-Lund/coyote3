"""DNA route payload builders used by ``DnaService``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.contracts.managed_resources import aspc_spec_for_category
from api.contracts.managed_ui_schemas import build_form_spec
from api.core.dna.dna_variants import format_pon
from api.core.dna.notation import one_letter_p
from api.core.dna.translocqueries import build_transloc_query
from api.http import api_error
from api.services.dna.export import consequence_terms
from api.services.reporting.dna_report_payload import hotspot_variant


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


def _collect_oncokb_genes(service, variants: list[dict]) -> list[str]:
    """Collect unique OncoKB gene symbols present in the variant list."""
    oncokb_genes: list[str] = []
    for variant in variants:
        symbol = variant.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL")
        if not symbol:
            continue
        oncokb_gene = service.oncokb_handler.get_oncokb_action_gene(symbol)
        if oncokb_gene and "Hugo Symbol" in oncokb_gene:
            hugo_symbol = oncokb_gene["Hugo Symbol"]
            if hugo_symbol not in oncokb_genes:
                oncokb_genes.append(hugo_symbol)
    return oncokb_genes


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
    filter_genes: list[str],
    cnv_filter_genes: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build display and summary section dictionaries for report payloads."""
    display_sections_data: dict[str, Any] = {"snvs": deepcopy(variants)}
    summary_sections_data: dict[str, Any] = {"snvs": tiered_variants}

    if "CNV" in analysis_sections:
        cnvs = service.load_cnvs_for_sample(
            sample=sample,
            sample_filters=sample_filters,
            filter_genes=cnv_filter_genes,
        )
        display_sections_data["cnvs"] = deepcopy(cnvs)
        summary_sections_data["cnvs"] = [cnv for cnv in cnvs if cnv.get("interesting")]

    if "BIOMARKER" in analysis_sections:
        biomarkers = list(
            service.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"]))
        )
        display_sections_data["biomarkers"] = biomarkers
        summary_sections_data["biomarkers"] = biomarkers

    if "TRANSLOCATION" in analysis_sections:
        transloc_query = build_transloc_query(
            str(sample["_id"]),
        )
        display_sections_data["translocs"] = list(
            service.translocation_handler.get_sample_translocations(transloc_query)
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
) -> dict[str, Any]:
    """Build the list variants payload used by DNA routes."""
    assay_config = assay_config_getter(sample)
    if not assay_config:
        raise api_error(404, "Assay config not found for sample")

    sample = util_module.common.merge_sample_settings_with_assay_config(sample, assay_config)
    sample_filters = deepcopy(sample.get("filters", {}))
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    analysis_sections = _normalize_dna_analysis_sections(assay_config.get("analysis_types", []))

    assay_panel_doc = service.assay_panel_handler.get_asp(asp_name=sample.get("assay"))
    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict = service.gene_list_handler.get_isgl_by_ids(checked_genelists)
    genes_covered_in_panel, filter_genes = util_module.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_genelists_genes_dict, target="snv"
    )
    checked_cnv_genelists = sample_filters.get("cnv_genelists", [])
    checked_cnv_genelists_genes_dict = service.gene_list_handler.get_isgl_by_ids(
        checked_cnv_genelists
    )
    _cnv_genes_covered_in_panel, cnv_filter_genes = util_module.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_cnv_genelists_genes_dict, target="cnv"
    )
    filter_conseq = get_filter_conseq_terms_fn(sample_filters.get("vep_consequences", []))

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
            "max_freq": sample_filters["max_freq"],
            "min_freq": sample_filters["min_freq"],
            "max_control_freq": sample_filters["max_control_freq"],
            "min_depth": sample_filters["min_depth"],
            "min_alt_reads": sample_filters["min_alt_reads"],
            "max_popfreq": sample_filters["max_popfreq"],
            "filter_conseq": filter_conseq,
            "filter_genes": filter_genes,
            "disp_pos": disp_pos,
        },
    )

    variants = list(service.variant_handler.get_case_variants(query))
    variants = service.blacklist_handler.add_blacklist_data(variants, assay_group)
    variants, tiered_variants = add_global_annotations_fn(variants, assay_group, subpanel)
    variants = hotspot_variant(variants)
    variants = sorted(variants, key=_variant_case_af_value, reverse=True)

    sample_ids = util_module.common.get_case_and_control_sample_ids(sample)
    bam_id = service.bam_record_handler.get_bams(sample_ids)
    vep_variant_class_meta = service.vep_metadata_handler.get_variant_class_translations(
        sample.get("vep_version", "103")
    )
    vep_conseq_meta = service.vep_metadata_handler.get_conseq_translations(
        sample.get("vep_version", "103")
    )
    has_hidden_comments = service.sample_handler.hidden_sample_comments(sample.get("_id"))
    insilico_panel_genelists = service.gene_list_handler.get_isgl_by_asp(
        sample.get("assay"), is_active=True
    )
    all_panel_genelist_names = util_module.common.get_assay_genelist_names(insilico_panel_genelists)
    assay_config_schema = build_form_spec(aspc_spec_for_category("DNA"))

    oncokb_genes = _collect_oncokb_genes(service, variants)
    display_sections_data, summary_sections_data = _build_display_and_summary_sections(
        service,
        variants=variants,
        tiered_variants=tiered_variants,
        analysis_sections=analysis_sections,
        sample=sample,
        sample_filters=sample_filters,
        filter_genes=filter_genes,
        cnv_filter_genes=cnv_filter_genes,
    )

    if "cnv" in sample and str(sample["cnv"]).lower().endswith((".png", ".jpg", ".jpeg")):
        sample["cnvprofile"] = sample["cnv"]

    ai_text = generate_summary_text_fn(
        sample_ids,
        assay_config,
        assay_panel_doc,
        summary_sections_data,
        filter_genes,
        checked_genelists,
    )

    return {
        "sample": sample,
        "meta": {
            "request_path": request.url.path,
            "count": len(variants),
            "tiered": tiered_variants,
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
        "checked_genelists": checked_genelists,
        "checked_genelists_dict": genes_covered_in_panel,
        "filter_genes": filter_genes,
        "sample_ids": sample_ids,
        "bam_id": bam_id,
        "hidden_comments": has_hidden_comments,
        "vep_var_class_translations": vep_variant_class_meta,
        "vep_conseq_translations": vep_conseq_meta,
        "oncokb_genes": oncokb_genes,
        "verification_sample_used": verification_sample_used,
        "variants": variants,
        "display_sections_data": display_sections_data,
        "ai_text": ai_text,
    }


def plot_context_payload(*, service, sample: dict, assay_config_getter) -> dict[str, Any]:
    """Build plot context payload for DNA routes."""
    assay_config = assay_config_getter(sample)
    if not assay_config:
        raise api_error(404, "Assay config not found for sample")
    assay_config_schema = build_form_spec(aspc_spec_for_category("DNA"))
    return {
        "sample": sample,
        "assay_config": assay_config,
        "assay_config_schema": assay_config_schema,
        "plots_base_dir": assay_config.get("reporting", {}).get("plots_path", None),
    }


def biomarkers_payload(*, service, sample: dict) -> dict[str, Any]:
    """Build biomarker payload for DNA routes."""
    biomarkers = list(service.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"])))
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
    variant = service.variant_handler.get_variant(var_id)
    if not variant:
        raise api_error(404, "Variant not found")
    if str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise api_error(404, "Variant not found for sample")

    assay_config = assay_config_getter(sample)
    if not assay_config:
        raise api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")

    variant = service.blacklist_handler.add_blacklist_data([variant], assay_group)[0]
    in_other = service.variant_handler.get_variant_in_other_samples(variant)
    has_hidden_comments = service.variant_handler.hidden_var_comments(var_id)
    annotations, latest_classification, other_classifications, annotations_interesting = (
        service.annotation_handler.get_global_annotations(variant, assay_group, subpanel)
    )
    if not latest_classification or latest_classification.get("class") == 999:
        variant = add_alt_class_fn(variant, assay_group, subpanel)
    else:
        variant["additional_classifications"] = None

    expression = service.expression_handler.get_expression_data(
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

    civic = service.civic_handler.get_civic_data(variant, variant_desc)
    civic_gene = service.civic_handler.get_civic_gene_info(selected_csq.get("SYMBOL"))

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

    oncokb = service.oncokb_handler.get_oncokb_anno(variant, oncokb_hgvsp)
    oncokb_action = service.oncokb_handler.get_oncokb_action(variant, oncokb_hgvsp)
    oncokb_gene = service.oncokb_handler.get_oncokb_gene(selected_csq.get("SYMBOL"))
    brca_exchange = service.brca_handler.get_brca_data(variant, assay_group)
    iarc_tp53 = service.iarc_tp53_handler.find_iarc_tp53(variant)

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
        "brca_exchange": brca_exchange,
        "iarc_tp53": iarc_tp53,
        "assay_group": assay_group,
        "subpanel": subpanel,
        "pon": format_pon(variant),
        "sample_ids": sample_ids,
        "bam_id": service.bam_record_handler.get_bams(sample_ids),
        "vep_var_class_translations": service.vep_metadata_handler.get_variant_class_translations(
            sample.get("vep_version", "103")
        ),
        "vep_conseq_translations": service.vep_metadata_handler.get_conseq_translations(
            sample.get("vep_version", "103")
        ),
        "assay_group_mappings": service.assay_panel_handler.get_asp_group_mappings(),
    }
