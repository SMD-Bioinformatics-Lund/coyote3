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
import os

@cov_bp.route("/<string:id>", methods=["GET", "POST"])
@login_required
def list_variants(id):
    cov_cutoff = 1000
    #cov_dict = store.coverage2_handler.get_sample_coverage("66f285e8ecea5d8ee7e95afa")
    cov_dict = store.coverage2_handler.get_sample_coverage("TEST1234")
    del cov_dict['_id']
    
    filtered_dict = filter_genes(cov_dict)
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
                        break
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

def filter_genes(cov_dict):
    genes = [ "TP53", "BRCA1", "BRCA2", "TERT" ]
    if len(genes) > 0:
        filtered_dict = defaultdict(dict)
        for gene in cov_dict['genes']:
            if gene in genes:
                filtered_dict['genes'][gene] = cov_dict['genes'][gene]
        return filtered_dict
    else:
        return cov_dict