from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, IntegerField, FloatField
from wtforms.validators import InputRequired, NumberRange, Optional


class FusionFilterForm(FlaskForm):
    """Filter form"""
    
    reset = BooleanField()
    
    fusionlist_FCknown = BooleanField(validators=[Optional()])
    fusionlist_mitelman = BooleanField(validators=[Optional()])

    fusioncaller_arriba = BooleanField(validators=[Optional()])    
    fusioncaller_fusioncatcher = BooleanField(validators=[Optional()])
    fusioncaller_starfusion = BooleanField(validators=[Optional()])

    min_spanpairs = IntegerField('Spanning pairs', validators=[Optional()])
    min_spanreads = IntegerField('Spanning reads', validators=[Optional()])

    fusioneffect_inframe = BooleanField( validators=[Optional()])
    fusioneffect_outframe = BooleanField( validators=[Optional()])




