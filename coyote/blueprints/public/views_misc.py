
"""Public blueprint miscellaneous routes."""

from flask import current_app as app
from flask import render_template

from coyote.blueprints.public import public_bp


@public_bp.route("/contact")
def contact() -> str:
    """
    Displays the contact information page.

    Returns:
        str: Rendered HTML page containing contact details.
    """
    contact = app.config.get("CONTACT") or {}
    return render_template("contact.html", contact=contact)
