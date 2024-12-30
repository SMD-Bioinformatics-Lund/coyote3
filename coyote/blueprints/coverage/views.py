"""
Coyote case variants
"""

from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory, flash, abort, jsonify
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

@cov_bp.route("/<string:id>", methods=["GET", "POST"])
@login_required
def get_cov(id):
    cov_cutoff = 500

    sample = store.sample_handler.get_sample(id)  # id = name
    assay: str | None | Literal["unknown"] = util.common.get_assay_from_sample(sample)
    gene_lists, genelists_assay = store.panel_handler.get_assay_panels(assay)
    
    for panel in genelists_assay:
        if panel["type"] == "genelist":
            setattr(GeneForm, "genelist_" + panel["name"], BooleanField())
    form = GeneForm()
    
    # Check the length of the sample groups from db, and if len is more than one, tumwgs-solid or tumwgs-hema takes the priority in new coyote
    smp_grp = util.common.select_one_sample_group(sample.get("groups"))
    # Get group parameters from the sample group config file
    group_params = util.common.get_group_parameters(smp_grp)

    # Get group defaults from coyote config, if not found in group config
    settings = util.common.get_group_defaults(group_params)
    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        _id = str(sample.get("_id"))
        # Reset filters to defaults
        if form.reset.data:
            store.sample_handler.reset_sample_settings(_id, settings)
        # Change filters
        else:
            store.sample_handler.update_sample_settings(_id, form)
            ## get sample again to recieve updated forms!
            sample = store.sample_handler.get_sample_with_id(_id)

    genelist_filter = sample.get("checked_genelists", settings["default_checked_genelists"])
    filter_genes = util.common.create_filter_genelist(genelist_filter, gene_lists)

    cov_dict = store.coverage2_handler.get_sample_coverage(str(sample['_id']))
    del cov_dict['_id']

    filtered_dict = filter_genes_from_form(cov_dict,filter_genes)
    filtered_dict = find_low_covered_genes(filtered_dict,cov_cutoff)
    filtered_dict = organize_data_for_d3(filtered_dict)

    return render_template(
        "show_cov.html",
        coverage=filtered_dict,
        cov_cutoff=cov_cutoff
    )

@app.route('/update-gene-status', methods=['POST'])
def update_gene_status():
    data = request.get_json()
    gene = data.get('gene')
    status = data.get('status')
    # Return a response
    return jsonify({'message': f'Status for gene {gene} updated to {status}'})



def find_low_covered_genes(cov,cutoff):
    keep = defaultdict(dict)
    for gene in cov['genes']:
        has_low = False
        if 'CDS' in cov['genes'][gene]:
            for cds in cov['genes'][gene]['CDS']:
                if 'cov' in cov['genes'][gene]['CDS'][cds]:
                    if float(cov['genes'][gene]['CDS'][cds]['cov']) < cutoff:
                        has_low = True
        if 'probes' in cov['genes'][gene]:
            for probe in cov['genes'][gene]['probes']:
                if 'cov' in cov['genes'][gene]['probes'][probe]:
                    if float(cov['genes'][gene]['probes'][probe]['cov']) < cutoff:
                        has_low = True
        if has_low == True:
            keep['genes'][gene] = cov['genes'][gene]
    return keep

def organize_data_for_d3(filtered_dict):
        
    for gene in filtered_dict['genes']: 
        if 'exons' in filtered_dict['genes'][gene]:
            exons = []
            for exon in filtered_dict['genes'][gene]['exons']:
                exons.append(filtered_dict['genes'][gene]['exons'][exon])
            filtered_dict['genes'][gene]['exons'] = exons
        if 'CDS' in filtered_dict['genes'][gene]:
            cds = []
            for exon in filtered_dict['genes'][gene]['CDS']:
                cds.append(filtered_dict['genes'][gene]['CDS'][exon])
            filtered_dict['genes'][gene]['CDS'] = cds
        if 'probes' in filtered_dict['genes'][gene]:
            probes = []
            for probe in filtered_dict['genes'][gene]['probes']:
                probes.append(filtered_dict['genes'][gene]['probes'][probe])
            filtered_dict['genes'][gene]['probes'] = probes

    return filtered_dict

def filter_genes_from_form(cov_dict,filter_genes):
    if len(filter_genes) > 0:
        filtered_dict = defaultdict(dict)
        for gene in cov_dict['genes']:
            if gene in filter_genes:
                filtered_dict['genes'][gene] = cov_dict['genes'][gene]
        return filtered_dict
    else:
        return cov_dict