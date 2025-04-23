from flask import abort, redirect, request, url_for, flash
from flask_login import login_required
from flask import current_app as app
from coyote.blueprints.common import common_bp
from coyote.blueprints.home import home_bp
from coyote.extensions import store, util
from flask import render_template
from flask_login import current_user
import traceback
from coyote.util.decorators.access import require_sample_group_access
from coyote.services.auth.decorators import require


@common_bp.route("/errors/")
def error_screen():
    """
    Error screen
    """
    # TODO Example Error Code, should be removed later /modified
    try:
        error = 1 / 0
    except ZeroDivisionError as e:
        error = traceback.format_exc()

    if current_user.is_admin:
        return render_template("error.html", error=error)
    else:
        return render_template("error.html", error=[])


@common_bp.route(
    "/dna/sample/<string:sample_id>/sample_comment",
    methods=["POST"],
    endpoint="add_dna_sample_comment",
)
@common_bp.route(
    "/rna/sample/<string:sample_id>/sample_comment",
    methods=["POST"],
    endpoint="add_rna_sample_comment",
)
@common_bp.route("/sample/<string:sample_id>/sample_comment", methods=["POST"])
@login_required
@require_sample_group_access("sample_id")
@require("add_sample_comment", min_role="admin")
def add_sample_comment(sample_id):
    """
    Add Sample comment
    """
    data = request.form.to_dict()
    doc = util.dna.create_comment_doc(data, key="sample_comment")
    store.sample_handler.add_sample_comment(sample_id, doc)
    flash("Sample comment added", "green")
    sample = store.sample_handler.get_sample_with_id(sample_id)
    assay = util.common.get_assay_from_sample(sample)
    if request.endpoint == "common_bp.add_dna_sample_comment":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))


@common_bp.route("/sample/<string:sample_id>/hide_sample_comment", methods=["POST"])
@require_sample_group_access("sample_id")
@require("hide_sample_comment", min_role="admin")
@login_required
def hide_sample_comment(sample_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.sample_handler.hide_sample_comment(sample_id, comment_id)
    sample = store.sample_handler.get_sample_with_id(sample_id)
    assay = util.common.get_assay_from_sample(sample)
    sample_type = util.common.get_sample_type(assay)
    if sample_type == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))


@common_bp.route("/sample/unhide_sample_comment/<string:sample_id>", methods=["POST"])
@login_required
@require_sample_group_access("sample_id")
@require("unhide_sample_comment", min_role="admin")
def unhide_sample_comment(sample_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.sample_handler.unhide_sample_comment(sample_id, comment_id)
    sample = store.sample_handler.get_sample_with_id(sample_id)
    assay = util.common.get_assay_from_sample(sample)
    sample_type = util.common.get_sample_type(assay)
    if sample_type == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))


@common_bp.route("/<string:sample_id>/<string:assay_group>/genes", methods=["GET"])
@login_required
@require_sample_group_access("sample_id")
@require("view_report", min_role="admin")
def get_sample_genelists(sample_id, assay_group):
    """
    Add genes to a sample
    """
    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        sample = store.sample_handler.get_sample_with_id(sample_id)

    sample_assay = util.common.select_one_sample_group(sample.get("groups"))

    sample_genelist_names = sample.get("filters", {}).get("genelists", [])
    sample_genelists = store.panel_handler.get_assay_gene_list_by_name(
        assay_group, sample_genelist_names
    )

    sample_genelist_dict = {}
    if sample_genelists:
        for genelist in sample_genelists:
            sample_genelist_dict[genelist.get("displayname")] = genelist.get("genes")

    # Get all genes and lists for the assay
    if not sample_genelist_dict:
        assay_default_gene_lists = store.panel_handler.get_assay_gene_panel_genes(sample_assay)

        if assay_default_gene_lists:
            for genelist in assay_default_gene_lists:
                sample_genelist_dict[genelist.get("displayname")] = genelist.get("genes")

    # TODO: TRY TO SAVE AS A EMBBED THING IN THE SAMPLE REPORT
    # list(set(assay_default_genes)), sample_default_genes_dict
    return render_template(
        "sample_genes.html",
        sample=sample,
        assay=assay_group,
        genelists=sample_genelist_dict,
    )
