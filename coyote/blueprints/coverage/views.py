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
import os


@cov_bp.route("/<string:sample_id>", methods=["GET", "POST"])
@login_required
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
    filtered_dict = filter_genes_from_form(cov_dict, filter_genes, smp_grp)
    filtered_dict = find_low_covered_genes(filtered_dict, cov_cutoff, smp_grp)
    cov_table = coverage_table(filtered_dict, cov_cutoff)

    filtered_dict = organize_data_for_d3(filtered_dict)

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
def remove_blacklist(obj_id, group):
    """
    removes blacklisted region/gene
    """
    response = store.groupcov_handler.remove_blacklist(obj_id)
    return redirect(url_for("cov_bp.show_blacklisted_regions", group=group))


def find_low_covered_genes(cov, cutoff, smp_grp):
    """
    find low covered parts in defined regions of interest
    """
    keep = defaultdict(dict)
    for gene in cov["genes"]:
        has_low = False
        if "CDS" in cov["genes"][gene]:
            has_low = reg_low(cov["genes"][gene]["CDS"], "CDS", cutoff, gene, smp_grp)
        if "probes" in cov["genes"][gene]:
            has_low = reg_low(cov["genes"][gene]["probes"], "probe", cutoff, gene, smp_grp)
        if has_low == True:
            keep["genes"][gene] = cov["genes"][gene]
    return keep


def organize_data_for_d3(filtered_dict):
    """
    This is for javascript. Data imported as dicts to make blacklisting easier
    but needs to be as lists for javascript to jsonify correctly in plot functions
    """
    for gene in filtered_dict["genes"]:
        if "exons" in filtered_dict["genes"][gene]:
            exons = []
            for exon in filtered_dict["genes"][gene]["exons"]:
                exons.append(filtered_dict["genes"][gene]["exons"][exon])
            filtered_dict["genes"][gene]["exons"] = exons
        else:
            filtered_dict["genes"][gene]["exons"] = []
        if "CDS" in filtered_dict["genes"][gene]:
            cds = []
            for exon in filtered_dict["genes"][gene]["CDS"]:
                cds.append(filtered_dict["genes"][gene]["CDS"][exon])
            filtered_dict["genes"][gene]["CDS"] = cds
        else:
            filtered_dict["genes"][gene]["CDS"] = []
        if "probes" in filtered_dict["genes"][gene]:
            probes = []
            for probe in filtered_dict["genes"][gene]["probes"]:
                probes.append(filtered_dict["genes"][gene]["probes"][probe])
            filtered_dict["genes"][gene]["probes"] = probes
        else:
            filtered_dict["genes"][gene]["probes"] = []

    return filtered_dict


def filter_genes_from_form(cov_dict, filter_genes, smp_grp):
    filtered_dict = defaultdict(dict)
    for gene in cov_dict["genes"]:
        blacklisted = store.groupcov_handler.is_gene_blacklisted(gene, smp_grp)
        if gene in filter_genes and not blacklisted:
            filtered_dict["genes"][gene] = cov_dict["genes"][gene]
    return filtered_dict


def reg_low(region_dict, region, cutoff, gene, smp_grp):
    """
    filter against cutoff ignore if region is blacklisted
    """
    has_low = False
    for reg in region_dict:
        if "cov" in region_dict[reg]:
            if float(region_dict[reg]["cov"]) < cutoff:
                blacklisted = store.groupcov_handler.is_region_blacklisted(
                    gene, region, reg, smp_grp
                )
                if not blacklisted:
                    has_low = True
    return has_low


def coverage_table(cov_dict, cov_cutoff):
    """
    organize data to be presented condensed in table format
    """
    cov_table = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
    for gene in cov_dict["genes"]:
        gene_cov = cov_dict["genes"][gene]
        # if data has probes, create cov table based on these and their overlap to CDS
        if "probes" in gene_cov:
            for probe in gene_cov["probes"]:
                exons = assign_to_exon(probe, gene_cov)
                cov_dict["genes"][gene]["probes"][probe]["exon_nr"] = exons
                if len(exons) > 0:
                    for exon in exons:
                        if (
                            float(exon["cov"]) < cov_cutoff
                            or float(gene_cov["probes"][probe]["cov"]) < cov_cutoff
                        ):
                            cov_table[gene][exon["nbr"]] = exon
                else:
                    if float(gene_cov["probes"][probe]["cov"]) < cov_cutoff:
                        cov_table[gene][probe] = gene_cov["probes"][probe]
        else:
            """
            assign low cov CDS to cov_table
            """
            for exon in gene_cov["CDS"]:
                cov = gene_cov["CDS"][exon].get("cov", None)
                if cov is not None:
                    cov = float(cov)
                    if cov < cov_cutoff:
                        cov_table[gene][gene_cov["CDS"][exon]["nbr"]] = gene_cov["CDS"][exon]

    return cov_table


def assign_to_exon(probe, gene_cov):
    """
    assign probe to correct exon(cds)
    """
    exons = []
    for exon in gene_cov["CDS"]:
        p_start = int(gene_cov["probes"][probe]["start"])
        p_end = int(gene_cov["probes"][probe]["end"])
        e_start = int(gene_cov["CDS"][exon]["start"])
        e_end = int(gene_cov["CDS"][exon]["end"])
        if p_start <= e_end and p_end >= e_start:
            exons.append(gene_cov["CDS"][exon])
    # exons = ','.join(exons)
    return exons
