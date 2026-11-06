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
This module defines form classes for filtering and processing gene fusion events in genomic data analysis.
It provides Flask-WTF forms to customize filtering criteria, including fusion lists, caller tools, read thresholds, and effect types.
"""

from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField
from wtforms.validators import InputRequired, NumberRange, Optional


class FusionFilter(FlaskForm):
    """
    FusionFilter is a Flask-WTF form for filtering gene fusion events in genomic data analysis.

    This form provides boolean and numeric fields to filter fusion events based on:
    - Known fusion lists (e.g., FCknown, Mitelman)
    - Fusion caller tools (Arriba, FusionCatcher, STAR-Fusion)
    - Minimum spanning pairs and reads
    - Fusion effect types (in-frame, out-frame)
    - VEP consequence categories (splicing, stop gained/lost, frameshift, etc.)

    Used in the Coyote3 workflow to allow users to customize fusion event filtering criteria.
    """

    fusionlist_FCknown = BooleanField("FC Known", validators=[Optional()])
    fusionlist_mitelman = BooleanField("Mittleman", validators=[Optional()])

    fusioncaller_arriba = BooleanField("Arriba", validators=[Optional()])
    fusioncaller_fusioncatcher = BooleanField("Fusion Catcher", validators=[Optional()])
    fusioncaller_starfusion = BooleanField("Star Fusion", validators=[Optional()])

    min_spanning_pairs = IntegerField(
        "Min Spanning pairs", validators=[InputRequired(), NumberRange(min=0)]
    )
    min_spanning_reads = IntegerField(
        "Min Spanning reads", validators=[InputRequired(), NumberRange(min=0)]
    )

    fusioneffect_inframe = BooleanField("In-Frame", validators=[Optional()])
    fusioneffect_outframe = BooleanField("Out-of-Frame", validators=[Optional()])

    reset = BooleanField("reset")
