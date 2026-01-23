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
    TieredVariantSearchForm: Form for searching tiered reported variants with a text fields.
"""

from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    validators,
    BooleanField,
    SubmitField,
    SelectField,
    SelectMultipleField,
)
from wtforms.widgets import ListWidget, CheckboxInput


class TieredVariantSearchForm(FlaskForm):
    """
    WTForms form for searching  tiered variants in the Coyote3 application.

    Fields:
        variant_search (StringField): Text input for variant search query. Required.
    """

    variant_search = StringField(
        "Variant search",
        validators=[validators.DataRequired(message="Please enter a search string")],
        id="tiered-variant-search-input",
    )

    search_options = SelectField(
        "Search Options",
        choices=[
            ("variant", "Variant (HGVSc / HGVSp / Genomic)"),
            ("gene", "Gene Symbol"),
            ("transcript", "Transcript ID"),
            ("subpanel", "Sub Panel Name"),
            ("author", "Author"),
        ],
        default="variant",
        id="tiered-variant-search-options",
    )

    assay = SelectMultipleField(
        "Assay",
        choices=[],
        option_widget=CheckboxInput(),
        widget=ListWidget(prefix_label=False),
        id="tiered-variant-assay-select",
    )

    include_annotation_text = BooleanField(
        "Include Annotation Text",
        id="tiered-variant-annotation-text",
        default=False,
    )

    submit = SubmitField("Submit", id="tiered-variant-search-submit")
