"""
Coyote case variants
"""

from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory, flash, abort
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
    cov_cutoff = 500
    #cov_dict = store.coverage2_handler.get_sample_coverage("66f285e8ecea5d8ee7e95afa")
    cov_dict = store.coverage2_handler.get_sample_coverage("TEST123")
    del cov_dict['_id']
    filtered_dict = defaultdict(dict)
    genes = [ "TP53", "BRCA1", "BRCA2", "TERT"]
    for gene in cov_dict['genes']:
        if gene not in genes:
            filtered_dict['genes'][gene] = cov_dict['genes'][gene]
    filtered_dict = find_low_covered_genes(filtered_dict,cov_cutoff)

    exons = []
    for gene in filtered_dict['genes']:
        for exon in filtered_dict['genes'][gene]['exons']:
            exons.append(filtered_dict['genes'][gene]['exons'][exon])
        filtered_dict['genes'][gene]['exons'] = exons

    cds = []
    for gene in filtered_dict['genes']:
        for exon in filtered_dict['genes'][gene]['CDS']:
            cds.append(filtered_dict['genes'][gene]['CDS'][exon])
        filtered_dict['genes'][gene]['CDS'] = cds

    probes = []
    for gene in filtered_dict['genes']:
        for probe in filtered_dict['genes'][gene]['probes']:
            probes.append(filtered_dict['genes'][gene]['probes'][probe])
        filtered_dict['genes'][gene]['probes'] = probes

    return render_template(
        "show_cov.html",
        coverage=filtered_dict,
        cov_cutoff=cov_cutoff
    )

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
    