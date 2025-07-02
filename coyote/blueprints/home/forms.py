from flask import current_app as app
from flask_wtf import FlaskForm
from wtforms import IntegerField, StringField, validators


class SampleSearchForm(FlaskForm):
    """Sample search form"""

    sample_search = StringField(
        "Search sample", validators=[validators.DataRequired()]
    )
    search_mode_slider = IntegerField("Search mode", default=3)
