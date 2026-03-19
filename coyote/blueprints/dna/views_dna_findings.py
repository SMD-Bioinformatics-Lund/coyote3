"""DNA findings list routes and helpers."""

from __future__ import annotations

import io
import os
from copy import deepcopy

from flask import (
    Response,
    render_template,
    request,
    send_file,
    send_from_directory,
)
from flask import (
    current_app as app,
)
from PIL import Image
from wtforms import BooleanField

from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.forms import DNAFilterForm
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import raise_page_load_error


def raise_api_page_error(sample_id: str, page_name: str, exc: ApiRequestError) -> None:
    """Raise a standardized page error for DNA page-load failures."""
    raise_page_load_error(
        exc,
        logger=app.logger,
        log_message=f"Failed to load {page_name} for sample {sample_id}",
        summary=f"Unable to load {page_name}.",
        not_found_summary=f"{page_name} was not found for the selected sample.",
    )


@dna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
def list_dna_findings(sample_id: str) -> Response | str:
    """Render the DNA findings list page for a sample."""
    headers = forward_headers()
    api_client = get_web_api_client()

    def _load_api_context():
        """Load api context.

        Returns:
                The  load api context result.
        """
        return api_client.get_json(
            api_endpoints.dna_sample(sample_id, "small_variants"),
            headers=headers,
        )

    try:
        variants_payload = _load_api_context()
        app.logger.info("Loaded DNA findings list from API service for sample %s", sample_id)
    except ApiRequestError as exc:
        app.logger.error("DNA findings API fetch failed for sample %s: %s", sample_id, exc)
        raise_api_page_error(sample_id, "DNA findings", exc)

    sample = variants_payload.sample
    assay_config = variants_payload.assay_config
    sample_has_filters = sample.get("filters", None)
    sample_filters = deepcopy(variants_payload.filters)
    sample_ids = variants_payload.sample_ids
    assay_group = variants_payload.assay_group or assay_config.get("asp_group", "unknown")
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
                "Failed to reset DNA findings filters via API for sample %s: %s",
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
                    "Failed to reset DNA findings filters via API for sample %s: %s",
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
                    "Failed to update DNA findings filters via API for sample %s: %s",
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
            analysis_sections = variants_payload.analysis_sections
            display_sections_data = deepcopy(variants_payload.display_sections_data)
            ai_text = variants_payload.ai_text
            insilico_panel_genelists = variants_payload.assay_panels
            checked_genelists = variants_payload.checked_genelists
            genes_covered_in_panel = variants_payload.checked_genelists_dict
            verification_sample_used = variants_payload.verification_sample_used
        except ApiRequestError as exc:
            app.logger.error("DNA findings API refresh failed for sample %s: %s", sample_id, exc)
            raise_api_page_error(sample_id, "DNA findings", exc)

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
        "list_dna_findings.html",
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


@dna_bp.route("/sample/<string:sample_id>/exports/snvs.csv")
def download_snv_csv(sample_id: str) -> Response:
    """Download filtered SNV rows as CSV from API export context."""
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "small_variants", "exports", "snvs", "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("DNA SNV export API fetch failed for sample %s: %s", sample_id, exc)
        raise_api_page_error(sample_id, "DNA SNV export", exc)

    buf = io.BytesIO(str(payload.get("content", "")).encode("utf-8"))
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name=str(payload.get("filename", f"{sample_id}.filtered.snvs.csv")),
    )


@dna_bp.route("/sample/<string:sample_id>/exports/cnvs.csv")
def download_cnv_csv(sample_id: str) -> Response:
    """Download filtered CNV rows as CSV from API export context."""
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "small_variants", "exports", "cnvs", "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("DNA CNV export API fetch failed for sample %s: %s", sample_id, exc)
        raise_api_page_error(sample_id, "DNA CNV export", exc)

    buf = io.BytesIO(str(payload.get("content", "")).encode("utf-8"))
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name=str(payload.get("filename", f"{sample_id}.filtered.cnvs.csv")),
    )


@dna_bp.route("/sample/<string:sample_id>/exports/translocs.csv")
def download_transloc_csv(sample_id: str) -> Response:
    """Download filtered translocation rows as CSV from API export context."""
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(
                sample_id, "small_variants", "exports", "translocs", "context"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "DNA translocation export API fetch failed for sample %s: %s", sample_id, exc
        )
        raise_api_page_error(sample_id, "DNA translocation export", exc)

    buf = io.BytesIO(str(payload.get("content", "")).encode("utf-8"))
    return send_file(
        buf,
        mimetype="text/csv",
        as_attachment=True,
        download_name=str(payload.get("filename", f"{sample_id}.filtered.translocs.csv")),
    )


@dna_bp.route("/<string:sample_id>/var/<string:var_id>")
def show_small_variant(sample_id: str, var_id: str) -> Response | str:
    """Render the DNA small-variant detail page for a sample resource."""
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "small_variants", var_id),
            headers=forward_headers(),
        )
        app.logger.info("Loaded DNA small-variant detail from API service for sample %s", sample_id)
        return render_template(
            "show_small_variant_vep.html",
            sample_id=sample_id,
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
        app.logger.error(
            "DNA small-variant detail API fetch failed for sample %s: %s", sample_id, exc
        )
        raise_api_page_error(sample_id, "DNA small-variant detail", exc)


@dna_bp.route("/<string:sample_id>/plot/<string:fn>", endpoint="show_any_plot")  # type: ignore
@dna_bp.route("/<string:sample_id>/plot/rotated/<string:fn>", endpoint="show_any_plot_rotated")  # type: ignore
def show_any_plot(sample_id: str, fn: str, angle: int = 90) -> Response | str:
    """Serve a DNA plot image or a rotated variant of the same image."""
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "plot_context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("DNA plot context API fetch failed for sample %s: %s", sample_id, exc)
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load DNA plot context for sample {sample_id}",
            summary="Unable to load the requested plot.",
            not_found_summary="The plot context for this sample was not found.",
        )

    assay_config = payload.assay_config
    base_dir = payload.plots_base_dir or assay_config.get("reporting", {}).get("plots_path", None)

    if base_dir:
        file_path = os.path.join(base_dir, fn)
        if not os.path.exists(file_path):
            raise_page_load_error(
                ApiRequestError("Plot file not found.", status_code=404),
                logger=app.logger,
                log_message=f"Plot file missing at {file_path}",
                summary="Unable to open the requested plot.",
                not_found_summary="The requested plot file was not found.",
            )

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
            raise_page_load_error(
                ApiRequestError("Plot processing failed.", status_code=500),
                logger=app.logger,
                log_message=f"Failed to rotate DNA plot for sample {sample_id}",
                summary="Unable to process the requested plot.",
            )

    return send_from_directory(base_dir, fn)
