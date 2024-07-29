"""
Top level coyote
"""

from flask import abort
from flask import current_app as app
from flask import redirect, render_template, request, url_for
from flask_login import current_user
import traceback

# Legacy main-screen:
from flask_login import login_required
from coyote.extensions import store
from coyote.blueprints.home import home_bp
from coyote.blueprints.home.util import SampleSearchForm
from coyote.extensions import util


@home_bp.route("/", methods=["GET", "POST"])
@home_bp.route("/home", methods=["GET", "POST"])
@home_bp.route("/home/<string:status>", methods=["GET", "POST"])
@login_required
def home_screen(status="live"):
    form = SampleSearchForm()
    search_str = ""
    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    user_groups = current_user.get_groups()

    limit_done_samples = 50
    if request.args.get("all") == "1":
        limit_done_samples = None

    if status == "done":
        live_samples = []
        done_samples = store.sample_handler.get_samples(
            user_groups=user_groups, search_str=search_str, report=True, limit=limit_done_samples
        )
    else:
        live_samples = store.sample_handler.get_samples(
            user_groups=user_groups, search_str=search_str, report=False
        )
        done_samples = []

    # Add date for latest report to done_samples
    for samp in done_samples:
        if "reports" in samp and "time_created" in samp["reports"][-1]:
            samp["last_report_time_created"] = samp["reports"][-1]["time_created"]
        else:
            samp["last_report_time_created"] = 0
        samp["num_samples"] = store.sample_handler.get_num_samples(str(samp["_id"]))

    for samp in live_samples:
        samp["num_samples"] = store.sample_handler.get_num_samples(str(samp["_id"]))

    return render_template(
        "main_screen.html",
        live_samples=live_samples,
        done_samples=done_samples,
        form=form,
        assay=None,
        status=status,
    )


@home_bp.route("/panels/<string:assay>/<string:status>", methods=["GET", "POST"])
@home_bp.route("/panels/<string:assay>", methods=["GET", "POST"])
@login_required
def panels_screen(assay="myeloid_GMSv1", status="live"):
    return main_screen(assay, status)


@home_bp.route("/rna/<string:assay>/<string:status>", methods=["GET", "POST"])
@home_bp.route("/rna/<string:assay>", methods=["GET", "POST"])
@login_required
def rna_screen(assay="fusion", status="live"):
    return main_screen(assay, status)


@home_bp.route("/tumwgs/<string:assay>/<string:status>", methods=["GET", "POST"])
@home_bp.route("/tumwgs/<string:assay>", methods=["GET", "POST"])
@login_required
def tumwgs_screen(assay="tumwgs-solid", status="live"):
    return main_screen(assay, status)


@home_bp.route("/<string:assay>", methods=["GET", "POST"])
@home_bp.route("/<string:assay>/<string:status>", methods=["GET", "POST"])
@login_required
def main_screen(assay=None, status="live"):
    if not assay:
        return redirect(url_for("home_bp.home_screen"))

    form = SampleSearchForm()
    search_str = ""
    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    user_groups = current_user.get_groups()
    if assay:
        if assay in user_groups:
            user_groups = [assay]
        else:
            user_groups = []

    limit_done_samples = 50
    if request.args.get("all") == "1":
        limit_done_samples = None

    if status == "done":
        live_samples = []
        done_samples = store.sample_handler.get_samples(
            user_groups=user_groups, search_str=search_str, report=True, limit=limit_done_samples
        )
    elif status == "live":
        live_samples = store.sample_handler.get_samples(
            user_groups=user_groups, search_str=search_str, report=False
        )
        done_samples = []
    else:
        return redirect(url_for("home_bp.panels_screen", assay=assay, status="live"))

    # Add date for latest report to done_samples
    for samp in done_samples:
        if "reports" in samp and "time_created" in samp["reports"][-1]:
            samp["last_report_time_created"] = samp["reports"][-1]["time_created"]
        else:
            samp["last_report_time_created"] = 0
        samp["num_samples"] = store.sample_handler.get_num_samples(str(samp["_id"]))

    for samp in live_samples:
        samp["num_samples"] = store.sample_handler.get_num_samples(str(samp["_id"]))

    return render_template(
        "main_screen.html",
        live_samples=live_samples,
        done_samples=done_samples,
        form=form,
        assay=assay,
        status=status,
    )


@home_bp.route("/errors/")
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


@home_bp.route("/sample/sample_comment/<string:id>", methods=["POST"])
@login_required
def add_sample_comment(id):
    """
    Add Sample comment
    """
    data = request.form.to_dict()
    doc = util.dna.create_comment_doc(data, key="sample_comment")
    store.sample_handler.add_sample_comment(id, doc)
    sample = store.sample_handler.get_sample_with_id(id)
    assay = util.common.get_assay_from_sample(sample)
    sample_type = util.common.get_sample_type(assay)
    if sample_type == "dna":
        return redirect(url_for("dna_bp.list_variants", id=id))
    else:
        return redirect(url_for("rna_bp.list_fusions", id=id))


@app.route("/sample/hide_sample_comment/<string:sample_id>", methods=["POST"])
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


@app.route("/sample/unhide_sample_comment/<string:sample_id>", methods=["POST"])
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
