"""
Top level coyote
"""

from flask import abort
from flask import current_app as app
from flask import redirect, render_template, request, url_for

# Legacy main-screen:
from flask_login import login_required
from markdown import markdown
from coyote.extensions import store
from coyote.blueprints.main import main_bp


# TODO: Move this to config:
# Use this dict to enable 'restored' views for main assays:


# 1. INDEX AND RUN DETAILS:
@main_bp.route("/", methods=["GET"])
@login_required
def main_screen():
    hits = store.get_samples()
    #hits = list("hej")
    return render_template("main_screen.html", hits=hits)


