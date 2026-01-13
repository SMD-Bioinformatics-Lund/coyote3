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
This module provides a collection of Jinja2 template filters for use in Flask-based
genomic data analysis and reporting applications. The filters support common shared
filters, modifiers to display data in web templates.
"""

from flask import current_app as app
import arrow
from dateutil import tz
from datetime import datetime, tzinfo


STOCKHOLM = tz.gettz("Europe/Stockholm")


@app.template_filter(name="human_date")
def human_date(value: datetime | str) -> str:
    """
    Converts a date or datetime value to a human-readable relative time string
    (e.g., '3 days ago') in Central European Time (CET).

    Args:
        value (datetime | str): The input date or datetime string.

    Returns:
        str: A human-readable relative time string in CET timezone.
    """
    if not value:
        return "N/A"

    try:
        dt = arrow.get(value)

        # If it's naive, assume it is already Stockholm local time
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=STOCKHOLM)

        dt = dt.to(STOCKHOLM)
        now = arrow.now(STOCKHOLM)

        return dt.humanize(now)
    except Exception:
        return "Invalid date"
