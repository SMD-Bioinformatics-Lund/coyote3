"""DNA API routes."""

from copy import deepcopy
from fastapi import Body, Depends, Query, Request

from api.extensions import store, util
from api.core.dna.dna_filters import (
    cnv_organizegenes,
    cnvtype_variant,
    create_cnveffectlist,
    get_filter_conseq_terms,
)
from api.core.dna.notation import one_letter_p
from api.core.dna.dna_reporting import hotspot_variant
from api.core.dna.dna_variants import format_pon, get_variant_nomenclature
from api.core.dna.query_builders import build_cnv_query, build_query
from api.core.interpretation.annotation_enrichment import add_alt_class, add_global_annotations
from api.core.interpretation.report_summary import (
    create_annotation_text_from_gene,
    create_comment_doc,
    generate_summary_text,
)
from api.infra.repositories.dna_route_mongo import MongoDNARouteRepository
from api.runtime import app as runtime_app
from api.app import _api_error, _get_formatted_assay_config, app
from api.contracts.dna import (
    DnaBiomarkersPayload,
    DnaPlotContextPayload,
    DnaVariantContextPayload,
    DnaVariantsListPayload,
)
from api.contracts.samples import SampleMutationPayload
from api.security.access import ApiUser, _get_sample_for_api, require_access


class _HandlerStub:
    def __getattr__(self, _name):
        return lambda *args, **kwargs: None

_DNA_TESTABLE_STORE_HANDLERS = (
    "cnv_handler",
    "asp_handler",
    "isgl_handler",
    "variant_handler",
    "blacklist_handler",
    "bam_service_handler",
    "vep_meta_handler",
    "sample_handler",
    "schema_handler",
    "oncokb_handler",
    "biomarker_handler",
    "transloc_handler",
    "annotation_handler",
    "expression_handler",
    "civic_handler",
    "brca_handler",
    "iarc_tp53_handler",
    "fusion_handler",
)

for _handler_name in _DNA_TESTABLE_STORE_HANDLERS:
    if not hasattr(store, _handler_name):
        setattr(store, _handler_name, _HandlerStub())


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def _dna_repo() -> MongoDNARouteRepository:
    # Keep repository wiring aligned with module-level `store` so route tests
    # can patch `api.routes.dna.store` without reaching into infra modules.
    from api.infra.repositories import dna_route_mongo

    dna_route_mongo.store = store
    return MongoDNARouteRepository()


def _coerce_bool(value: object, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _load_cnvs_for_sample(sample: dict, sample_filters: dict, filter_genes: list[str]) -> list[dict]:
    cnv_query = build_cnv_query(str(sample["_id"]), filters={**sample_filters, "filter_genes": filter_genes})
    cnvs = list(_dna_repo().cnv_handler.get_sample_cnvs(cnv_query))
    filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
    if filter_cnveffects:
        cnvs = cnvtype_variant(cnvs, filter_cnveffects)
    return cnv_organizegenes(cnvs)


@app.get("/api/v1/dna/samples/{sample_id}/variants", response_model=DnaVariantsListPayload)
def list_dna_variants(request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")

    sample = util.common.merge_sample_settings_with_assay_config(sample, assay_config)
    sample_filters = deepcopy(sample.get("filters", {}))
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    analysis_sections = assay_config.get("analysis_types", [])

    assay_panel_doc = _dna_repo().asp_handler.get_asp(asp_name=sample.get("assay"))
    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict = _dna_repo().isgl_handler.get_isgl_by_ids(checked_genelists)
    genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_genelists_genes_dict
    )
    filter_conseq = get_filter_conseq_terms(sample_filters.get("vep_consequences", []))

    disp_pos = []
    verification_sample_used = None
    if assay_config.get("verification_samples"):
        verification_samples = assay_config.get("verification_samples")
        for veri_key, verification_pos in verification_samples.items():
            if veri_key in sample.get("name", ""):
                disp_pos = verification_pos
                verification_sample_used = veri_key
                break

    query = build_query(
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

    variants = list(_dna_repo().variant_handler.get_case_variants(query))
    variants = _dna_repo().blacklist_handler.add_blacklist_data(variants, assay_group)
    variants, tiered_variants = add_global_annotations(variants, assay_group, subpanel)
    variants = hotspot_variant(variants)

    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    bam_id = _dna_repo().bam_service_handler.get_bams(sample_ids)
    vep_variant_class_meta = _dna_repo().vep_meta_handler.get_variant_class_translations(sample.get("vep", 103))
    vep_conseq_meta = _dna_repo().vep_meta_handler.get_conseq_translations(sample.get("vep", 103))
    has_hidden_comments = _dna_repo().sample_handler.hidden_sample_comments(sample.get("_id"))
    insilico_panel_genelists = _dna_repo().isgl_handler.get_isgl_by_asp(sample.get("assay"), is_active=True)
    all_panel_genelist_names = util.common.get_assay_genelist_names(insilico_panel_genelists)
    assay_config_schema = _dna_repo().schema_handler.get_schema(assay_config.get("schema_name"))

    oncokb_genes = []
    for variant in variants:
        symbol = variant.get("INFO", {}).get("selected_CSQ", {}).get("SYMBOL")
        if not symbol:
            continue
        oncokb_gene = _dna_repo().oncokb_handler.get_oncokb_action_gene(symbol)
        if oncokb_gene and "Hugo Symbol" in oncokb_gene:
            hugo_symbol = oncokb_gene["Hugo Symbol"]
            if hugo_symbol not in oncokb_genes:
                oncokb_genes.append(hugo_symbol)

    display_sections_data = {"snvs": deepcopy(variants)}
    summary_sections_data = {"snvs": tiered_variants}

    if "CNV" in analysis_sections:
        cnvs = _load_cnvs_for_sample(sample, sample_filters, filter_genes)
        display_sections_data["cnvs"] = deepcopy(cnvs)
        summary_sections_data["cnvs"] = [cnv for cnv in cnvs if cnv.get("interesting")]

    if "BIOMARKER" in analysis_sections:
        biomarkers = list(_dna_repo().biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"])))
        display_sections_data["biomarkers"] = biomarkers
        summary_sections_data["biomarkers"] = biomarkers

    if "TRANSLOCATION" in analysis_sections:
        translocs = list(_dna_repo().transloc_handler.get_sample_translocations(sample_id=str(sample["_id"])))
        display_sections_data["translocs"] = translocs

    if "FUSION" in analysis_sections:
        display_sections_data["fusions"] = []
        summary_sections_data["translocs"] = [
            transloc for transloc in display_sections_data.get("translocs", []) if transloc.get("interesting")
        ]

    if "cnv" in sample and str(sample["cnv"]).lower().endswith((".png", ".jpg", ".jpeg")):
        sample["cnvprofile"] = sample["cnv"]

    ai_text = generate_summary_text(
        sample_ids,
        assay_config,
        assay_panel_doc,
        summary_sections_data,
        filter_genes,
        checked_genelists,
    )

    payload = {
        "sample": sample,
        "meta": {"request_path": request.url.path, "count": len(variants), "tiered": tiered_variants},
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
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/dna/samples/{sample_id}/plot_context", response_model=DnaPlotContextPayload)
def dna_plot_context(sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_config_schema = _dna_repo().schema_handler.get_schema(assay_config.get("schema_name"))
    return util.common.convert_to_serializable(
        {
            "sample": sample,
            "assay_config": assay_config,
            "assay_config_schema": assay_config_schema,
            "plots_base_dir": assay_config.get("reporting", {}).get("plots_path", None),
        }
    )


@app.get("/api/v1/dna/samples/{sample_id}/biomarkers", response_model=DnaBiomarkersPayload)
def list_dna_biomarkers(sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    biomarkers = list(_dna_repo().biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"])))
    payload = {
        "sample": sample,
        "meta": {"count": len(biomarkers)},
        "biomarkers": biomarkers,
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/dna/samples/{sample_id}/variants/{var_id}", response_model=DnaVariantContextPayload)
def show_dna_variant(sample_id: str, var_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant:
        raise _api_error(404, "Variant not found")
    if str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")

    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")

    variant = _dna_repo().blacklist_handler.add_blacklist_data([variant], assay_group)[0]
    in_other = _dna_repo().variant_handler.get_variant_in_other_samples(variant)
    has_hidden_comments = _dna_repo().variant_handler.hidden_var_comments(var_id)
    annotations, latest_classification, other_classifications, annotations_interesting = (
        _dna_repo().annotation_handler.get_global_annotations(variant, assay_group, subpanel)
    )
    if not latest_classification or latest_classification.get("class") == 999:
        variant = add_alt_class(variant, assay_group, subpanel)
    else:
        variant["additional_classifications"] = None

    expression = _dna_repo().expression_handler.get_expression_data(list(variant.get("transcripts", [])))

    variant_desc = "NOTHING_IN_HERE"
    selected_csq = variant.get("INFO", {}).get("selected_CSQ", {})
    if (
        selected_csq.get("SYMBOL") == "CALR"
        and selected_csq.get("EXON") == "9/9"
        and "frameshift_variant" in str(selected_csq.get("Consequence", ""))
    ):
        variant_desc = "EXON 9 FRAMESHIFT"
    if (
        selected_csq.get("SYMBOL") == "FLT3"
        and "SVLEN" in variant.get("INFO", {})
        and variant.get("INFO", {}).get("SVLEN", 0) > 10
    ):
        variant_desc = "ITD"

    civic = _dna_repo().civic_handler.get_civic_data(variant, variant_desc)
    civic_gene = _dna_repo().civic_handler.get_civic_gene_info(selected_csq.get("SYMBOL"))

    oncokb_hgvsp = []
    if selected_csq.get("HGVSp"):
        hgvsp = one_letter_p(selected_csq.get("HGVSp"))
        hgvsp = hgvsp.replace("p.", "")
        oncokb_hgvsp.append(hgvsp)
    if selected_csq.get("Consequence") in [
        "frameshift_variant",
        "stop_gained",
        "frameshift_deletion",
        "frameshift_insertion",
    ]:
        oncokb_hgvsp.append("Truncating Mutations")

    oncokb = _dna_repo().oncokb_handler.get_oncokb_anno(variant, oncokb_hgvsp)
    oncokb_action = _dna_repo().oncokb_handler.get_oncokb_action(variant, oncokb_hgvsp)
    oncokb_gene = _dna_repo().oncokb_handler.get_oncokb_gene(selected_csq.get("SYMBOL"))
    brca_exchange = _dna_repo().brca_handler.get_brca_data(variant, assay_group)
    iarc_tp53 = _dna_repo().iarc_tp53_handler.find_iarc_tp53(variant)

    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    bam_id = _dna_repo().bam_service_handler.get_bams(sample_ids)

    pon = format_pon(variant)
    assay_group_mappings = _dna_repo().asp_handler.get_asp_group_mappings()
    vep_variant_class_meta = _dna_repo().vep_meta_handler.get_variant_class_translations(sample.get("vep", 103))
    vep_conseq_meta = _dna_repo().vep_meta_handler.get_conseq_translations(sample.get("vep", 103))

    payload = {
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
        "pon": pon,
        "sample_ids": sample_ids,
        "bam_id": bam_id,
        "vep_var_class_translations": vep_variant_class_meta,
        "vep_conseq_translations": vep_conseq_meta,
        "assay_group_mappings": assay_group_mappings,
    }
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/unfp", response_model=SampleMutationPayload)
def unmark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    _dna_repo().variant_handler.unmark_false_positive_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_false_positive")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/fp", response_model=SampleMutationPayload)
def mark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    _dna_repo().variant_handler.mark_false_positive_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_false_positive")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/uninterest", response_model=SampleMutationPayload)
def unmark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    _dna_repo().variant_handler.unmark_interesting_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_interesting")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/interest", response_model=SampleMutationPayload)
def mark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    _dna_repo().variant_handler.mark_interesting_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_interesting")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/relevant", response_model=SampleMutationPayload)
def unmark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    _dna_repo().variant_handler.unmark_irrelevant_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_irrelevant")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/irrelevant", response_model=SampleMutationPayload)
def mark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    _dna_repo().variant_handler.mark_irrelevant_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_irrelevant")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/blacklist", response_model=SampleMutationPayload)
def add_variant_to_blacklist(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    _dna_repo().blacklist_handler.blacklist_variant(variant, assay_group)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="blacklist")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/hide", response_model=SampleMutationPayload)
def hide_variant_comment(
    sample_id: str,
    var_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    _dna_repo().variant_handler.hide_var_comment(var_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_comment", resource_id=comment_id, action="hide")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/unhide", response_model=SampleMutationPayload)
def unhide_variant_comment(
    sample_id: str,
    var_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = _dna_repo().variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    _dna_repo().variant_handler.unhide_variant_comment(var_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_comment", resource_id=comment_id, action="unhide")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/fp/bulk", response_model=SampleMutationPayload)
def set_variant_false_positive_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    variant_ids: list[str] = Query(default_factory=list),
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    payload_variant_ids = payload.get("variant_ids") if isinstance(payload, dict) else None
    if isinstance(payload_variant_ids, list):
        variant_ids = payload_variant_ids
    apply = _coerce_bool(payload.get("apply") if isinstance(payload, dict) else None, default=apply)
    if variant_ids:
        if apply:
            _dna_repo().variant_handler.mark_false_positive_var_bulk(variant_ids)
        else:
            _dna_repo().variant_handler.unmark_false_positive_var_bulk(variant_ids)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_false_positive_bulk")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/irrelevant/bulk", response_model=SampleMutationPayload)
def set_variant_irrelevant_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    variant_ids: list[str] = Query(default_factory=list),
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    payload_variant_ids = payload.get("variant_ids") if isinstance(payload, dict) else None
    if isinstance(payload_variant_ids, list):
        variant_ids = payload_variant_ids
    apply = _coerce_bool(payload.get("apply") if isinstance(payload, dict) else None, default=apply)
    if variant_ids:
        if apply:
            _dna_repo().variant_handler.mark_irrelevant_var_bulk(variant_ids)
        else:
            _dna_repo().variant_handler.unmark_irrelevant_var_bulk(variant_ids)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_irrelevant_bulk")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/bulk/tier", response_model=SampleMutationPayload)
def set_variant_tier_bulk(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    variant_ids = payload.get("variant_ids", []) or []
    assay_group = payload.get("assay_group")
    subpanel = payload.get("subpanel")
    apply = _coerce_bool(payload.get("apply", True), default=True)
    tier_raw = payload.get("tier", 3)
    try:
        class_num = int(tier_raw)
    except (TypeError, ValueError):
        class_num = 3
    if class_num not in {1, 2, 3, 4}:
        class_num = 3
    if not variant_ids:
        return util.common.convert_to_serializable(
            _mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_tier_bulk")
        )

    bulk_docs = []
    for variant_id in variant_ids:
        var = _dna_repo().variant_handler.get_variant(str(variant_id))
        if not var:
            continue
        if str(var.get("SAMPLE_ID")) != str(sample.get("_id")):
            continue

        selected_csq = var.get("INFO", {}).get("selected_CSQ", {})
        transcript = selected_csq.get("Feature")
        gene = selected_csq.get("SYMBOL")
        hgvs_p = selected_csq.get("HGVSp")
        hgvs_c = selected_csq.get("HGVSc")
        hgvs_g = f"{var['CHROM']}:{var['POS']}:{var['REF']}/{var['ALT']}"
        consequence = selected_csq.get("Consequence")
        gene_oncokb = _dna_repo().oncokb_handler.get_oncokb_gene(gene)

        text = create_annotation_text_from_gene(
            gene, consequence, assay_group, gene_oncokb=gene_oncokb
        )

        nomenclature = "p"
        if hgvs_p != "" and hgvs_p is not None:
            variant = hgvs_p
        elif hgvs_c != "" and hgvs_c is not None:
            variant = hgvs_c
            nomenclature = "c"
        else:
            variant = hgvs_g
            nomenclature = "g"

        variant_data = {
            "gene": gene,
            "assay_group": assay_group,
            "subpanel": subpanel,
            "transcript": transcript,
        }

        if not apply:
            _dna_repo().annotation_handler.delete_classified_variant(
                variant=variant,
                nomenclature=nomenclature,
                variant_data=variant_data,
                class_num=class_num,
                annotation_text=text,
            )
            continue

        class_doc = util.common.create_classified_variant_doc(
            variant=variant,
            nomenclature=nomenclature,
            class_num=class_num,
            variant_data=variant_data,
        )
        bulk_docs.append(deepcopy(class_doc))

        text_doc = util.common.create_classified_variant_doc(
            variant=variant,
            nomenclature=nomenclature,
            class_num=class_num,
            variant_data=variant_data,
            text=text,
            source="bulk_tier_default_text",
        )
        bulk_docs.append(deepcopy(text_doc))

    if bulk_docs:
        _dna_repo().annotation_handler.insert_annotation_bulk(bulk_docs)

    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_tier_bulk")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/classify", response_model=SampleMutationPayload)
def classify_variant_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="assign_tier", min_role="manager", min_level=99)),
):
    _get_sample_for_api(sample_id, user)
    form_data = payload.get("form_data", {})
    target_id = str(payload.get("id", "unknown"))
    class_num = util.common.get_tier_classification(form_data)
    nomenclature, variant = get_variant_nomenclature(form_data)
    if class_num != 0:
        _dna_repo().annotation_handler.insert_classified_variant(variant, nomenclature, class_num, form_data)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="classification", resource_id=target_id, action="classify")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/rmclassify", response_model=SampleMutationPayload)
def remove_classified_variant_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="remove_tier", min_role="admin")),
):
    _get_sample_for_api(sample_id, user)
    form_data = payload.get("form_data", {})
    target_id = str(payload.get("id", "unknown"))
    nomenclature, variant = get_variant_nomenclature(form_data)
    _dna_repo().annotation_handler.delete_classified_variant(variant, nomenclature, form_data)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="classification", resource_id=target_id, action="remove_classified")
    )


@app.post("/api/v1/dna/samples/{sample_id}/comments/add", response_model=SampleMutationPayload)
def add_variant_comment_mutation(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="add_variant_comment", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    form_data = payload.get("form_data", {})
    target_id = str(payload.get("id", "unknown"))
    nomenclature, variant = get_variant_nomenclature(form_data)
    doc = create_comment_doc(form_data, nomenclature=nomenclature, variant=variant)
    comment_scope = form_data.get("global")
    if comment_scope == "global":
        _dna_repo().annotation_handler.add_anno_comment(doc)
    if nomenclature == "f":
        if comment_scope != "global":
            _dna_repo().fusion_handler.add_fusion_comment(target_id, doc)
        resource = "fusion_comment"
    elif nomenclature == "t":
        if comment_scope != "global":
            _dna_repo().transloc_handler.add_transloc_comment(target_id, doc)
        resource = "translocation_comment"
    elif nomenclature == "cn":
        if comment_scope != "global":
            _dna_repo().cnv_handler.add_cnv_comment(target_id, doc)
        resource = "cnv_comment"
    else:
        if comment_scope != "global":
            _dna_repo().variant_handler.add_var_comment(target_id, doc)
        resource = "variant_comment"
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource=resource, resource_id=target_id, action="add_comment")
    )


