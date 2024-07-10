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
from coyote.blueprints.main import main_bp
from coyote.blueprints.main.util import SampleSearchForm


@main_bp.route("/", methods=["GET", "POST"])
@main_bp.route("/home", methods=["GET", "POST"])
@main_bp.route("/<string:assay>", methods=["GET", "POST"])
@login_required
def main_screen(assay=None):
    form = SampleSearchForm()
    # Check if a search was performed
    search_str = ""
    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    # if no assay chosen, show all available samples to user
    # else only show samples if the user is part of assay
    user_groups = current_user.get_groups()
    if assay:
        if assay in user_groups:
            user_groups = [assay]
        else:
            user_groups = []

    live_samples_iter = store.sample_handler.get_samples(
        user_groups=user_groups, search_str=search_str
    )
    done_samples_iter = store.sample_handler.get_samples(
        user_groups=user_groups, search_str=search_str, report=True
    )

    limit_done_samples = 50
    if request.args.get("all") == "1":
        limit_done_samples = 0
    done_samples_iter = done_samples_iter.limit(limit_done_samples)

    done_samples = []
    # Add date for latest report
    for samp in done_samples_iter:
        if "reports" in samp and "time_created" in samp["reports"][-1]:
            samp["last_report_time_created"] = samp["reports"][-1]["time_created"]
        else:
            samp["last_report_time_created"] = 0
        if limit_done_samples != 0:
            samp["num_samples"] = store.sample_handler.get_num_samples(str(samp["_id"]))
        done_samples.append(samp)

    live_samples = []
    for samp in live_samples_iter:
        samp["num_samples"] = store.sample_handler.get_num_samples(str(samp["_id"]))
        live_samples.append(samp)

    return render_template(
        "main_screen.html", live_samples=live_samples, done_samples=done_samples, form=form
    )


@main_bp.route("/panels/<string:assay>", methods=["GET", "POST"])
@main_bp.route("/panels/", methods=["GET", "POST"])
@login_required
def panels_screen(assay=None):
    """
    PANEL assay-urls in page header
    """
    if not assay:
        return redirect(url_for("main_bp.panels_screen", assay="myeloid_GMSv1"))

    return main_screen(assay)


@main_bp.route("/rna/<string:assay>", methods=["GET", "POST"])
@main_bp.route("/rna", methods=["GET", "POST"])
@login_required
def rna_screen(assay=None):
    """
    RNA assay-urls in page header
    """
    if not assay:
        return redirect(url_for("main_bp.rna_screen", assay="fusion"))

    return main_screen(assay)


@main_bp.route("/errors/")
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
