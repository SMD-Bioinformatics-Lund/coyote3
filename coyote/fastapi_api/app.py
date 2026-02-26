"""FastAPI application for Coyote3 API v1."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import os

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse
from flask.sessions import SecureCookieSessionInterface
from itsdangerous import BadSignature

from coyote import init_app
from coyote.extensions import store, util
from coyote.models.user import UserModel
from coyote.services.dna.dna_filters import (
    cnv_organizegenes,
    cnvtype_variant,
    create_cnveffectlist,
    get_filter_conseq_terms,
)
from coyote.services.dna.query_builders import build_cnv_query, build_query
from coyote.services.dna.dna_reporting import hotspot_variant
from coyote.services.dna.dna_variants import format_pon
from coyote.services.interpretation.annotation_enrichment import add_alt_class, add_global_annotations
from coyote.services.workflow.dna_workflow import DNAWorkflowService
from coyote.services.workflow.rna_workflow import RNAWorkflowService


os.environ.setdefault("REQUIRE_EXTERNAL_API", "0")
flask_app = init_app(
    testing=bool(int(os.getenv("TESTING", "0"))),
    development=bool(int(os.getenv("DEVELOPMENT", "0"))),
)
_session_interface = SecureCookieSessionInterface()
_session_serializer = _session_interface.get_signing_serializer(flask_app)

app = FastAPI(
    title="Coyote3 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
)


@dataclass
class ApiUser:
    username: str
    role: str
    access_level: int
    permissions: list[str]
    denied_permissions: list[str]
    assays: list[str]


def _api_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"status": status_code, "error": message})


def _to_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _role_levels() -> dict[str, int]:
    return {role["_id"]: role.get("level", 0) for role in store.roles_handler.get_all_roles()}


def _get_formatted_assay_config(sample: dict):
    assay_config = store.aspc_handler.get_aspc_no_meta(
        sample.get("assay"), sample.get("profile", "production")
    )
    if not assay_config:
        return None
    schema_name = assay_config.get("schema_name")
    assay_config_schema = store.schema_handler.get_schema(schema_name)
    return util.common.format_assay_config(deepcopy(assay_config), assay_config_schema)


def _decode_session_user(request: Request) -> ApiUser:
    cookie_name = flask_app.config.get("SESSION_COOKIE_NAME", "session")
    cookie_val = request.cookies.get(cookie_name)
    if not cookie_val or _session_serializer is None:
        raise _api_error(401, "Login required")

    try:
        session_data = _session_serializer.loads(cookie_val)
    except BadSignature:
        raise _api_error(401, "Login required")

    user_id = session_data.get("_user_id")
    if not user_id:
        raise _api_error(401, "Login required")

    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        raise _api_error(401, "Login required")

    role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
    asp_docs = store.asp_handler.get_all_asps(is_active=True)
    user_model = UserModel.from_mongo(user_doc, role_doc, asp_docs)

    return ApiUser(
        username=user_model.username,
        role=user_model.role,
        access_level=user_model.access_level,
        permissions=list(user_model.permissions),
        denied_permissions=list(user_model.denied_permissions),
        assays=list(user_model.assays),
    )


def _enforce_access(
    user: ApiUser,
    permission: str | None = None,
    min_level: int | None = None,
    min_role: str | None = None,
) -> None:
    resolved_role_level = 0
    if min_role:
        resolved_role_level = _role_levels().get(min_role, 0)

    permission_ok = (
        permission is not None
        and permission in user.permissions
        and permission not in user.denied_permissions
    )
    level_ok = min_level is not None and user.access_level >= min_level
    role_ok = min_role is not None and user.access_level >= resolved_role_level

    if permission or min_level is not None or min_role:
        if not (permission_ok or level_ok or role_ok):
            raise _api_error(403, "You do not have access to this page.")


def require_access(
    permission: str | None = None,
    min_level: int | None = None,
    min_role: str | None = None,
):
    def dep(request: Request) -> ApiUser:
        user = _decode_session_user(request)
        _enforce_access(user, permission=permission, min_level=min_level, min_role=min_role)
        return user

    return dep


def _get_sample_for_api(sample_id: str, user: ApiUser):
    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        sample = store.sample_handler.get_sample_by_id(sample_id)
    if not sample:
        raise _api_error(404, "Sample not found")

    sample_assay = sample.get("assay", "")
    if sample_assay not in set(user.assays or []):
        raise _api_error(403, "Access denied: sample assay mismatch")
    return sample


@app.exception_handler(HTTPException)
async def http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": exc.status_code, "error": str(exc.detail)},
    )


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/vi/docs", include_in_schema=False)
def docs_alias_vi():
    return RedirectResponse(url="/api/v1/docs", status_code=307)


@app.get("/api/v1/auth/whoami")
def whoami(user: ApiUser = Depends(require_access(min_level=1))):
    return {
        "username": user.username,
        "role": user.role,
        "access_level": user.access_level,
        "permissions": sorted(user.permissions),
        "denied_permissions": sorted(user.denied_permissions),
    }


@app.get("/api/v1/dna/samples/{sample_id}/variants")
def list_dna_variants(request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")

    sample = util.common.merge_sample_settings_with_assay_config(sample, assay_config)
    sample_filters = deepcopy(sample.get("filters", {}))
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")

    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample.get("assay"))
    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict = store.isgl_handler.get_isgl_by_ids(checked_genelists)
    _genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_genelists_genes_dict
    )
    filter_conseq = get_filter_conseq_terms(sample_filters.get("vep_consequences", []))

    disp_pos = []
    if assay_config.get("verification_samples"):
        verification_samples = assay_config.get("verification_samples")
        for veri_key, verification_pos in verification_samples.items():
            if veri_key in sample.get("name", ""):
                disp_pos = verification_pos
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

    variants = list(store.variant_handler.get_case_variants(query))
    variants = store.blacklist_handler.add_blacklist_data(variants, assay_group)
    variants, tiered_variants = add_global_annotations(variants, assay_group, subpanel)
    variants = hotspot_variant(variants)

    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
            "assay_group": assay_group,
            "subpanel": subpanel,
        },
        "meta": {"request_path": request.url.path, "count": len(variants), "tiered": tiered_variants},
        "filters": sample_filters,
        "variants": variants,
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/dna/samples/{sample_id}/variants/{var_id}")
def show_dna_variant(sample_id: str, var_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant:
        raise _api_error(404, "Variant not found")
    if str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")

    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")

    variant = store.blacklist_handler.add_blacklist_data([variant], assay_group)[0]
    in_other = store.variant_handler.get_variant_in_other_samples(variant)
    has_hidden_comments = store.variant_handler.hidden_var_comments(var_id)
    annotations, latest_classification, other_classifications, annotations_interesting = (
        store.annotation_handler.get_global_annotations(variant, assay_group, subpanel)
    )
    if not latest_classification or latest_classification.get("class") == 999:
        variant = add_alt_class(variant, assay_group, subpanel)
    else:
        variant["additional_classifications"] = None

    expression = store.expression_handler.get_expression_data(list(variant.get("transcripts", [])))

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

    civic = store.civic_handler.get_civic_data(variant, variant_desc)
    civic_gene = store.civic_handler.get_civic_gene_info(selected_csq.get("SYMBOL"))

    one_letter_p = flask_app.jinja_env.filters.get("one_letter_p", lambda x: x)
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

    oncokb = store.oncokb_handler.get_oncokb_anno(variant, oncokb_hgvsp)
    oncokb_action = store.oncokb_handler.get_oncokb_action(variant, oncokb_hgvsp)
    oncokb_gene = store.oncokb_handler.get_oncokb_gene(selected_csq.get("SYMBOL"))
    brca_exchange = store.brca_handler.get_brca_data(variant, assay_group)
    iarc_tp53 = store.iarc_tp53_handler.find_iarc_tp53(variant)

    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)

    pon = format_pon(variant)
    assay_group_mappings = store.asp_handler.get_asp_group_mappings()
    vep_variant_class_meta = store.vep_meta_handler.get_variant_class_translations(sample.get("vep", 103))
    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(sample.get("vep", 103))

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


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/unfp")
def unmark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    store.variant_handler.unmark_false_positive_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_false_positive")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/fp")
def mark_false_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    store.variant_handler.mark_false_positive_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_false_positive")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/uninterest")
def unmark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    store.variant_handler.unmark_interesting_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_interesting")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/interest")
def mark_interesting_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    store.variant_handler.mark_interesting_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_interesting")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/relevant")
def unmark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    store.variant_handler.unmark_irrelevant_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="unmark_irrelevant")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/irrelevant")
def mark_irrelevant_variant(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    store.variant_handler.mark_irrelevant_var(var_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="mark_irrelevant")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/blacklist")
def add_variant_to_blacklist(
    sample_id: str,
    var_id: str,
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    store.blacklist_handler.blacklist_variant(variant, assay_group)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant", resource_id=var_id, action="blacklist")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/hide")
def hide_variant_comment(
    sample_id: str,
    var_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    store.variant_handler.hide_var_comment(var_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_comment", resource_id=comment_id, action="hide")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/unhide")
def unhide_variant_comment(
    sample_id: str,
    var_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
):
    sample = _get_sample_for_api(sample_id, user)
    variant = store.variant_handler.get_variant(var_id)
    if not variant or str(variant.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Variant not found for sample")
    store.variant_handler.unhide_variant_comment(var_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_comment", resource_id=comment_id, action="unhide")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/bulk/fp")
def set_variant_false_positive_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    variant_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    if variant_ids:
        if apply:
            store.variant_handler.mark_false_positive_var_bulk(variant_ids)
        else:
            store.variant_handler.unmark_false_positive_var_bulk(variant_ids)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_false_positive_bulk")
    )


@app.post("/api/v1/dna/samples/{sample_id}/variants/bulk/irrelevant")
def set_variant_irrelevant_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    variant_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(permission="manage_snvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    if variant_ids:
        if apply:
            store.variant_handler.mark_irrelevant_var_bulk(variant_ids)
        else:
            store.variant_handler.unmark_irrelevant_var_bulk(variant_ids)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="variant_bulk", resource_id="bulk", action="set_irrelevant_bulk")
    )


@app.get("/api/v1/rna/samples/{sample_id}/fusions")
def list_rna_fusions(request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")

    sample, sample_filters = RNAWorkflowService.merge_and_normalize_sample_filters(
        sample, assay_config, sample_id, flask_app.logger
    )
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample.get("assay"))
    filter_context = RNAWorkflowService.compute_filter_context(
        sample=sample, sample_filters=sample_filters, assay_panel_doc=assay_panel_doc
    )
    query = RNAWorkflowService.build_fusion_list_query(
        assay_group=assay_group,
        sample_id=str(sample["_id"]),
        sample_filters=sample_filters,
        filter_context=filter_context,
    )
    fusions = list(store.fusion_handler.get_sample_fusions(query))
    fusions, tiered_fusions = add_global_annotations(fusions, assay_group, subpanel)

    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
            "assay_group": assay_group,
            "subpanel": subpanel,
        },
        "meta": {"request_path": request.url.path, "count": len(fusions), "tiered": tiered_fusions},
        "filters": sample_filters,
        "filter_context": filter_context,
        "fusions": fusions,
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}")
def show_rna_fusion(sample_id: str, fusion_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    fusion = store.fusion_handler.get_fusion(fusion_id)
    if not fusion:
        raise _api_error(404, "Fusion not found")
    if str(fusion.get("SAMPLE_ID", "")) != str(sample.get("_id")):
        raise _api_error(404, "Fusion not found for sample")

    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    assay_group = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    show_context = RNAWorkflowService.build_show_fusion_context(fusion, assay_group, subpanel)

    payload = {
        "sample": sample,
        "sample_summary": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "assay_group": assay_group,
            "subpanel": subpanel,
        },
        "fusion": show_context["fusion"],
        "in_other": show_context["in_other"],
        "annotations": show_context["annotations"],
        "latest_classification": show_context["latest_classification"],
        "annotations_interesting": show_context["annotations_interesting"],
        "other_classifications": show_context["other_classifications"],
        "has_hidden_comments": show_context["hidden_comments"],
        "hidden_comments": show_context["hidden_comments"],
        "assay_group": assay_group,
        "subpanel": subpanel,
        "assay_group_mappings": show_context["assay_group_mappings"],
    }
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/fp")
def mark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.mark_false_positive_fusion(fusion_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="mark_false_positive")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/unfp")
def unmark_false_positive_fusion(
    sample_id: str,
    fusion_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.unmark_false_positive_fusion(fusion_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="unmark_false_positive")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/pick/{callidx}/{num_calls}")
def pick_fusion_call(
    sample_id: str,
    fusion_id: str,
    callidx: str,
    num_calls: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.pick_fusion(fusion_id, callidx, num_calls)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion", resource_id=fusion_id, action="pick_fusion_call")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hide")
def hide_fusion_comment(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.hide_fus_comment(fusion_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_comment", resource_id=comment_id, action="hide")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/unhide")
def unhide_fusion_comment(
    sample_id: str,
    fusion_id: str,
    comment_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    store.fusion_handler.unhide_fus_comment(fusion_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_comment", resource_id=comment_id, action="unhide")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/bulk/fp")
def set_fusion_false_positive_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    if fusion_ids:
        store.fusion_handler.mark_false_positive_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_bulk", resource_id="bulk", action="set_false_positive_bulk")
    )


@app.post("/api/v1/rna/samples/{sample_id}/fusions/bulk/irrelevant")
def set_fusion_irrelevant_bulk(
    sample_id: str,
    apply: bool = Query(default=True),
    fusion_ids: list[str] = Query(default_factory=list),
    user: ApiUser = Depends(require_access(min_level=1)),
):
    _get_sample_for_api(sample_id, user)
    if fusion_ids:
        store.fusion_handler.mark_irrelevant_bulk(fusion_ids, apply)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="fusion_bulk", resource_id="bulk", action="set_irrelevant_bulk")
    )


@app.get("/api/v1/dna/samples/{sample_id}/cnvs")
def list_dna_cnvs(request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")

    sample = util.common.merge_sample_settings_with_assay_config(sample, assay_config)
    sample_filters = deepcopy(sample.get("filters", {}))
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample.get("assay"))
    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict = store.isgl_handler.get_isgl_by_ids(checked_genelists)
    _genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_genelists_genes_dict
    )
    cnv_query = build_cnv_query(str(sample["_id"]), filters={**sample_filters, "filter_genes": filter_genes})
    cnvs = list(store.cnv_handler.get_sample_cnvs(cnv_query))
    filter_cnveffects = create_cnveffectlist(sample_filters.get("cnveffects", []))
    if filter_cnveffects:
        cnvs = cnvtype_variant(cnvs, filter_cnveffects)
    cnvs = cnv_organizegenes(cnvs)

    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "meta": {"request_path": request.url.path, "count": len(cnvs)},
        "filters": sample_filters,
        "cnvs": cnvs,
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}")
def show_dna_cnv(sample_id: str, cnv_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    cnv = store.cnv_handler.get_cnv(cnv_id)
    if not cnv:
        raise _api_error(404, "CNV not found")
    cnv_sample_id = cnv.get("SAMPLE_ID") or cnv.get("sample_id")
    if cnv_sample_id and str(cnv_sample_id) != str(sample.get("_id")):
        raise _api_error(404, "CNV not found for sample")
    if not cnv_sample_id:
        sample_cnvs = list(store.cnv_handler.get_sample_cnvs({"SAMPLE_ID": str(sample.get("_id"))}))
        sample_cnv_ids = {str(doc.get("_id")) for doc in sample_cnvs}
        if str(cnv.get("_id")) not in sample_cnv_ids:
            raise _api_error(404, "CNV not found for sample")

    assay_config = _get_formatted_assay_config(sample)
    assay_group = assay_config.get("asp_group", "unknown") if assay_config else "unknown"
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))

    payload = {
        "sample": sample,
        "sample_summary": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "assay_group": assay_group,
        },
        "cnv": cnv,
        "annotations": store.cnv_handler.get_cnv_annotations(cnv),
        "sample_ids": sample_ids,
        "bam_id": store.bam_service_handler.get_bams(sample_ids),
        "has_hidden_comments": store.cnv_handler.hidden_cnv_comments(cnv_id),
        "hidden_comments": store.cnv_handler.hidden_cnv_comments(cnv_id),
        "assay_group": assay_group,
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/dna/samples/{sample_id}/translocations")
def list_dna_translocations(
    request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))
):
    sample = _get_sample_for_api(sample_id, user)
    translocs = list(store.transloc_handler.get_sample_translocations(sample_id=str(sample["_id"])))
    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "meta": {"request_path": request.url.path, "count": len(translocs)},
        "translocations": translocs,
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}")
def show_dna_translocation(
    sample_id: str, transloc_id: str, user: ApiUser = Depends(require_access(min_level=1))
):
    sample = _get_sample_for_api(sample_id, user)
    transloc = store.transloc_handler.get_transloc(transloc_id)
    if not transloc:
        raise _api_error(404, "Translocation not found")
    transloc_sample_id = transloc.get("SAMPLE_ID") or transloc.get("sample_id")
    if transloc_sample_id and str(transloc_sample_id) != str(sample.get("_id")):
        raise _api_error(404, "Translocation not found for sample")
    if not transloc_sample_id:
        sample_translocs = list(
            store.transloc_handler.get_sample_translocations(sample_id=str(sample.get("_id")))
        )
        sample_transloc_ids = {str(doc.get("_id")) for doc in sample_translocs}
        if str(transloc.get("_id")) not in sample_transloc_ids:
            raise _api_error(404, "Translocation not found for sample")

    assay_config = _get_formatted_assay_config(sample)
    assay_group = assay_config.get("asp_group", "unknown") if assay_config else "unknown"
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))

    payload = {
        "sample": sample,
        "sample_summary": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "assay_group": assay_group,
        },
        "translocation": transloc,
        "annotations": store.transloc_handler.get_transloc_annotations(transloc),
        "sample_ids": sample_ids,
        "bam_id": store.bam_service_handler.get_bams(sample_ids),
        "vep_conseq_translations": store.vep_meta_handler.get_conseq_translations(sample.get("vep", 103)),
        "has_hidden_comments": store.transloc_handler.hidden_transloc_comments(transloc_id),
        "hidden_comments": store.transloc_handler.hidden_transloc_comments(transloc_id),
        "assay_group": assay_group,
    }
    return util.common.convert_to_serializable(payload)


def _mutation_payload(sample_id: str, resource: str, resource_id: str, action: str) -> dict:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


@app.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unmarkinteresting")
def unmark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.cnv_handler.unmark_interesting_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_interesting")
    )


@app.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/interesting")
def mark_interesting_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.cnv_handler.mark_interesting_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_interesting")
    )


@app.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/fpcnv")
def mark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.cnv_handler.mark_false_positive_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_false_positive")
    )


@app.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unfpcnv")
def unmark_false_positive_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.cnv_handler.unmark_false_positive_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_false_positive")
    )


@app.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/noteworthycnv")
def mark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.cnv_handler.noteworthy_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="mark_noteworthy")
    )


@app.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/notnoteworthycnv")
def unmark_noteworthy_cnv(
    sample_id: str,
    cnv_id: str,
    user: ApiUser = Depends(require_access(permission="manage_cnvs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.cnv_handler.unnoteworthy_cnv(cnv_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv", resource_id=cnv_id, action="unmark_noteworthy")
    )


@app.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hide")
def hide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
):
    _get_sample_for_api(sample_id, user)
    store.cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv_comment", resource_id=comment_id, action="hide")
    )


@app.post("/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/unhide")
def unhide_cnv_comment(
    sample_id: str,
    cnv_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
):
    _get_sample_for_api(sample_id, user)
    store.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="cnv_comment", resource_id=comment_id, action="unhide")
    )


@app.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/interestingtransloc")
def mark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.transloc_handler.mark_interesting_transloc(transloc_id)
    return util.common.convert_to_serializable(
        _mutation_payload(
            sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="mark_interesting",
        )
    )


@app.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/uninterestingtransloc")
def unmark_interesting_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.transloc_handler.unmark_interesting_transloc(transloc_id)
    return util.common.convert_to_serializable(
        _mutation_payload(
            sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="unmark_interesting",
        )
    )


@app.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/fptransloc")
def mark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.transloc_handler.mark_false_positive_transloc(transloc_id)
    return util.common.convert_to_serializable(
        _mutation_payload(
            sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="mark_false_positive",
        )
    )


@app.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/ptransloc")
def unmark_false_positive_translocation(
    sample_id: str,
    transloc_id: str,
    user: ApiUser = Depends(require_access(permission="manage_translocs", min_role="user", min_level=9)),
):
    _get_sample_for_api(sample_id, user)
    store.transloc_handler.unmark_false_positive_transloc(transloc_id)
    return util.common.convert_to_serializable(
        _mutation_payload(
            sample_id,
            resource="translocation",
            resource_id=transloc_id,
            action="unmark_false_positive",
        )
    )


@app.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hide")
def hide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_variant_comment", min_role="manager", min_level=99)
    ),
):
    _get_sample_for_api(sample_id, user)
    store.transloc_handler.hide_transloc_comment(transloc_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="translocation_comment", resource_id=comment_id, action="hide")
    )


@app.post("/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/unhide")
def unhide_translocation_comment(
    sample_id: str,
    transloc_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_variant_comment", min_role="manager", min_level=99)
    ),
):
    _get_sample_for_api(sample_id, user)
    store.transloc_handler.unhide_transloc_comment(transloc_id, comment_id)
    return util.common.convert_to_serializable(
        _mutation_payload(sample_id, resource="translocation_comment", resource_id=comment_id, action="unhide")
    )


@app.get("/api/v1/dna/samples/{sample_id}/report/preview")
def preview_dna_report(
    sample_id: str,
    include_snapshot: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="preview_report", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    DNAWorkflowService.validate_report_inputs(flask_app.logger, sample, assay_config)

    html, snapshot_rows = DNAWorkflowService.build_report_payload(
        sample=sample,
        assay_config=assay_config,
        save=0,
        include_snapshot=_to_bool(include_snapshot, default=False),
    )
    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "meta": {
            "request_path": f"/api/v1/dna/samples/{sample_id}/report/preview",
            "include_snapshot": include_snapshot,
            "snapshot_count": len(snapshot_rows),
        },
        "report": {"html": html, "snapshot_rows": snapshot_rows if include_snapshot else []},
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/rna/samples/{sample_id}/report/preview")
def preview_rna_report(
    sample_id: str,
    include_snapshot: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="preview_report", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    RNAWorkflowService.validate_report_inputs(flask_app.logger, sample, assay_config)

    html, snapshot_rows = RNAWorkflowService.build_report_payload(
        sample=sample,
        save=0,
        include_snapshot=_to_bool(include_snapshot, default=False),
    )
    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "meta": {
            "request_path": f"/api/v1/rna/samples/{sample_id}/report/preview",
            "include_snapshot": include_snapshot,
            "snapshot_count": len(snapshot_rows),
        },
        "report": {"html": html, "snapshot_rows": snapshot_rows if include_snapshot else []},
    }
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/dna/samples/{sample_id}/report/save")
def save_dna_report(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    DNAWorkflowService.validate_report_inputs(flask_app.logger, sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = DNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=flask_app.config.get("REPORTS_BASE_PATH", "reports"),
    )
    DNAWorkflowService.prepare_report_output(report_path, report_file, logger=flask_app.logger)

    html, snapshot_rows = DNAWorkflowService.build_report_payload(
        sample=sample,
        assay_config=assay_config,
        save=1,
        include_snapshot=True,
    )
    report_oid = DNAWorkflowService.persist_report(
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=user.username,
    )

    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "report": {
            "id": report_id,
            "oid": str(report_oid),
            "file": report_file,
            "snapshot_count": len(snapshot_rows),
        },
        "meta": {"status": "saved"},
    }
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/rna/samples/{sample_id}/report/save")
def save_rna_report(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    RNAWorkflowService.validate_report_inputs(flask_app.logger, sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = RNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=flask_app.config.get("REPORTS_BASE_PATH", "reports"),
    )
    RNAWorkflowService.prepare_report_output(report_path, report_file, logger=flask_app.logger)

    html, snapshot_rows = RNAWorkflowService.build_report_payload(
        sample=sample,
        save=1,
        include_snapshot=True,
    )
    report_oid = RNAWorkflowService.persist_report(
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=user.username,
    )

    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "report": {
            "id": report_id,
            "oid": str(report_oid),
            "file": report_file,
            "snapshot_count": len(snapshot_rows),
        },
        "meta": {"status": "saved"},
    }
    return util.common.convert_to_serializable(payload)
