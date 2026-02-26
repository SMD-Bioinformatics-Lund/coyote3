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
Custom Jinja2 template filters for Flask apps in the Coyote3 framework.

These filters help format, annotate, and transform genomic variant and clinical data
for display in web-based reports.
"""

from flask import current_app as app
from coyote.filters.shared import (
    format_fusion_desc_badges as shared_format_fusion_desc_badges,
    uniq_callers as shared_uniq_callers,
)


@app.template_filter()
def format_fusion_desc_few(st, preview_count=None):
    """
    Jinja2 filter to format a comma-separated string of fusion description terms
    into styled HTML spans for display in reports.

    Args:
        st (str): Comma-separated string of fusion description terms.
        preview_count (int, optional): If provided, limits the number of terms displayed.

    Returns:
        Markup: HTML markup with each term styled according to its category.
    """
    return shared_format_fusion_desc_badges(st, preview_count=preview_count)


@app.template_filter()
def format_fusion_desc(st: str) -> str:
    """
    Jinja2 filter to format a comma-separated string of fusion description terms
    into styled HTML spans for display in reports.

    Args:
        st (str): Comma-separated string of fusion description terms.

    Returns:
        str: HTML markup with each term styled according to its category.
    """
    return shared_format_fusion_desc_badges(st)


@app.template_filter()
def uniq_callers(calls: list) -> set:
    """
    Jinja2 filter to extract unique caller names from a list of call dictionaries.

    Args:
        calls (list): List of dictionaries, each containing a 'caller' key.

    Returns:
        set: Set of unique caller names.
    """
    return shared_uniq_callers(calls)
