"""
Top level coyote
"""

from flask import abort
from flask import current_app as app
from flask import (
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
    flash,
)
from flask_login import current_user

# Legacy main-screen:
from flask_login import login_required
from coyote.extensions import store
from coyote.blueprints.home import home_bp
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.extensions import util
from coyote.util.decorators.access import require_sample_group_access
from coyote.services.auth.decorators import require
import os


@home_bp.route("/", methods=["GET", "POST"])
@home_bp.route("/<string:status>", methods=["GET", "POST"])
@login_required
def home_screen(status="live"):

    form = SampleSearchForm()
    search_str = ""
    search_slider_values = {1: "done", 2: "both", 3: "live"}
    search_mode = None

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data
        search_mode = search_slider_values[int(form.search_mode_slider.data)]

    limit_done_samples = 50

    if not search_mode:
        search_mode = status
        show_all = True
    else:
        status = search_mode
        show_all = False

    user_groups = current_user.groups

    if status == "done" or search_mode in ["done", "both"]:
        done_samples = store.sample_handler.get_samples(
            user_groups=user_groups,
            status=status,
            search_str=search_str,
            report=True,
            limit=limit_done_samples,
            use_cache=True,
        )
    elif status == "live":
        time_limit = util.common.get_date_days_ago(days=1000)
        done_samples = store.sample_handler.get_samples(
            user_groups=user_groups,
            status=status,
            search_str=search_str,
            report=True,
            time_limit=time_limit,
            use_cache=True,
        )
    else:
        done_samples = []

    if status == "live" or search_mode in ["live", "both"]:
        live_samples = store.sample_handler.get_samples(
            user_groups=user_groups,
            status=status,
            search_str=search_str,
            report=False,
            use_cache=True,
        )
    else:
        live_samples = []

    # TODO: We need to add sample_num to the sample object when we get the samples to make this even faster
    # Add date for latest report to done_samples
    done_sample_ids = [str(s["_id"]) for s in done_samples]
    done_gt_map = store.variant_handler.get_gt_lengths_by_sample_ids(
        done_sample_ids
    )

    for samp in done_samples:
        # Set last report time
        samp["last_report_time_created"] = (
            samp["reports"][-1]["time_created"]
            if samp.get("reports") and samp["reports"][-1].get("time_created")
            else 0
        )

        # Set number of samples from GT length
        samp["num_samples"] = done_gt_map.get(str(samp["_id"]), 0)

    live_sample_ids = [str(s["_id"]) for s in live_samples]
    gt_lengths_map = store.variant_handler.get_gt_lengths_by_sample_ids(
        live_sample_ids
    )

    # Inject GT length into sample objects
    for samp in live_samples:
        samp["num_samples"] = gt_lengths_map.get(str(samp["_id"]), 0)

    return render_template(
        "main_screen.html",
        live_samples=live_samples,
        done_samples=done_samples,
        form=form,
        assay=None,
        status=status,
        search_mode=search_mode,
        show_all=show_all,
    )


@home_bp.route(
    "/panels/<string:assay>/<string:status>", methods=["GET", "POST"]
)
@home_bp.route("/panels/<string:assay>", methods=["GET", "POST"])
@login_required
def panels_screen(assay="myeloid_GMSv1", status="live"):
    return main_screen(assay, status)


@home_bp.route("/wgs/<string:assay>/<string:status>", methods=["GET", "POST"])
@home_bp.route("/wgs/<string:assay>", methods=["GET", "POST"])
@login_required
def wgs_screen(assay="tumwgs-solid", status="live"):
    return main_screen(assay, status)


@home_bp.route("/rna/<string:assay>/<string:status>", methods=["GET", "POST"])
@home_bp.route("/rna/<string:assay>", methods=["GET", "POST"])
@login_required
def rna_panels_screen(assay="solidRNA_GMSv5", status="live"):
    return main_screen(assay, status)


@home_bp.route("/wts/<string:assay>", methods=["GET", "POST"])
@login_required
def rna_wts_screen(assay="fusion", status="live"):
    return main_screen(assay, status)


@home_bp.route("/<string:assay>", methods=["GET", "POST"])
@home_bp.route("/<string:assay>/<string:status>", methods=["GET", "POST"])
@login_required
def main_screen(assay=None, status="live"):
    if not assay:
        return redirect(url_for("home_bp.home_screen"))

    form = SampleSearchForm()
    search_str = ""
    search_slider_values = {1: "done", 2: "both", 3: "live"}
    search_mode = None

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data
        search_mode = search_slider_values[int(form.search_mode_slider.data)]

    limit_done_samples = 50
    if request.args.get("all") == "1" or search_mode:
        limit_done_samples = None

    if not search_mode:
        search_mode = status
        show_all = True
    else:
        status = search_mode
        show_all = False

    user_groups = current_user.groups

    if assay:
        if assay in user_groups:
            user_groups = [assay]
        else:
            user_groups = []

    if status == "done" or search_mode in ["done", "both"]:
        done_samples = store.sample_handler.get_samples(
            user_groups=user_groups,
            search_str=search_str,
            report=True,
            limit=limit_done_samples,
        )
    elif status == "live":
        time_limit = util.common.get_date_days_ago(days=1000)
        done_samples = store.sample_handler.get_samples(
            user_groups=user_groups,
            search_str=search_str,
            report=True,
            time_limit=time_limit,
        )
    else:
        done_samples = []

    if status == "live" or search_mode in ["live", "both"]:
        live_samples = store.sample_handler.get_samples(
            user_groups=user_groups, search_str=search_str, report=False
        )
    else:
        live_samples = []

    # Add date for latest report to done_samples
    for samp in done_samples:
        if "reports" in samp and "time_created" in samp["reports"][-1]:
            samp["last_report_time_created"] = samp["reports"][-1][
                "time_created"
            ]
        else:
            samp["last_report_time_created"] = 0
        samp["num_samples"] = store.variant_handler.get_num_samples(
            str(samp["_id"])
        )

    for samp in live_samples:
        samp["num_samples"] = store.variant_handler.get_num_samples(
            str(samp["_id"])
        )

    return render_template(
        "main_screen.html",
        live_samples=live_samples,
        done_samples=done_samples,
        form=form,
        assay=assay,
        status=status,
    )


@home_bp.route("/<string:sample_id>/reports/<string:report_id>")
@login_required
@require("view_reports", min_role="admin")
@require_sample_group_access("sample_id")
def view_report(sample_id, report_id):
    """
    View a saved report or serve a file if filepath is provided
    """

    # get the report path from the sample_id and report_id
    report = store.sample_handler.get_report(sample_id, report_id)
    filepath = report.get("filepath", None)
    if filepath:
        # Get directory and filename
        directory, filename = os.path.split(filepath)

        # Check if file exists
        if os.path.exists(filepath):
            return send_from_directory(directory, filename)
        else:
            flash("Requested report file does not exist.", "red")

    return redirect(url_for("dna_bp.home_screen"))
