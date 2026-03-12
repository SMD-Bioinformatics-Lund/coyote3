"""DNA small-variant routes and helpers."""

from __future__ import annotations

import io
import os
from copy import deepcopy

from PIL import Image
from flask import (
    Response,
    current_app as app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    url_for,
)
from wtforms import BooleanField

from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.forms import DNAFilterForm
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


def raise_api_page_error(sample_id: str, page_name: str, exc: ApiRequestError) -> None:
    flash(f"Failed to load {page_name}: {exc}", "red")
    app.logger.error("Failed to load %s for sample %s: %s", page_name, sample_id, exc)
    raise exc


@dna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
def list_small_variants(sample_id: str) -> Response | str:
    headers = forward_headers()
    api_client = get_web_api_client()

    def _load_api_context():
        return api_client.get_json(
            api_endpoints.dna_sample(sample_id, "small_variants"),
            headers=headers,
        )

    try:
        variants_payload = _load_api_context()
        app.logger.info("Loaded DNA small-variant list from API service for sample %s", sample_id)
    except ApiRequestError as exc:
        app.logger.error("DNA small-variant API fetch failed for sample %s: %s", sample_id, exc)
        raise_api_page_error(sample_id, "DNA small variants", exc)

    sample = variants_payload.sample
    assay_config = variants_payload.assay_config
    sample_has_filters = sample.get("filters", None)
    sample_filters = deepcopy(variants_payload.filters)
    sample_ids = variants_payload.sample_ids
    assay_group = variants_payload.assay_group or assay_config.get("asp_group", "unknown")
    subpanel = variants_payload.subpanel
    analysis_sections = variants_payload.analysis_sections
    display_sections_data = deepcopy(variants_payload.display_sections_data)
    ai_text = variants_payload.ai_text

    insilico_panel_genelists = variants_payload.assay_panels
    all_panel_genelist_names = variants_payload.all_panel_genelist_names
    checked_genelists = variants_payload.checked_genelists
    genes_covered_in_panel = variants_payload.checked_genelists_dict
    verification_sample_used = variants_payload.verification_sample_used

    if not sample_has_filters:
        try:
            api_client.delete_json(
                api_endpoints.sample(sample_id, "filters"),
                headers=headers,
            )
            variants_payload = _load_api_context()
            sample = variants_payload.sample
            sample_filters = deepcopy(variants_payload.filters)
            display_sections_data = deepcopy(variants_payload.display_sections_data)
            ai_text = variants_payload.ai_text
            checked_genelists = variants_payload.checked_genelists
            genes_covered_in_panel = variants_payload.checked_genelists_dict
            verification_sample_used = variants_payload.verification_sample_used
        except ApiRequestError as exc:
            app.logger.error(
                "Failed to reset DNA small-variant filters via API for sample %s: %s",
                sample_id,
                exc,
            )

    if all_panel_genelist_names:
        for gene_list in all_panel_genelist_names:
            setattr(DNAFilterForm, f"genelist_{gene_list}", BooleanField())

    form = DNAFilterForm()

    if request.method == "POST" and form.validate_on_submit():
        if form.reset.data:
            try:
                api_client.delete_json(
                    api_endpoints.sample(sample_id, "filters"),
                    headers=headers,
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to reset DNA small-variant filters via API for sample %s: %s",
                    sample_id,
                    exc,
                )
        else:
            filters_from_form = {
                key: value
                for key, value in form.data.items()
                if key not in {"csrf_token", "reset", "submit"}
            }
            try:
                api_client.put_json(
                    api_endpoints.sample(sample_id, "filters"),
                    headers=headers,
                    json_body={"filters": filters_from_form},
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to update DNA small-variant filters via API for sample %s: %s",
                    sample_id,
                    exc,
                )

        try:
            variants_payload = _load_api_context()
            sample = variants_payload.sample
            assay_config = variants_payload.assay_config
            sample_filters = deepcopy(variants_payload.filters)
            sample_ids = variants_payload.sample_ids
            assay_group = variants_payload.assay_group or assay_config.get("asp_group", "unknown")
            subpanel = variants_payload.subpanel
            analysis_sections = variants_payload.analysis_sections
            display_sections_data = deepcopy(variants_payload.display_sections_data)
            ai_text = variants_payload.ai_text
            insilico_panel_genelists = variants_payload.assay_panels
            checked_genelists = variants_payload.checked_genelists
            genes_covered_in_panel = variants_payload.checked_genelists_dict
            verification_sample_used = variants_payload.verification_sample_used
        except ApiRequestError as exc:
            app.logger.error("DNA small-variant API refresh failed for sample %s: %s", sample_id, exc)
            raise_api_page_error(sample_id, "DNA small variants", exc)

    has_hidden_comments = variants_payload.hidden_comments

    form_data = deepcopy(sample_filters)
    form_data.update(
        {
            **{f"vep_{k}": True for k in sample_filters.get("vep_consequences", [])},
            **{f"cnveffect_{k}": True for k in sample_filters.get("cnveffects", [])},
            **{f"genelist_{k}": True for k in checked_genelists},
            **{assay_group: True},
        }
    )
    form.process(data=form_data)

    return render_template(
        "list_small_variants_vep.html",
        sample=sample,
        sample_ids=sample_ids,
        assay_group=assay_group,
        analysis_sections=analysis_sections,
        display_sections_data=display_sections_data,
        assay_panels=insilico_panel_genelists,
        checked_genelists_dict=genes_covered_in_panel,
        hidden_comments=has_hidden_comments,
        vep_var_class_translations=variants_payload.vep_var_class_translations,
        vep_conseq_translations=variants_payload.vep_conseq_translations,
        bam_id=variants_payload.bam_id,
        form=form,
        ai_text=ai_text,
        verification_sample_used=verification_sample_used,
        oncokb_genes=variants_payload.oncokb_genes,
    )


@dna_bp.route("/<string:sample_id>/var/<string:var_id>")
def show_small_variant(sample_id: str, var_id: str) -> Response | str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "small_variants", var_id),
            headers=forward_headers(),
        )
        app.logger.info("Loaded DNA small-variant detail from API service for sample %s", sample_id)
        return render_template(
            "show_small_variant_vep.html",
            variant=payload.variant,
            in_other=payload.in_other,
            annotations=payload.annotations,
            hidden_comments=payload.hidden_comments,
            latest_classification=payload.latest_classification,
            expression=payload.expression,
            civic=payload.civic,
            civic_gene=payload.civic_gene,
            oncokb=payload.oncokb,
            oncokb_action=payload.oncokb_action,
            oncokb_gene=payload.oncokb_gene,
            sample=payload.sample,
            brca_exchange=payload.brca_exchange,
            iarc_tp53=payload.iarc_tp53,
            assay_group=payload.assay_group,
            pon=payload.pon,
            other_classifications=payload.other_classifications,
            subpanel=payload.subpanel,
            sample_ids=payload.sample_ids,
            bam_id=payload.bam_id,
            annotations_interesting=payload.annotations_interesting,
            vep_var_class_translations=payload.vep_var_class_translations,
            vep_conseq_translations=payload.vep_conseq_translations,
            assay_group_mappings=payload.assay_group_mappings,
        )
    except ApiRequestError as exc:
        app.logger.error("DNA small-variant detail API fetch failed for sample %s: %s", sample_id, exc)
        raise_api_page_error(sample_id, "DNA small-variant detail", exc)


@dna_bp.route("/<string:sample_id>/plot/<string:fn>", endpoint="show_any_plot")  # type: ignore
@dna_bp.route("/<string:sample_id>/plot/rotated/<string:fn>", endpoint="show_any_plot_rotated")  # type: ignore
def show_any_plot(sample_id: str, fn: str, angle: int = 90) -> Response | str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "plot_context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("DNA plot context API fetch failed for sample %s: %s", sample_id, exc)
        flash("Failed to load sample context for plot", "red")
        return redirect(url_for("home_bp.samples_home"))

    assay_config = payload.assay_config
    base_dir = payload.plots_base_dir or assay_config.get("reporting", {}).get("plots_path", None)

    if base_dir:
        file_path = os.path.join(base_dir, fn)
        if not os.path.exists(file_path):
            flash(f"File not found: {file_path}", "red")
            return request.url

    if request.endpoint == "dna_bp.show_any_plot_rotated":
        try:
            with Image.open(os.path.join(base_dir, fn)) as img:
                rotated_img = img.rotate(-angle, expand=True)
                img_io = io.BytesIO()
                rotated_img.save(img_io, format="PNG")
                img_io.seek(0)
                return send_file(img_io, mimetype="image/png")
        except Exception as exc:  # noqa: BLE001
            app.logger.error("Error rotating image: %s", exc)
            flash("Error processing image", "red")
            return request.url

    return send_from_directory(base_dir, fn)
