from flask import abort, redirect, request, url_for
from flask_login import login_required
from flask import current_app as app
from coyote.blueprints.common import common_bp
from coyote.extensions import store, util
from flask import render_template
from flask_login import current_user
import traceback


@common_bp.route("/errors/")
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


@common_bp.route("/sample/sample_comment/<string:id>", methods=["POST"])
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
        return redirect(url_for("fusions_bp.list_fusions", id=id))
