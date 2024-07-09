from flask_wtf import FlaskForm
from wtforms import StringField, validators
from flask import current_app as app


class SampleSearchForm(FlaskForm):
    """Sample search form"""

    sample_search = StringField("Search sample", validators=[validators.DataRequired()])


class MainUtility:
    """
    Utility class for Main blueprint
    """

    pass
