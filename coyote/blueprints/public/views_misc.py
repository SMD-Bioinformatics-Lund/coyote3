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
