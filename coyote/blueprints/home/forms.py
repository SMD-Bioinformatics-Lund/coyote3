from flask_wtf import FlaskForm
from wtforms import StringField, validators, IntegerField
from flask import current_app as app


class SampleSearchForm(FlaskForm):
    """Sample search form"""

    sample_search = StringField("Search sample", validators=[validators.DataRequired()])
    search_mode_slider = IntegerField("Search mode", default=3)
