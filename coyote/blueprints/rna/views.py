#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
Views for handling RNA fusion cases in the Coyote3 application.
All routes require user authentication and appropriate sample access.
"""

import os

from flask import current_app as app
from flask import (
    flash,
    redirect,
    render_template,
    request,
    url_for,
    Response,
)
from flask_login import current_user, login_required

from coyote.blueprints.rna.forms import FusionFilter

from coyote.extensions import store, util
from coyote.blueprints.rna import rna_bp, filters
from datetime import datetime
from coyote.errors.exceptions import AppError
from coyote.util.decorators.access import require_sample_access
from coyote.util.misc import get_sample_and_assay_config
from coyote.services.auth.decorators import require
from coyote.util.common_utility import CommonUtility
from copy import deepcopy
from coyote.blueprints.rna.fusion_queries import build_fusion_query


@rna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
@require_sample_access("sample_id")
def list_fusions(sample_id: str) -> str | Response:
    """
    Display and filter RNA fusion events for a given sample.

    This view handles both GET and POST requests to display fusion events
    for the specified sample. It supports dynamic filtering of fusions
    based on user input, manages sample group and assay configuration,
    and prepares data for rendering the fusion list template.

    Parameters:
        sample_id (str): The sample identifier.

    Returns:
        Response: Rendered HTML template for the fusion list page.
    """

    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    sample_has_filters = sample.get("filters", None)

    ## get the assay from the sample, fallback to the first group if not set
    sample_assay = sample.get("assay")

    # Get the profile from the sample, fallback to production if not set
    sample_profile = sample.get("profile", "production")

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get("asp_group", "unknown")  # myeloid, solid, lymphoid
    subpanel: str | None = sample.get("subpanel")  # breast, LP, lung, etc.
    analysis_sections = assay_config.get("analysis_types", [])
    display_sections_data = {}
    summary_sections_data = {}
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

    # Get fusion lists for the sample panel (RNA-specific; list_type="fusionlist")
    fusionlist_options = store.isgl_handler.get_isgl_by_asp(
        sample_assay, is_active=True, list_type="fusionlist"
    )

    # Adding default fusion lists to RNA assay config if diagnosis-driven lists are enabled
    if assay_config.get("use_diagnosis_genelist", False) and subpanel:
        assay_default_config_fusionlist_ids = store.isgl_handler.get_isgl_ids(
            sample_assay, subpanel, "fusionlist", is_active=True
        )
        assay_config["filters"].setdefault("fusionlists", [])
        assay_config["filters"]["fusionlists"].extend(assay_default_config_fusionlist_ids)

    # Get filter settings from the sample and merge with assay config if sample does not have values
    sample = util.common.merge_sample_settings_with_assay_config(sample, assay_config)
    sample_filters = deepcopy(sample.get("filters", {}))

    # Update the sample filters with the default values from the assay config if the sample is new and does not have any filters set
    if not sample_has_filters:
        store.sample_handler.reset_sample_settings(sample["_id"], assay_config.get("filters"))

    # Create the form
    form = FusionFilter()

    ###########################################################################
    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        _id = str(sample.get("_id"))
        # Reset filters to defaults
        if form.reset.data:
            app.logger.info(f"Resetting filters to default settings for the sample {sample_id}")
            store.sample_handler.reset_sample_settings(_id, assay_config.get("filters", {}))
        else:
            filters_from_form = util.common.format_filters_from_form(form, assay_config_schema)
            # Dynamic RNA fusionlists are rendered as manual checkboxes in template.
            # Persist selected list IDs explicitly.
            filters_from_form["fusionlists"] = request.form.getlist("fusionlist_id")
            # Persist fusion callers using canonical values as stored in fusion docs.
            filters_from_form["fusion_callers"] = util.rna.create_fusioncallers(
                filters_from_form.get("fusion_callers", [])
            )
            # Persist fusion effects using canonical values as stored in fusion docs.
            filters_from_form["fusion_effects"] = util.rna.create_fusioneffectlist(
                filters_from_form.get("fusion_effects", [])
            )
            # if there are any adhoc genes for the sample, add them to the form data before saving
            if sample.get("filters", {}).get("adhoc_genes"):
                filters_from_form["adhoc_genes"] = sample.get("filters", {}).get("adhoc_genes")
            store.sample_handler.update_sample_filters(_id, filters_from_form)

        ## get sample again to receive updated forms!
        sample = store.sample_handler.get_sample_by_id(_id)
        sample_filters = deepcopy(sample.get("filters"))
    ############################################################################
    # Check if sample has hidden comments
    has_hidden_comments = store.sample_handler.hidden_sample_comments(sample.get("_id"))

    fusion_effects = util.rna.create_fusioneffectlist(sample_filters.get("fusion_effects", []))
    fusion_callers = util.rna.create_fusioncallers(sample_filters.get("fusion_callers", []))
    checked_fusionlists = sample_filters.get("fusionlists", [])

    checked_fusionlists_genes_dict: list[dict] = store.isgl_handler.get_isgl_by_ids(
        checked_fusionlists
    )
    # Reuse common effective-gene helper by mapping selected fusionlists as working genelists.
    sample_for_gene_filter = deepcopy(sample)
    sample_for_gene_filter.setdefault("filters", {})
    sample_for_gene_filter["filters"]["genelists"] = checked_fusionlists
    genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
        sample_for_gene_filter, assay_panel_doc, checked_fusionlists_genes_dict
    )

    # Convert canonical values back to checkbox suffixes used by the WTForm field names.
    fusion_effect_form_keys = []
    for effect in fusion_effects:
        if effect == "in-frame":
            fusion_effect_form_keys.append("inframe")
        elif effect == "out-of-frame":
            fusion_effect_form_keys.append("outframe")

    # Add them to the form and update with the requested settings
    form_data = deepcopy(sample_filters)
    form_data.update(
        {
            **{f"fusioncaller_{k}": True for k in fusion_callers},
            **{f"fusioneffect_{k}": True for k in fusion_effect_form_keys},
            **{f"fusionlist_{k}": True for k in checked_fusionlists},
            **{assay_group: True},
        }
    )
    form.process(data=form_data)

    ## Change this to fusionquery.py

    query = build_fusion_query(
        assay_group,
        settings={
            "id": str(sample["_id"]),
            "min_spanning_reads": sample_filters.get("min_spanning_reads", 0),
            "min_spanning_pairs": sample_filters.get("min_spanning_pairs", 0),
            "fusion_effects": fusion_effects,
            "fusion_callers": fusion_callers,
            "checked_fusionlists": checked_fusionlists,
            "filter_genes": filter_genes,
        },
    )

    fusions = list(store.fusion_handler.get_sample_fusions(query))

    fusions, tiered_fusions = util.dna.add_global_annotations(fusions, assay_group, subpanel)
    summary_sections_data["fusions"] = tiered_fusions

    app.logger.info(f"this is the fusion and fusion query,{query}")

    # TODO: load them as a display_sections_data instead of attaching to sample
    sample["expr"] = store.rna_expression_handler.get_rna_expression(str(sample["_id"]))
    sample["classification"] = store.rna_classification_handler.get_rna_classification(
        str(sample["_id"])
    )
    sample["QC_metrics"] = store.rna_qc_handler.get_rna_qc(str(sample["_id"]))

    # AI summary suggestion text for "Suggest" button, aligned with DNA flow.
    ai_text = util.bpcommon.generate_summary_text(
        sample_ids,
        assay_config,
        assay_panel_doc,
        summary_sections_data,
        filter_genes,
        checked_fusionlists,
    )

    # Your logic for handling RNA samples
    return render_template(
        "list_fusions.html",
        sample=sample,
        form=form,
        fusions=fusions,
        fusionlist_options=fusionlist_options,
        checked_fusionlists=checked_fusionlists,
        checked_fusionlists_dict=genes_covered_in_panel,
        hidden_comments=has_hidden_comments,
        ai_text=ai_text,
        sample_id=sample["_id"],
    )


@rna_bp.route("/<string:sample_id>/fusion/<string:fusion_id>")
@require_sample_access("sample_id")
def show_fusion(sample_id: str, fusion_id: str) -> Response | str:
    """
    Display details for a specific RNA fusion event.

    Retrieves the fusion by its ID, fetches the associated sample, obtains
    annotations and classification for the fusion, and renders the
    show_fusion.html template with this data.

    Args:
        sample_id (str): The unique identifier of the sample.
        fusion_id (str): The unique identifier of the fusion event.

    Returns:
        Response | str: Rendered HTML template for the fusion details page.
    """
    fusion = store.fusion_handler.get_fusion(fusion_id)

    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get("asp_group", "unknown")  # myeloid, solid, lymphoid
    subpanel: str | None = sample.get("subpanel")  # breast, LP, lung, etc.

    # Get sample data if the fusion is present in other samples
    in_other = store.fusion_handler.get_fusion_in_other_samples(fusion)

    # annotations, latest_classification = store.fusion_handler.get_fusion_annotations(fusion)
    # Get global annotations for the fusion

    selected_fusion_call = util.rna.get_selected_fusioncall(fusion)
    (
        annotations,
        latest_classification,
        other_classifications,
        annotations_interesting,
    ) = store.annotation_handler.get_global_annotations(selected_fusion_call, assay_group, subpanel)

    if not latest_classification or latest_classification.get("class") == 999:
        fusion = util.dna.add_alt_class(fusion, assay_group, subpanel)
    else:
        fusion["additional_classifications"] = None

    # Check if variant has hidden comments
    has_hidden_comments = store.fusion_handler.hidden_fusion_comments(fusion_id)

    # Get assay groups mappings with the sample assay
    assay_group_mappings = store.asp_handler.get_asp_group_mappings()

    # get all the fusion callsers to the top level in the fusion doc
    fusion["fusion_callers"] = util.rna.get_fusion_callers(fusion)

    return render_template(
        "show_fusion.html",
        fusion=fusion,
        in_other=in_other,
        sample=sample,
        annotations=annotations,
        latest_classification=latest_classification,
        annotations_interesting=annotations_interesting,
        other_classifications=other_classifications,
        hidden_comments=has_hidden_comments,
        assay_group=assay_group,
        subpanel=subpanel,
        assay_group_mappings=assay_group_mappings,
    )


@rna_bp.route("/<string:sample_id>/fusion/fp/<string:fus_id>", methods=["POST"])
@require_sample_access("sample_id")
def mark_false_fusion(sample_id: str, fus_id: str) -> Response:
    """
    Mark the specified RNA fusion event as a false positive in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the fusion details page after updating the status.

    """
    store.fusion_handler.mark_false_positive_fusion(fus_id)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/unfp/<string:fus_id>", methods=["POST"])
@require_sample_access("sample_id")
def unmark_false_fusion(sample_id: str, fus_id: str) -> Response:
    """
    Unmark the False Positive status of a fusion event in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the fusion details page after updating the status.
    """
    store.fusion_handler.unmark_false_positive_fusion(fus_id)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route(
    "/<string:sample_id>/fusion/pickfusioncall/<string:fus_id>/<string:callidx>/<string:num_calls>",
    methods=["GET", "POST"],
)
@require_sample_access("sample_id")
def pick_fusioncall(sample_id: str, fus_id: str, callidx: str, num_calls: str) -> Response:
    """
    Pick a specific fusion call for a fusion event.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.
        callidx (str): The index of the fusion call to pick.
        num_calls (str): The total number of fusion calls.

    Returns:
        Response: Redirects to the fusion details page after updating the picked call.
    """
    store.fusion_handler.pick_fusion(fus_id, callidx, num_calls)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/hide_fusion_comment/<string:fus_id>", methods=["POST"])
@require_sample_access("sample_id")
def hide_fusion_comment(sample_id: str, fus_id: str) -> Response:
    """
    Hide a comment associated with a fusion event.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the variant details page after hiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.fusion_handler.hide_fus_comment(fus_id, comment_id)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/unhide_fusion_comment/<string:fus_id>", methods=["POST"])
@require_sample_access("sample_id")
def unhide_fusion_comment(sample_id: str, fus_id: str) -> Response:
    """
    Unhide a previously hidden comment associated with a fusion event.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the variant details page after unhiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.fusion_handler.unhide_fus_comment(fus_id, comment_id)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


##### PREVIEW REPORT ####
def _build_rna_snapshot_rows(fusions: list[dict]) -> list[dict]:
    """Create reported_variants snapshot rows from RNA fusions included in the report."""
    created_on = CommonUtility.utc_now()
    rows = []

    for fus in fusions:
        cls = fus.get("classification") or {}
        tier = cls.get("class", 999)
        if fus.get("blacklist") or tier in (None, 999, 4):
            continue

        calls = fus.get("calls") or []
        selected = next((c for c in calls if c.get("selected") == 1), calls[0] if calls else {})

        gene1 = fus.get("gene1")
        gene2 = fus.get("gene2")
        if (
            (not gene1 or not gene2)
            and isinstance(fus.get("genes"), str)
            and "^" in fus.get("genes")
        ):
            _g = fus.get("genes").split("^")
            gene1 = gene1 or _g[0]
            gene2 = gene2 or (_g[1] if len(_g) > 1 else None)

        bp1 = selected.get("breakpoint1", "")
        bp2 = selected.get("breakpoint2", "")

        simple_id = f"{gene1 or 'NA'}::{gene2 or 'NA'}::{bp1}::{bp2}"
        rows.append(
            {
                "var_oid": fus.get("_id"),
                "simple_id": simple_id,
                "tier": tier,
                "gene": f"{gene1 or 'NA'}-{gene2 or 'NA'}",
                "transcript": selected.get("transcript"),
                "hgvsp": None,
                "hgvsc": None,
                "created_on": created_on,
                "annotation_oid": cls.get("_id"),
            }
        )

    return rows


def _build_rna_report_payload(sample: dict, save: int = 0, include_snapshot: bool = False):
    """Build RNA report HTML and optional reported-variant snapshot rows."""
    assay = util.common.get_assay_from_sample(sample)
    fusion_query = {"SAMPLE_ID": str(sample["_id"])}
    fusions = list(store.fusion_handler.get_sample_fusions(fusion_query))

    for fus_idx, fus in enumerate(fusions):
        (
            fusions[fus_idx]["global_annotations"],
            fusions[fus_idx]["classification"],
        ) = store.fusion_handler.get_fusion_annotations(fusions[fus_idx])

    class_desc = list(app.config.get("REPORT_CONFIG").get("CLASS_DESC").values())
    class_desc_short = list(app.config.get("REPORT_CONFIG").get("CLASS_DESC_SHORT").values())
    analysis_desc = app.config.get("REPORT_CONFIG").get("ANALYSIS_DESCRIPTION", {}).get(assay)
    analysis_method = util.common.get_analysis_method(assay)
    report_header = util.common.get_report_header(assay, sample)
    report_date = datetime.now().date()

    html = render_template(
        "report_fusion.html",
        assay=assay,
        fusions=fusions,
        report_header=report_header,
        analysis_method=analysis_method,
        analysis_desc=analysis_desc,
        sample=sample,
        class_desc=class_desc,
        class_desc_short=class_desc_short,
        report_date=report_date,
        save=save,
    )

    if not include_snapshot:
        return html, []
    return html, _build_rna_snapshot_rows(fusions)


@rna_bp.route("/sample/<string:sample_id>/preview_report", methods=["GET", "POST"])
@rna_bp.route("/sample/preview_report/<string:sample_id>", methods=["GET", "POST"])
@require_sample_access("sample_id")
@require("preview_report", min_role="user", min_level=9)
def generate_rna_report(sample_id: str, **kwargs) -> Response | str:
    """
    Generate and render a preview of the RNA report for a given sample.
    """
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, _, _ = result

    sample_assay = sample.get("assay", None)
    if sample_assay is None:
        flash("No assay group found for sample", "red")
        return redirect(url_for("home_bp.samples_home"))

    save = kwargs.get("save", 0)
    try:
        html, _ = _build_rna_report_payload(sample, save=save, include_snapshot=False)
        return html
    except Exception as exc:
        app.logger.exception(f"Failed to generate preview report: {exc}")
        flash("Failed to generate report preview.", "red")
        return redirect(url_for("home_bp.samples_home"))


@rna_bp.route("/sample/<string:sample_id>/report/save")
@require_sample_access("sample_id")
@require("create_report", min_role="admin")
def save_rna_report(sample_id: str) -> Response:
    """
    Generate and persist an RNA HTML report + reported_variant snapshots.

    Args:
        sample_id (str): The unique identifier of the sample.

    Returns:
        Response: Redirect to samples home with success/error flash.
    """
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, _ = result

    case_id = sample.get("case_id")
    control_id = sample.get("control_id")
    clarity_case_id = sample.get("case", {}).get("clarity_id")
    clarity_control_id = sample.get("control", {}).get("clarity_id")

    assay_group: str = assay_config.get("asp_group", "rna")
    report_num: int = sample.get("report_num", 0) + 1
    report_timestamp: str = util.dna.get_report_timestamp()

    if control_id:
        report_id: str = (
            f"{case_id}_{clarity_case_id}-{control_id}_{clarity_control_id}.{report_timestamp}"
        )
    else:
        report_id: str = f"{case_id}_{clarity_case_id}.{report_timestamp}"

    report_path: str = os.path.join(
        app.config.get("REPORTS_BASE_PATH", "reports"),
        assay_config.get("reporting", {}).get("report_path", assay_group),
    )
    os.makedirs(report_path, exist_ok=True)
    report_file: str = os.path.join(report_path, f"{report_id}.html")

    if os.path.exists(report_file):
        flash("Report already exists.", "red")
        app.logger.warning(f"Report file already exists: {report_file}")
        raise AppError(
            status_code=409,
            message="Report already exists with the requested name.",
            details=f"File name: {os.path.basename(report_file)}",
        )

    try:
        html, snapshot_rows = _build_rna_report_payload(sample, save=1, include_snapshot=True)

        if not util.common.write_report(html, report_file):
            raise AppError(
                status_code=500,
                message=f"Failed to save report {report_id}.html",
                details="Could not write the report to the file system.",
            )

        report_oid = store.sample_handler.save_report(
            sample_id=sample_id,
            report_num=report_num,
            report_id=report_id,
            filepath=report_file,
        )

        store.reported_variants_handler.bulk_upsert_from_snapshot_rows(
            sample_name=sample.get("name"),
            sample_oid=sample.get("_id"),
            report_oid=report_oid,
            report_id=report_id,
            snapshot_rows=snapshot_rows or [],
            created_by=current_user.username,
        )

        flash(f"Report {report_id}.html has been successfully saved.", "green")
        app.logger.info(f"Report saved: {report_file}")
    except AppError as app_err:
        flash(app_err.message, "red")
        app.logger.error(f"AppError: {app_err.message} | Details: {app_err.details}")
    except Exception as exc:
        flash("An unexpected error occurred while saving the report.", "red")
        app.logger.exception(f"Unexpected error: {exc}")

    return redirect(url_for("home_bp.samples_home", reload=True))


@rna_bp.route("/multi_class/<sample_id>", methods=["POST"])
@require_sample_access("sample_id")
def classify_multi_variant(sample_id: str) -> Response:
    """
    Classify multiple variants for a given sample.

    This view processes a POST request containing a list of selected variant IDs and classification actions.
    It supports applying or removing classification tiers, marking variants as irrelevant or false positive,
    and updates the database accordingly.

    Args:
        sample_id (str): The unique identifier of the sample whose variants are being classified.

    Returns:
        Response: Redirects to the fusion list page after processing the classification actions.
    """

    action = request.form.get("action")

    variants_to_modify = request.form.getlist("selected_object_id")
    assay = request.form.get("assay", None)
    subpanel = request.form.get("subpanel", None)
    tier = request.form.get("tier", None)
    irrelevant = request.form.get("irrelevant", None)
    false_positive = request.form.get("false_positive", None)

    if tier and action == "apply":
        flash(
            "Bulk tier assignment is not supported for RNA fusions. Use fusion detail page.",
            "yellow",
        )
    elif false_positive:
        if action == "apply":
            store.fusion_handler.mark_false_positive_bulk(variants_to_modify, True)
        elif action == "remove":
            store.fusion_handler.mark_false_positive_bulk(variants_to_modify, False)
    elif irrelevant:
        if action == "apply":
            store.fusion_handler.mark_irrelevant_bulk(variants_to_modify, True)
        elif action == "remove":
            store.fusion_handler.mark_irrelevant_bulk(variants_to_modify, False)
    return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))
