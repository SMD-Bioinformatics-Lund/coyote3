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
Coyote coverage for mane-transcripts
"""


from collections import defaultdict
from flask import (
    current_app as app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from coyote.blueprints.coverage import cov_bp
from coyote.extensions import store, util
from coyote.util.decorators.access import (
    require_group_access,
    require_sample_access,
)


@cov_bp.route("/<string:sample_id>", methods=["GET", "POST"])
@require_sample_access("sample_id")
def get_cov(sample_id):
    cov_cutoff = 500
    if request.method == "POST":
        cov_cutoff_form = request.form.get("depth_cutoff")
        cov_cutoff = int(cov_cutoff_form)
    # cov_cutoff = 1500
    sample = store.sample_handler.get_sample(sample_id)

    sample_assay = sample.get("assay", "unknown")
    sample_profile = sample.get("profile", "production")
    assay_config = store.aspc_handler.get_aspc_no_meta(
        sample_assay, sample_profile
    )
    assay_group: str = assay_config.get(
        "assay_group", "unknown"
    )  # myeloid, solid, lymphoid
    subpanel: str | None = sample.get("subpanel")  # breast, LP, lung, etc.

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

    # Get group parameters from the sample group config file
    sample_filters = sample.get("filters", {})

    # Checked genelists
    checked_genelists = sample_filters.get("genelists", [])

    # Get the genelists for the sample panel checked genelists from the filters
    if checked_genelists:
        checked_genelists_genes_dict: list[dict] = (
            store.isgl_handler.get_isgl_by_ids(checked_genelists)
        )
        genes_covered_in_panel: list[dict] = (
            util.common.get_genes_covered_in_panel(
                checked_genelists_genes_dict, assay_panel_doc
            )
        )

        # Create a unique list of genes from the selected genelists which are currently active in the panel
        filter_genes = util.common.create_filter_genelist(
            genes_covered_in_panel
        )
    else:
        checked_genelists = assay_panel_doc.get("_id")
        filter_genes = assay_panel_doc.get("covered_genes", [])

    cov_dict = store.coverage2_handler.get_sample_coverage(str(sample["_id"]))
    del cov_dict["_id"]
    del sample["_id"]
    filtered_dict = util.coverage.filter_genes_from_form(
        cov_dict, filter_genes, assay_group
    )
    filtered_dict = util.coverage.find_low_covered_genes(
        filtered_dict, cov_cutoff, assay_group
    )
    cov_table = util.coverage.coverage_table(filtered_dict, cov_cutoff)

    filtered_dict = util.coverage.organize_data_for_d3(filtered_dict)

    return render_template(
        "show_cov.html",
        coverage=filtered_dict,
        cov_cutoff=cov_cutoff,
        sample=sample,
        genelists=checked_genelists,
        smp_grp=assay_group,
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

    return render_template(
        "show_blacklisted.html", blacklisted=grouped_by_gene, group=group
    )


@cov_bp.route(
    "/remove_blacklist/<string:obj_id>/<string:group>", methods=["GET"]
)
@require_group_access("group")
def remove_blacklist(obj_id, group):
    """
    removes blacklisted region/gene
    """
    response = store.groupcov_handler.remove_blacklist(obj_id)
    return redirect(url_for("cov_bp.show_blacklisted_regions", group=group))
