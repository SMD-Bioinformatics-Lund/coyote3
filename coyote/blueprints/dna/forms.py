from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, IntegerField, FloatField
from wtforms.validators import InputRequired, NumberRange, Optional


class FilterForm(FlaskForm):
    """Filter form"""

    min_reads = IntegerField("minreads", validators=[InputRequired(), NumberRange(min=0)])
    min_depth = IntegerField("mindepth", validators=[InputRequired(), NumberRange(min=0)])
    min_freq = FloatField("Min freq", validators=[InputRequired(), NumberRange(min=0, max=1)])
    max_freq = FloatField("Max freq", validators=[InputRequired(), NumberRange(min=0, max=1)])
    max_popfreq = FloatField(
        "Population freq", validators=[InputRequired(), NumberRange(min=0, max=1)]
    )
    min_cnv_size = IntegerField("Min CNV size", validators=[InputRequired(), NumberRange(min=1)])
    max_cnv_size = IntegerField("Max CNV size", validators=[InputRequired(), NumberRange(min=2)])

    # SNVs
    splicing = BooleanField()
    stop_gained = BooleanField()
    stop_lost = BooleanField()
    start_lost = BooleanField()
    frameshift = BooleanField()
    inframe_indel = BooleanField()
    missense = BooleanField()
    other_coding = BooleanField()
    synonymous = BooleanField()
    UTR = BooleanField()
    non_coding = BooleanField()
    intronic = BooleanField()
    intergenic = BooleanField()
    regulatory = BooleanField()
    feature_elon_trunc = BooleanField()

    # CNVs
    cnveffect_loss = BooleanField(validators=[Optional()])
    cnveffect_gain = BooleanField(validators=[Optional()])

    # Fusion
    min_spanpairs = IntegerField("Spanning pairs", validators=[Optional()])
    min_spanreads = IntegerField("Spanning reads", validators=[Optional()])

    ### assays filters
    solid = BooleanField()
    myeloid = BooleanField()
    tumwgs = BooleanField()
    lymphoid = BooleanField()
    parp = BooleanField()
    historic = BooleanField()

    # reset button
    reset = BooleanField()


class GeneForm(FilterForm):
    pass


class FusionFilter(FlaskForm):

    min_reads = IntegerField("minreads", validators=[Optional()])
    min_depth = IntegerField("mindepth", validators=[Optional()])
    min_freq = FloatField("Min freq", validators=[Optional()])
    max_freq = FloatField("Max freq", validators=[Optional()])
    max_popfreq = FloatField("Population freq", validators=[Optional()])
    min_cnv_size = IntegerField("Min CNV size", validators=[Optional()])
    max_cnv_size = IntegerField("Max CNV size", validators=[Optional()])

    splicing = BooleanField()
    stop_gained = BooleanField()
    frameshift = BooleanField()
    stop_lost = BooleanField()
    start_lost = BooleanField()
    inframe_indel = BooleanField()
    missense = BooleanField()
    other_coding = BooleanField()
    synonymous = BooleanField()
    UTR = BooleanField()
    non_coding = BooleanField()
    intronic = BooleanField()
    intergenic = BooleanField()
    regulatory = BooleanField()
    feature_elon_trunc = BooleanField()

    cnveffect_loss = BooleanField(validators=[Optional()])
    cnveffect_gain = BooleanField(validators=[Optional()])

    fusionlist_FCknown = BooleanField(validators=[Optional()])
    fusionlist_mitelman = BooleanField(validators=[Optional()])

    fusioncaller_arriba = BooleanField(validators=[Optional()])
    fusioncaller_fusioncatcher = BooleanField(validators=[Optional()])
    fusioncaller_starfusion = BooleanField(validators=[Optional()])

    min_spanpairs = IntegerField("Spanning pairs", validators=[InputRequired(), NumberRange(min=0)])
    min_spanreads = IntegerField("Spanning reads", validators=[InputRequired(), NumberRange(min=0)])

    fusioneffect_inframe = BooleanField(validators=[Optional()])
    fusioneffect_outframe = BooleanField(validators=[Optional()])

    reset = BooleanField()
