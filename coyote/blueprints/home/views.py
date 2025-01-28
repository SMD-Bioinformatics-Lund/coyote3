"""
Top level coyote
"""

from flask import abort
from flask import current_app as app
from flask import redirect, render_template, request, url_for
from flask_login import current_user

# Legacy main-screen:
from flask_login import login_required
from coyote.extensions import store
from coyote.blueprints.home import home_bp
from coyote.blueprints.home.util import SampleSearchForm
from coyote.extensions import util


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
    if request.args.get("all") == "1" or search_mode:
        limit_done_samples = None

    if not search_mode:
        search_mode = status
        show_all = True
    else:
        status = search_mode
        show_all = False

    user_groups = current_user.get_groups()

    if status == "done" or search_mode in ["done", "both"]:
        done_samples = store.sample_handler.get_samples(
            user_groups=user_groups, search_str=search_str, report=True, limit=limit_done_samples
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
            samp["last_report_time_created"] = samp["reports"][-1]["time_created"]
        else:
            samp["last_report_time_created"] = 0
        samp["num_samples"] = store.variant_handler.get_num_samples(str(samp["_id"]))

    for samp in live_samples:
        samp["num_samples"] = store.variant_handler.get_num_samples(str(samp["_id"]))

    print("search_mode", search_mode)
    print("search_str", search_str)
    print("status", status)
    print("live_samples", len(live_samples))
    print("done_samples", len(done_samples))
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

    user_groups = current_user.get_groups()

    if assay:
        if assay in user_groups:
            user_groups = [assay]
        else:
            user_groups = []

    if status == "done" or search_mode in ["done", "both"]:
        done_samples = store.sample_handler.get_samples(
            user_groups=user_groups, search_str=search_str, report=True, limit=limit_done_samples
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
            samp["last_report_time_created"] = samp["reports"][-1]["time_created"]
        else:
            samp["last_report_time_created"] = 0
        samp["num_samples"] = store.variant_handler.get_num_samples(str(samp["_id"]))

    for samp in live_samples:
        samp["num_samples"] = store.variant_handler.get_num_samples(str(samp["_id"]))

    return render_template(
        "main_screen.html",
        live_samples=live_samples,
        done_samples=done_samples,
        form=form,
        assay=assay,
        status=status,
    )
