from flask import abort, redirect, request, url_for, flash
from flask_login import login_required
from flask import current_app as app
from coyote.blueprints.common import common_bp
from coyote.blueprints.home import home_bp
from coyote.extensions import store, util
from flask import render_template
from flask_login import current_user
import traceback


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

    if current_user.is_admin():
        return render_template("error.html", error=error)
    else:
        return render_template("error.html", error=[])


@common_bp.route("/sample/sample_comment/<string:id>", methods=["POST"])
@login_required
def add_sample_comment(id):
    """
    Add Sample comment
    """
    data = request.form.to_dict()
    doc = util.dna.create_comment_doc(data, key="sample_comment")
    store.sample_handler.add_sample_comment(id, doc)
    flash("Sample comment added", "green")
    sample = store.sample_handler.get_sample_with_id(id)
    assay = util.common.get_assay_from_sample(sample)
    sample_type = util.common.get_sample_type(assay)
    if sample_type == "dna":
        return redirect(url_for("dna_bp.list_variants", id=id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=id))


@common_bp.route("/sample/hide_sample_comment/<string:sample_id>", methods=["POST"])
@login_required
def hide_sample_comment(sample_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.sample_handler.hide_sample_comment(sample_id, comment_id)
    sample = store.sample_handler.get_sample_with_id(sample_id)
    assay = util.common.get_assay_from_sample(sample)
    sample_type = util.common.get_sample_type(assay)
    if sample_type == "dna":
        return redirect(url_for("dna_bp.list_variants", id=sample_id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))


@common_bp.route("/sample/unhide_sample_comment/<string:sample_id>", methods=["POST"])
@login_required
def unhide_sample_comment(sample_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.sample_handler.unhide_sample_comment(sample_id, comment_id)
    sample = store.sample_handler.get_sample_with_id(sample_id)
    assay = util.common.get_assay_from_sample(sample)
    sample_type = util.common.get_sample_type(assay)
    if sample_type == "dna":
        return redirect(url_for("dna_bp.list_variants", id=sample_id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=sample_id))


@common_bp.route("/<string:sample_id>/<string:assay>/<string:panel>/genes", methods=["GET"])
@login_required
def get_sample_genelists(sample_id, assay, panel):
    """
    Add genes to a sample
    """
    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        sample = store.sample_handler.get_sample_with_id(sample_id)

    sample_default_gene_list_names = list(sample.get("checked_genelists", {}).keys())
    if sample_default_gene_list_names:
        sample_default_gene_list_names = [
            g_list.replace("genelist_", "") for g_list in sample_default_gene_list_names
        ]
    assay = util.common.get_assay_from_sample(sample)

    sample_default_genes_lists = store.panel_handler.get_assay_gene_list_by_name(
        assay, sample_default_gene_list_names
    )
    group = sample.get("groups")

    sample_default_genes_dict = {}
    if sample_default_genes_lists:
        for gene_list in sample_default_genes_lists:
            sample_default_genes_dict[gene_list.get("displayname")] = gene_list.get("genes")

    assay_default_gene_lists = store.panel_handler.get_assay_default_gene_list(assay)
    assay_default_genes = []
    if assay_default_gene_lists:
        for gene_list in assay_default_gene_lists:
            print(gene_list)
            assay_default_genes.extend(gene_list.get("genes"))

    # TODO: TRY TO SAVE AS A EMBBED THING IN THE SAMPLE REPORT
    # list(set(assay_default_genes)), sample_default_genes_dict
    return render_template(
        "sample_genes.html",
        sample=sample,
        assay=assay,
        panel=panel,
        assay_default_genelist=list(set(assay_default_genes)),
        sample_filtered_genelists=sample_default_genes_dict,
    )
