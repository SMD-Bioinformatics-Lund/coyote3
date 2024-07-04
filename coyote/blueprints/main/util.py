from flask_wtf import FlaskForm
from wtforms import StringField, validators


class SampleSearchForm(FlaskForm):
    """Sample search form"""

    sample_search = StringField("Search sample", validators=[validators.DataRequired()])


class BaseUtilityFunctions:
    pass
