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
from copy import deepcopy

from flask import render_template
from flask_login import login_required
from coyote.extensions import store, util
from coyote.blueprints.dashboard import dashboard_bp
import json
from collections import OrderedDict
from flask_login import current_user
from flask import current_app as app
from time import time


@dashboard_bp.route("/", methods=["GET", "POST"])
@dashboard_bp.route("/dashboard/", methods=["GET", "POST"])
@dashboard_bp.route("", methods=["GET", "POST"])
@login_required
def dashboard() -> str:
    """
    Dashboard
    """

    total_samples_count = store.sample_handler.get_all_sample_counts()
    analysed_samples_count = store.sample_handler.get_all_sample_counts(
        report=True
    )
    pending_samples_count = total_samples_count - analysed_samples_count

    # User specific samples stats, assay and group wise
    user_samples_stats = store.sample_handler.get_assay_specific_sample_stats(
        assays=current_user.assays
    )

    ##### Generic Variant Stats
    variant_stats = {}
    variant_stats["total_variants"] = (
        store.variant_handler.get_total_variant_counts()
    )

    # Get all unique variants
    variant_stats["unique_variants"] = (
        store.variant_handler.get_unique_total_variant_counts()
    )

    # get unique variants Snps
    variant_stats["unique_snps"] = store.variant_handler.get_unique_snp_count()

    # get unique CNVs
    variant_stats[
        "unique_cnvs"
    ]: int = store.cnv_handler.get_unique_cnv_count()

    # get unique Translocations
    variant_stats[
        "unique_translocs"
    ]: int = store.transloc_handler.get_unique_transloc_count()

    # get unique RNA fusions
    variant_stats[
        "unique_fusions"
    ]: int = store.fusion_handler.get_unique_fusion_count()

    # Get total blacklisted variants
    variant_stats[
        "unique_blacklist_variants"
    ]: int = store.blacklist_handler.get_unique_blacklist_count()

    # Get total False positive variants
    variant_stats[
        "unique_fps"
    ]: int = store.variant_handler.get_unique_fp_count()  # Change it back

    ### Generic Variant Stats End

    # Get total genes analysed from all the asp
    unique_gene_count_all_panels = (
        store.asp_handler.get_all_asps_unique_gene_count()
    )

    # Get gene counts in each panel
    asp_gene_counts = store.asp_handler.get_all_asp_gene_counts()
    asp_gene_counts = util.dashboard.format_asp_gene_stats(
        deepcopy(asp_gene_counts)
    )

    # TODO: Add more stats here
    # Total Assays analysed
    # total_assay_count = 0

    # TODO: Add more stats here
    # Variant Caller specific stats
    # class_stats = util.dashboard.format_classified_stats(
    #    store.annotation_handler.get_classified_stats()
    # )

    # assay_class_stats = util.dashboard.format_assay_classified_stats(
    #    store.annotation_handler.get_assay_classified_stats()
    # )

    return render_template(
        "dashboard.html",
        total_samples=total_samples_count,
        analysed_samples=analysed_samples_count,
        pending_samples=pending_samples_count,
        # class_stats_data=json.dumps(class_stats),
        # assay_class_stats_data=json.dumps(assay_class_stats),
        variant_stats=variant_stats,
        unique_gene_count_all_panels=unique_gene_count_all_panels,
        assay_gene_stats_grouped=asp_gene_counts,
        user_samples_stats=user_samples_stats,
    )
