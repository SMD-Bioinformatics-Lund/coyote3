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

from flask_wtf import FlaskForm
from wtforms import StringField, validators, IntegerField
from flask import current_app as app


class SampleSearchForm(FlaskForm):
    """Sample search form"""

    sample_search = StringField(
        "Search sample", validators=[validators.DataRequired()]
    )
    search_mode_slider = IntegerField("Search mode", default=3)
