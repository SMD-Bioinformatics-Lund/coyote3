"""
Coyote coverage for mane-transcripts
"""

from flask import current_app as app
from flask import (
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
    flash,
    abort,
    jsonify,
)
from flask_login import current_user, login_required
from pprint import pformat
from wtforms import BooleanField
from coyote.extensions import store, util
from coyote.blueprints.coverage import cov_bp
from coyote.blueprints.home import home_bp
from coyote.errors.exceptions import AppError
from typing import Literal, Any
from datetime import datetime
from collections import defaultdict
from flask_weasyprint import HTML, render_pdf
from coyote.blueprints.dna.forms import GeneForm
from coyote.util.decorators.access import require_sample_group_access, require_group_access
from coyote.services.auth.decorators import require
import os


@cov_bp.route("/<string:sample_id>", methods=["GET", "POST"])
@login_required
@require_sample_group_access("sample_id")
def get_cov(sample_id):
    cov_cutoff = 500
    if request.method == "POST":
        cov_cutoff_form = request.form.get("depth_cutoff")
        cov_cutoff = int(cov_cutoff_form)
    # cov_cutoff = 1500
    sample = store.sample_handler.get_sample(sample_id)

    assay: str | None | Literal["unknown"] = util.common.get_assay_from_sample(sample)
    gene_lists, genelists_assay = store.panel_handler.get_assay_panels(assay)

    smp_grp = util.common.select_one_sample_group(sample.get("groups"))
    # Get group parameters from the sample group config file
    group_params = util.common.get_group_parameters(smp_grp)

    # Get group defaults from coyote config, if not found in group config
    settings = util.common.get_group_defaults(group_params)
    genelist_filter = sample.get("checked_genelists", settings["default_checked_genelists"])
    genelist_clean = [name.replace("genelist_", "") for name in genelist_filter]

    checked_genelist_dict = util.common.create_genelists_dict(genelist_clean, gene_lists)
    filter_genes = util.common.create_filter_genelist(checked_genelist_dict)
    cov_dict = store.coverage2_handler.get_sample_coverage(str(sample["_id"]))
    del cov_dict["_id"]
    del sample["_id"]
    filtered_dict = util.coverage.filter_genes_from_form(cov_dict, filter_genes, smp_grp)
    filtered_dict = util.coverage.find_low_covered_genes(filtered_dict, cov_cutoff, smp_grp)
    cov_table = util.coverage.coverage_table(filtered_dict, cov_cutoff)

    filtered_dict = util.coverage.organize_data_for_d3(filtered_dict)

    return render_template(
        "show_cov.html",
        coverage=filtered_dict,
        cov_cutoff=cov_cutoff,
        sample=sample,
        genelists=genelist_clean,
        smp_grp=smp_grp,
        cov_table=cov_table,
    )


@app.route("/update-gene-status", methods=["POST"])
@login_required
def update_gene_status():
    data = request.get_json()
    gene = data.get("gene")
    status = data.get("status")
    coord = data.get("coord")
    smp_grp = data.get("smp_grp")
    region = data.get("region")
    if coord != "":
        coord = coord.replace(":", "_")
        coord = coord.replace("-", "_")
        store.groupcov_handler.blacklist_coord(gene, coord, region, smp_grp)
        # Return a response
        return jsonify(
            {
                "message": f" Status for {gene}:{region}:{coord} was set as {status} for group: {smp_grp}. Page needs to be reload to take effect"
            }
        )
    else:
        store.groupcov_handler.blacklist_gene(gene, smp_grp)
        return jsonify(
            {
                "message": f" Status for full gene: {gene} was set as {status} for group: {smp_grp}. Page needs to be reload to take effect"
            }
        )


@cov_bp.route("/blacklisted/<string:group>", methods=["GET", "POST"])
@login_required
@require_group_access("group")
def show_blacklisted_regions(group):
    """
    show what regions/genes that has been blacklisted by user
    function to remove blacklisted status
    """
    grouped_by_gene = defaultdict(dict)
    blacklisted = store.groupcov_handler.get_regions_per_group(group)
    for entry in blacklisted:
        if entry["region"] == "gene":
            grouped_by_gene[entry["gene"]]["gene"] = entry["_id"]
        elif entry["region"] == "CDS":
            grouped_by_gene[entry["gene"]]["CDS"] = entry
        elif entry["region"] == "probe":
            grouped_by_gene[entry["gene"]]["probe"] = entry

    return render_template("show_blacklisted.html", blacklisted=grouped_by_gene, group=group)


@cov_bp.route("/remove_blacklist/<string:obj_id>/<string:group>", methods=["GET"])
@login_required
@require_group_access("group")
def remove_blacklist(obj_id, group):
    """
    removes blacklisted region/gene
    """
    response = store.groupcov_handler.remove_blacklist(obj_id)
    return redirect(url_for("cov_bp.show_blacklisted_regions", group=group))
