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
from coyote.util.decorators.access import (
    require_group_access,
    require_sample_access,
)
from coyote.web_api.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@cov_bp.route("/<string:sample_id>", methods=["GET", "POST"])
@require_sample_access("sample_id")
def get_cov(sample_id):
    cov_cutoff = 500
    if request.method == "POST":
        cov_cutoff_form = request.form.get("depth_cutoff")
        cov_cutoff = int(cov_cutoff_form)
    try:
        payload = get_web_api_client().get_coverage_sample(
            sample_id=sample_id,
            cov_cutoff=cov_cutoff,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to load coverage via API for sample %s: %s", sample_id, exc)
        return redirect(url_for("home_bp.samples_home"))

    return render_template(
        "show_cov.html",
        coverage=payload.coverage,
        cov_cutoff=payload.cov_cutoff,
        sample=payload.sample,
        genelists=payload.genelists,
        smp_grp=payload.smp_grp,
        cov_table=payload.cov_table,
    )


@app.route("/update-gene-status", methods=["POST"])
@login_required
def update_gene_status():
    data = request.get_json()
    try:
        payload = get_web_api_client().update_coverage_blacklist(
            payload=data,
            headers=build_forward_headers(request.headers),
        )
        return jsonify(payload)
    except ApiRequestError as exc:
        return jsonify({"message": str(exc)}), exc.status_code or 502


@cov_bp.route("/blacklisted/<string:group>", methods=["GET", "POST"])
@require_group_access("group")
def show_blacklisted_regions(group):
    """
    show what regions/genes that has been blacklisted by user
    function to remove blacklisted status
    """
    try:
        payload = get_web_api_client().get_coverage_blacklisted(
            group=group,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to load blacklisted regions via API for group %s: %s", group, exc)
        return redirect(url_for("home_bp.samples_home"))

    return render_template("show_blacklisted.html", blacklisted=payload.blacklisted, group=payload.group)


@cov_bp.route("/remove_blacklist/<string:obj_id>/<string:group>", methods=["GET"])
@require_group_access("group")
def remove_blacklist(obj_id, group):
    """
    removes blacklisted region/gene
    """
    try:
        get_web_api_client().remove_coverage_blacklist(
            obj_id=obj_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError:
        pass
    return redirect(url_for("cov_bp.show_blacklisted_regions", group=group))
