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
This module defines WTForms forms for the Coyote3 Flask application.

Classes:
    SampleSearchForm: Form for searching samples with a text field and search mode slider.
"""

from flask_wtf import FlaskForm
from wtforms import StringField, validators, IntegerField


class SampleSearchForm(FlaskForm):
    """
    WTForms form for searching samples in the Coyote3 application.

    Fields:
        sample_search (StringField): Text input for sample search query. Required.
        search_mode_slider (IntegerField): Slider to select search mode. Default is 3.
    """

    sample_search = StringField(
        "Search sample", validators=[validators.DataRequired()]
    )
    search_mode_slider = IntegerField("Search mode", default=3)
